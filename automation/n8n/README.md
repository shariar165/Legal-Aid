# n8n workflows

Two self-hosted [n8n](https://n8n.io) workflows around the Ain backend. All the logic lives in the backend (tested
in `backend/tests/test_automation.py`). n8n handles scheduling, branching and notifying, so the workflows stay
small enough to read at a glance.

| Workflow | Trigger | What it does |
|---|---|---|
| `law-freshness-watch.json` | every day 06:00 (Asia/Dhaka) | `GET /api/corpus/freshness`: the backend re-reads each Bangladesh act on bdlaws.minlaw.gov.bd, parses it with the scraper's own parser, and compares every corpus section (NFC and whitespace normalised). If a section changed, disappeared or was added, or the site could not be reached, the team gets an alert with the citation ids and the rebuild commands. |
| `analysis-digest.json` | webhook `POST /webhook/ain-job-digest`, sent by the backend when an analysis finishes | Formats a one-line summary. If the analysis has a critical risk or a claim flagged for human review, it alerts the team. The payload is counts only: no file name, no document text, no finding. |

## Set up

1. Start n8n: `docker compose up -d` in this folder, then open http://localhost:5678 and create the owner account.
2. Backend `.env` (root):
   ```
   AIN_AUTOMATION_TOKEN=<a long random string>        # python -c "import secrets; print(secrets.token_urlsafe(32))"
   AIN_WEBHOOK_URL=http://localhost:5678/webhook/ain-job-digest
   ```
   Restart the backend. Without the token, `/api/corpus/freshness` answers 404; without the URL, no digest is sent.
3. In n8n, **Credentials → New → Header Auth**, name it `Ain automation token`, with header name `Authorization`
   and value `Bearer <AIN_AUTOMATION_TOKEN>`.
4. **Workflows → Import from file** for both JSON files. In each, open the **Settings** node and set
   `notifyWebhookUrl` (a Slack, Discord or Teams incoming-webhook URL). In the freshness workflow also check
   `ainBaseUrl` (`http://host.docker.internal:8000` reaches a backend running on the host), and select the
   `Ain automation token` credential on the **Check bdlaws vs corpus** node.
5. Run each workflow once with **Execute workflow**, then switch them to *Active*.

Command-line import instead of step 4 (n8n running, owner account created):
`n8n import:workflow --input=law-freshness-watch.json --projectId=<your personal project id>`, and the same for
`analysis-digest.json`. Then do the Settings and credential edits from step 4 in the editor. If you run n8n with
`npx n8n` rather than Docker, set `ainBaseUrl` to `http://localhost:8000`.

The settings sit in a node, not in `$env`, because n8n 2.x blocks environment access inside nodes by default. The
token stays in n8n's encrypted credential store and never appears in the exported JSON.

## Behaviour worth knowing

- One freshness check runs at a time, and its result is reused for 10 minutes (`?force=true` skips the cache), so
  the endpoint can't be used to hammer a government site.
- The check waits 1 s between acts, gives each page 30 s with one retry, and stops at the first act if the site
  is unreachable. That counts as an "incomplete" alert, not a silent pass.
- The workflow never rebuilds the corpus. Re-scraping changes what the verifier compares claims against, so a
  person reviews the diff and runs the `rebuild-corpus` steps (`.claude/skills/rebuild-corpus/SKILL.md`).

## Tested so far

The backend side (the diff logic against a page built from our own corpus with one section changed and one removed,
an unreachable site, token gating, the cache, and the count-only digest and its POST) is covered by pytest. The
JavaScript in both workflows (the Code node and the alert expressions) was run in Node against a real job digest and
against changed/outage freshness reports. The workflows have **not yet been imported into a running n8n**: the
development machine didn't have the memory for Docker Desktop. Do that once, as in step 5, before relying on them.
