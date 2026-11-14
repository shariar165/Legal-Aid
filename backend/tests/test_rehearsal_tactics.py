"""Rehearsal Council: every tactic is sourced, every example line passes the guard, every law anchor is verbatim."""

import re

from ain.agents.verifier import gate_currency
from ain.models import RehearsalSetup, RehearsalTurn
from ain.rehearsal import guard, rubric, tactics
from ain.retrieval import nfc

BANGLA = re.compile(r"[ঀ-৿]")


def test_every_tactic_has_an_openable_source():
    for t in tactics.load():
        for src in t.sources:
            missing = [k for k in tactics.SOURCE_KEYS if not str(src.get(k) or "").strip()]
            assert not missing, f"{t.id}: source lacks {missing}"
            assert src["url"].startswith("https://"), t.id
            assert 1990 <= int(src["year"]) <= 2026, t.id


def test_example_lines_are_bangla_and_pass_the_guard():
    for t in tactics.load():
        assert BANGLA.search(t.example_bn), t.id
        assert not re.search(r"[0-9০-৯]", t.example_bn), f"{t.id}: example line has a figure"
        assert guard.check_dalal(t.example_bn, t.id, t.id, set()) == "", t.id


def test_law_anchors_are_verbatim_and_in_force(corpus):
    for t in tactics.load():
        assert t.law, f"{t.id}: Regal needs at least one anchor"
        for a in t.law:
            sec = corpus.get(a.citation_id)
            assert sec is not None, f"{t.id}: {a.citation_id} is not in the corpus"
            assert nfc(a.quote) in nfc(sec.text), f"{t.id}: quote is not verbatim in {a.citation_id}"
            assert gate_currency(sec).status == "pass", f"{t.id}: {a.citation_id} is not in force"
        assert not re.search(r"[0-9০-৯]|ধারা|section", t.regal_bn, re.I), f"{t.id}: regal_bn names a section or a figure"


def test_order_and_rubric_references_are_consistent():
    ids = {t.id for t in tactics.load()}
    assert sorted(tactics.order()) == sorted(ids)
    items = {i.id for i in rubric.items()}
    for t in tactics.load():
        assert set(t.tests) <= items and set(t.counter_of) <= items, t.id
    for i in rubric.items():
        if i.applies.startswith("tactic:"):
            assert i.applies.split(":", 1)[1] in ids


def test_scheduler_reacts_then_continues_and_stops():
    setup = RehearsalSetup()
    first = tactics.schedule(setup, [])
    assert first == tactics.order()[0]
    asked_receipt = [RehearsalTurn(n=1, tactic_id=first, dalal_line="x", worker_reply="রসিদ দেবেন?", hits=["receipt"])]
    assert tactics.schedule(setup, asked_receipt) == "no_receipt"  # the dalal pushes back on what the worker asked
    turns = []
    while (nxt := tactics.schedule(setup, turns)) is not None:
        turns.append(RehearsalTurn(n=len(turns) + 1, tactic_id=nxt, dalal_line="x", worker_reply="ঠিক"))
    least, most = tactics.turn_limits()
    assert least <= len(turns) <= most
    assert len({t.tactic_id for t in turns}) == len(turns)  # no tactic twice
