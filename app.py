import os

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

from rn import aloha, areen, layan

load_dotenv()

DB_CONFIG = {
    "host": os.environ.get("PG_HOST", "127.0.0.1"),
    "port": int(os.environ.get("PG_PORT", "5432")),
    "dbname": os.environ.get("PG_DB", "recharge_desk"),
    "user": os.environ.get("PG_USER", "recharge_readonly"),
    "password": os.environ.get("PG_PASSWORD", ""),
}

app = Flask(__name__)


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
}


def lookup_company(number: str):
    """Find which company a phone number belongs to (latest sale wins)."""
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


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/refresh", methods=["POST"])
def refresh():
    data = request.get_json(silent=True) or {}
    number = (data.get("phone_number") or "").strip()

    if not is_valid_number(number):
        return jsonify({"code": 4, "message": "Invalid phone number"}), 400

    try:
        company_name = lookup_company(number)
    except Exception:
        app.logger.exception("DB lookup failed")
        return jsonify({"code": 4, "message": "Database error"}), 500

    if company_name is None:
        return jsonify({"code": 0, "message": "Number not found in the system"}), 200

    handler = COMPANY_HANDLERS.get(company_name.strip().lower())

    if handler is None:
        return (
            jsonify({"code": 4, "message": f"Unsupported company: {company_name}"}),
            200,
        )

    try:
        result = handler(number)
    except Exception:
        app.logger.exception("Handler failed")
        return jsonify({"code": 4, "message": "Error while processing the request"}), 200

    if result == 3:
        result = 1
    if result not in (0, 1, 2, 4):
        result = 4

    messages = {
        0: "Number not found in the system",
        1: "Number refreshed successfully",
        2: "Please wait before refreshing this number again",
        4: "An unexpected error occurred",
    }

    return jsonify({"code": result, "message": messages[result]}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
