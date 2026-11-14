"""Rehearsal sessions at rest: encrypted like analyses (ain/vault.py), owned through the accounts DB.

A `rehearsals` row ties a session to its owner and is deleted with the user (ON DELETE CASCADE): account erasure and
the guest purge then call `purge_orphans`, which removes every session file that no longer has a row.
"""

from __future__ import annotations

import re
import threading
import time
import uuid

from ain import auth, config, vault
from ain.models import RehearsalSession

ID = re.compile(r"^[0-9a-f]{12}$")
SCHEMA = """
CREATE TABLE IF NOT EXISTS rehearsals (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS rehearsals_user ON rehearsals(user_id);
"""
_ready: set[str] = set()
_lock = threading.Lock()


def _conn():
    ctx = auth._db()
    path = str(config.DB_FILE)
    if path not in _ready:
        with _lock, auth._db() as c:
            c.executescript(SCHEMA)
            _ready.add(path)
    return ctx


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def record(user_id: str, sid: str) -> None:
    with _conn() as c:
        c.execute("INSERT INTO rehearsals (id, user_id, created_at) VALUES (?, ?, ?)", (sid, user_id, time.time()))


def owns(user_id: str, sid: str) -> bool:
    if not ID.match(sid):
        return False
    with _conn() as c:
        return c.execute("SELECT 1 FROM rehearsals WHERE id = ? AND user_id = ?", (sid, user_id)).fetchone() is not None


def _path(sid: str):
    return config.RUNS_DIR / f"rehearsal-{sid}.json.enc"


def save(s: RehearsalSession) -> None:
    config.RUNS_DIR.mkdir(parents=True, exist_ok=True)
    _path(s.id).write_bytes(vault.encrypt(s.model_dump_json().encode("utf-8")))


def load(sid: str) -> RehearsalSession | None:
    p = _path(sid)
    return RehearsalSession.model_validate_json(vault.decrypt(p.read_bytes())) if p.exists() else None


def delete(sid: str) -> None:
    with _conn() as c:
        c.execute("DELETE FROM rehearsals WHERE id = ?", (sid,))
    _path(sid).unlink(missing_ok=True)


def purge_orphans() -> list[str]:
    """Delete session files whose owner (and so whose row) is gone. Returns the ids removed."""
    if not config.RUNS_DIR.exists():
        return []
    with _conn() as c:
        known = {r["id"] for r in c.execute("SELECT id FROM rehearsals")}
    gone = []
    for f in config.RUNS_DIR.glob("rehearsal-*.json.enc"):
        sid = f.name[len("rehearsal-") : -len(".json.enc")]
        if sid not in known:
            f.unlink(missing_ok=True)
            gone.append(sid)
    return gone
