# আইন কপাইলট · Ain Copilot

**A multi-agent legal copilot for Bangladesh.** It reads a raw contract (PDF, DOCX, text, or a phone photo in Bangla or English) and finds non-obvious compliance risks. It then writes a memorandum in which **every legal claim has been verified against official statute text**. One engine serves two views:

- **Citizen mode** (`/`) is for a migrant worker on a phone. It works in Bangla, can read every answer aloud, and asks the worker to confirm a blurry salary figure. It shows the real take-home pay, the labour law of the country of work, where to get help there, and drafts a letter to the recruiting agency.
- **Counsel mode** (`/counsel`) is for a lawyer, NGO caseworker or factory compliance team. It is a workspace with four views:
  - **Report**: an IRAC memo with risk cards (what is wrong, what to do, the checked law), an at-a-glance summary and a DOCX download.
  - **Contract**: the document as a paper sheet, with each clause tinted by the severity of its risk.
  - **Council**: question the three LLM Council members (in English or Bangla), let them deliberate, read the Chief Justice's ruling, and see how each one voted.
  - **Verification**: the Verification Ledger, the live agent activity, a comparison against a plain chatbot, and a privacy receipt.

> Decision support, not legal advice.

---

## Why it is different

| | |
|---|---|
| **Citations can't be made up** | The agents may cite only `citation_id`s returned by retrieval over our own corpus. A citation produced any other way is rejected before verification. |
| **4-gate verifier** | Every claim passes four gates. **G1** checks that the section exists *and applies* to this document. **G2** checks quote fidelity. **G3** checks entailment, judged by a different model family that sees only the section text. **G4** checks that the law is still in force. Dropped claims stay visible in the ledger. |
| **Virtual Bench** | High and critical claims go to 3 judges from different model families (Claude, Gemini, DeepSeek via OpenRouter). They review each other anonymously, and a Chief Justice (GPT) writes a majority opinion and records any dissent. A dissent raises a ⚠ human-review flag. |
| **LLM Council** | The three judges have personalities: **Sunny** (happy, leans lenient on borderline severity), **Regal** (proud, holds its view) and **Grey** (gloomy, leans harsh). Personality changes tone and borderline severity only, never how the statute is read. In Counsel mode you can question them in English or Bangla; each answers in character with a one-line position and a confidence level, only from the redacted analysis, and may cite only sections that passed verification. **Deliberation:** after the first answers, the members respond to each other (agree, challenge or change position), then the Chief Justice writes a ruling: unanimous / majority / split, the consensus, the points still in dispute, and one next step. |
| **Real-world currency** | The corpus is the consolidated text as of Oct 2026. The 2012 Trafficking Act is **repealed**; the Critic re-anchors a stale citation to the 2026 Act and re-verifies it. Labour Act s.46 maternity leave now reads **60 + 60 days**, from the 2026 amendment. |
| **Country of work** | Bangladeshi workers go to many countries, so the labour law of the 8 main destinations is in the corpus: **Saudi Arabia, UAE, Malaysia, Qatar, Oman, Kuwait, Singapore, Bahrain**. The country is found in the contract (English or Bangla, e.g. "সৌদি আরবে") or picked by the user. Each country's law adds to Bangladesh law and ILO standards: recruitment fees, passports, deduction caps (50% in Saudi Arabia, 25% in Oman and Kuwait…), the ticket home and the end-of-service gratuity. The worker also sees the Bangladesh labour wing to contact there. |
| **Employer's own promises** | The contract is checked against (1) **fair-recruitment standards** many employers sign up to (ILO General Principles, Employer Pays Principle, RBA Code; always marked *voluntary standard, not law*), (2) an **employer policy or handbook the user uploads**, and (3) the **published policy of a named company** (`corpus/companies.yaml`). A contradiction is shown only if the policy quote passes the same 4 gates as a statute: "The employer's policy says X; this contract says Y." |
| **Regime switch** | For a factory inside an EPZ, the Router turns **off** the Labour Act 2006 and applies the BEPZ Labour Act 2019 (s.3 gives it overriding effect). A Labour Act citation in an EPZ document fails G1. |
| **Valid abroad, void in BD** | A clash badge marks clauses that are normal under English or EU law but void in Bangladesh: non-competes (Contract Act s.27), shortened limitation periods (s.28), 150-day payment terms (Bangladesh Bank's four-month repatriation rule). |
| **Off-playbook risks** | Adversarial Counsel runs agentic RAG with bilingual queries, so it finds risks the YAML playbook doesn't cover. Examples: silence on return airfare combined with termination at will; an exit penalty combined with withheld wages (debt bondage); a buyer's multi-union clause that can't be performed inside an EPZ. |
| **Wage Truth Calculator** | Uses arithmetic only, no LLM. Example: RM 1,200 − RM 650 in deductions = **RM 550 take-home**, against the RM 1,700 legal minimum and the 50% deduction cap. |
| **Privacy** | OCR runs locally (EasyOCR on CPU), so the photo never leaves the machine. A PII Shield redacts names, passport, NID, phone, address and DOB before any model call. A guard in the LLM layer blocks any payload that still contains an identifier, including council chat messages (rejected with HTTP 422). OpenRouter calls request `data_collection: deny`. |

## Architecture

```
upload ─► Ingestion (PyMuPDF · python-docx · EasyOCR bn+en, cached) → clauses + facts
       ─► PII Shield → placeholders; only redacted text ever leaves the machine
       ─► Jurisdiction Router → law packs (EPZ ⇒ BEPZ Labour Act replaces Labour Act; country of work ⇒ its labour law)
       ─► Risk Analyst (YAML playbook) ║ Adversarial Counsel (agentic RAG) ║ Wage Calculator (waits for the human salary check)
       ─► Policy Check: contract vs the employer's own policy (uploaded, or the named company's published one)
       ─► Citation Verifier: G1 existence/applicability · G2 fidelity · G3 entailment · G4 currency
            └─ high/critical → Virtual Bench (Sunny · Regal · Grey + Chief Justice, OpenRouter)
       ─► Critic (re-anchors repealed law, withdraws unsupported risks)
       ─► Memo Drafter (cites only verified ids) → memo · citizen cards · letter · DOCX

after the run:
  Council chat ─► round 1: each chosen member answers in character (position · confidence · reply)
               ─► round 2 (deliberation): members read each other's answers and respond
               ─► Chief Justice ruling: agreement · consensus · disputes · next step
                  all from the redacted result + verified ledger rows; any citation_id outside
                  that context is stripped, in every round
```

The orchestrator emits each step as an SSE event, so the UI progress and the agent activity log show what is actually happening rather than a timer.

### Models (`backend/ain/config.yaml`)

| Role | Provider | Used for |
|---|---|---|
| `fast` | Groq · Llama 3.1 8B | facts extraction, routing confirmation |
| `reasoner` | Groq · GPT-OSS 120B | risk analysis, adversarial counsel, drafting |
| `judge` | Groq · Qwen3 32B | single-judge entailment (a different family from the drafter) |
| `plain` | Groq · Llama 3.3 70B | the "plain chatbot" baseline: one prompt, no tools |
| `bench_a` / `bench_b` / `bench_c` | OpenRouter · Claude / Gemini / DeepSeek | Sunny / Regal / Grey |
| `chairman` | OpenRouter · GPT | Chief Justice |

### Corpus (`backend/corpus/processed/corpus.jsonl`, 1,154 sections)
- **Bangladesh**, scraped from [bdlaws.minlaw.gov.bd](http://bdlaws.minlaw.gov.bd) with deep links to each section:
  - Contract Act 1872; Stamp Act 1899; CPC 1908 (ss.13, 14, 44A); FER Act 1947
  - Labour Act 2006 (as amended 2026); BEPZ Labour Act 2019
  - Overseas Employment & Migrants Act 2013; Trafficking Act 2026 (and the repealed 2012 Act)
  - Personal Data Protection Act 2026
- **International**, as verbatim excerpts cut from official documents by `corpus/curate_intl.py`:
  - ILO C29, C95, C181
  - EU CSDDD Art.10 and GDPR Art.44 (Publications Office CELLAR)
  - Bangladesh Bank GFET 2018 Ch.8 para 13, Notification FE 1/77-BB, FE Circular 13/2020
- **Countries of work** (`ain/countries.yaml` lists each country's aliases, currency, wage figures and help contact):

  | Country | Law (source) | What is covered |
  |---|---|---|
  | Saudi Arabia | Labor Law, Royal Decree M/51 (English translation, WIPO Lex) | employer pays recruitment, iqama and return ticket (Art. 40), wages not withheld (61), end-of-service award (84), deductions ≤ half the wage (93) |
  | UAE | Federal Decree-Law 33/2021 (MOHRE English text via FAOLEX) | no recruitment fees (Art. 6), documents not withheld and repatriation paid (13), forced labour (14), deductions ≤ 50% (25), end-of-service benefit (51) |
  | Malaysia | Employment Act 1955 (AGC text), Minimum Wages Order 2024 | deductions (s.24), forced labour (s.90B), RM 1,700 minimum wage |
  | Qatar | Labour Law 14/2004 (embassy translation) | no fees from workers (Art. 33), gratuity (54), employer pays the return (57), deductions ≤ 50% (70) |
  | Oman | Labour Law, Royal Decree 53/2023 (Decree.om translation) | forced labour (Art. 5), passport only with written consent (6), return home (14), no fees (31), withholding ≤ ¼ (96) |
  | Kuwait | Law 6/2010 (embassy translation, archived) | employer pays the return (Art. 10), gratuity (51), deductions ≤ 25% (59) |
  | Singapore | EFMA 1990 s.22A, Employment Act s.32, Passports Act s.47(5) (Singapore Statutes Online) | no payment for a job, deductions ≤ 50%, keeping another person's passport is an offence |
  | Bahrain | Labour Law 36/2012, Labour Market Law 19/2006 (LLOC English versions) | no money for a permit or job (Art. 23), loan deductions ≤ 10% (44), attachment ≤ 25% (45), leaving indemnity (116) |

  Gulf laws are official or embassy English translations; the Arabic text prevails, and older translations are marked *amended*, so the currency gate shows a warning.
- **Fair-recruitment standards** (voluntary, not law): ILO General Principles and Operational Guidelines for Fair Recruitment (2019), Employer Pays Principle, RBA Code of Conduct 8.0 §A.1.
- **Companies' published policies** (`corpus/companies.yaml`, cut by `corpus/curate_companies.py`): IOI Corporation (recruitment guideline) and Top Glove (zero-cost recruitment and passport policies).

No statute text or section number is typed by hand. A test checks that every playbook quote appears verbatim in its source section.

Rebuild after changing a source (from `backend/`):

```bash
..\.venv\Scripts\python -m corpus.fetch_intl          # download international and country sources into corpus/raw/
..\.venv\Scripts\python -m corpus.curate_intl         # cut the verbatim excerpts (fails loudly on a missing marker)
..\.venv\Scripts\python -m corpus.curate_companies    # companies' published policies
..\.venv\Scripts\python -m corpus.build_corpus        # merge everything into corpus.jsonl
..\.venv\Scripts\python -m ain.retrieval              # rebuild the dense embeddings
```

### Adding or correcting a company

Add an entry to `backend/corpus/companies.yaml` and run `curate_companies` and `build_corpus`. The rules:
- quote **only the company's own published document**, downloaded from its own website (`policy_url`); never press reports, audits or allegations;
- findings always read "The employer's published policy says X; this contract says Y", and say nothing else about the company;
- `published` is the document's own date. A policy fetched more than a year ago gets a warning in the currency gate, asking for a re-check;
- if a company asks for a correction, update or remove its entry and record the reason in `notes`.

## Project layout

```
backend/
  ain/            FastAPI app (api.py), orchestrator, LLM layer, models, DOCX export
    agents/       ingestion · pii · router · risk_analyst · adversary · calculator · policy_check
                  verifier · bench · council · critic · drafter · ablation
    countries.yaml  destination countries (aliases, currency, wage figures, help contacts)
    playbook/     rules.yaml (the risk playbook)
  corpus/         bdlaws scraper, international + country + company excerpt curation, companies.yaml, processed corpus + embeddings
  demo/           hero documents, the sample contract photo, pre-warmed OCR cache
  eval/           gold set and evaluation runner
  scripts/        smoke_live.py (live model check + cache warm-up), make_photo_sample.py
  tests/          offline pytest suite
web/              Next.js app: citizen UI (/) and Counsel workspace (/counsel)
```

## Run it

Prerequisites: Python 3.13 (the project's `.venv`) and Node 22.

```bash
# backend (CPU-only torch keeps the install small)
.venv\Scripts\python -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env          # then add GROQ_API_KEY and OPENROUTER_API_KEY
cd backend
..\.venv\Scripts\python -m uvicorn ain.api:app --port 8000

# frontend (second terminal)
cd web
npm install
npm run dev                     # http://localhost:3000  ·  http://localhost:3000/counsel
```

### LLM modes (`AIN_LLM_MODE` in `.env`)
- `live` is the default when a key is present. It calls Groq (main pipeline) and OpenRouter (Bench), and caches every answer on disk. If only one provider has a key, roles fall back to the other provider.
- `replay` uses only the cache, with no network. Run `python -m scripts.smoke_live` once with keys and the demo then works offline. Council chat questions are new each time, so chat goes live whenever the bench roles have a key, and falls back to canned answers otherwise.
- `fake` gives deterministic offline answers. It is used by the tests and runs when no key is configured. Law retrieval and all four gates are real; only the language-model answers are canned. The UI labels this mode "offline demo".

Model IDs live in `backend/ain/config.yaml`. `scripts/smoke_live.py` checks each one against the providers' live `/models` lists.

### API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/health` | LLM mode, which provider keys are set, corpus size |
| `GET` | `/api/samples` | demo documents |
| `GET` | `/api/countries` | countries of work whose labour law is in the corpus |
| `POST` | `/api/analyze` | upload a document or pick a sample; optional `destination_country` (code) and `policy` (the employer's own policy file); returns a job id |
| `GET` | `/api/jobs/{id}` | job status |
| `GET` | `/api/jobs/{id}/events` | SSE stream of agent events |
| `POST` | `/api/jobs/{id}/confirm` | human salary check |
| `GET` | `/api/jobs/{id}/result` | full analysis: risks, ledger, memo, trace, privacy |
| `GET` | `/api/jobs/{id}/memo.docx` | memo export |
| `POST` | `/api/jobs/{id}/ablation` | run the plain-chatbot comparison |
| `GET` | `/api/council` | the three council members and their models |
| `POST` | `/api/jobs/{id}/council/chat` | ask one or more council members a question (`language`: `en` or `bn`) |
| `POST` | `/api/jobs/{id}/council/deliberate` | round 2: members answer each other, then the Chief Justice rules |
| `GET` | `/api/corpus/{citation_id}` | statute text of one section |
| `POST` | `/api/auth/signup` · `/api/auth/login` · `/api/auth/logout` | accounts; the session is an HttpOnly cookie |
| `GET` / `DELETE` | `/api/auth/me` | who is signed in (`guest`, `account` or none) · delete the account and all its analyses |
| `GET` | `/api/jobs` | the caller's saved analyses |
| `DELETE` | `/api/jobs/{id}` | delete one analysis |

Every `/api/jobs/{id}/…` route answers only the job's owner; anyone else gets `404`, the same as for a job that doesn't exist.

### Security and user data

- **Who owns what.** Citizen mode needs no signup. The first analysis on a device creates a private **guest** session, which owns that device's analyses; guests and their data are deleted after 7 days. Counsel mode (`/counsel`) needs an **account** (email + password). Signing up or signing in from a guest session moves the guest's analyses into the account.
- **Passwords** are hashed with argon2id. A wrong password and an unknown email get the same answer. After 5 failed sign-ins (per IP or per email) sign-in is locked for 15 minutes, and sign-ups are limited to 10 per IP per hour.
- **Sessions** are random tokens in an `HttpOnly`, `SameSite=Lax` cookie (`Secure` with `AIN_COOKIE_SECURE=1`). Only a SHA-256 of each token is stored, in `backend/.data/ain.db`. Account sessions last 30 days and renew while in use. A new token is issued at every sign-in.
- **CSRF**: state-changing requests from a browser origin outside `AIN_CORS` are rejected with `403`.
- **Encryption at rest**: results are stored as `backend/runs/{id}.json.enc`, encrypted with the Fernet key in `AIN_DATA_KEY`. Without that variable, a development key is created once in `backend/.data/secret.key`. Back the key up: without it, stored analyses can't be read. Results saved before accounts existed (plaintext `runs/*.json`) have no owner and are no longer served. `python -m scripts.purge_legacy_runs --delete` (from `backend/`) removes them.
- **Erasure**: users can delete one analysis, or their whole account with all its analyses, from the account menu in Counsel mode.
- Not built yet: email verification and password reset (there is no mail provider), OAuth and 2FA.

## Tests and evaluation

```bash
cd backend
..\.venv\Scripts\python -m pytest -q            # 94 offline tests
..\.venv\Scripts\python -m eval.run_eval        # recall / precision / citation validity / drop rate / ablation
..\.venv\Scripts\python -m scripts.smoke_live   # live keys: model check + hero docs + cache warm-up
cd ..\web && npm run lint && npm run build
```

The tests cover:
- corpus integrity: every anchor exists and every quote is verbatim;
- bilingual retrieval;
- PII redaction, plus a check that **no outbound payload contains PII**;
- the router, including that **EPZ documents never rely on the Labour Act**;
- countries of work: detection in English and Bangla, one pack per country, each wage figure is stated in its cited section, and every country has its own law in the playbook;
- the employer's own policy: contradictions are verified against the policy text, an invented promise fails the fidelity gate, the policy is redacted with the same placeholders as the contract, and a named company's published policy is used automatically;
- each verifier gate failing on its own bad case;
- the Critic's repeal healing;
- Bench majority/dissent, the three personas, and that judges see only the statute and the claim;
- council chat: replies stay grounded in the analysis, citations outside the verified ledger are stripped (also from the prose), and PII in a question is refused;
- council deliberation: each member sees only its colleagues' answers, the Chief Justice gets a neutral context and both rounds, rulings are sanitised, and Bangla answers are requested and returned;
- wage arithmetic;
- the drafter stripping unverified citations;
- end-to-end runs on both hero documents: ≥3 risks, 100% of memo citations verified, ≥1 claim dropped, ≥1 off-playbook risk;
- the full HTTP flow including SSE, the human salary check and the council endpoints.

## 3-minute demo script

1. **Citizen, 60 s.** On a phone, choose the *Malaysia job contract (photo)* sample.
   - The steps tick off as real agent events arrive. The salary card says the photo is blurry (OCR confidence 77%); confirm RM 1,200.
   - The result reads "৭টি বড় বিপদ" (seven serious dangers) and can be read aloud in Bangla. The take-home pay is RM 550 against the RM 1,700 minimum.
   - Open **বিস্তারিত** (Details) to show the real section numbers, each linking to bdlaws. Show the letter to the agency.
2. **Counsel, 90 s.** Tap *Full legal memo*.
   - **Report** lists the risks by severity; **Contract** shows which clauses carry them.
   - In **Verification**, filter the ledger to ✕ Dropped: the 2012 Trafficking Act citation fails the currency gate, and the Critic's re-anchored 2026 citation passes ✓.
   - Open the *Dhaka EPZ* sample. The Router shows the Labour Act struck through. Labour Act s.176 (trade unions) is ✕ dropped as inapplicable inside an EPZ, and the off-playbook multi-union risk is flagged *Valid abroad · void in BD*.
   - In **Council**, show each member's vote, any dissent and its ⚠ human-review flag. Ask the entire council "Should I sign this contract as it stands?", then press **Hold a deliberation**: the members answer each other and the Chief Justice's ruling appears. Switch the answer language to বাংলা to show the same in Bangla.
3. **Proof, 30 s.** Open **Verification → Compare with a plain chatbot**: the plain prompt's citations mostly fail (invented sections, repealed Acts, the wrong regime), while the memo's citations are 100% verified. Download the DOCX.

## Honest limitations
- The 2026 Labour Act amendments are read from bdlaws' consolidated text. The Bangla text is authoritative, and English propositions are checked against it by the judge models.
- Cross-lingual dense retrieval is weak on CPU-sized models, so the system relies on **bilingual queries** (Bangla BM25 MRR 0.75 against 0.19 for English-only dense search).
- The gold set covers only our own seeded demo documents. Treat the eval numbers as regression checks, not as a benchmark.
- EasyOCR on CPU takes about 1–5 minutes per page on first read. Results are cached by file hash, and demo photos are pre-cached.
- Country coverage is the 8 main destinations. For any other country only Bangladesh law and ILO standards are checked, and the UI says so. Qatar's 2020 minimum wage and Kuwait's minimum wage have no official English text in the corpus yet, so the calculator shows no minimum for them.
- The company database starts small (two companies). The format is designed for growth, but each entry needs a published document from the company itself.
- Council members can discuss only what the analysis already verified; they cannot research new law. Deliberation adds four model calls per question (three responses and the ruling).
