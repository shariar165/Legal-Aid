import type { Metadata } from "next";
import Link from "next/link";
import { LiveStatus } from "@/components/docs/LiveStatus";
import s from "@/components/docs/docs.module.css";
import { inter, sourceSerif } from "@/lib/fonts";

export const metadata: Metadata = {
  title: "Docs · Ain Copilot",
  description: "How Ain Copilot works: architecture, AI stack, MCP server, evaluation, safety, and the live system status.",
};

const NAV = [
  ["live", "Live"],
  ["how", "How it works"],
  ["ai", "AI stack"],
  ["mcp", "MCP"],
  ["eval", "Evaluation"],
  ["safety", "Safety"],
  ["process", "Build process"],
  ["limits", "Limits"],
] as const;

const PIPELINE = [
  ["Ingestion", "PyMuPDF, python-docx, or local EasyOCR (Bangla + English) for a phone photo. Clauses are split at numbered sub-clauses, schedules and annexes; PDF headers and footers are removed."],
  ["PII Shield", "Names, passport, NID, phone, address and date of birth become placeholders. Only redacted text ever reaches a model, and the LLM layer blocks any payload that still holds an identifier."],
  ["Jurisdiction Router", "Picks the law packs. Inside an EPZ the BEPZ Labour Act 2019 replaces the Labour Act 2006; the country of work adds its own labour law."],
  ["Risk Analyst + Adversarial Counsel", "A YAML playbook finds the known risks. In parallel, an agentic-RAG adversary with bilingual queries looks for clause interactions, dangerous gaps and regime conflicts the playbook misses (map → reduce on long contracts)."],
  ["Wage Truth Calculator", "Arithmetic only, after a human confirms a blurry salary figure: take-home pay against the cited minimum wage and deduction cap."],
  ["4-gate Verifier + Virtual Bench", "G1 existence and applicability, G2 quote fidelity, G3 entailment by a different model family, G4 still in force. High and critical claims go to three judges from different families and a Chief Justice."],
  ["Critic", "Re-anchors a citation to repealed law (e.g. the 2012 Trafficking Act → the 2026 Act) and re-verifies it; withdraws risks left without support."],
  ["Memo Drafter", "An IRAC memo that may cite only verified citation_ids, plus the citizen's cards in Bangla, a letter to the agency and a DOCX export."],
] as const;

export default function DocsPage() {
  return (
    <div lang="en" className={`${s.page} ${inter.variable} ${sourceSerif.variable}`}>
      <header className={s.top}>
        <div className={s.topInner}>
          <Link href="/" className={s.brand}>
            আইন Ain Copilot
          </Link>
          <nav className={s.nav} aria-label="On this page">
            {NAV.map(([id, label]) => (
              <a key={id} href={`#${id}`}>
                {label}
              </a>
            ))}
          </nav>
        </div>
      </header>

      <main className={s.main}>
        <section className={s.hero}>
          <p className={s.eyebrow}>Docs · pitch · system status</p>
          <h1>A legal copilot whose citations can&apos;t be made up.</h1>
          <p className={s.lede}>
            About a million Bangladeshis go abroad for work each year, and most sign an English contract they cannot read. Ain reads the contract (a PDF, a Word file or a phone photo, in Bangla or
            English), finds the non-obvious risks, and writes a memo in which every legal claim has been checked against official statute text by four gates and a three-judge AI bench.
          </p>
          <div className={s.ctas}>
            <Link className={s.btn} href="/">
              Citizen mode (Bangla, phone)
            </Link>
            <Link className={s.btnGhost} href="/counsel">
              Counsel mode (lawyers, NGOs)
            </Link>
            <a className={s.btnGhost} href="#mcp">
              Use it over MCP
            </a>
          </div>
          <p className={s.disclaimer}>Decision support, not legal advice.</p>
        </section>

        <section id="live" className={s.section}>
          <h2>Live system</h2>
          <p className={s.sub}>Read from the running backend when this page loads: corpus, model routing, cache, MCP surface and the last evaluation run.</p>
          <LiveStatus />
        </section>

        <section id="how" className={s.section}>
          <h2>How it works</h2>
          <p className={s.sub}>
            One engine, two views. Every step streams to the UI as a server-sent event, so the progress screen and the agent log show what is really happening, not a timer.
          </p>
          <ol className={s.pipeline}>
            {PIPELINE.map(([name, what]) => (
              <li key={name}>
                <div>
                  <strong>{name}</strong>
                  <span>{what}</span>
                </div>
              </li>
            ))}
          </ol>
          <p className={s.note}>
            After the run, Counsel mode lets you question the <strong>LLM Council</strong>: Remedies (Sunny), Text (Regal) and Enforcement (Grey). They deliberate, and the Chief Justice rules. They may cite
            only rows that passed verification.
          </p>
        </section>

        <section id="ai" className={s.section}>
          <h2>AI stack</h2>
          <p className={s.sub}>Free-tier models from five model families, chosen per role. Different families check each other.</p>
          <div className={s.grid3}>
            <div className={s.card}>
              <h3>Models</h3>
              <span className={s.tag}>GPT-OSS 120B / 20B</span>
              <span className={s.tag}>Qwen 3.8 27B</span>
              <span className={s.tag}>Gemma 4 31B</span>
              <span className={s.tag}>dots.3</span>
              <span className={s.tag}>ERNIE 5.5 Flash</span>
              <span className={s.tag}>multilingual-e5-small</span>
              <span className={s.tag}>EasyOCR</span>
              <p>Groq runs the main pipeline; two judges sit on OpenRouter&apos;s free models and one on Groq, and no two judges share a model. Every role has a backup on the other provider.</p>
            </div>
            <div className={s.card}>
              <h3>Prompting</h3>
              <ul>
                <li>Role prompts: judge, Chief Justice, opposing counsel, IRAC drafter</li>
                <li>Strict JSON contracts; JSON mode with a fallback when a model rejects it</li>
                <li>Persona lenses shape reasoning only. The verdict test is word-for-word identical for all judges, and a test enforces that.</li>
                <li>Anonymised peer review, then a ruling that records dissent</li>
              </ul>
            </div>
            <div className={s.card}>
              <h3>Retrieval (RAG)</h3>
              <ul>
                <li>Hybrid: BM25 over NFC-normalised Bangla + English tokens and e5 dense vectors, fused by reciprocal rank</li>
                <li>Agentic RAG: the Adversary writes its own bilingual queries</li>
                <li>Corrective: 4 gates + the Critic re-anchoring repealed law</li>
                <li>Section-level chunks with deep links to bdlaws</li>
              </ul>
            </div>
            <div className={s.card}>
              <h3>Token and cost control</h3>
              <ul>
                <li>Disk cache of every answer; replay mode costs 0 tokens</li>
                <li>Cheap-model routing (20B for extraction, 120B for reasoning)</li>
                <li>Token-bucket pacing under Groq&apos;s per-minute budget, re-synced from its headers</li>
                <li>Map → reduce digests for long contracts; flags for batching and statute windows</li>
              </ul>
            </div>
            <div className={s.card}>
              <h3>Orchestration</h3>
              <p>A custom asyncio multi-agent pipeline (no framework): parallel analyst/adversary/calculator branches, a human-in-the-loop salary check, a bench with quorum rules and graceful judge failure, and provider fallback chains marked in the trace. Self-hosted n8n runs a daily law-freshness watch and alerts on critical analyses.</p>
            </div>
            <div className={s.card}>
              <h3>Data</h3>
              <p>bdlaws.minlaw.gov.bd scraped section by section, plus verbatim excerpts cut from official PDFs (ILO, EU, Bangladesh Bank, 8 destination countries, companies&apos; own policies). No statute text is typed by hand: a test checks every playbook quote is verbatim.</p>
            </div>
          </div>
        </section>

        <section id="mcp" className={s.section}>
          <h2>MCP server</h2>
          <p className={s.sub}>
            Ain is a Model Context Protocol server too, so Claude Desktop, Claude Code, Cursor or any MCP client can use the verified-law engine as tools. It is built on the official Python SDK and reuses the
            engine as it is.
          </p>
          <div className={s.grid2}>
            <div className={s.tableWrap}>
              <table className={s.table}>
                <thead>
                  <tr>
                    <th>Tool</th>
                    <th>What it does</th>
                  </tr>
                </thead>
                <tbody>
                  {[
                    ["search_law", "hybrid search in English or Bangla, by law pack"],
                    ["get_section", "verbatim text, status, official link"],
                    ["verify_citation", "the 4 gates on one claim"],
                    ["wage_truth", "take-home pay against the cited minimum and cap"],
                    ["analyze_contract", "the whole pipeline, verified citations only"],
                    ["list_countries", "the 8 destinations and their packs"],
                  ].map(([t, d]) => (
                    <tr key={t}>
                      <td className={s.mono}>{t}</td>
                      <td>{d}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div>
              <pre className={s.code}>{`// .mcp.json (Claude Code), stdio
{
  "mcpServers": {
    "ain-copilot": {
      "command": ".venv/Scripts/python",
      "args": ["-m", "ain.mcp_server"],
      "env": { "PYTHONPATH": "backend" }
    }
  }
}

# or streamable HTTP, when AIN_MCP_TOKEN is set
POST /api/mcp
Authorization: Bearer $AIN_MCP_TOKEN`}</pre>
              <p className={s.note}>
                Also resources (<code>ain://corpus/&#123;citation_id&#125;</code>, <code>ain://playbook/rules</code>) and a <code>review_contract</code> prompt. Text containing an identifier is refused.
              </p>
            </div>
          </div>
        </section>

        <section id="eval" className={s.section}>
          <h2>Evaluation</h2>
          <p className={s.sub}>Four ways we measure the AI, all runnable from the repo.</p>
          <div className={s.grid2}>
            <div className={s.card}>
              <h3>Gold set</h3>
              <p>
                <code>eval/run_eval.py</code>: recall and precision against the expected risks for each demo document, the share of memo citations verified, the drop rate, the off-playbook count, and per-document
                must-cite checks. Results are shown <a href="#eval-results">above</a>.
              </p>
            </div>
            <div className={s.card}>
              <h3>Plain-chatbot ablation</h3>
              <p>The reasoner&apos;s own model with one prompt and no tools. Its citations go through the same gates, so the gap measures the pipeline, not the model.</p>
            </div>
            <div className={s.card}>
              <h3>Bench trap set</h3>
              <p>
                <code>eval/bench_quality.py</code>: 38 claim/statute pairs built to trip judges (exceptions, provisos, wrong regime). A quota-saving flag stays off until it leaves the answers unchanged.
              </p>
            </div>
            <div className={s.card}>
              <h3>Offline test suite</h3>
              <p>274 pytest tests with a deterministic fake LLM: corpus integrity, every gate failing on its own bad case, no PII in any outbound payload, the EPZ regime switch, the bench rules, the MCP tools and the automation hooks.</p>
            </div>
          </div>
        </section>

        <section id="safety" className={s.section}>
          <h2>Safety, privacy, guardrails</h2>
          <div className={s.grid3}>
            <div className={s.card}>
              <h3>Hallucination</h3>
              <p>Agents may cite only citation_ids that retrieval returned. Anything else is rejected before the gates, and the drafter strips unverified ids from the memo and from council replies.</p>
            </div>
            <div className={s.card}>
              <h3>Privacy</h3>
              <p>OCR runs locally. The PII Shield redacts before any model call, a guard blocks leaks (HTTP 422), OpenRouter calls send <code>data_collection: deny</code>, and results are encrypted at rest with Fernet.</p>
            </div>
            <div className={s.card}>
              <h3>Accounts</h3>
              <p>argon2id passwords, hashed HttpOnly session tokens, Origin-checked CSRF, rate limits, 404 for anyone but the owner, and erasure of one analysis or the whole account.</p>
            </div>
          </div>
        </section>

        <section id="process" className={s.section}>
          <h2>Build process</h2>
          <p className={s.sub}>Spec-driven, with Claude Code as the pair programmer and three gates before every commit.</p>
          <div className={s.grid3}>
            <div className={s.card}>
              <h3>1 · Spec</h3>
              <p>
                Each feature began as an approved plan in Claude Code&apos;s plan mode: context, the approach, the files it touches and how to verify it. All 13 are in <code>docs/specs/</code>.
              </p>
            </div>
            <div className={s.card}>
              <h3>2 · Build</h3>
              <p>
                Shared rules in <code>AGENTS.md</code> (and <code>CLAUDE.md</code>), project skills in <code>.claude/skills/</code>, and persistent agent memory across sessions. The council&apos;s pixel art was
                designed in Claude Design.
              </p>
            </div>
            <div className={s.card}>
              <h3>3 · Gates</h3>
              <p>Offline tests, then the gold set and the bench trap set for any change to prompts or routing, then a browser check. The eval report comes before the commit.</p>
            </div>
          </div>
        </section>

        <section id="limits" className={s.section}>
          <h2>Honest limitations</h2>
          <div className={s.card}>
            <ul>
              <li>Narrow by design: employment, migration and factory supply contracts. Other documents get only general checks and are labelled as outside Ain&apos;s focus.</li>
              <li>No court judgments yet: statutes, regulations, voluntary standards and three ILO CEACR observations.</li>
              <li>Free-tier limits make long documents slow (minutes), not broken.</li>
              <li>The gold set covers our own seeded demo documents: a regression check, not a benchmark.</li>
              <li>Eight destination countries; Qatar&apos;s and Kuwait&apos;s minimum wages have no official English text in the corpus yet.</li>
            </ul>
          </div>
        </section>
      </main>
    </div>
  );
}
