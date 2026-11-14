"""Promise Record (প্রতিশ্রুতির লিখিত রেকর্ড): a dated record of what the worker says the agent promised.

Each promise is checked against law only through claims in promise_checks.yaml (plus the destination's passport
anchors from the playbook and its minimum wage from countries.yaml), and each claim passes the verifier's gates
(`verifier.verify_claim`, no bench) before it is shown. Nothing here asks a model to write about the law, and the
contact fields (names, phones) never reach a model: they are stored only as placeholders, and the DOCX puts the real
values back on this machine, as the memo export does.
"""

from __future__ import annotations

import io
from datetime import date
from functools import lru_cache
from pathlib import Path

import yaml
from docx import Document as Docx
from docx.shared import Pt

from ain import config, countries
from ain.agents.pii import rehydrate
from ain.agents.verifier import verify_claim
from ain.llm import LLM
from ain.models import (
    Claim,
    ComplaintPath,
    L10n,
    PackDecision,
    PromiseContacts,
    PromiseRecord,
    PromiseRow,
    RehearsalSession,
    RehearsalSetup,
    RouteDecision,
    Verification,
)
from ain.naming import label
from ain.rehearsal import guard
from ain.retrieval import get_corpus

CHECKS_FILE = Path(__file__).with_name("promise_checks.yaml")
RULES_FILE = config.BACKEND / "ain" / "playbook" / "rules.yaml"
DISCLAIMER = L10n(bn="সিদ্ধান্তে সহায়তা, আইনি পরামর্শ নয়।", en="Decision support, not legal advice.")
TITLE = L10n(bn="প্রতিশ্রুতির লিখিত রেকর্ড", en="Promise Record")


@lru_cache
def checks() -> dict:
    return yaml.safe_load(CHECKS_FILE.read_text(encoding="utf-8"))


@lru_cache
def _passport_anchors() -> dict[str, list[dict]]:
    rules = yaml.safe_load(RULES_FILE.read_text(encoding="utf-8"))
    rule = next((r for r in rules if r.get("id") == "PB-PASSPORT"), {})
    return dict(rule.get("pack_anchors") or {})


def route(setup: RehearsalSetup) -> RouteDecision:
    packs = [PackDecision(pack="bd_migration", label="Bangladesh migration law", reason="Rehearsal Council: recruitment in Bangladesh")]
    c = countries.by_name(setup.country)
    if c:
        packs.append(PackDecision(pack=c.pack, label=c.label, reason=f"Destination chosen by the worker: {c.name['en']}"))
    return RouteDecision(packs=packs)


def _value(setup: RehearsalSetup, field: str):
    if field in ("has_contract", "through_dalal"):
        return getattr(setup, field)
    return getattr(setup.promises, field)


def _applies(when: str, setup: RehearsalSetup) -> bool:
    if when == "always":
        return True
    field, _, rest = when.partition(" ")
    v = _value(setup, field)
    if rest.startswith("in "):
        return v in [x.strip() for x in rest[3:].strip("[] ").split(",")]
    if rest == "is false":
        return v is False
    if rest == "is true":
        return v is True
    if rest == "given":
        return bool(str(v or "").strip())
    raise ValueError(f"promise_checks.yaml: cannot read when: {when!r}")


def _shown(value) -> str:
    if isinstance(value, bool):
        return {True: "হ্যাঁ", False: "না"}[value]
    return {"agent": "এজেন্ট/দালাল", "employer": "নিয়োগকারী", "me": "আমার কাছে", "unsure": "জানি না"}.get(str(value), str(value))


def _figures_sourced(v: Verification) -> bool:
    """No unsourced numbers: every figure in a proposition must be in its section's own text (or its act and number).
    A playbook anchor can paraphrase a figure ("RM100,000" for words in the statute); such a claim is not shown."""
    sec = v.section
    return sec is not None and not guard.unsourced_numbers(v.claim.proposition, sec.text, sec.act_en, sec.section, str(sec.year))


async def _verify(llm: LLM, rd: RouteDecision, claims: list[Claim]) -> list[Verification]:
    corpus = get_corpus()
    out = []
    for c in claims:  # one at a time: offline this is instant, live it stays inside the judge's rate limit
        v = await verify_claim(llm, corpus, rd, c, None, use_bench=False)
        if v.verdict != "dropped" and not _figures_sourced(v):
            v = v.model_copy(update={"verdict": "dropped", "note": "Gives a figure that is not in the section's text."})
        out.append(v)
    return out


def _claims_for(check: dict, setup: RehearsalSetup) -> list[Claim]:
    out = [
        Claim(id=f"PR-{check['id']}-{i}", risk_id=f"PR-{check['id']}", proposition=c["proposition"], citation_id=c["citation_id"], quote=c["quote"])
        for i, c in enumerate(check.get("claims") or [], 1)
    ]
    c = countries.by_name(setup.country)
    if c and check.get("playbook_rule") == "PB-PASSPORT":
        for i, a in enumerate(_passport_anchors().get(c.pack, []), 1):
            out.append(Claim(id=f"PR-{check['id']}-pb{i}", risk_id=f"PR-{check['id']}", proposition=a["proposition"], citation_id=a["citation_id"], quote=a.get("quote")))
    if c and check.get("min_wage") and c.min_wage:
        mw = c.min_wage
        out.append(
            Claim(
                id=f"PR-{check['id']}-mw", risk_id=f"PR-{check['id']}", citation_id=mw["citation_id"],
                proposition=f"{c.of['en']} monthly minimum wage is {c.currency} {int(mw['amount']):,}.",
            )
        )
    return out


async def build(llm: LLM, setup: RehearsalSetup, contacts: PromiseContacts, created: date | None = None) -> PromiseRecord:
    rd = route(setup)
    rows: list[PromiseRow] = []
    unverified: list[str] = []
    for check in checks()["checks"]:
        if not _applies(check["when"], setup):
            continue
        results = await _verify(llm, rd, _claims_for(check, setup))
        shown = [v for v in results if v.verdict in ("verified", "partial")]
        dropped = [v.claim.citation_id for v in results if v.verdict == "dropped"]
        unverified += dropped
        rows.append(
            PromiseRow(field=check["field"], label=L10n(**check["label"]), promised=_shown(_value(setup, check["field"])), checks=shown, unverified=dropped)
        )
    for extra in setup.promises.extra:
        if extra.strip():
            rows.append(PromiseRow(field="extra", label=L10n(bn="অন্য প্রতিশ্রুতি", en="Other promise"), promised=extra.strip()))
    paths: list[ComplaintPath] = []
    for p in checks()["paths"]:
        claim = Claim(id=f"PR-path-{p['id']}", risk_id="PR-paths", proposition=p["proposition"], citation_id=p["citation_id"], quote=p["quote"])
        (v,) = await _verify(llm, rd, [claim])
        if v.verdict in ("verified", "partial"):
            paths.append(ComplaintPath(id=p["id"], label=L10n(**p["label"]), check=v))
        else:
            unverified.append(p["citation_id"])
    return PromiseRecord(created_at=(created or date.today()).isoformat(), contacts=contacts, rows=rows, paths=paths, unverified=list(dict.fromkeys(unverified)))


def cost_note() -> L10n:
    c = next(c for c in checks()["checks"] if c["id"] == "cost")
    return L10n(**c["note"])


# ---------------------------------------------------------------- DOCX


def record_docx(s: RehearsalSession) -> bytes:
    """Rendered on this machine: the placeholders become the values the worker typed."""
    r = s.record
    assert r is not None
    real = lambda t: rehydrate(t, s.mapping)  # noqa: E731
    d = Docx()
    d.styles["Normal"].font.size = Pt(11)
    d.add_heading(f"{TITLE.bn} · {TITLE.en}", level=0)
    head = d.add_paragraph()
    head.add_run(f"তারিখ / Date: {r.created_at}\n").bold = True
    c = countries.by_name(s.setup.country)
    if c:
        head.add_run(f"গন্তব্য / Destination: {c.name['bn']} ({c.name['en']})\n")
    if s.setup.job or s.setup.promises.job:
        head.add_run(f"কাজ / Job: {real(s.setup.job or s.setup.promises.job)}\n")
    head.add_run(f"Ain Copilot · {DISCLAIMER.bn} · {DISCLAIMER.en}").italic = True

    k = r.contacts
    people = [("এজেন্ট/দালালের নাম", k.agent_name), ("ফোন", k.agent_phone), ("এজেন্সির নাম", k.agency_name), ("কোথায় কথা হয়েছে", k.place)]
    if any(v for _, v in people) or k.notes:
        d.add_heading("কার সঙ্গে কথা হয়েছে · Who made the promises", level=1)
        for name, v in people:
            if v:
                d.add_paragraph(f"{name}: {real(v)}")
        if k.notes:
            d.add_paragraph(f"নোট: {real(k.notes)}")

    d.add_heading("যা প্রতিশ্রুতি দেওয়া হয়েছে, আর আইন কী বলে · What was promised, and what the law says", level=1)
    note = cost_note()
    for row in r.rows:
        para = d.add_paragraph()
        para.add_run(f"{row.label.bn} ({row.label.en}): ").bold = True
        para.add_run(real(row.promised))
        for v in row.checks:
            sec = v.section
            assert sec is not None
            q = d.add_paragraph(style="List Bullet")
            q.add_run(f"{v.claim.proposition} ")
            q.add_run(f"[{label(sec).bn} · {label(sec).en}] ").italic = True
            q.add_run(f"“{v.claim.quote}” " if v.claim.quote else "")
            q.add_run(sec.url)
        if row.field == "total_cost":
            d.add_paragraph(f"{note.bn} {note.en}", style="List Bullet")
        if row.unverified:
            d.add_paragraph("এই বিষয়ে কিছু আইন যাচাই হয়নি, তাই দেখানো হলো না।", style="List Bullet")

    d.add_heading("কোথায় অভিযোগ করবেন · Where to complain", level=1)
    for p in r.paths:
        sec = p.check.section
        assert sec is not None
        para = d.add_paragraph(style="List Bullet")
        para.add_run(f"{p.label.bn}: ").bold = True
        para.add_run(f"{p.check.claim.proposition} [{label(sec).bn}] “{p.check.claim.quote}” {sec.url}")
    if s.debrief:
        d.add_heading("টাকা দেওয়ার আগে যা জিজ্ঞেস করবেন · Ask before you pay", level=1)
        for q in s.debrief.checklist:
            d.add_paragraph(q.bn, style="List Number")

    d.add_heading("স্বাক্ষর · Signatures", level=1)
    d.add_paragraph("এজেন্ট/দালালের স্বাক্ষর ও তারিখ: ____________________________")
    d.add_paragraph("সাক্ষীর স্বাক্ষর ও তারিখ: ____________________________")
    d.add_paragraph(
        "এই রেকর্ড কর্মীর নিজের বর্ণনা থেকে তৈরি। আইনের অংশগুলো Ain-এর যাচাই করা আইনের সংকলন থেকে হুবহু উদ্ধৃত। "
        "This record is the worker's own account; the law is quoted verbatim from Ain's verified corpus."
    )
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()
