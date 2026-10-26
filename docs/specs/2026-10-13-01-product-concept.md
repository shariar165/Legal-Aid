# Ain Copilot (আইন কপাইলট): a Bangladesh-first multi-agent legal risk engine

## Context
- **What the challenge asks for:** a working multi-agent prototype. It must take in a raw legal document, find **at least 3 non-obvious compliance risks**, and produce a **verified memo that cites real statutes**.
- **Your choices:**
  - Domain: Bangladesh.
  - LLM: **Groq**.
  - Timeline: **2+ weeks**.
  - Focus: a general BD contract-risk engine. The hero demo is RMG (garments), where BD law meets EU/German supply-chain law.
- **Workspace:** `D:\Ai congress laywer` is empty apart from a fresh Python 3.13 `.venv`, so this is a greenfield Python build.

---

## 1. Analysis of the challenge

### What the judges will actually test
1. **Ingest a raw document.** Expect messy input: a PDF, a scan, or a Bangla deed photo. A clean `.txt` will look weak.
2. **Find non-obvious risks.** Spotting an uncapped liability clause is obvious. Non-obvious risks come from three places:
   - (a) a clause that is valid in the template's home jurisdiction but **void or unenforceable under local mandatory law**;
   - (b) **two clauses that are each fine alone but risky together**;
   - (c) **something important that is missing** (an absence risk).
3. **Produce a verified memo.** Every citation must resolve to real statute text. The system must show *how* it verified each one. This is where most teams will fail, because LLMs hallucinate section numbers.
4. **Be genuinely multi-agent.** Agents need distinct roles and a visible orchestration trace, not one prompt split into several.

### Why Bangladesh is a strong (and hard) domain
| Difficulty | What it means for us |
|---|---|
| No free legal API like CourtListener exists for BD | We build our own corpus. Our moat is a structured, section-level BD statute index, which nobody else in the competition will have. |
| `bdlaws.minlaw.gov.bd` has every Act in **English and Bangla**, with stable URLs per section (e.g. `/act-26/section-160.html` for the Contract Act 1872; internal IDs ≠ section numbers) | Each citation can deep-link to the **official government source**, which gives auditable verification. |
| Colonial-era Acts (1872–1908) were heavily amended by Bangladesh (e.g. Registration Act s.17A in 2004) | Indian or UK case law is a trap: the same section number can mean different things in each country. A "jurisdiction-drift" check is a differentiator. |
| Post-2024 regime changes by ordinance: Personal Data Protection Ordinance 2025 (approved 9 Oct 2025; some sections apply 18 months after gazette), National Data Governance Ordinance 2025, Cyber Security Ordinance 2025 | A **legal-currency agent** checks whether the cited law is still in force. That shows real-world awareness. |
| Bilingual documents: deeds and notices in Bangla, commercial contracts in English | The bilingual pipeline is itself an innovation. |
| Foreign buyer templates (EU/UK/US) are used everywhere in RMG and IT outsourcing | This is the richest source of "valid at home, void in BD" risks. |

### Impact story (for the pitch)
- RMG brings in roughly 80% of export earnings and employs about 4M workers.
- LDC graduation is scheduled for Nov 2026, though a deferral request is reported. After it, the EU gives a 3-year EBA transition to 2029, and GSP+ then requires labour and human-rights compliance.
- EU CSDDD and German LkSG push due-diligence duties down onto BD suppliers through buyer contracts.
- Most BD SMEs and factories cannot afford counsel that reads 60-page buyer codes against both BD law and EU law. Ain Copilot does exactly that.
- Secondary story: citizens can photograph a Bangla deed or legal notice and get the risks and **deadlines** in plain Bangla (access to justice, given the court backlog).

---

## 2. Non-obvious risk playbook (seed knowledge for the Risk agents)
Each entry is stored as a structured rule: trigger pattern, statute anchor, why it is non-obvious, and a mitigation clause. The verifier confirms every anchor against the corpus at runtime. Exact section numbers below must be re-checked when the corpus is built.

| # | Trigger in the document | BD anchor | Why it is non-obvious |
|---|---|---|---|
| 1 | Post-termination non-compete or non-solicit | Contract Act 1872 **s.27** (restraint of trade void; only exception is sale of goodwill) | Standard in UK/US templates, but void in BD. The client has a false sense of protection. |
| 2 | "Claims must be brought within 6 months" | Contract Act **s.28** | Shortening a limitation period is void, except for arbitration clauses. |
| 3 | Liquidated damages or penalty | Contract Act **s.74** | Only "reasonable compensation" is recoverable, so a pre-agreed sum is not automatic. |
| 4 | Instrument executed unstamped or understamped | Stamp Act 1899 **s.35** | The document is **inadmissible in evidence** until duty and penalty are paid. This is never visible from the text alone, so it is an absence risk. |
| 5 | Lease over 1 year, or a sale agreement (bainanama) | Registration Act 1908 **s.17 / s.17A / s.49**; TPA s.53A | If unregistered, it is not admissible and specific performance or part-performance protection is lost. |
| 6 | Deferred payment over 120 days in an export/buyer contract | FERA 1947 + Bangladesh Bank GFET export-proceeds repatriation rule | A commercial term silently breaches **FX regulation**. This is a strong cross-domain risk. |
| 7 | "Manager" or "executive" titles with routine duties | Labour Act 2006 s.2(65) "worker" definition | Misclassification means overtime, gratuity and termination benefits under the Labour Act still apply. |
| 8 | Termination with 30 days' notice | Labour Act **s.26** (120 days notice for monthly-rated permanent workers, plus compensation) | Foreign templates under-provide notice. |
| 9 | 12-week maternity leave | Labour Act **s.46** (8 + 8 weeks) | Undercuts the statutory minimum. |
| 10 | Factory inside an EPZ | **BEPZ Labour Act 2019** applies instead of the Labour Act 2006 | Picking the wrong regime makes the whole analysis wrong. The jurisdiction router must catch this. |
| 11 | Wage below the RMG minimum-wage gazette | Minimum Wage Board notification | Must be checked against the current gazette (currency agent). |
| 12 | Royalty or technical-fee payments abroad | FERA + BIDA/BB remittance conditions; Income Tax Act 2023 withholding on non-resident payments; VAT & SD Act 2012 reverse-charge VAT | No gross-up clause means a cost shock. |
| 13 | Foreign governing law plus foreign-court jurisdiction | CPC 1908 **s.44A** (reciprocating territories only) | A foreign judgment may need a fresh suit in BD. |
| 14 | Foreign-seated arbitration | Arbitration Act 2001 (limited application to foreign seats; enforcement under s.45–47, NY Convention) | Check that interim relief and enforcement routes actually exist. |
| 15 | Personal or worker data shared with an EU buyer | PDP Ordinance 2025 (cross-border transfer and consent) **vs** GDPR | Two-way conflict, and the phased commencement makes currency critical. |
| 16 | Buyer code makes the supplier bear the cost of all due diligence | EU CSDDD (Dir. 2024/1760, as modified by Omnibus simplification) / German LkSG | Cost shifting plus unilateral termination rights. The global-framework agent flags it. |

The **Adversarial Counsel agent** also looks for risks outside the playbook, such as clause interactions, missing clauses and defined-term traps. It may only *propose* new risks; an anchor must still pass verification.

---

## 3. Architecture (multi-agent, agentic RAG)

```
Upload (PDF / DOCX / photo / Bangla scan)
   │
[1] Ingestion agent ── OCR (Surya / Tesseract-ben) → layout → clause segmentation
   │                    → doc-type classification, parties, dates, governing law, EPZ?, language
[2] PII Shield ── redacts names/NID/phone/bank → placeholder map (re-hydrated only in final memo)
   │
[3] Jurisdiction Router ── decides which law packs apply: BD core | Labour/EPZ | FX/Tax | EU/DE | ICC/UNCITRAL
   │
   ├──► [4a] BD Statute Researcher   (recursive RAG: section → cross-refs → definitions → amendments)
   ├──► [4b] Global Framework agent  (EUR-Lex CSDDD/GDPR, German LkSG, ILO, ICC, NY Convention)
   ├──► [4c] Case-law agent          (BD Supreme Court judgments; persuasive only, clearly labelled)
   │
[5] Risk Analyst ── runs playbook rules per clause (parallel, async)
[6] Adversarial Counsel ── cross-clause + absence + "valid abroad / void in BD" hunting
   │
[7] Citation Verifier  ◄── THE CORE DIFFERENTIATOR (see §4)
[8] Legal-Currency agent ── is the law in force? amended? repealed? ordinance gazetted?
   │
[9] Memo Drafter ── IRAC memo (EN + বাংলা summary), severity ranking, mitigation clauses
[10] Critic / QA ── rejects any claim lacking a VERIFIED citation; loops back to 4/5 (max 2 rounds)
   │
Memo (PDF/DOCX) + Verification Ledger + agent trace graph
```

**Orchestration:** use LangGraph. It provides a stateful graph, parallel branches, critic loops and a visible trace, and the graph is easy to show judges. Each agent is a node with typed Pydantic state.

---

## 4. "Hallucination-free" citation verification (the core differentiator)
A claim enters the memo only if it passes **all four gates**:
1. **Existence:** Act + section resolves to a record in the local corpus, with a URL to bdlaws.minlaw.gov.bd, EUR-Lex, etc.
2. **Quote fidelity:** any quoted statutory text fuzzy-matches the corpus (rapidfuzz ratio ≥ 90). Paraphrases are marked as paraphrases.
3. **Entailment:** an LLM judge (a different Groq model from the drafter) is given *only* the retrieved section text and asked whether it supports the proposition. The answer must be "supports"; "neutral" or "contradicts" fails. Use 3-sample self-consistency, which Groq's speed makes cheap.
4. **Currency:** the section is not marked repealed or substituted, and the amendment notes are checked.

Results:
- Outcome: ✅ Verified / ⚠️ Partially verified (shown with a caveat) / ❌ Dropped (logged in the appendix, never shown as advice).
- The memo carries a **Verification Ledger** table with: claim, citation, source link, the 4 gate results, and the retrieved text snippet.
- The structure prevents invented section numbers: the drafter can only cite `citation_id`s returned by retrieval tools, never free text.

---

## 5. Data and corpus plan
| Source | Use | Method |
|---|---|---|
| bdlaws.minlaw.gov.bd | ~40 core Acts in EN + BN, section-level | Polite scraper (rate-limited, cached). Store JSON with `{act_id, title_en/bn, year, section_no, heading, text_en, text_bn, url, amended_by, status}` |
| Bangladesh Bank (bb.org.bd) | GFET chapters and selected FE circulars | Download PDFs and extract text |
| Bangladesh Gazette / Minimum Wage Board | RMG wage gazette | Manual curation |
| EUR-Lex | CSDDD 2024/1760, GDPR 2016/679 | CELLAR/HTML download, article-level chunks |
| gesetze-im-internet.de + Open Legal Data API | German LkSG text plus related rulings | API / HTML |
| ILO NORMLEX | Core conventions (C87, C98, C155, C190…) | HTML |
| supremecourt.gov.bd | Selected judgments | PDF; demo subset only |
| CourtListener / CAP | Optional persuasive common-law support | REST API; always labelled "foreign, persuasive" |

Core Acts to index first:
- Contract Act 1872; Specific Relief Act 1877; TPA 1882; Stamp Act 1899; Registration Act 1908; CPC 1908; Limitation Act 1908
- FERA 1947; Companies Act 1994; Arbitration Act 2001; Labour Act 2006 (+ Rules 2015); VAT & SD Act 2012; BEPZ Labour Act 2019; Income Tax Act 2023
- PDP Ordinance 2025; Cyber Security Ordinance 2025

The pre-built corpus is committed to the repo, so the demo works offline.

---

## 6. Tech stack (tuned for Groq)
- **LLM via Groq** behind a single `llm.py` abstraction, with model names in config. Verify current IDs at console.groq.com/docs/models when building. Likely roles:
  - a large reasoning model (e.g. `openai/gpt-oss-120b` or `llama-3.3-70b-versatile`) for risk analysis and drafting;
  - a *different* model family (e.g. `qwen/qwen3-32b`) as the entailment judge, so the judge is independent of the drafter;
  - a small fast model for classification and routing;
  - Groq **Whisper** for optional Bangla voice questions.
- **Groq constraints:** context is around 128k, not 1M, and free-tier TPM/RPM limits are tight. So use **recursive retrieval instead of long-context stuffing**: per-clause processing, a token budgeter, exponential backoff, a disk cache of LLM calls (`diskcache`), and an optional dev/paid key for the demo.
- **Embeddings (local, since Groq has no embedding API):** `BAAI/bge-m3`, which is multilingual and handles Bangla, plus the `bge-reranker-v2-m3` reranker. Hybrid search with **BM25** (`rank_bm25`), because exact legal terms and section numbers matter.
- **Vector store:** Qdrant (local mode) or LanceDB.
- **OCR:** Surya OCR (supports Bengali) as primary, Tesseract `ben+eng` as fallback; PyMuPDF / pdfplumber for digital PDFs; python-docx for input.
- **Backend:** FastAPI with an SSE stream of agent progress. **Frontend:** Next.js + shadcn with clause highlighting, a risk heatmap, a live agent-graph trace and a ledger view. A Streamlit fallback UI can be built in week 1.
- **Memo export:** DOCX (python-docx) + PDF.
- **PII shielding:** regex + spaCy/GLiNER multilingual NER. Only placeholder text reaches Groq, which answers the "sensitive employment contract" privacy prompt.

---

## 7. Repo layout (proposed)
```
ain-copilot/
  corpus/            scrapers/, raw/, processed/*.jsonl, build_index.py
  app/
    agents/          ingestion.py, pii.py, router.py, statute_rag.py, global_rag.py,
                     caselaw.py, risk_analyst.py, adversary.py, verifier.py,
                     currency.py, drafter.py, critic.py
    playbook/        rules/*.yaml   (the 16 seed rules + mitigation clauses)
    graph.py         LangGraph wiring
    llm.py           Groq client, model routing, cache, rate-limit backoff
    retrieval.py     hybrid BM25 + bge-m3 + reranker
    models.py        Pydantic state: Clause, Risk, Citation, VerificationResult, Memo
    api.py           FastAPI + SSE
    export.py        DOCX/PDF memo
  web/               Next.js UI
  eval/              seeded_contracts/, gold_risks.yaml, run_eval.py
  demo/              hero documents
```

---

## 8. Build phases (about 2.5 weeks)
1. **Days 1–3: corpus.** Build the bdlaws scraper (EN + BN) for the core Acts, plus EUR-Lex/LkSG/ILO ingestion. Add hybrid retrieval and its index. Run a retrieval sanity test: looking up "restraint of trade" should return Contract Act s.27.
2. **Days 4–6: ingestion and PII.** Add OCR (EN + BN), clause segmentation, document classification and the PII shield. Then add the Groq `llm.py` with caching and backoff.
3. **Days 7–10: agents.** Build the Router, the Statute/Global researchers (recursive cross-ref following), the Risk Analyst with the YAML playbook, and Adversarial Counsel. Wire them up with LangGraph.
4. **Days 11–13: verification.** Build the verifier's 4 gates, the currency agent and the critic loop. Then the memo drafter: IRAC, a Bangla summary, mitigation clauses and the ledger.
5. **Days 14–16: UI and export.** Build the Next.js UI (clause-risk highlighting, agent trace, ledger) and DOCX/PDF export.
6. **Days 17–18: evaluation and demo.** Run the evaluation harness, tune, record the demo, and prepare the pitch.

---

## 9. Hero demo script (about 3 minutes)
1. Upload a **60-page EU buyer Supplier Code + Purchase Agreement** for a Gazipur RMG factory, plus a **scanned Bangla employment appointment letter**.
2. The live agent graph lights up: Router picks Labour Act + FX + EU CSDDD/LkSG + Contract Act.
3. The output shows 5+ risks. At least 3 are clearly non-obvious:
   - 150-day payment terms breach the BB 120-day export-proceeds rule;
   - the non-compete is void under Contract Act s.27;
   - the factory is in an EPZ, so the BEPZ Labour Act 2019 applies and the buyer's "freedom of association" clause must be mapped to workers' welfare associations;
   - the unilateral CSDDD cost-shift has no termination cure period.
4. Open the **Verification Ledger**: each citation is clickable to bdlaws.minlaw.gov.bd, with the 4 gates shown. Show one ❌ claim that was **automatically dropped**, which is live evidence of hallucination control.
5. Download the bilingual memo with suggested replacement clauses.

---

## 10. Verification and evaluation (how we prove it works)
- **Gold test set:** 10–15 seeded contracts (employment, lease, supplier, NDA, SaaS) with deliberately planted risks from §2 plus control clauses that are legal.
- **Metrics:**
  - risk recall and precision against the gold set;
  - **citation validity rate**, the share of memo citations that resolve to real sections (target 100%);
  - entailment pass rate;
  - drop rate;
  - latency per document.
- **Ablation for the pitch:** compare "single LLM prompt" with "Ain Copilot". The single prompt invents or mis-numbers citations; ours does not.
- **End-to-end checks:**
  - run `run_eval.py`;
  - run the hero docs through the FastAPI endpoint;
  - confirm that every ledger link opens the correct bdlaws section;
  - test a Bangla scan photo taken on a phone.

---

## 11. Key risks and mitigations
- **Groq rate limits:** clause batching, caching, a token budgeter, and a pre-warmed cache for the demo docs.
- **Bangla OCR quality:** use Surya first and let the user correct the OCR text in the UI. Mark low-confidence OCR regions.
- **Statute text drift:** stamp each record with a scrape date. The currency agent warns about recent ordinances.
- **Scraping etiquette:** rate-limit, cache once, and cite the source.
- **Legal liability:** show a clear "decision-support, not legal advice" banner and a "consult an advocate" CTA. Confidence levels appear on every risk.

## 12. Why this beats the reference products (pitch)
Harvey, Spellbook and Luminance are built for US/UK firms. None of them:
- knows the BD-amended colonial statutes;
- reads Bangla;
- links the **BD Labour + FX + EU due-diligence** triangle that BD exporters face right now;
- shows a per-citation verification ledger against official government sources.

Sources consulted during analysis:
- [Dhaka Tribune: PDP Ordinance 2025 approved](https://www.dhakatribune.com/bangladesh/393590/bangladesh-government-approves-personal-data)
- [Daily Star: PDP Ordinance key takeaways](https://www.thedailystar.net/tech-startup/news/bangladeshs-personal-data-protection-ordinance-2025-key-takeaways-4015401)
- [TBS: LDC graduation scenarios](https://www.tbsnews.net/analysis/what-if-we-graduate-ldc-next-year-or-three-years-later-1297226)
- [Daily Star: EU GSP 2029](https://online92.thedailystar.net/business/news/eus-gsp-lifeline-bangladesh-must-win-2029-4051411)
- [bdlaws Contract Act 1872](http://bdlaws.minlaw.gov.bd/act-26.html)
