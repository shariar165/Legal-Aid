# Ain Copilot web app

The Next.js 16 front end of Ain Copilot (App Router, Cache Components on). It has two modes over one backend:

| Route | Who | What |
|---|---|---|
| `/` | a migrant worker on a phone | Citizen mode: Bangla-first, read aloud, a salary check for blurry photos, take-home pay, help contacts in the country of work, a letter to the recruiting agency. A private guest session is created automatically. |
| `/counsel`, `/counsel/[jobId]` | lawyers, NGO caseworkers, compliance teams | Counsel workspace: Report (IRAC memo, DOCX), Contract, Council (chat with the three LLM judges, deliberation, Chief Justice ruling) and Verification (ledger, agent trace, plain-chatbot comparison, privacy receipt). Needs an account. |
| `/login`, `/signup` | | account pages; a guest's analyses move into the account on sign-in |

Code map: `src/components/citizen/*` and `src/components/counsel/*` hold the two UIs. `src/lib/api.ts` is the typed client for the FastAPI backend (`backend/ain/api.py`). `src/lib/useAnalysis.ts` follows a job over server-sent events, and `src/lib/useSession.ts` handles the session.

## Run

The backend must be running first (see the repository README). Then:

```bash
npm install
npm run dev          # http://localhost:3000
npm run lint
npm run build && npm start   # production build; lighter on memory than dev
```

## Environment

| Variable | When | Meaning |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | build time | Where the browser calls the backend. Default `http://localhost:8000`. Set it to `""` for same-origin calls through the proxy below. |
| `AIN_INTERNAL_API` | build time | When set (the Docker image uses `http://127.0.0.1:8000`), `next.config.ts` rewrites `/api/*` to the backend and turns gzip off, so server-sent events stream. The browser then sees one origin, so the HttpOnly session cookie stays first-party. |
| `NEXT_PUBLIC_HELPDESK_PHONE` | build time | Optional number for the citizen "call for help" button. |

The backend's `AIN_CORS` must list the origin the browser uses: `http://localhost:3000` in development, or the public URL of a deployment. Its CSRF check rejects other origins.

## Notes for contributors

- This is Next.js 16: read `node_modules/next/dist/docs/` before relying on older conventions (see `AGENTS.md`).
- Route gating must redirect from the fresh `useSession(onSession)` callback, never from stored session state. Cache Components keep visited routes alive, and stale state caused a login loop.
