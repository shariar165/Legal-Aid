"use client";

import { useEffect, useRef, useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { EvalRow, Metrics } from "@/lib/api";
import s from "./docs.module.css";

/* Colours come from the page's CSS tokens (light/dark), read at runtime because SVG presentation
   attributes can't resolve var(). Palette: dataviz reference slots 1-2 (blue, orange). */
type Viz = { surface: string; grid: string; axis: string; c1: string; c2: string };
const FALLBACK: Viz = { surface: "#ffffff", grid: "#e8ebe7", axis: "#59635d", c1: "#2a78d6", c2: "#eb6834" };

function useViz(ref: React.RefObject<HTMLElement | null>): Viz {
  const [viz, setViz] = useState(FALLBACK);
  useEffect(() => {
    const read = () => {
      if (!ref.current) return;
      const cs = getComputedStyle(ref.current);
      const v = (name: string, fb: string) => cs.getPropertyValue(name).trim() || fb;
      setViz({ surface: v("--viz-surface", FALLBACK.surface), grid: v("--viz-grid", FALLBACK.grid), axis: v("--viz-axis", FALLBACK.axis), c1: v("--viz-1", FALLBACK.c1), c2: v("--viz-2", FALLBACK.c2) });
    };
    read();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    mq.addEventListener("change", read);
    return () => mq.removeEventListener("change", read);
  }, [ref]);
  return viz;
}

const PACK_LABELS: Record<string, string> = {
  bd_labour: "BD Labour Act",
  bd_contract: "BD Contract & civil",
  bd_epz: "BD EPZ Labour Act",
  bd_migration: "BD Migration & trafficking",
  bd_data: "BD Data protection",
  bd_fx: "BD Foreign exchange",
  std_recruitment: "Fair-recruitment standards",
  ilo: "ILO conventions",
  ilo_supervisory: "ILO CEACR comments",
};

const DOC_LABELS: Record<string, string> = {
  "migrant_my_contract.txt": "Malaysia contract",
  "migrant_my_contract_photo.jpg": "Malaysia (photo)",
  "migrant_sa_contract.txt": "Saudi contract",
  "rmg_dhaka_epz.txt": "Dhaka EPZ supply",
  "long_migrant_msa.txt": "Long (~25 pp)",
  "control_clean.txt": "Clean control",
};

const packLabel = (p: string) => PACK_LABELS[p] ?? (p.endsWith("_labour") || p.endsWith("_employment") ? `${p.slice(0, 2).toUpperCase()} labour law` : p.startsWith("co_") ? "Company policies" : p.startsWith("eu_") ? "EU law" : p);
const docLabel = (d: string) => DOC_LABELS[d] ?? d.replace(/\.[a-z]+$/, "");

type TipProps = { active?: boolean; payload?: { name?: string; value?: number; payload?: Record<string, unknown> }[]; label?: string | number };

function Tip({ active, payload, label, unit }: TipProps & { unit: string }) {
  if (!active || !payload?.length) return null;
  return (
    <div className={s.tooltip}>
      <strong>{label}</strong>
      {payload.map((p) => (
        <div key={p.name}>
          {p.name}: {p.value} {unit}
        </div>
      ))}
    </div>
  );
}

function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className={s.legend}>
      {items.map((i) => (
        <span key={i.label}>
          <i className={s.swatch} style={{ background: i.color }} aria-hidden />
          {i.label}
        </span>
      ))}
    </div>
  );
}

export function CorpusChart({ corpus }: { corpus: Metrics["corpus"] }) {
  const ref = useRef<HTMLDivElement>(null);
  const viz = useViz(ref);
  // fold the long tail of small packs (countries, companies, EU) into labelled groups so the chart stays readable
  const groups = new Map<string, number>();
  for (const p of corpus.by_pack) groups.set(packLabel(p.pack), (groups.get(packLabel(p.pack)) ?? 0) + p.sections);
  const ranked = [...groups.entries()].map(([name, sections]) => ({ name, sections })).sort((a, b) => b.sections - a.sections);
  const shown = ranked.slice(0, 9);
  const rest = ranked.slice(9).reduce((n, r) => n + r.sections, 0);
  const data = rest ? [...shown, { name: "Other packs", sections: rest }] : shown;
  return (
    <div className={s.chartCard} ref={ref}>
      <h3>Corpus by law pack</h3>
      <p className={s.chartSub}>
        {corpus.sections.toLocaleString()} verbatim sections from {corpus.acts} acts and documents. A section can sit in more than one pack.
      </p>
      <ResponsiveContainer width="100%" height={data.length * 30 + 30}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 36, bottom: 0, left: 0 }} barCategoryGap={6}>
          <CartesianGrid horizontal={false} stroke={viz.grid} />
          <XAxis type="number" tick={{ fill: viz.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" width={170} tick={{ fill: viz.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: viz.grid, opacity: 0.5 }} content={<Tip unit="sections" />} />
          <Bar dataKey="sections" name="Sections" fill={viz.c1} radius={[0, 4, 4, 0]} label={{ position: "right", fill: viz.axis, fontSize: 12 }} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <DataTable head={["Pack", "Sections"]} rows={data.map((d) => [d.name, d.sections])} />
    </div>
  );
}

function StackedDocs({ title, sub, rows, a, b, unit }: { title: string; sub: string; rows: EvalRow[]; a: { key: string; label: string; get: (r: EvalRow) => number }; b: { key: string; label: string; get: (r: EvalRow) => number }; unit: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const viz = useViz(ref);
  const data = rows.map((r) => ({ name: docLabel(r.document), [a.key]: a.get(r), [b.key]: b.get(r) }));
  return (
    <div className={s.chartCard} ref={ref}>
      <h3>{title}</h3>
      <p className={s.chartSub}>{sub}</p>
      <Legend items={[{ label: a.label, color: viz.c1 }, { label: b.label, color: viz.c2 }]} />
      <ResponsiveContainer width="100%" height={data.length * 34 + 30}>
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 16, bottom: 0, left: 0 }} barCategoryGap={8}>
          <CartesianGrid horizontal={false} stroke={viz.grid} />
          <XAxis type="number" allowDecimals={false} tick={{ fill: viz.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
          <YAxis type="category" dataKey="name" width={124} tick={{ fill: viz.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
          <Tooltip cursor={{ fill: viz.grid, opacity: 0.5 }} content={<Tip unit={unit} />} />
          {/* 2px surface stroke = the gap between stacked segments; only the outer end is rounded */}
          <Bar dataKey={a.key} name={a.label} stackId="x" fill={viz.c1} stroke={viz.surface} strokeWidth={2} isAnimationActive={false} />
          <Bar dataKey={b.key} name={b.label} stackId="x" fill={viz.c2} stroke={viz.surface} strokeWidth={2} radius={[0, 4, 4, 0]} isAnimationActive={false} />
        </BarChart>
      </ResponsiveContainer>
      <DataTable head={["Document", a.label, b.label]} rows={data.map((d) => [d.name, d[a.key] as number, d[b.key] as number])} />
    </div>
  );
}

export function RisksChart({ rows }: { rows: EvalRow[] }) {
  return (
    <StackedDocs
      title="Risks found per document"
      sub="Confirmed risks, split by where they came from. The gold set requires at least 3 off-playbook risks per hero document."
      rows={rows}
      unit="risks"
      a={{ key: "playbook", label: "Playbook & checks", get: (r) => r.risks_confirmed - r.adversary_risks }}
      b={{ key: "adversary", label: "Off-playbook (Adversary)", get: (r) => r.adversary_risks }}
    />
  );
}

export function ClaimsChart({ rows }: { rows: EvalRow[] }) {
  return (
    <StackedDocs
      title="Legal claims through the 4 gates"
      sub="Every citation an agent proposes is checked. Dropped claims stay visible in the ledger, never in the memo."
      rows={rows.filter((r) => r.claims > 0)}
      unit="claims"
      a={{ key: "kept", label: "Verified or partial", get: (r) => r.claims - r.dropped }}
      b={{ key: "dropped", label: "Dropped", get: (r) => r.dropped }}
    />
  );
}

function DataTable({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <details className={s.tableToggle}>
      <summary>Show as a table</summary>
      <table className={s.table}>
        <thead>
          <tr>
            {head.map((h, i) => (
              <th key={h} className={i ? s.num : undefined}>
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={String(r[0])}>
              {r.map((c, i) => (
                <td key={i} className={i ? s.num : undefined}>
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  );
}
