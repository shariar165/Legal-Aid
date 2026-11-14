"""Rehearsal Council: the dalal's guardrails. A line that states law, insults, names someone or invents a figure is
replaced by the tactic's curated example line."""

import pytest

from ain.companies import load_companies
from ain.models import PromisedTerms, RehearsalSetup
from ain.rehearsal import dalal, guard, tactics
from tests.conftest import RecordingLLM

T = "no_receipt"


@pytest.mark.parametrize(
    "line, reason",
    [
        ("রসিদ লাগবে না, এটা আইনে আছে।", "law"),
        ("ধারা অনুযায়ী কোনো রসিদ দিতে হয় না।", "law"),
        ("It's legal, no receipt needed.", "law"),
        ("BD-OEMA-2013-s31 says you don't need one.", "law"),
        ("সরকারি রেট এটাই, রসিদ লাগে না।", "law"),
        ("বোকার মতো প্রশ্ন করবেন না, রসিদ লাগবে না।", "insult"),
        ("মোঃ করিম সাহেবের অফিসে টাকা দেন।", "named"),
        ("আমাদের এক্সপ্রেস ওভারসিজ এজেন্সিতে আসেন।", "named"),
        ("Call 01712345678 for the receipt.", "named"),
        ("Rahim bhai will handle it.", "named"),
        ("সবাই পাঁচ লাখ দেয়, রসিদ লাগে না।", "figure"),
        ("সবাই ৭,০০,০০০ টাকা দেয়।", "figure"),
    ],
)
def test_guard_replaces_lines_that_break_a_rule(line, reason):
    why = guard.check_dalal(line, T, T, allowed_numbers={"400000"})
    assert why, line
    assert {"law": "law", "insult": "insult", "named": "named", "figure": "figure"}[reason] in why


def test_guard_blocks_registry_company_names():
    c = load_companies()
    if not c:
        pytest.skip("no company registry")
    for co in c:
        assert guard.check_dalal(f"{co.name} তে চাকরি পাকা।", T, T, set()), co.name


def test_guard_allows_the_workers_own_figures_and_rejects_an_off_schedule_tactic():
    assert guard.check_dalal("আপনি তো ৪,০০,০০০ টাকার কথা বলেছিলেন, ওটাই দিবেন।", T, T, {"400000"}) == ""
    assert "instead of the scheduled" in guard.check_dalal("পাসপোর্টটা দেন।", "passport_for_processing", T, set())


async def test_dalal_falls_back_to_the_example_line_and_sees_no_pii():
    tactic = tactics.by_id()["passport_for_processing"]
    setup = RehearsalSetup(country="Malaysia", promises=PromisedTerms(salary="৪০,০০০ টাকা"))
    bad = RecordingLLM(overrides={"rehearsal_dalal": {"tactic_id": tactic.id, "line": "আইন বলে পাসপোর্ট এজেন্টের কাছে রাখতে হয়।"}})
    line, reason = await dalal.line(bad, tactic, setup, [])
    assert line == tactic.example_bn and "law" in reason
    good = RecordingLLM(overrides={"rehearsal_dalal": {"tactic_id": tactic.id, "line": "পাসপোর্টটা দিয়ে যান, ৪০,০০০ টাকার চাকরি পাকা।"}})
    line, reason = await dalal.line(good, tactic, setup, [])
    assert reason == "" and "৪০,০০০" in line  # a figure the worker gave may be repeated
    assert good.payloads[0]["task"] == "rehearsal_dalal" and tactic.id in good.payloads[0]["user"]
