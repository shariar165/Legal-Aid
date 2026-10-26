"use client";

import dynamic from "next/dynamic";
import { useEffect, useState } from "react";
import { api, type Health, type Metrics } from "@/lib/api";
import s from "./docs.module.css";

// Recharts measures the DOM, so the charts render on the client only
const CorpusChart = dynamic(() => import("./Charts").then((m) => m.CorpusChart), { ssr: false });
const RisksChart = dynamic(() => import("./Charts").then((m) => m.RisksChart), { ssr: false });
const ClaimsChart = dynamic(() => import("./Charts").then((m) => m.ClaimsChart), { ssr: false });

const MODE_LABEL: Record<Health["llm_mode"], string> = {
  live: "Live models",
  replay: "Replay cache",
  fake: "Offline demo",
};

const pct = (x: number | null) => (x === null ? "–" : `${Math.round(x * 100)}%`);

function useLive() {
  const [state, setState] = useState<{ health?: Health; metrics?: Metrics; error?: string; at?: Date }>({});
  useEffect(() => {
    let alive = true;
    Promise.all([api.health(), api.metrics()])
      .then(([health, metrics]) => alive && setState({ health, metrics, at: new Date() }))
      .catch((e: unknown) => alive && setState({ error: e instanceof Error ? e.message : String(e) }));
    return () => {
      alive = false;
    };
  }, []);
  return state;
}

export function LiveStatus() {
  const { health, metrics, error, at } = useLive();
  if (error) {
    return <p className={s.notice}>The backend did not answer ({error}). Start it with <code>python -m uvicorn ain.api:app --port 8000</code> from <code>backend/</code>; the rest of this page doesn&apos;t need it.</p>;
  }
  if (!health || !metrics) {
    return (
      <div className={s.liveHead} aria-live="polite">
        <i className={`${s.dot} ${s.dotOff}`} aria-hidden /> Connecting to the backend…
      </div>
    );
  }
  const keys = Object.entries(health.providers);
  return (
    <>
      <div className={s.liveHead} aria-live="polite">
        <i className={s.dot} aria-hidden /> Live from <code>/api/health</code> and <code>/api/metrics</code>, read at {at?.toLocaleTimeString()}
      </div>
      <div className={s.tiles}>
        <Tile label="Model mode" value={MODE_LABEL[health.llm_mode]} note={keys.map(([p, ok]) => `${p} ${ok ? "key set" : "no key"}`).join(" · ")} />
        <Tile label="Law sections" value={health.corpus_sections.toLocaleString()} note={`${health.acts} acts and documents`} />
        <Tile label="Countries of work" value={String(metrics.corpus.countries)} note="+ Bangladesh law and ILO standards" />
        <Tile label="Retrieval" value={health.dense_retrieval ? "Hybrid" : "BM25"} note={health.dense_retrieval ? "BM25 + e5 dense, RRF fusion" : "dense search off on this server"} />
        <Tile label="LLM answers cached" value={metrics.llm.cache_entries === null ? "–" : metrics.llm.cache_entries.toLocaleString()} note="replayed at 0 tokens" />
        <Tile label="MCP tools" value={String(metrics.mcp.tools.length)} note={metrics.mcp.http_enabled ? "stdio + HTTP (/api/mcp) on" : "stdio on · HTTP off here"} />
        <Tile label="Binding-law sections" value={(metrics.corpus.by_kind.law ?? 0).toLocaleString()} note={`${metrics.corpus.by_kind.standard ?? 0} standards · ${metrics.corpus.by_kind.company_policy ?? 0} company policy · ${metrics.corpus.by_kind.supervisory ?? 0} ILO comments`} />
        <Tile label="Model roles" value={String(metrics.llm.roles.length)} note="each with a cross-provider backup" />
      </div>

      <div className={s.grid2}>
        <CorpusChart corpus={metrics.corpus} />
        <div className={s.chartCard}>
          <h3>Model routing</h3>
          <p className={s.chartSub}>
            From <code>backend/ain/config.yaml</code>. OpenRouter is used with free models only and <code>data_collection: deny</code>.
          </p>
          <div className={s.tableWrap}>
            <table className={s.table}>
              <thead>
                <tr>
                  <th>Role</th>
                  <th>Primary</th>
                  <th>Backup</th>
                </tr>
              </thead>
              <tbody>
                {metrics.llm.roles.map((r) => (
                  <tr key={r.role}>
                    <td className={`${s.mono} ${s.nowrap}`}>{r.role}</td>
                    <td className={s.mono}>
                      {r.provider} · {r.model}
                    </td>
                    <td className={`${s.mono} ${s.muted}`}>{r.backup ? `${r.backup.provider} · ${r.backup.model}` : "–"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <EvalBlock metrics={metrics} />
    </>
  );
}

function EvalBlock({ metrics }: { metrics: Metrics }) {
  const rows = metrics.eval.results;
  if (!rows.length) return <p className={s.note}>No eval run found. Run <code>python -m eval.run_eval</code> from <code>backend/</code>.</p>;
  const fake = rows.every((r) => r.mode === "fake");
  return (
    <div id="eval-results" style={{ marginTop: 14 }}>
      <p className={s.notice}>
        {fake ? (
          <>
            These numbers come from the <strong>offline regression run</strong> (<code>{metrics.eval.source}</code>, fake LLM). Retrieval and all four gates are real; the model answers are canned. They show that the
            pipeline holds its guarantees, not how well a live model reasons.
          </>
        ) : (
          <>
            Last eval run: <code>{metrics.eval.source}</code>, mode <strong>{rows[0].mode}</strong>. The gold set covers our own seeded demo documents, so treat this as a regression check, not a benchmark.
          </>
        )}
      </p>
      <div className={s.grid2} style={{ marginTop: 14 }}>
        <RisksChart rows={rows} />
        <ClaimsChart rows={rows} />
      </div>
      <div className={s.tableWrap} style={{ marginTop: 14 }}>
        <table className={s.table}>
          <thead>
            <tr>
              <th>Document</th>
              <th className={s.num}>Recall</th>
              <th className={s.num}>Precision</th>
              <th className={s.num}>Memo citations verified</th>
              <th className={s.num}>Plain chatbot citations supported</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.document}>
                <td className={s.mono}>{r.document}</td>
                <td className={s.num}>{pct(r.recall)}</td>
                <td className={s.num}>{pct(r.precision)}</td>
                <td className={s.num}>{pct(r.citation_validity)}</td>
                <td className={s.num}>{r.ablation_plain_supported ?? "–"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className={s.tile}>
      <div className={s.tileLabel}>{label}</div>
      <div className={s.tileValue}>{value}</div>
      {note && <div className={s.tileNote}>{note}</div>}
    </div>
  );
}
