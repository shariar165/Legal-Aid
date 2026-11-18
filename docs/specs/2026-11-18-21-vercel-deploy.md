# Deploy the Ain Copilot frontend to Vercel (backend later)

## Context
The judges need a public link to the Next.js app (`web/`). The FastAPI backend will run on Railway (lite mode), but
that waits until the Railway account is re-authenticated. **This round is Vercel only.** The frontend goes up now,
and the `/api` proxy to Railway is switched on later by setting one variable and redeploying.

What already exists:
- `web/next.config.ts`: when `AIN_INTERNAL_API` is set at build time, `/api/*` is rewritten to that backend (an
  external rewrite on Vercel) and gzip is turned off so SSE streams. With `NEXT_PUBLIC_API_URL=""`, the browser calls
  its own origin, so the HttpOnly session cookie stays first-party.
- `web/src/lib/api.ts:5` falls back to `http://localhost:8000` when `NEXT_PUBLIC_API_URL` is unset. That fallback is
  wrong on Vercel, so the variable must be set to `""`.
- The Vercel CLI 65.11.0 is installed and logged in as `shariar165`. `.vercel` is gitignored in `web/.gitignore`.

## Steps
1. **Spec.** Save this plan as `docs/specs/2026-11-18-21-vercel-deploy.md`.
2. **Local gate.** `cd web && npm run lint && npm run build` must pass before anything goes up.
3. **Link.** From `web/`, run `vercel link` and create the project (suggested name `ain-copilot`; framework Next.js
   is detected; root = `web/`, since the CLI runs from there). Make sure the Node version in the project settings is
   22.x, to match local.
4. **Env vars** (build-time, for both Preview and Production):
   - `NEXT_PUBLIC_API_URL=""`: same-origin calls.
   - `NEXT_TELEMETRY_DISABLED=1`.
   - Leave `AIN_INTERNAL_API` **unset** for now: there is no backend yet, so `/api/*` returns 404 and the UI shows its
     offline state rather than calling localhost.
5. **Preview deploy.** `vercel deploy` from `case-desk`. Browser check of the preview (logged in through Vercel):
   `/`, `/counsel`, `/docs` and `/login` render. No browser console errors other than the expected failed `/api`
   calls, and no requests go to `localhost:8000`. Security headers from `next.config.ts` are present.
6. **Promote to production.** `vercel promote <preview-url>` (or `vercel deploy --prod`). The judges get the
   production alias `https://<project>.vercel.app`: Standard Deployment Protection covers previews and per-deployment
   URLs, not the production domain. Check the alias in a logged-out (incognito) window.
7. **Docs.** Add a short "Vercel" subsection next to the Docker/HF section of the repo `README.md`, and a row in the
   `web/README.md` env table: the env values, and that `AIN_INTERNAL_API` is build-time, so changing it needs a
   redeploy. Commit on `case-desk` (offline `pytest` must pass first, per AGENTS.md).

## Later (not in this round)
- **Railway backend, lite mode:** `backend/requirements-lite.txt` (no torch, sentence-transformers, FAISS or EasyOCR),
  start command `uvicorn ain.api:app --host 0.0.0.0 --port $PORT`, Serverless on, `AIN_DENSE=0`, `AIN_CORS`=the
  Vercel production origin, `AIN_COOKIE_SECURE=1`, `AIN_DATA_KEY`, provider keys, and a volume for `AIN_DATA_DIR`.
  Railpack only detects `requirements.txt`, so the install command must point at the lite file; to check then.
- **Connect:** `vercel env add AIN_INTERNAL_API production` = the Railway URL, then redeploy and promote.
- **SSE check:** run a full analysis through the proxy. The backend pings every 15 s (`orchestrator.Job.stream`),
  under Vercel's 120 s proxy limit. If the stream still cuts off, change the `onerror` path in
  `web/src/lib/useAnalysis.ts` to poll `GET /api/jobs/{id}` instead of re-following. Re-following replays events
  from 0, which duplicates the trace.
- **Merge `case-desk` → `main`** once the full stack works live, so the repo the judges see matches the demo.

## Verification
- `npm run lint && npm run build` pass locally, and the Vercel build log is green.
- Production alias opens logged-out. Pages render, and the network tab shows `/api/*` on the same origin (404 for
  now) with nothing going to localhost.
- `pytest -q` passes before the docs commit.
