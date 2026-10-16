import type { AblationRow, GateStatus, Section, Severity, Verdict } from "@/lib/api";
import type { IconName } from "./Icons";

export const SEVERITY_LABEL: Record<Severity, string> = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };
export const SEVERITY_RANK: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export const ORIGIN_LABEL = {
  playbook: "Playbook",
  adversary: "Adversarial Counsel",
  calculator: "Wage Calculator",
  critic: "Critic",
  drafter: "Procedural",
  ablation: "Ablation",
} as const;

export const GATES = [
  { id: "existence", short: "Exists", name: "Existence & applicability" },
  { id: "fidelity", short: "Quote", name: "Quote fidelity" },
  { id: "entailment", short: "Meaning", name: "Entailment (judge / bench)" },
  { id: "currency", short: "In force", name: "Currency (in force?)" },
] as const;

export const GATE_ICON: Record<GateStatus, IconName> = { pass: "check", warn: "alert", fail: "x", skip: "minus" };
export const GATE_STATUS_LABEL: Record<GateStatus, string> = { pass: "passed", warn: "warning", fail: "failed", skip: "not run" };
export const VERDICT_LABEL: Record<Verdict, string> = { verified: "Verified", partial: "Partial", dropped: "Dropped" };
export const VERDICT_ICON: Record<Verdict, IconName> = { verified: "checkCircle", partial: "alert", dropped: "xCircle" };

export const OUTCOME: Record<AblationRow["outcome"], { label: string; ok: boolean }> = {
  supported: { label: "Supported", ok: true },
  unsupported: { label: "Not supported by the text", ok: false },
  unresolvable: { label: "Section not found", ok: false },
  repealed: { label: "Repealed law", ok: false },
  inapplicable: { label: "Wrong regime", ok: false },
};

/** "Contract Act 1872 · s.27" from a corpus record. */
export function citeLabel(s: Section): string {
  const act = s.act_en.replace(/^The\s+/, "").replace(/,/g, "");
  const unit = /^(ILO|EU)-/.test(s.act_key) ? "Art. " : /^(BD-GFET|BD-FENOTIF|BD-FECIRC|MY-MWO)/.test(s.act_key) ? "para " : "s.";
  return s.section.startsWith("Ch.") ? `${act} · ${s.section}` : `${act} · ${unit}${s.section}`;
}

export function money(currency: string, n: number): string {
  return `${currency} ${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}
