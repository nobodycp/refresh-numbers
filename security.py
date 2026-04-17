"""
Security helpers for refresh-numbers.

Provides:
  - HMAC-signed single-use session tokens (issue + verify + consume)
  - Per-number cooldown store
  - Structured request logger (rotating file)
  - Origin / Referer validation
  - Honeypot field name
  - Real-IP extraction helper

State that must be shared across gunicorn workers lives in a local
SQLite file (security.sqlite3) with WAL mode enabled. The HMAC secret
lives in $SECRET_KEY, or is auto-generated into .secret_key on first run
so workers share it and it survives restarts.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
from logging.handlers import RotatingFileHandler
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent
SECURITY_DB = APP_DIR / "security.sqlite3"
SECRET_FILE = APP_DIR / ".secret_key"
LOG_DIR = APP_DIR / "logs"
LOG_FILE = LOG_DIR / "refresh.log"

TOKEN_TTL_SECONDS = 300
MIN_SUBMIT_DELAY_SECONDS = 1
PHONE_COOLDOWN_SECONDS = 6 * 60 * 60
MAX_BODY_BYTES = 2048

HONEYPOT_FIELD_NAME = "website"

ALLOWED_ORIGINS = {
    "https://rn.prosim.ps",
    "http://rn.prosim.ps",
    "http://127.0.0.1:5050",
    "http://localhost:5050",
    "http://127.0.0.1:5000",
    "http://localhost:5000",
    "http://127.0.0.1:8000",
    "http://localhost:8000",
}

_db_lock = threading.Lock()


def _load_secret_key() -> str:
    env_val = os.environ.get("SECRET_KEY", "").strip()
    if env_val:
        return env_val
    if SECRET_FILE.exists():
        val = SECRET_FILE.read_text().strip()
        if val:
            return val
    new_key = secrets.token_hex(32)
    SECRET_FILE.write_text(new_key)
    try:
        os.chmod(SECRET_FILE, 0o600)
    except OSError:
        pass
    return new_key


SECRET_KEY = _load_secret_key().encode()


# ---------------------------------------------------------------- sqlite

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(SECURITY_DB), timeout=10, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db() -> None:
    with _db_lock, _db() as c:
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS used_nonces (
                nonce        TEXT PRIMARY KEY,
                consumed_at  INTEGER NOT NULL
            )
            """
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_nonces_ts ON used_nonces(consumed_at)"
        )
        c.execute(
            """
            CREATE TABLE IF NOT EXISTS phone_cooldown (
                phone            TEXT PRIMARY KEY,
                last_refresh_at  INTEGER NOT NULL
            )
            """
        )


# ---------------------------------------------------------------- logger

def setup_logger(name: str = "refresh") -> logging.Logger:
    LOG_DIR.mkdir(exist_ok=True)
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        str(LOG_FILE), maxBytes=2_000_000, backupCount=5, encoding="utf-8"
    )
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(handler)
    logger.propagate = False
    return logger


# ---------------------------------------------------------------- token

def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _sign(payload: bytes) -> str:
    mac = hmac.new(SECRET_KEY, payload, hashlib.sha256).digest()
    return _b64url(mac)


def _ua_fingerprint(ua: str) -> str:
    return hashlib.sha256((ua or "").encode()).hexdigest()[:16]


def issue_token(ua: str) -> str:
    """Return a signed token tied to UA + time, with a fresh nonce."""
    payload = {
        "n": secrets.token_urlsafe(16),
        "t": int(time.time()),
        "u": _ua_fingerprint(ua),
    }
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    return _b64url(body) + "." + _sign(body)


def verify_token(token: str, ua: str) -> tuple[bool, str]:
    """
    Validate signature, expiry, UA, and human-minimum delay.
    Does NOT consume the nonce.
    Returns (True, nonce) on success; (False, reason_code) on failure.
    """
    if not token or "." not in token:
        return False, "token_missing"

    body_b64, sig = token.split(".", 1)
    try:
        body = _b64url_decode(body_b64)
    except Exception:
        return False, "token_malformed"

    if not hmac.compare_digest(_sign(body), sig):
        return False, "token_signature"

    try:
        payload = json.loads(body)
    except Exception:
        return False, "token_payload"

    now = int(time.time())
    issued_at = int(payload.get("t", 0))
    age = now - issued_at

    if age < 0:
        return False, "token_future"
    if age > TOKEN_TTL_SECONDS:
        return False, "token_expired"
    if age < MIN_SUBMIT_DELAY_SECONDS:
        return False, "token_too_fast"
    if payload.get("u") != _ua_fingerprint(ua):
        return False, "token_ua_mismatch"

    nonce = payload.get("n")
    if not isinstance(nonce, str) or not nonce:
        return False, "token_nonce_missing"

    return True, nonce


def consume_nonce(nonce: str) -> bool:
    """Atomically mark nonce as used. Returns True on first use, False on replay."""
    now = int(time.time())
    try:
        with _db_lock, _db() as c:
            c.execute(
                "INSERT INTO used_nonces(nonce, consumed_at) VALUES(?, ?)",
                (nonce, now),
            )
        return True
    except sqlite3.IntegrityError:
        return False


def cleanup_nonces() -> None:
    """Best-effort purge of expired nonce rows."""
    cutoff = int(time.time()) - TOKEN_TTL_SECONDS - 120
    try:
        with _db_lock, _db() as c:
            c.execute("DELETE FROM used_nonces WHERE consumed_at < ?", (cutoff,))
    except Exception:
        pass


# ---------------------------------------------------------------- cooldown

def phone_cooldown_remaining(phone: str) -> int:
    """Seconds remaining; 0 if allowed now."""
    with _db_lock, _db() as c:
        row = c.execute(
            "SELECT last_refresh_at FROM phone_cooldown WHERE phone=?", (phone,)
        ).fetchone()
    if not row:
        return 0
    elapsed = int(time.time()) - int(row[0])
    return max(0, PHONE_COOLDOWN_SECONDS - elapsed)


def record_phone_refresh(phone: str) -> None:
    now = int(time.time())
    with _db_lock, _db() as c:
        c.execute(
            """
            INSERT INTO phone_cooldown(phone, last_refresh_at) VALUES(?, ?)
            ON CONFLICT(phone) DO UPDATE SET last_refresh_at=excluded.last_refresh_at
            """,
            (phone, now),
        )


# ---------------------------------------------------------------- origin

def origin_allowed(origin: str, referer: str) -> bool:
    if origin:
        return origin in ALLOWED_ORIGINS
    if referer:
        for allowed in ALLOWED_ORIGINS:
            if referer == allowed or referer.startswith(allowed + "/"):
                return True
    return False


# ---------------------------------------------------------------- misc

def mask_phone(p: str) -> str:
    if not p or len(p) < 7:
        return "***"
    return p[:3] + "****" + p[-2:]
