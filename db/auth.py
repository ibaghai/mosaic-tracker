"""User-account + session helpers.

Stdlib-only password hashing (PBKDF2-HMAC-SHA256, 200k iterations) and
opaque random session tokens stored hashed. No third-party dep.

Public surface used by api/app.py:

    create_user(email, password) -> dict
    verify_login(email, password) -> dict | None
    create_session(user_id, days=30) -> token (raw, returned ONCE; only the
        hash is persisted)
    get_user_for_token(token) -> dict | None
    delete_session(token) -> None
    list_users() -> list[dict]                # admin/debug
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
from datetime import datetime, timedelta
from typing import Optional

from db.models import get_connection


# ── Password hashing ─────────────────────────────────────────────────────────

_PBKDF2_ITERATIONS = 200_000
_SALT_BYTES = 16


def _hash_password(password: str, *, salt: Optional[bytes] = None) -> str:
    """Return `pbkdf2$<iter>$<salt_hex>$<hash_hex>` for storage."""
    if salt is None:
        salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS
    )
    return f"pbkdf2${_PBKDF2_ITERATIONS}${salt.hex()}${derived.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        scheme, iter_str, salt_hex, hash_hex = stored.split("$", 3)
    except ValueError:
        return False
    if scheme != "pbkdf2":
        return False
    try:
        iters = int(iter_str)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(hash_hex)
    except (ValueError, TypeError):
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, iters
    )
    return hmac.compare_digest(derived, expected)


# ── User CRUD ────────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def _validate_password(password: str) -> Optional[str]:
    """Return an error message if invalid, else None."""
    if not password or len(password) < 8:
        return "Password must be at least 8 characters."
    if len(password) > 200:
        return "Password is too long (max 200 chars)."
    return None


def create_user(email: str, password: str) -> dict:
    """Create a user. Raises ValueError on bad input or duplicate email."""
    email_n = _normalize_email(email)
    if not _EMAIL_RE.match(email_n):
        raise ValueError("Enter a valid email address.")
    err = _validate_password(password)
    if err:
        raise ValueError(err)
    pw_hash = _hash_password(password)
    conn = get_connection()
    try:
        with conn:
            cursor = conn.execute(
                "INSERT INTO users (email, password_hash) VALUES (?, ?)",
                (email_n, pw_hash),
            )
            user_id = cursor.lastrowid
        return {"id": user_id, "email": email_n}
    except Exception as exc:
        # SQLite raises IntegrityError on UNIQUE conflict.
        if "UNIQUE" in str(exc).upper():
            raise ValueError("An account with that email already exists.") from exc
        raise
    finally:
        conn.close()


def verify_login(email: str, password: str) -> Optional[dict]:
    """Return the user dict on a valid email+password combo, else None.

    Always runs the PBKDF2 hash even when the email is unknown, to avoid
    leaking which emails exist via timing.
    """
    email_n = _normalize_email(email)
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ?",
            (email_n,),
        ).fetchone()
        if row is None:
            # Burn time so timing matches the success path.
            _verify_password(password, _hash_password("dummy-for-timing"))
            return None
        if not _verify_password(password, row["password_hash"]):
            return None
        with conn:
            conn.execute(
                "UPDATE users SET last_login_at = datetime('now') WHERE id = ?",
                (row["id"],),
            )
        return {"id": row["id"], "email": row["email"]}
    finally:
        conn.close()


def get_user_by_id(user_id: int) -> Optional[dict]:
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT id, email, created_at, last_login_at FROM users WHERE id = ?",
            (user_id,),
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


# ── Sessions ─────────────────────────────────────────────────────────────────

SESSION_DEFAULT_DAYS = 30
SESSION_COOKIE_NAME = "mosaic_session"


def _hash_token(token: str) -> str:
    """SHA-256 the token before storing — DB compromise won't leak active sessions."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(user_id: int, *, days: int = SESSION_DEFAULT_DAYS) -> str:
    """Create a session, return the raw token (caller sets in cookie)."""
    token = secrets.token_urlsafe(32)
    expires_at = (datetime.utcnow() + timedelta(days=days)).isoformat()
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (_hash_token(token), user_id, expires_at),
            )
        return token
    finally:
        conn.close()


def get_user_for_token(token: Optional[str]) -> Optional[dict]:
    """Resolve a session token → user dict. Refreshes last_used_at on hit.
    Returns None if the token is missing, unknown, or expired.
    """
    if not token:
        return None
    th = _hash_token(token)
    conn = get_connection()
    try:
        row = conn.execute(
            """
            SELECT s.id AS session_id, s.expires_at, u.id, u.email
            FROM sessions s
            JOIN users u ON u.id = s.user_id
            WHERE s.token_hash = ?
            """,
            (th,),
        ).fetchone()
        if row is None:
            return None
        # Cheap expiry check (string compare on ISO timestamps works lexically).
        if row["expires_at"] < datetime.utcnow().isoformat():
            with conn:
                conn.execute("DELETE FROM sessions WHERE id = ?", (row["session_id"],))
            return None
        with conn:
            conn.execute(
                "UPDATE sessions SET last_used_at = datetime('now') WHERE id = ?",
                (row["session_id"],),
            )
        return {"id": row["id"], "email": row["email"]}
    finally:
        conn.close()


def delete_session(token: Optional[str]) -> None:
    if not token:
        return
    th = _hash_token(token)
    conn = get_connection()
    try:
        with conn:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (th,))
    finally:
        conn.close()


def purge_expired_sessions() -> int:
    """Sweep expired sessions. Called opportunistically on startup."""
    conn = get_connection()
    try:
        with conn:
            cur = conn.execute(
                "DELETE FROM sessions WHERE expires_at < datetime('now')"
            )
            return cur.rowcount or 0
    finally:
        conn.close()


# ── Signup gate ──────────────────────────────────────────────────────────────

def signups_allowed() -> bool:
    """Env-flagged gate. Default True in dev so you can create your account;
    flip to false in prod once your accounts exist.
    """
    val = (os.getenv("SIGNUPS_ALLOWED") or "true").strip().lower()
    return val in {"1", "true", "yes", "on"}
