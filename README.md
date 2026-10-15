# আইন কপাইলট · Ain Copilot

**A multi-agent legal copilot for Bangladesh.** It reads a raw contract (PDF, DOCX, text, or a phone photo in Bangla or English) and finds non-obvious compliance risks. It then writes a memorandum in which **every legal claim has been verified against official statute text**. One engine serves two views:

- **Citizen mode** (`/`) is for a migrant worker on a phone. It works in Bangla, can read every answer aloud, and asks the worker to confirm a blurry salary figure. It shows the real take-home pay and drafts a letter to the recruiting agency.
- **Counsel mode** (`/counsel`) is for a lawyer, NGO caseworker or factory compliance team. It shows a clause-level risk heatmap and an IRAC memo. Alongside are the Verification Ledger, the Virtual Bench ruling, a live agent trace, a comparison against a plain LLM, a privacy receipt, and a DOCX export.

> Decision support, not legal advice.

---

## Why it is different

| | |
|---|---|
| **Citations can't be made up** | The agents may cite only `citation_id`s returned by retrieval over our own corpus. A citation produced any other way is rejected before verification. |
| **4-gate verifier** | Every claim passes four gates. **G1** checks that the section exists *and applies* to this document. **G2** checks quote fidelity. **G3** checks entailment, judged by a different model family that sees only the section text. **G4** checks that the law is still in force. Dropped claims stay visible in the ledger. |
| **Virtual Bench** | High and critical claims go to 3 judges from different model families (Claude, Gemini, DeepSeek via OpenRouter). They review each other anonymously, and a Chief Justice (GPT) writes a majority opinion and records any dissent. A dissent raises a ⚠ human-review flag. |
| **Real-world currency** | The corpus is the consolidated text as of Oct 2026. The 2012 Trafficking Act is **repealed**; the Critic re-anchors a stale citation to the 2026 Act and re-verifies it. Labour Act s.46 maternity leave now reads **60 + 60 days**, from the 2026 amendment. |
| **Regime switch** | For a factory inside an EPZ, the Router turns **off** the Labour Act 2006 and applies the BEPZ Labour Act 2019 (s.3 gives it overriding effect). A Labour Act citation in an EPZ document fails G1. |
| **Valid abroad, void in BD** | A clash badge marks clauses that are normal under English or EU law but void in Bangladesh: non-competes (Contract Act s.27), shortened limitation periods (s.28), 150-day payment terms (Bangladesh Bank's four-month repatriation rule). |
| **Off-playbook risks** | Adversarial Counsel runs agentic RAG with bilingual queries, so it finds risks the YAML playbook doesn't cover. Examples: silence on return airfare combined with termination at will; an exit penalty combined with withheld wages (debt bondage); a buyer's multi-union clause that can't be performed inside an EPZ. |
| **Wage Truth Calculator** | Uses arithmetic only, no LLM. Example: RM 1,200 − RM 650 in deductions = **RM 550 take-home**, against the RM 1,700 legal minimum and the 50% deduction cap. |
| **Privacy** | OCR runs locally (EasyOCR on CPU), so the photo never leaves the machine. A PII Shield redacts names, passport, NID, phone, address and DOB before any model call. A guard in the LLM layer blocks any payload that still contains an identifier. OpenRouter calls request `data_collection: deny`. |

## Architecture

```
upload ─► Ingestion (PyMuPDF · python-docx · EasyOCR bn+en, cached) → clauses + facts
       ─► PII Shield → placeholders; only redacted text ever leaves the machine
       ─► Jurisdiction Router → law packs (EPZ ⇒ BEPZ Labour Act replaces Labour Act)
       ─► Risk Analyst (YAML playbook) ║ Adversarial Counsel (agentic RAG) ║ Wage Calculator (waits for the human salary check)
       ─► Citation Verifier: G1 existence/applicability · G2 fidelity · G3 entailment · G4 currency
            └─ high/critical → Virtual Bench (3 judges + Chief Justice, OpenRouter)
       ─► Critic (re-anchors repealed law, withdraws unsupported risks)
       ─► Memo Drafter (cites only verified ids) → memo · citizen cards · letter · DOCX
```

The orchestrator emits each step as an SSE event, so the UI progress and the Agent Trace show what is actually happening rather than a timer.

### Corpus (`backend/corpus/processed/corpus.jsonl`, 1,113 sections)
- **Bangladesh**, scraped from [bdlaws.minlaw.gov.bd](http://bdlaws.minlaw.gov.bd) with deep links to each section:
  - Contract Act 1872; Stamp Act 1899; CPC 1908 (ss.13, 14, 44A); FER Act 1947
  - Labour Act 2006 (as amended 2026); BEPZ Labour Act 2019
  - Overseas Employment & Migrants Act 2013; Trafficking Act 2026 (and the repealed 2012 Act)
  - Personal Data Protection Act 2026
- **International**, as verbatim excerpts cut from official documents by `corpus/curate_intl.py`:
  - ILO C29, C95, C181
  - Malaysia Employment Act 1955 s.24 (AGC text) and Minimum Wages Order 2024 (P.U.(A) 376)
  - EU CSDDD Art.10 and GDPR Art.44 (Publications Office CELLAR)
  - Bangladesh Bank GFET 2018 Ch.8 para 13, Notification FE 1/77-BB, FE Circular 13/2020

No statute text or section number is typed by hand. A test checks that every playbook quote appears verbatim in its source section.

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
- `replay` uses only the cache, with no network. Run `python -m scripts.smoke_live` once with keys and the demo then works offline.
- `fake` gives deterministic offline answers. It is used by the tests and runs when no key is configured. Law retrieval and all four gates are real; only the language-model answers are canned. The UI labels this mode "offline demo".

Model IDs live in `backend/ain/config.yaml`. `scripts/smoke_live.py` checks each one against the providers' live `/models` lists.

## Tests and evaluation

```bash
cd backend
..\.venv\Scripts\python -m pytest -q            # 45 offline tests
..\.venv\Scripts\python -m eval.run_eval        # recall / precision / citation validity / drop rate / ablation
..\.venv\Scripts\python -m scripts.smoke_live   # live keys: model check + hero docs + cache warm-up
cd ..\web && npm run lint && npm run build
```

The tests cover:
- corpus integrity: every anchor exists and every quote is verbatim;
- bilingual retrieval;
- PII redaction, plus a check that **no outbound payload contains PII**;
- the router, including that **EPZ documents never rely on the Labour Act**;
- each verifier gate failing on its own bad case;
- the Critic's repeal healing;
- Bench majority/dissent, and that judges see only the statute and the claim;
- wage arithmetic;
- the drafter stripping unverified citations;
- end-to-end runs on both hero documents: ≥3 risks, 100% of memo citations verified, ≥1 claim dropped, ≥1 off-playbook risk;
- the full HTTP flow including SSE and the human salary check.

## 3-minute demo script

1. **Citizen, 60 s.** On a phone, choose the *Malaysia job contract (photo)* sample.
   - The steps tick off as real agent events arrive. The salary card says the photo is blurry (OCR confidence 77%); confirm RM 1,200.
   - The result reads "৭টি বড় বিপদ" (seven serious dangers) and can be read aloud in Bangla. The take-home pay is RM 550 against the RM 1,700 minimum.
   - Open **বিস্তারিত** (Details) to show the real section numbers, each linking to bdlaws. Show the letter to the agency.
2. **Counsel, 90 s.** Tap *Full legal memo*.
   - The heatmap shows which clauses carry risk.
   - The **Ledger** filtered to ✕ Dropped shows the 2012 Trafficking Act citation failing the currency gate, and the Critic's re-anchored 2026 citation passing ✓.
   - Open the *Dhaka EPZ* sample. The Router shows the Labour Act struck through. Labour Act s.176 (trade unions) is ✕ dropped as inapplicable inside an EPZ, and the off-playbook multi-union risk is flagged *Valid abroad · void in BD*.
   - Show the **Virtual Bench** dissent and its ⚠ human-review flag.
3. **Proof, 30 s.** Open **vs Plain LLM**: the plain prompt's citations mostly fail (invented sections, repealed Acts, the wrong regime), while the memo's citations are 100% verified. Download the DOCX.

## Honest limitations
- The 2026 Labour Act amendments are read from bdlaws' consolidated text. The Bangla text is authoritative, and English propositions are checked against it by the judge models.
- Cross-lingual dense retrieval is weak on CPU-sized models, so the system relies on **bilingual queries** (Bangla BM25 MRR 0.75 against 0.19 for English-only dense search).
- The gold set covers only our own seeded demo documents. Treat the eval numbers as regression checks, not as a benchmark.
- EasyOCR on CPU takes about 1–5 minutes per page on first read. Results are cached by file hash, and demo photos are pre-cached.
#   L e g a l - A i d  
 