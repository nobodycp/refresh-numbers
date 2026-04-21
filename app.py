import json
import os
import time

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, render_template, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.middleware.proxy_fix import ProxyFix

from rn import aloha, areen, layan, sky
from security import (
    HONEYPOT_FIELD_NAME,
    MAX_BODY_BYTES,
    PHONE_COOLDOWN_SECONDS,
    cleanup_nonces,
    consume_nonce,
    init_db,
    issue_token,
    mask_phone,
    origin_allowed,
    phone_cooldown_remaining,
    record_phone_refresh,
    setup_logger,
    verify_token,
)

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("PG_HOST", "127.0.0.1"),
    "port": int(os.environ.get("PG_PORT", "5432")),
    "dbname": os.environ.get("PG_DB", "recharge_desk"),
    "user": os.environ.get("PG_USER", "recharge_readonly"),
    "password": os.environ.get("PG_PASSWORD", ""),
}

app = Flask(__name__)
app.url_map.strict_slashes = False

# Behind Caddy reverse proxy: trust one hop of X-Forwarded-*
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

# Cap incoming bodies hard at the WSGI layer too
app.config["MAX_CONTENT_LENGTH"] = MAX_BODY_BYTES

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["600 per hour"],
    strategy="fixed-window",
    headers_enabled=False,
)

sec_log = setup_logger()
init_db()


# ------------------------------------------------------------------ helpers

def get_db():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.set_session(readonly=True, autocommit=True)
    return conn


def is_valid_number(number: str) -> bool:
    return (
        isinstance(number, str)
        and len(number) == 10
        and number.startswith("05")
        and number.isdigit()
    )


COMPANY_HANDLERS = {
    "layan": layan,
    "aloha": aloha,
    "areen": areen,
    "sky": sky,
}


def lookup_company(number: str):
    conn = get_db()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """
                SELECT c.name AS company
                FROM sales_sale s
                JOIN companies_company c ON c.id = s.company_id
                WHERE s.reference_number = %s
                ORDER BY s.created_at DESC
                LIMIT 1
                """,
                (number,),
            )
            row = cur.fetchone()
    finally:
        conn.close()
    return row["company"] if row else None


def log_event(kind: str, **fields) -> None:
    payload = {"kind": kind, **fields}
    sec_log.info(json.dumps(payload, ensure_ascii=False))


def ip_of(req) -> str:
    return req.remote_addr or "0.0.0.0"


# ------------------------------------------------------------------ headers

@app.after_request
def set_security_headers(resp):
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    resp.headers.setdefault("Referrer-Policy", "same-origin")
    resp.headers.setdefault(
        "Permissions-Policy",
        "geolocation=(), camera=(), microphone=(), payment=()",
    )
    resp.headers.setdefault(
        "Strict-Transport-Security",
        "max-age=31536000; includeSubDomains",
    )
    resp.headers.setdefault(
        "Content-Security-Policy",
        (
            "default-src 'self'; "
            "img-src 'self' data:; "
            "style-src 'self' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "object-src 'none'"
        ),
    )
    if request.path == "/":
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ------------------------------------------------------------------ routes

@app.route("/")
@limiter.limit("60 per minute")
def index():
    ua = request.headers.get("User-Agent", "")
    token = issue_token(ua)
    return render_template(
        "index.html",
        csrf_token=token,
        honeypot_field=HONEYPOT_FIELD_NAME,
    )


@app.route("/healthz")
@limiter.exempt
def healthz():
    return "ok", 200


@app.route("/refresh", methods=["POST"])
@limiter.limit("5 per minute; 30 per hour; 120 per day")
def refresh():
    ip = ip_of(request)
    ua = request.headers.get("User-Agent", "")

    if not request.is_json:
        log_event("rejected", ip=ip, reason="not_json")
        return jsonify({"code": 4, "message": "Invalid request"}), 400

    if not origin_allowed(
        request.headers.get("Origin", ""),
        request.headers.get("Referer", ""),
    ):
        log_event(
            "rejected",
            ip=ip,
            reason="bad_origin",
            origin=request.headers.get("Origin", ""),
            referer=request.headers.get("Referer", ""),
        )
        return jsonify({"code": 4, "message": "Forbidden"}), 403

    data = request.get_json(silent=True) or {}
    if not isinstance(data, dict):
        log_event("rejected", ip=ip, reason="bad_payload_type")
        return jsonify({"code": 4, "message": "Invalid request"}), 400

    # Honeypot — silently return notfound so bots can't tell
    if (data.get(HONEYPOT_FIELD_NAME) or "").strip():
        log_event("rejected", ip=ip, reason="honeypot_tripped", ua=ua[:120])
        return jsonify({"code": 0, "message": "Number not found in the system"}), 200

    # Token
    token = request.headers.get("X-CSRF-Token") or data.get("token", "")
    ok, nonce_or_reason = verify_token(token, ua)
    if not ok:
        log_event("rejected", ip=ip, reason=nonce_or_reason)
        return (
            jsonify({"code": 4, "message": "Session expired, refresh the page", "reload": True}),
            403,
        )

    if not consume_nonce(nonce_or_reason):
        log_event("rejected", ip=ip, reason="token_replay")
        return (
            jsonify({"code": 4, "message": "Session expired, refresh the page", "reload": True}),
            403,
        )

    # Best-effort cleanup of expired nonces (~ every ~30 calls is enough).
    if int(time.time()) % 30 == 0:
        cleanup_nonces()

    number = (data.get("phone_number") or "").strip()
    if not is_valid_number(number):
        log_event("rejected", ip=ip, reason="bad_number")
        return jsonify({"code": 4, "message": "Invalid phone number"}), 400

    # Per-number cooldown (before hitting any upstream)
    remaining = phone_cooldown_remaining(number)
    if remaining > 0:
        elapsed_since_last = PHONE_COOLDOWN_SECONDS - remaining
        log_event("cooldown", ip=ip, phone=mask_phone(number), remaining=remaining)
        return (
            jsonify({
                "code": 2,
                "message": "Please wait before refreshing this number again",
                "elapsed_seconds": elapsed_since_last,
                "remaining_seconds": remaining,
            }),
            200,
        )

    try:
        company_name = lookup_company(number)
    except Exception:
        app.logger.exception("DB lookup failed")
        log_event("error", ip=ip, reason="db_lookup")
        return jsonify({"code": 4, "message": "Database error"}), 500

    if company_name is None:
        log_event("notfound", ip=ip, phone=mask_phone(number))
        return jsonify({"code": 0, "message": "Number not found in the system"}), 200

    handler = COMPANY_HANDLERS.get(company_name.strip().lower())
    if handler is None:
        log_event(
            "unsupported_company",
            ip=ip,
            phone=mask_phone(number),
            company=company_name,
        )
        return (
            jsonify({"code": 4, "message": f"Unsupported company: {company_name}"}),
            200,
        )

    t0 = time.time()
    try:
        result = handler(number)
    except Exception:
        app.logger.exception("Handler failed")
        log_event(
            "error",
            ip=ip,
            reason="handler_exception",
            phone=mask_phone(number),
            company=company_name,
        )
        return jsonify({"code": 4, "message": "Error while processing the request"}), 200
    dur_ms = int((time.time() - t0) * 1000)

    if result == 3:
        result = 1
    if result not in (0, 1, 2, 4):
        result = 4

    if result == 1:
        record_phone_refresh(number)

    log_event(
        "refresh",
        ip=ip,
        phone=mask_phone(number),
        company=company_name,
        code=result,
        upstream_ms=dur_ms,
    )

    messages = {
        0: "Number not found in the system",
        1: "Number refreshed successfully",
        2: "Please wait before refreshing this number again",
        4: "An unexpected error occurred",
    }

    return jsonify({"code": result, "message": messages[result]}), 200


# ------------------------------------------------------------------ errors

@app.errorhandler(429)
def too_many(e):
    log_event(
        "rate_limited",
        ip=ip_of(request),
        path=request.path,
        limit=str(getattr(e, "description", "")),
    )
    return jsonify({"code": 4, "message": "Too many requests. Slow down."}), 429


@app.errorhandler(413)
def too_large(e):
    log_event("rejected", ip=ip_of(request), reason="body_too_large")
    return jsonify({"code": 4, "message": "Payload too large"}), 413


@app.errorhandler(404)
def not_found(e):
    return jsonify({"code": 4, "message": "Not found"}), 404


@app.errorhandler(405)
def bad_method(e):
    return jsonify({"code": 4, "message": "Method not allowed"}), 405


if __name__ == "__main__":
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.jinja_env.auto_reload = True
    app.run(host="0.0.0.0", port=5050, debug=False)
