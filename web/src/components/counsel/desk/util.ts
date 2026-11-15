import type { AnalysisResult, Clause } from "@/lib/api";
import type { Lang } from "@/lib/desk/i18n";
import { citeLabel } from "../format";

/** A cited section's name in the reader's language: the backend's bilingual name, else the English label. */
export function citeName(result: AnalysisResult, citationId: string, lang: Lang): string {
  const named = result.citation_names?.[citationId];
  if (named) return named[lang];
  const section = result.ledger.find((v) => v.claim.citation_id === citationId && v.section)?.section;
  return section ? citeLabel(section) : citationId;
}

export const isBangla = (text: string) => /[ঀ-৿]/.test(text);

/** The clause's own number when it starts with one ("2. Salary…" → 2, "১০. …" → 10), else its position. */
export function clauseNo(c: Clause): number {
  const m = c.text.match(/^\s*([0-9০-৯]{1,3})[.)]/);
  if (!m) return c.index + 1;
  return Number(m[1].replace(/[০-৯]/g, (d) => String("০১২৩৪৫৬৭৮৯".indexOf(d))));
}

export { money } from "../format";
