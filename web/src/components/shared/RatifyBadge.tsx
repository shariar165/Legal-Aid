import { Fragment } from "react";
import type { Ratification } from "@/lib/api";
import type { Lang } from "@/lib/citizen/i18n";
import s from "./ratify.module.css";

/** "BD ✓ · MY ✗": who has ratified a cited international instrument (spec 29 step 2.1). Screen readers and the tooltip
 *  get the sentence ("Not ratified by Bangladesh or Malaysia…"); `full` also shows it under the badge. */
export function RatifyBadge({ r, lang = "en", full = false }: { r: Ratification | undefined; lang?: Lang; full?: boolean }) {
  if (!r) return null;
  const note = r.note[lang];
  return (
    <>
      <span className={s.badge} data-persuasive={r.persuasive} title={note}>
        <span aria-hidden="true">
          {r.parties.map((p, i) => (
            <Fragment key={p.country}>
              {i > 0 && <span className={s.dot}> · </span>}
              <span className={s.party} data-ok={p.ratified}>
                {p.country} <span className={s.mark}>{p.ratified ? "✓" : "✗"}</span>
              </span>
            </Fragment>
          ))}
        </span>
        {!full && <span className={s.srOnly}>{note}</span>}
      </span>
      {full && (
        <span className={s.note} data-persuasive={r.persuasive} lang={lang}>
          {note}
        </span>
      )}
    </>
  );
}
