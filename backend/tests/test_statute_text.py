"""No judge, verifier or council prompt drops part of a cited section: every section the playbook or the trap set cites
is shown whole, and the few sections over STATUTE_MAX_CHARS keep the cited sub-section, the quote and every proviso.
Also the statute window's anchoring, and the Malaysia minimum-wage table read row by row. Offline, fake LLM."""

import pytest
import yaml

from ain import config
from ain.agents import bench, council
from ain.agents.verifier import gate_entailment
from ain.models import Claim
from ain.orchestrator import new_job, run_pipeline
from tests.conftest import RecordingLLM
from tests.test_bench import _risk

RULES = config.BACKEND / "ain" / "playbook" / "rules.yaml"
TRAPS = config.BACKEND / "eval" / "bench_traps.yaml"


def _anchors(rule):
    out = list(rule.get("anchors") or [])
    for key in ("anchors_by_pack", "pack_anchors"):
        for v in (rule.get(key) or {}).values():
            out += v
    return out


def cited_claims():
    """Every claim the playbook can raise, and every trap: (citation_id, proposition, quote)."""
    rules = yaml.safe_load(RULES.read_text(encoding="utf-8"))
    out = {(a["citation_id"], a["proposition"], a.get("quote")) for r in rules for a in _anchors(r)}
    out |= {(t["citation_id"], t["proposition"], None) for t in yaml.safe_load(TRAPS.read_text(encoding="utf-8"))}
    return sorted(out, key=str)


def _flat(t: str) -> str:
    return " ".join(t.split())


def _claim(cid, prop, quote=None):
    return Claim(id="R1.1", risk_id="R1", proposition=prop, citation_id=cid, quote=quote)


async def test_judges_and_the_verifier_read_every_cited_section_whole(corpus):
    seen = 0
    for cid, prop, quote in cited_claims():
        sec = corpus.get(cid)
        assert len(sec.text) <= bench.STATUTE_MAX_CHARS, f"{cid} is cited but longer than the judges' limit"
        llm, claim = RecordingLLM(), _claim(cid, prop, quote)
        await bench.convene(llm, claim, sec, _risk(), "supports")
        await gate_entailment(llm, claim, sec)
        prompts = [p for p in llm.payloads if p["task"] in ("bench_opinion", "bench_review", "bench_chair", "entailment")]
        assert len(prompts) == 8
        for p in prompts:
            assert _flat(sec.text) in _flat(p["user"]), (cid, p["task"])
        seen += 1
    assert seen > 60


async def test_the_long_sections_cited_before_are_no_longer_cut(corpus):
    # s.24(8) starts at char 3,479 and Art. 13(12)'s exceptions just after char 3,000: both were cut off before
    for cid, words in (("MY-EA-1955-s24", "shall not exceed fifty per centum"), ("AE-LABOUR-2021-a13", "unless he has already joined the service of another employer")):
        llm = RecordingLLM()
        await bench.convene(llm, _claim(cid, "x"), corpus.get(cid), _risk(), "supports")
        assert all(words in p["user"] for p in llm.payloads if p["task"].startswith("bench_opinion"))


def test_sections_up_to_the_limit_are_shown_whole_and_longer_ones_keep_provisos(corpus):
    for sec in corpus.sections:
        w = bench.cited_text(sec, _claim(sec.citation_id, sec.heading))
        if len(sec.text) <= bench.STATUTE_MAX_CHARS:
            assert w == sec.text, sec.citation_id
            continue
        flat_w = _flat(w)
        for m in bench.PROVISO.finditer(sec.text):
            assert _flat(sec.text[m.start(): m.end() + 12]) in flat_w, (sec.citation_id, m.group(0))


def test_a_long_section_keeps_whichever_sub_section_is_cited(corpus):
    for sec in corpus.sections:
        if len(sec.text) <= bench.STATUTE_MAX_CHARS:
            continue
        parts = bench.units(sec.text)
        for unit in parts[:: max(1, len(parts) // 6)]:  # a spread of sub-sections through the section
            m = bench._LABEL.match(unit) or bench._LABEL.match(unit.split(" ", 1)[-1])
            if not m:
                continue
            claim = _claim(sec.citation_id, f"Under s.{sec.section}({m.group(1)}), something.")
            assert _flat(unit) in _flat(bench.cited_text(sec, claim)), (sec.citation_id, m.group(1))


async def test_council_members_read_the_whole_verified_section(docs):
    name = "migrant_my_contract.txt"
    r = await run_pipeline(new_job(name), (docs / name).read_bytes(), name, llm=RecordingLLM())
    for risk in [k for k in r.risks if k.status != "dropped"]:
        ctx, _ = council.build_context(r, risk, bench.PERSONAS[0])
        for v in council._rows(r, risk.id):
            assert _flat(v.section.text) in _flat(ctx), v.claim.citation_id


# ------------------------------------------------------------------ the statute window (flag), anchored


@pytest.mark.parametrize("limit", [1500, 800])
def test_window_keeps_the_cited_sub_section_the_quote_and_provisos_for_every_cited_claim(corpus, limit):
    for cid, prop, quote in cited_claims():
        sec = corpus.get(cid)
        claim = _claim(cid, prop, quote)
        w = bench.window(sec.text, prop, limit, claim)
        if w == sec.text:
            continue
        flat_w = _flat(w)
        assert all(_flat(p) in _flat(sec.text) for p in w.split("\n") if p != "[...]"), cid  # verbatim pieces only
        if quote:
            assert bench._flat(quote) in bench._flat(w), (cid, quote)
        parts = bench.units(sec.text)
        for labels in bench.cited_labels(prop):
            hits = [u for u in parts if bench._starts_with(u, labels[0]) or bench._holds_item(u, labels[0])]
            assert hits, (cid, labels)  # the cited sub-section is found in the text ...
            assert _flat(hits[0]) in flat_w, (cid, labels)  # ... and kept
        for m in bench.PROVISO.finditer(sec.text):
            assert _flat(sec.text[m.start(): m.end() + 12]) in flat_w, (cid, m.group(0))


def test_cited_labels_cover_the_ways_propositions_cite():
    assert bench.cited_labels("Under the Malaysian Employment Act 1955 s.24(8), the total") == [["8"]]
    assert bench.cited_labels("Under UAE Federal Decree-Law 33/2021 Art. 13(12), the employer") == [["12"]]
    assert bench.cited_labels("Under OEMA 2013 s.31(গ), withholding") == [["গ"]]
    assert bench.cited_labels("s.24(4)(e) and section 26(১)") == [["4", "e"], ["1"]]
    assert bench.cited_labels("Under OEMA 2013 s.28, a migrant worker") == []


def test_window_keeps_the_definition_a_cited_sub_section_relies_on():
    text = (
        "5. (1) In this section, \"recruitment fee\" means any fee or cost charged to a worker for recruitment. "
        "(2) An agency shall keep records of its licences and renew them every year. "
        "(3) The register shall be open for inspection by an officer at any reasonable time. "
        "(4) No agency shall charge a worker any recruitment fee. "
        "(5) A person who contravenes this section commits an offence."
    )
    w = bench.window(text, "agency charge worker", 200, _claim("X", "Under s.5(4), no fee may be charged."))
    assert "(4) No agency shall charge" in w and "\"recruitment fee\" means" in w and "(2) An agency shall keep records" not in w


# ------------------------------------------------------------------ Malaysia Minimum Wages Order table


def test_minimum_wage_table_is_read_row_by_row_where_paragraph_3_1_introduces_it(corpus):
    text = corpus.get("MY-MWO-2024-p3").text
    row = "shall be as follows: Minimum Wages Rate: Monthly: RM1,700 | Daily (Number of working days in a week): 6: RM65.38; 5: RM78.46; 4: RM98.08 | Hourly: RM8.72 (2)"
    assert row in text
    assert "Monthly Daily Hourly" not in text and "P.U. (A) 376" not in text  # no flattened table, no page header
