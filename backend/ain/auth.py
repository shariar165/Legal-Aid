"""Accounts, sessions and job ownership.

Every analysis belongs to exactly one principal:
- a guest: one device, no signup, created on the first analysis and purged after 7 days;
- an account: email + password (argon2id). Signing up or logging in from a guest session
  moves the guest's analyses into the account.

Sessions are opaque random tokens in an HttpOnly cookie. Only their SHA-256 is stored, so a
copy of the database cannot be replayed as a login. A job that is not the caller's answers
404, exactly like a job that does not exist, so job ids cannot be probed.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import sqlite3
import threading
import time
import uuid
from collections import defaultdict, deque
from contextlib import contextmanager
from dataclasses import dataclass
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException, Request, Response
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

from ain import config

COOKIE = "ain_session"
ACCOUNT_TTL = 30 * 86400  # sliding: renewed once less than half is left
GUEST_TTL = 7 * 86400  # fixed: the guest and its analyses are purged after this
PASSWORD_MIN, PASSWORD_MAX = 10, 128
JOB_ID = re.compile(r"^[0-9a-f]{12}$")
EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]+\.[^@\s]+$")
BAD_LOGIN = "Invalid email or password."

LOGIN_LIMIT, LOGIN_WINDOW = 5, 15 * 60  # failed attempts per IP and per email
SIGNUP_LIMIT, SIGNUP_WINDOW = 10, 60 * 60  # attempts per IP

_hasher = PasswordHasher()
# an unknown email still pays the argon2 cost, so response time doesn't reveal which emails exist
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))

SCHEMA = """
PRAGMA journal_mode = WAL;
CREATE TABLE IF NOT EXISTS users (
    id         TEXT PRIMARY KEY,
    email      TEXT UNIQUE COLLATE NOCASE,
    pw_hash    TEXT,
    is_guest   INTEGER NOT NULL,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    token_hash TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at REAL NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS jobs (
    job_id     TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS jobs_user ON jobs(user_id, created_at);
"""

_init_lock = threading.Lock()
_initialised: set[str] = set()


@contextmanager
def _db():
    """One short-lived connection per operation; commits on success, rolls back on error."""
    path = config.DB_FILE
    if str(path) not in _initialised:
        with _init_lock:
            if str(path) not in _initialised:
                path.parent.mkdir(parents=True, exist_ok=True)
                with sqlite3.connect(path) as c:
                    c.executescript(SCHEMA)
                _initialised.add(str(path))
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        with conn:
            yield conn
    finally:
        conn.close()


@dataclass(frozen=True)
class Principal:
    user_id: str
    email: str | None
    is_guest: bool
    token_hash: str
    expires_at: float

    @property
    def kind(self) -> str:
        return "guest" if self.is_guest else "account"


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _new_session(conn: sqlite3.Connection, user_id: str, ttl: float) -> tuple[str, float]:
    token = secrets.token_urlsafe(32)
    now = time.time()
    conn.execute(
        "INSERT INTO sessions (token_hash, user_id, expires_at, created_at) VALUES (?, ?, ?, ?)",
        (_hash_token(token), user_id, now + ttl, now),
    )
    return token, now + ttl


def set_cookie(response: Response, token: str, expires_at: float) -> None:
    response.set_cookie(
        COOKIE,
        token,
        max_age=max(0, int(expires_at - time.time())),
        httponly=True,
        secure=config.cookie_secure(),
        samesite="lax",
        path="/",
    )


def clear_cookie(response: Response) -> None:
    response.delete_cookie(COOKIE, path="/", httponly=True, secure=config.cookie_secure(), samesite="lax")


# ---------------------------------------------------------------- reading the session


def principal(request: Request) -> Principal | None:
    """The caller's session, or None. Expired sessions are deleted; account sessions slide."""
    token = request.cookies.get(COOKIE)
    if not token or len(token) > 256:
        return None
    token_hash = _hash_token(token)
    now = time.time()
    with _db() as conn:
        row = conn.execute(
            "SELECT s.user_id, s.expires_at, u.email, u.is_guest FROM sessions s JOIN users u ON u.id = s.user_id WHERE s.token_hash = ?",
            (token_hash,),
        ).fetchone()
        if row is None:
            return None
        if row["expires_at"] <= now:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash,))
            return None
        expires_at = row["expires_at"]
        if not row["is_guest"] and expires_at - now < ACCOUNT_TTL / 2:
            expires_at = now + ACCOUNT_TTL
            conn.execute("UPDATE sessions SET expires_at = ? WHERE token_hash = ?", (expires_at, token_hash))
    return Principal(row["user_id"], row["email"], bool(row["is_guest"]), token_hash, expires_at)


def require_principal(request: Request, response: Response) -> Principal:
    """The caller's session; a device without one gets a new guest identity (and cookie)."""
    p = principal(request)
    if p is not None:
        return p
    user_id = uuid.uuid4().hex
    with _db() as conn:
        conn.execute("INSERT INTO users (id, email, pw_hash, is_guest, created_at) VALUES (?, NULL, NULL, 1, ?)", (user_id, time.time()))
        token, expires_at = _new_session(conn, user_id, GUEST_TTL)
    set_cookie(response, token, expires_at)
    return Principal(user_id, None, True, _hash_token(token), expires_at)


def require_account(request: Request) -> Principal:
    p = principal(request)
    if p is None or p.is_guest:
        raise HTTPException(401, "Sign in to continue.")
    return p


def owned_job(job_id: str, request: Request) -> Principal:
    """The caller, if they own `job_id`. Otherwise 404, the same answer as for a job that doesn't exist."""
    p = principal(request) if JOB_ID.match(job_id) else None
    if p is not None:
        with _db() as conn:
            row = conn.execute("SELECT 1 FROM jobs WHERE job_id = ? AND user_id = ?", (job_id, p.user_id)).fetchone()
        if row is not None:
            return p
    raise HTTPException(404, "Unknown job")


# ---------------------------------------------------------------- accounts


def _normalise_email(email: str) -> str:
    email = email.strip().lower()
    if len(email) > 254 or not EMAIL.match(email):
        raise HTTPException(422, "Enter a valid email address.")
    return email


def _check_password(password: str) -> None:
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise HTTPException(422, f"Password must be {PASSWORD_MIN}-{PASSWORD_MAX} characters.")


def signup(email: str, password: str, current: Principal | None) -> tuple[Principal, str]:
    """Create an account. A guest caller is upgraded in place, so its analyses come along."""
    email = _normalise_email(email)
    _check_password(password)
    pw_hash = _hasher.hash(password)
    taken = HTTPException(409, "An account with this email already exists. Sign in instead.")
    try:
        return _create_account(email, pw_hash, current, taken)
    except sqlite3.IntegrityError:  # lost a race with a concurrent signup for the same email
        raise taken from None


def _create_account(email: str, pw_hash: str, current: Principal | None, taken: HTTPException) -> tuple[Principal, str]:
    with _db() as conn:
        if conn.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise taken
        if current is not None and current.is_guest:
            user_id = current.user_id
            conn.execute("UPDATE users SET email = ?, pw_hash = ?, is_guest = 0 WHERE id = ?", (email, pw_hash, user_id))
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (user_id,))  # rotate: the guest token stops working
        else:
            if current is not None:
                conn.execute("DELETE FROM sessions WHERE token_hash = ?", (current.token_hash,))
            user_id = uuid.uuid4().hex
            conn.execute("INSERT INTO users (id, email, pw_hash, is_guest, created_at) VALUES (?, ?, ?, 0, ?)", (user_id, email, pw_hash, time.time()))
        token, expires_at = _new_session(conn, user_id, ACCOUNT_TTL)
    return Principal(user_id, email, False, _hash_token(token), expires_at), token


def login(email: str, password: str, current: Principal | None) -> tuple[Principal, str]:
    """Verify credentials and start a fresh session. A guest caller's analyses move into the account."""
    email = email.strip().lower()
    with _db() as conn:
        row = conn.execute("SELECT id, email, pw_hash FROM users WHERE email = ? AND is_guest = 0", (email,)).fetchone()
    try:
        _hasher.verify(row["pw_hash"] if row else _DUMMY_HASH, password)
        ok = row is not None
    except (VerificationError, InvalidHashError):
        ok = False
    if not ok:
        raise HTTPException(401, BAD_LOGIN)
    user_id = row["id"]
    with _db() as conn:
        if _hasher.check_needs_rehash(row["pw_hash"]):
            conn.execute("UPDATE users SET pw_hash = ? WHERE id = ?", (_hasher.hash(password), user_id))
        if current is not None and current.is_guest:
            conn.execute("UPDATE jobs SET user_id = ? WHERE user_id = ?", (user_id, current.user_id))
            conn.execute("DELETE FROM users WHERE id = ?", (current.user_id,))
        elif current is not None:
            conn.execute("DELETE FROM sessions WHERE token_hash = ?", (current.token_hash,))
        token, expires_at = _new_session(conn, user_id, ACCOUNT_TTL)
    return Principal(user_id, row["email"], False, _hash_token(token), expires_at), token


def logout(p: Principal) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash = ?", (p.token_hash,))


def delete_user(user_id: str) -> list[str]:
    """Delete a user with their sessions and job rows. Returns the job ids, whose files the caller removes."""
    with _db() as conn:
        ids = [r["job_id"] for r in conn.execute("SELECT job_id FROM jobs WHERE user_id = ?", (user_id,))]
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    return ids


def purge_expired(now: float | None = None) -> list[str]:
    """Drop expired sessions and guests older than GUEST_TTL. Returns the purged guests' job ids."""
    now = time.time() if now is None else now
    with _db() as conn:
        conn.execute("DELETE FROM sessions WHERE expires_at <= ?", (now,))
        cutoff = now - GUEST_TTL
        ids = [
            r["job_id"]
            for r in conn.execute("SELECT j.job_id FROM jobs j JOIN users u ON u.id = j.user_id WHERE u.is_guest = 1 AND u.created_at < ?", (cutoff,))
        ]
        conn.execute("DELETE FROM users WHERE is_guest = 1 AND created_at < ?", (cutoff,))
    return ids


# ---------------------------------------------------------------- jobs


def record_job(user_id: str, job_id: str, name: str) -> None:
    with _db() as conn:
        conn.execute("INSERT INTO jobs (job_id, user_id, name, created_at) VALUES (?, ?, ?, ?)", (job_id, user_id, name, time.time()))


def list_jobs(user_id: str) -> list[dict]:
    with _db() as conn:
        rows = conn.execute("SELECT job_id, name, created_at FROM jobs WHERE user_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    return [dict(r) for r in rows]


def forget_job(job_id: str) -> None:
    with _db() as conn:
        conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))


# ---------------------------------------------------------------- brute-force limits


class RateLimiter:
    """In-memory sliding window. Per process, which fits the single uvicorn worker this app runs."""

    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _recent(self, key: str, window: float) -> deque[float]:
        q = self._hits[key]
        cutoff = time.monotonic() - window
        while q and q[0] < cutoff:
            q.popleft()
        return q

    def blocked(self, key: str, limit: int, window: float) -> bool:
        with self._lock:
            return len(self._recent(key, window)) >= limit

    def hit(self, key: str) -> None:
        with self._lock:
            self._hits[key].append(time.monotonic())

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


LIMITER = RateLimiter()


def client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------- CSRF + security headers

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
SECURITY_HEADERS = {
    "x-content-type-options": "nosniff",
    "referrer-policy": "same-origin",
    "x-frame-options": "DENY",
}


class SecurityMiddleware:
    """Rejects state-changing requests from browser origins outside the allowlist (CSRF),
    adds security headers, and marks per-user responses `no-store`."""

    def __init__(self, app, origins: list[str]) -> None:
        self.app = app
        self.origins = set(origins)

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if scope["method"] not in SAFE_METHODS and not self._origin_allowed(Headers(scope=scope)):
            return await JSONResponse({"detail": "Cross-site request blocked."}, status_code=403)(scope, receive, send)
        private = scope["path"].startswith(("/api/jobs", "/api/auth"))

        async def send_with_headers(message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for k, v in SECURITY_HEADERS.items():
                    headers.setdefault(k, v)
                if private:
                    headers.setdefault("cache-control", "no-store")
            await send(message)

        await self.app(scope, receive, send_with_headers)

    def _origin_allowed(self, headers: Headers) -> bool:
        origin = headers.get("origin")
        if origin is None and (referer := headers.get("referer")):
            parts = urlsplit(referer)
            origin = f"{parts.scheme}://{parts.netloc}"
        # no Origin and no Referer: not a browser page (curl, scripts, tests), so no ambient-cookie risk
        return origin is None or origin.rstrip("/") in self.origins
