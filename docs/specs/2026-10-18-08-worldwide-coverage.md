# Plan: worldwide coverage — top-8 destination countries + employer/company policy

## Context
Bangladeshi migrant workers work in dozens of countries, but Ain's foreign-law coverage today is **2 Malaysian sections** (`MY-EA-1955-s24`, `MY-MWO-2024-p3`). The router only adds a foreign pack when `destination_country == "Malaysia"` (`ain/agents/router.py:49`), and the wage calculator only knows RM (`ain/agents/calculator.py:13-14`). A Saudi or Qatar contract gets checked against Bangladesh law + ILO only, so users can't rely on it.

The user wants: (1) host-country law for the countries where most Bangladeshis work, and (2) **company policy** in three forms: the employer's own uploaded policy, industry recruitment standards, and a database of named companies' published policies.

Constraints the project already relies on and that we keep:
- Every statute/policy text is **cut verbatim** from a downloaded official document between two literal markers (`corpus/curate_intl.py` `cut()`); never typed by hand. Section numbers are taken from the downloaded text, not from memory.
- Agents may cite only `citation_id`s that exist in the corpus; the 4-gate verifier runs on every claim.
- `pytest` (offline, fake LLM) must stay green; `tests/test_corpus.py` enforces that every playbook quote is verbatim.

---

## Phase 1 — Country packs for the top 8 destinations

**Countries:** Saudi Arabia, UAE, Malaysia (expanded), Qatar, Oman, Kuwait, Singapore, Bahrain.

### 1a. Country registry (new) — `backend/ain/countries.yaml`
One data file replaces the hard-coded Malaysia logic everywhere:
```yaml
- code: SA
  name: Saudi Arabia
  aliases: {en: ["saudi arabia","ksa","riyadh","jeddah","dammam"], bn: ["সৌদি"]}
  currencies: [SAR]
  pack: sa_labour
  label: {en: "Saudi Labor Law (Royal Decree M/51) …", bn: "সৌদি শ্রম আইন …"}
  min_wage: null                       # or {amount, currency, citation_id}
  deduction_cap: {pct: 50, citation_id: SA-LABOR-2005-a?}   # filled from the downloaded text
  help: {en: "Bangladesh Embassy Labour Wing, Riyadh", bn: "…"}   # where to go for help
```
- Loaded by a small `ain/countries.py` (`load_countries()`, `by_alias()`, `by_currency()`), `lru_cache`d like `risk_analyst.load_rules`.
- **`ain/agents/ingestion.py`**: build `COUNTRIES` / `CURRENCY` / `MONEY` regex from the registry (adds SAR, AED, QAR, OMR, KWD, BHD, SGD/S$, plus Bangla country names).
- **`ain/agents/router.py`**: replace the `if facts.destination_country == "Malaysia"` branch with a registry lookup; `PACK_LABELS` gets the country packs from the registry. Rename `my_employment` → keep the id (tests and runs refer to it) and add the new ids `sa_labour, ae_labour, qa_labour, om_labour, kw_labour, sg_labour, bh_labour`.
- **`ain/agents/calculator.py`**: `MINIMUM_WAGES` / `DEDUCTION_CAPS` built from the registry instead of literals. Only countries whose gazette text in the corpus states a figure get a minimum wage (e.g. Malaysia RM1,700; Qatar and Kuwait if the downloaded text confirms it). For the others the UI says "no statutory minimum wage for this job in our corpus", not "there is no minimum wage".
- **`ain/naming.py`**: add EN/BN short names for each new `act_key`; `_unit()` returns "Art./অনুচ্ছেদ" for Gulf laws (articles, not sections).

### 1b. Corpus — extend `corpus/fetch_intl.py` + `corpus/curate_intl.py`
Same method as today: add the source URL to `SOURCES`, add one `SPECS` entry per excerpt. Prefer the government's own English text (note "official English translation; the Arabic text prevails" in `amendment_notes`).

| Country | Candidate official sources (confirm availability at implementation) |
|---|---|
| Saudi Arabia | Labor Law (Royal Decree M/51, as amended 2025) — HRSD English text; Domestic Workers Regulation |
| UAE | Federal Decree-Law 33/2021 on Labour Relations + Cabinet Resolution 1/2022 — MOHRE / UAE legislation portal; Decree-Law 9/2022 (domestic workers) |
| Qatar | Law 14/2004 (Labour Law), Law 21/2015 (entry/exit/residence — passports), Law 17/2020 (minimum wage) — Al Meezan |
| Oman | Labour Law, Royal Decree 53/2023 — Ministry of Labour / Qanoon |
| Kuwait | Private Sector Labour Law 6/2010; Domestic Workers Law 68/2015 — PAM |
| Singapore | Employment Act 1968, Employment of Foreign Manpower Act 1990 + EFM (Work Passes) Regulations — Singapore Statutes Online |
| Bahrain | Labour Law 36/2012 — LMRA / legislation portal |
| Malaysia (add) | Passports Act 1966 (passport retention), Employment Act Part XIIB (foreign employees), Act 446 (worker housing) |

**Target topics per country (≈4–6 excerpts each, ~45 total):** recruitment costs borne by the employer · passport/document retention · wage payment & deduction limits · minimum wage (where it exists) · end-of-service benefit / return airfare · domestic-worker regime (if separate).
If a topic has no clear text in a country's law, we skip it and leave it out of that country's anchors. We do not substitute another law.

After curating: rebuild `corpus.jsonl` (bd_sections + intl_sections), then `python -m ain.retrieval` to rebuild embeddings (the corpus-hash check in `Corpus.__init__` otherwise disables dense search).

### 1c. Playbook — make migrant rules country-aware
- **`ain/agents/risk_analyst.py` `Rule.anchors_for()`**: today `anchors_by_pack` only handles `bd_epz`/`bd_labour` and *replaces* the defaults. Add a separate `country_anchors: {pack: [...]}` field. The result is the base `anchors` (BD + ILO) **plus** the anchors for the active country pack. The EPZ/Labour precedence stays unchanged.
- **`ain/playbook/rules.yaml`**:
  - `PB-PASSPORT`, `PB-RECRUIT-FEE`, `PB-DEDUCTION-CAP`, `PB-MIN-WAGE`: add `country_anchors` for each country; widen `packs:` to all country packs where relevant. Remove the hard-coded Malaysia anchor from base `anchors` (it moves under `my_employment`).
  - `PB-MIN-WAGE` titles and `citizen_line` become country-neutral, e.g. "below the legal minimum wage in {country}". `{country}` and `{amount}` are filled from the registry in `risk_analyst`, and the Bangla text uses the registry's Bangla name.
  - New rules: `PB-RETURN-TICKET` (no employer-paid return airfare at contract end) and `PB-END-OF-SERVICE` (gratuity waived or omitted). Each one is anchored only to country texts that actually contain the rule.
- **`ain/agents/adversary.py`** already receives `country=`; also pass the active country pack so its agentic RAG searches that country's sections.

### 1d. UI — country awareness
- Citizen (`web/src/components/citizen/`) and Counsel report show a **country chip**, e.g. "🇸🇦 সৌদি আরব · checked: Saudi Labor Law, BD OEMA 2013, ILO". The chip also has a **picker** for when detection fails; the chosen value is posted as a `destination_country` form field to `/api/analyze`, which overrides detection.
- Unsupported country → an honest banner: "We don't have {country} law yet; only Bangladesh law and ILO standards were checked."
- Show the registry's **help contact** (labour wing / embassy) in the citizen action list.
- `GET /api/countries` (new, in `ain/api.py`) feeds the picker.

---

## Phase 2 — Industry codes & recruitment standards (`std_recruitment` pack)
Verbatim excerpts, using the same `curate_intl` method, from: ILO General Principles & Operational Guidelines for Fair Recruitment (2019), ILO C189 Domestic Workers, the Employer Pays Principle (Leadership Group for Responsible Recruitment), the Dhaka Principles, and the RBA Code of Conduct (current version).
- `Section` gets `kind: "law" | "standard" | "company_policy"` (default `"law"`; models.py + all builders). G4 ("in force") reads as "current version" for standards.
- The router adds `std_recruitment` whenever `bd_migration` is active.
- Standards **never raise severity on their own**. In the playbook they appear as extra anchors. The risk card shows them under "Also breaks: Employer Pays Principle" with a "voluntary standard, not law" badge (`web/src/components/counsel/` risk card + citizen card).

---

## Phase 3 — Upload the employer's own policy (second document)
- **API**: `/api/analyze` accepts an optional `policy: UploadFile` (same `ALLOWED`/`MAX_BYTES` checks), plus a "＋ Add employer's policy / handbook (optional)" slot in both upload forms (`web/src/lib/api.ts`, citizen + counsel upload components).
- **Pipeline (`ain/orchestrator.py`)**: ingest → OCR → **PII Shield** → clause-split the policy using the existing `ingestion.build_document` and `pii` functions. Its clauses become **job-local sections** `POLICY-c<n>` (`kind="company_policy"`) in a per-job **corpus overlay**: a thin `Corpus` subclass or wrapper that adds sections to `by_id` and BM25. This lets G1–G3 verify claims about the policy exactly like statutes, and G2 quote fidelity proves the quote is really in the uploaded policy.
- **New agent `ain/agents/policy_check.py`** (role `reasoner`):
  1. Runs the playbook over the policy too (a bad policy is itself a risk).
  2. Contradiction finder: pairs contract clauses with policy commitments ("Policy says the employer pays all recruitment fees; clause 7 deducts RM 200/month"). Output category `policy_contradiction`, with citations to both the contract clause and `POLICY-c<n>`.
- Report: a new "Contract vs employer's own policy" section in the memo (`ain/agents/drafter.py`) and on risk cards. Citizen line: "কোম্পানির নিজের নীতিতেই বলা আছে…".
- The policy file is encrypted at rest via `ain/vault.py`, like runs, and deleted with the job (`_delete_job_files`).

---

## Phase 4 — Database of named companies' published policies
- **Data**: `backend/corpus/companies.yaml`. Each company has: `slug`, legal name + aliases (e.g. "… Sdn Bhd", "… W.L.L.", "… LLC", "… Pte Ltd"), country, sector, `policy_url` (the company's **own** site only), `retrieved_at`, and `specs` (start/end markers). A new `corpus/curate_companies.py` reuses `cut()` to write `processed/company_sections.jsonl` (`kind="company_policy"`, `packs: ["co_<slug>"]`, citation ids `CO-<SLUG>-<n>`).
- **Seed**: 5–10 large employers of Bangladeshi workers in the top-8 countries that publish a recruitment/forced-labour policy. Each one is verified at implementation time to have an official public document; no company is added from memory.
- **Matching**: `ingestion.extract_facts` gets `employer_name` (from company-suffix patterns; company names are not PII and are not redacted). An alias match adds the `co_<slug>` pack, and the Phase 3 contradiction check then runs against that company's published policy, with no upload needed.
- **Guardrails (legal safety)**:
  - We quote only the company's own words, labelled "as published on {date}", and never third-party allegations.
  - The wording is fixed: "The employer's published policy says X; this contract says Y."
  - Records older than 12 months show a "may be outdated, re-check" badge.
  - Each record has a `notes`/correction field. The README gets a "how to add or correct a company" section.

---

## Demo docs & eval
- New demo docs in `backend/demo/docs/` (with fictional employer names): `migrant_sa_contract.txt` (Saudi: passport kept, fees deducted, no return ticket), `migrant_qa_contract.txt` (wage below the QAR minimum), and `employer_policy_sample.txt` (a fictional company that promises "employer pays", contradicted by the Saudi contract).
- Add them to `SAMPLES` in `ain/api.py` and add their expected findings to `eval/gold.yaml`.

## Critical files
`backend/ain/countries.yaml` (new) · `ain/countries.py` (new) · `ain/agents/router.py` · `ain/agents/ingestion.py` · `ain/agents/calculator.py` · `ain/agents/risk_analyst.py` · `ain/playbook/rules.yaml` · `ain/naming.py` · `ain/models.py` · `ain/retrieval.py` (overlay) · `ain/orchestrator.py` · `ain/agents/policy_check.py` (new) · `ain/agents/drafter.py` · `ain/api.py` · `corpus/fetch_intl.py` · `corpus/curate_intl.py` · `corpus/curate_companies.py` (new) · `web/src/lib/api.ts` · citizen + counsel upload/risk-card components · `README.md`.

## Verification
1. `python -m corpus.fetch_intl && python -m corpus.curate_intl && python -m corpus.curate_companies`: the build fails loudly on any missing marker.
2. Rebuild `corpus.jsonl` and embeddings, then run `pytest` (offline). New and extended tests:
   - `test_corpus.py`: every registry country has passport, fee and deduction anchors; every quote is verbatim; every `kind="company_policy"` record has an http `policy_url` and a `retrieved_at` date.
   - Router: each country alias (EN and BN) selects the right pack; an unknown country adds only BD + ILO.
   - Calculator: QAR/KWD floors read from the registry; a country with no figure does not produce a below-minimum flag.
   - Policy overlay: a fabricated `POLICY-c99` quote fails G2; a real contradiction passes.
   - Company match: an alias in the contract adds `co_<slug>`.
3. `python -m eval.run_eval`: the new gold entries are found and Malaysia/EPZ results don't regress.
4. `python -m scripts.smoke_live` with keys, then a manual run in the browser: Saudi sample (citizen, Bangla) shows the country chip, the Saudi-law citations and the help contact; Counsel with the policy upload shows a contract-vs-policy contradiction and the Council can cite it.

## Order of work
Phase 1 (biggest user value) → 2 → 3 → 4. Each phase ends green on `pytest` and can be committed separately.
