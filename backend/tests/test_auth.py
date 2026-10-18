"""Accounts, sessions and data isolation: one principal can never reach another's analysis."""

import time

import pytest
from fastapi.testclient import TestClient

from ain import api, auth, config
from ain.orchestrator import JOBS, load_result
from tests.test_api import _wait

PASSWORD = "correct horse battery"
ORIGIN = {"Origin": "http://localhost:3000"}


def _client() -> TestClient:
    return TestClient(api.app)


@pytest.fixture
def a():
    with _client() as c:
        yield c


@pytest.fixture
def b():
    with _client() as c:
        yield c


def _email(tag: str) -> str:
    return f"{tag}-{time.time_ns()}@example.org"


def _analyze(client) -> str:
    job = client.post("/api/analyze", data={"sample_id": "control"}).json()["job_id"]
    assert _wait(client, job)["status"] == "done"
    return job


def test_signup_me_logout_login(a):
    assert a.get("/api/auth/me").json() == {"kind": None, "email": None}
    email = _email("Asha")
    r = a.post("/api/auth/signup", json={"email": f"  {email.upper()} ", "password": PASSWORD})
    assert r.status_code == 200 and r.json() == {"kind": "account", "email": email.lower()}
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie and "path=/" in cookie
    assert a.get("/api/auth/me").json()["kind"] == "account"

    assert a.post("/api/auth/logout").json() == {"ok": True}
    assert a.get("/api/auth/me").json()["kind"] is None
    assert a.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()["kind"] == "account"


def test_only_token_hashes_are_stored(a):
    a.post("/api/auth/signup", json={"email": _email("hash"), "password": PASSWORD})
    token = a.cookies[auth.COOKIE]
    with auth._db() as conn:
        hashes = {r["token_hash"] for r in conn.execute("SELECT token_hash FROM sessions")}
        pw = conn.execute("SELECT pw_hash FROM users WHERE pw_hash IS NOT NULL LIMIT 1").fetchone()["pw_hash"]
    assert token not in hashes and auth._hash_token(token) in hashes
    assert pw.startswith("$argon2id$") and PASSWORD not in pw


def test_signup_validation(a, b):
    email = _email("dup")
    assert a.post("/api/auth/signup", json={"email": email, "password": PASSWORD}).status_code == 200
    assert b.post("/api/auth/signup", json={"email": email.upper(), "password": PASSWORD}).status_code == 409
    assert b.post("/api/auth/signup", json={"email": _email("short"), "password": "tooshort"}).status_code == 422
    assert b.post("/api/auth/signup", json={"email": "not-an-email", "password": PASSWORD}).status_code == 422


def test_wrong_password_is_generic_and_rate_limited(a, b):
    email = _email("brute")
    a.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    wrong = b.post("/api/auth/login", json={"email": email, "password": "wrong password!"})
    unknown = b.post("/api/auth/login", json={"email": _email("nobody"), "password": "wrong password!"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json()["detail"] == unknown.json()["detail"] == auth.BAD_LOGIN

    auth.LIMITER.reset()
    for _ in range(auth.LOGIN_LIMIT):
        assert b.post("/api/auth/login", json={"email": email, "password": "wrong password!"}).status_code == 401
    # locked out even with the right password until the window passes
    assert b.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 429


def test_another_user_cannot_reach_a_job(a, b):
    job = _analyze(a)
    r = a.get(f"/api/jobs/{job}/result").json()
    assert [j["job_id"] for j in a.get("/api/jobs").json()] == [job]

    b.post("/api/analyze", data={"sample_id": "control"})  # b has its own guest session
    assert job not in {j["job_id"] for j in b.get("/api/jobs").json()}
    for method, path, kw in [
        ("get", f"/api/jobs/{job}", {}),
        ("get", f"/api/jobs/{job}/events", {}),
        ("get", f"/api/jobs/{job}/result", {}),
        ("get", f"/api/jobs/{job}/memo.docx", {}),
        ("post", f"/api/jobs/{job}/confirm", {"json": {"value": "1800"}}),
        ("post", f"/api/jobs/{job}/ablation", {}),
        ("post", f"/api/jobs/{job}/council/chat", {"json": {"message": "hi", "members": ["happy"]}}),
        ("post", f"/api/jobs/{job}/council/deliberate", {"json": {"message": "hi", "replies": []}}),
        ("delete", f"/api/jobs/{job}", {}),
    ]:
        res = getattr(b, method)(path, **kw)
        assert res.status_code == 404, (method, path, res.status_code)
        assert res.json()["detail"] == "Unknown job"  # same answer as a job that doesn't exist
    with _client() as anonymous:
        assert anonymous.get(f"/api/jobs/{job}/result").status_code == 404
    assert a.get(f"/api/jobs/{job}/result").json()["memo"] == r["memo"]


def test_guest_jobs_follow_signup_and_old_token_dies(a):
    job = _analyze(a)
    guest_token = a.cookies[auth.COOKIE]
    assert a.get("/api/auth/me").json()["kind"] == "guest"
    assert a.post("/api/auth/signup", json={"email": _email("guest"), "password": PASSWORD}).status_code == 200
    assert a.cookies[auth.COOKIE] != guest_token
    assert [j["job_id"] for j in a.get("/api/jobs").json()] == [job]
    with _client() as stale:
        stale.cookies.set(auth.COOKIE, guest_token)
        assert stale.get("/api/auth/me").json()["kind"] is None
        assert stale.get(f"/api/jobs/{job}").status_code == 404


def test_guest_jobs_merge_into_account_on_login(a, b):
    email = _email("merge")
    a.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
    mine = _analyze(a)
    theirs = _analyze(b)
    assert b.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 200
    assert {j["job_id"] for j in b.get("/api/jobs").json()} == {mine, theirs}


def test_account_only_and_cross_site_requests(a):
    _analyze(a)  # guest
    assert a.delete("/api/auth/me").status_code == 401
    assert a.post("/api/auth/logout", headers={"Origin": "https://evil.example"}).status_code == 403
    assert a.post("/api/auth/logout", headers={"Origin": "null"}).status_code == 403
    assert a.post("/api/auth/logout", headers={"Referer": "https://evil.example/page"}).status_code == 403
    assert a.post("/api/auth/logout", headers=ORIGIN).status_code == 200
    h = a.get("/api/health").headers
    assert h["x-content-type-options"] == "nosniff" and h["x-frame-options"] == "DENY"
    assert a.get("/api/jobs").headers["cache-control"] == "no-store"


def test_results_are_encrypted_at_rest(a):
    job = _analyze(a)
    r = a.get(f"/api/jobs/{job}/result").json()
    path = config.RUNS_DIR / f"{job}.json.enc"
    raw = path.read_bytes()
    assert r["memo"]["title"].encode() not in raw and b"control_clean" not in raw and b'"risks"' not in raw
    JOBS.pop(job)  # force a read from disk
    assert load_result(job).memo.title == r["memo"]["title"]


def test_delete_job_and_account(a):
    a.post("/api/auth/signup", json={"email": _email("erase"), "password": PASSWORD})
    keep, gone = _analyze(a), _analyze(a)
    assert a.delete(f"/api/jobs/{gone}").json() == {"ok": True}
    assert a.get(f"/api/jobs/{gone}/result").status_code == 404
    assert not (config.RUNS_DIR / f"{gone}.json.enc").exists()

    assert a.delete("/api/auth/me").json() == {"ok": True}
    assert not (config.RUNS_DIR / f"{keep}.json.enc").exists() and keep not in JOBS
    assert a.get("/api/auth/me").json()["kind"] is None


def test_old_guests_are_purged(a, b):
    guest_job = _analyze(a)
    b.post("/api/auth/signup", json={"email": _email("stays"), "password": PASSWORD})
    account_job = _analyze(b)
    purged = auth.purge_expired(time.time() + auth.GUEST_TTL + 60)
    api._delete_job_files(purged)
    assert guest_job in purged and account_job not in purged
    assert not (config.RUNS_DIR / f"{guest_job}.json.enc").exists()
    assert a.get("/api/auth/me").json()["kind"] is None
