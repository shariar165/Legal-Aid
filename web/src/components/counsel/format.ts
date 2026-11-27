import type { AblationRow, GateStatus, Section, Severity, Verdict } from "@/lib/api";
import type { IconName } from "@/components/shared/Icons";

export const SEVERITY_LABEL: Record<Severity, string> = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };
export const SEVERITY_RANK: Record<Severity, number> = { critical: 0, high: 1, medium: 2, low: 3 };

export const ORIGIN_LABEL = {
  playbook: "Playbook",
  adversary: "Adversarial Counsel",
  calculator: "Wage Calculator",
  critic: "Critic",
  drafter: "Procedural",
  ablation: "Ablation",
  policy: "Policy Check",
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

/** tone: ok = survived the gates, bad = wrong, none = Jukti could not check it (never counted against the model) */
export const OUTCOME: Record<AblationRow["outcome"], { label: string; tone: "ok" | "bad" | "none" }> = {
  supported: { label: "Supported", tone: "ok" },
  wrong: { label: "Wrong", tone: "bad" },
  fabricated: { label: "Section doesn't exist", tone: "bad" },
  outside_corpus: { label: "Outside our corpus", tone: "none" },
  // a comparison stored before spec 29 step 2.2; "unresolvable" mixed made-up sections with law Jukti doesn't hold
  unsupported: { label: "Not supported by the text", tone: "bad" },
  unresolvable: { label: "Not checkable here", tone: "none" },
  repealed: { label: "Repealed law", tone: "bad" },
  inapplicable: { label: "Wrong regime", tone: "bad" },
};

export const WRONG_WHY: Record<NonNullable<AblationRow["why"]>, string> = {
  repealed: "repealed",
  wrong_regime: "wrong regime",
  not_supported: "the text doesn't say this",
};

/** "Contract Act 1872 · s.27" from a corpus record. */
/** Mirrors backend/ain/naming.py: Gulf laws and ILO/EU texts number articles, standards are marked as not law. */
export function citeLabel(s: Section): string {
  const act = s.act_en.replace(/^The\s+/, "").replace(/,/g, "") + (s.kind === "standard" ? " (voluntary standard)" : "");
  if (s.act_key === "STD-EPP") return act;
  if (s.kind === "supervisory") return `${act} · ${s.heading} (ILO supervisory, interpretive)`;
  if (s.kind === "company_policy" && s.act_key.startsWith("CO-")) return `${s.act_en.split(": ")[0]} · published policy · clause ${s.section}`;
  if (s.kind === "company_policy") return `${act} · clause ${s.section}`;
  const unit = /^STD-ILO-FAIR/.test(s.act_key)
    ? "principle "
    : /^STD-RBA/.test(s.act_key)
      ? "§ "
      : /^(ILO|EU|SA|AE|QA|OM|KW|BH)-/.test(s.act_key)
        ? "Art. "
        : /^(BD-GFET|BD-FENOTIF|BD-FECIRC|MY-MWO)/.test(s.act_key)
          ? "para "
          : "s.";
  return s.section.startsWith("Ch.") ? `${act} · ${s.section}` : `${act} · ${unit}${s.section}`;
}

export function money(currency: string, n: number): string {
  return `${currency} ${n.toLocaleString("en-US", { maximumFractionDigits: 0 })}`;
}
