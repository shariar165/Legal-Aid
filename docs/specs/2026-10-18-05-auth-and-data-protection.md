# Authentication & user-data protection for Ain Copilot

## Context
Right now the FastAPI backend (`backend/ain/api.py`) has no identity at all. Every job endpoint (`/api/jobs/{id}/result`, `/events`, `/memo.docx`, `/council/*`, `/confirm`, `/ablation`) answers anyone who knows the 12-hex job ID. Results are stored as plaintext JSON in `backend/runs/{id}.json`. The PII Shield already redacts identifiers before storage (`orchestrator.py:251`), but the contract text, the risks and the council chats are still sensitive, and anyone with a job link can read them.

Goal: every analysis belongs to exactly one principal (a guest device or a registered account), only that principal can reach it, and the data is encrypted on disk.

**Decision (user):** Guest + accounts.
- Citizen mode needs no signup. Each device gets a private guest session that owns its analyses, and guest data is deleted after 7 days.
- Signing up turns the guest into an account: the guest's jobs move to the account, and the account adds history across devices.
- Counsel mode (`/counsel/*`) requires an account.

## Design

### Backend: new module `backend/ain/auth.py`
- **Store:** stdlib `sqlite3` at `backend/.data/ain.db`, which gets added to `.gitignore`. Tables:
  - `users(id, email UNIQUE COLLATE NOCASE, pw_hash NULL, is_guest, created_at)`
  - `sessions(token_hash PK, user_id, expires_at, created_at)`
  - `jobs(job_id PK, user_id, name, created_at)`

  The path comes from `AIN_DB` in `config.py` (pattern of `RUNS_DIR`).
- **Passwords:** argon2id via `argon2-cffi`. Minimum 10 characters, maximum 128. Rehash on login when the hash parameters change. Login failures always return the same generic "Invalid email or password", so the endpoint doesn't reveal which emails have accounts.
- **Sessions:** an opaque `secrets.token_urlsafe(32)` in an `ain_session` cookie, with `HttpOnly`, `SameSite=Lax`, `Path=/`, and `Secure` when `AIN_COOKIE_SECURE=1`. Only `sha256(token)` is stored, so a leaked DB doesn't expose live sessions. Lifetimes: 30 days for accounts (sliding) and 7 days for guests. The token is rotated on login and signup to prevent session fixation. Logout deletes the row.
- **FastAPI dependencies:**
  - `current_principal(optional)` reads the cookie.
  - `require_principal` lazily creates a guest user and session on the first `/api/analyze`, then sets the cookie.
  - `require_account` rejects guests with 401.
  - `owned_job(job_id)` returns **404** (not 403) when the job isn't the caller's, so job IDs can't be probed.
- **CSRF:** a middleware rejects non-GET requests whose `Origin` (or `Referer`) is not in the `AIN_CORS` allowlist. This sits on top of SameSite=Lax.
- **Brute-force limit:** an in-memory sliding window keyed by IP and by email: 5 failed logins per 15 minutes, then 429. Signups are limited to 10 per IP per hour.
- **Cleanup:** the existing startup hook in `api.py` also starts a periodic task, hourly at most. It deletes expired sessions, guest users older than 7 days, their `jobs` rows, and their `runs/*.json` files.

### Endpoints (`api.py`)
- New, under `/api/auth`:
  - `POST /signup` with `{email, password}`. If the caller is a guest, the guest's jobs are re-owned by the new account.
  - `POST /login`. Any current guest's jobs are merged into the account.
  - `POST /logout`.
  - `GET /me` returns `{kind: "guest"|"account"|null, email}`.
  - `DELETE /me` deletes the account, its sessions, jobs and run files (right to erasure).
  - `GET /api/jobs` lists the caller's analyses: id, name, created_at.
  - `DELETE /api/jobs/{id}` deletes one analysis.
- **Changed endpoints:**
  - `/api/analyze` uses `require_principal` and records ownership with `auth.record_job` right after `new_job`.
  - Every `/api/jobs/{id}/*` route goes through `owned_job`. That covers `job_status`, `job_events`, `confirm`, `_result_or_409`, `memo`, `run_ablation`, `council_chat` and `council_deliberate`.
- **Stay public:** `/api/health`, `/api/samples`, `/api/council`, `/api/corpus/{id}`.
- **CORS:** `allow_credentials=True`. The origins are already an explicit list, which credentials require. Methods are narrowed to GET/POST/DELETE.

### Encryption at rest (`orchestrator.py`)
- `_persist` and `load_result` become the only read/write path for run files. `api.py:220` and `api.py:243` currently write `RUNS_DIR` directly; they will call `orchestrator._persist` instead (rename it to a public `save_result`).
- Run files are encrypted with Fernet from `cryptography`. The key comes from `AIN_DATA_KEY`. In dev, if the key is unset, one is generated once into `backend/.data/secret.key`, which is gitignored. Run files become `{id}.json.enc`.
- The 127 legacy plaintext files have no owner, so after this change they can't be reached through the API. A one-off `scripts/purge_legacy_runs.py` lets you delete them. Nothing is deleted automatically.

### Frontend (`web/`)
- `src/lib/api.ts`:
  - Every `fetch` gets `credentials: "include"` through one small wrapper.
  - New `auth.signup/login/logout/me/deleteAccount`, `jobs.list/remove`.
  - `json()` throws a typed `AuthError` on 401.
- `src/lib/useAnalysis.ts`: `new EventSource(url, { withCredentials: true })`.
- `src/lib/useSession.ts` (new client hook): calls `/api/auth/me` and exposes `{kind, email, refresh}`.
- **New routes:** `src/app/login/page.tsx` and `src/app/signup/page.tsx`. These are client forms that honour `?next=`, styled with `counsel.module.css` tokens. They are English-first, with Bangla strings added via `lib/citizen/i18n.ts` for the citizen "save" entry point. Because `cacheComponents` is on, session-dependent UI sits behind `<Suspense>`. Auth is enforced by the backend; the frontend only redirects on 401.
- **Counsel gate:** `CounselStart` and `CounselApp` check `useSession`. A non-account visitor is sent to `/login?next=/counsel/...`.
- **Header account chip** in the Counsel topbar (`CounselStart.tsx:58`, `CounselApp.tsx:80`): signed-in email, "My analyses" (from `GET /api/jobs`), sign out, delete account.
- **Citizen HomeScreen** (`HomeScreen.tsx:46`): a small "Save my results / ফলাফল সংরক্ষণ করুন" link to signup. No change to the guest flow.
- **Security headers:** `next.config.ts` `headers()` adds `X-Content-Type-Options: nosniff`, `Referrer-Policy: same-origin` (stops job IDs leaking through Referer), `X-Frame-Options: DENY`, and `Permissions-Policy` (camera=self, used for the photo flow). FastAPI responses get the same headers from a tiny middleware.

### Dependencies and config
- `requirements.txt`: add `argon2-cffi` and `cryptography`, at exact pinned versions per the file's convention.
- `.env.example`: add `AIN_DATA_KEY=`, `AIN_COOKIE_SECURE=0`, and `AIN_CORS=` with a comment on how to generate the key.
- README: one "Security" section covering the guest/account model and the key handling.

## Out of scope (stated, not built)
- Email verification and password-reset emails, since there's no mail provider. A user who forgets their password must sign up again.
- OAuth and 2FA.

## Verification
1. `pytest` from `backend/` (offline, fake LLM). The existing `test_api.py` must keep passing unchanged: `TestClient` keeps cookies, so its first `/api/analyze` gets a guest session automatically. `test_council.py` must pass too.
2. New `backend/tests/test_auth.py`:
   - Signup, me, logout, then login.
   - A wrong password gets the generic error, and the 6th failure gets 429.
   - Duplicate email is rejected, and so is a short password.
   - Client B gets **404** on client A's result, events, memo, council and confirm.
   - Guest jobs move to the new account on signup.
   - A guest gets 401 on an account-only check.
   - A POST with a foreign `Origin` gets 403.
   - The run file on disk does not contain the plaintext memo title, and it round-trips through `load_result`.
   - `DELETE /api/auth/me` removes the jobs and files.
   - The guest-expiry cleanup purges old guests.
3. Manual run (`uvicorn ain.api:app --port 8000` and `npm run dev`):
   - Citizen flow works with no login.
   - Opening a `/counsel/<id>` link in a private window goes to login, and after login another user's job shows "not found".
   - SSE trace still streams.
   - The DOCX download works.
   - `npm run lint` and `npm run build` pass.
