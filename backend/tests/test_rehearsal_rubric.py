"""Rehearsal Council: the readiness rubric on scripted transcripts. Decided in code; no model is involved."""

import pytest

from ain.models import RehearsalTurn
from ain.rehearsal import rubric


def _script(*rows):
    """(tactic_id, reply, action) per turn."""
    return [RehearsalTurn(n=i, tactic_id=t, dalal_line="...", worker_reply=r, action=a) for i, (t, r, a) in enumerate(rows, 1)]


def _status(turns):
    score, items = rubric.score(turns)
    return score, {i.id: i.status for i in items}


def test_prepared_worker_scores_full_marks():
    turns = _script(
        ("trust_me", "ভাই, আপনার এজেন্সির লাইসেন্স নম্বরটা কী?", "none"),
        ("lucrative_job", "বেতন কত সেটা লিখিত চুক্তিতে দেখাবেন?", "none"),
        ("passport_for_processing", "না ভাই, পাসপোর্ট আমার কাছেই থাকবে।", "none"),
        ("pay_in_parts", "আগে মোট খরচ কত সেটা কাগজে লিখে দিন।", "none"),
        ("no_receipt", "যত টাকাই দিই, রসিদ দিতে হবে।", "none"),
        ("contract_later", "পরিবারের সঙ্গে কথা বলে জানাব।", "none"),
    )
    score, s = _status(turns)
    assert score == 100 and set(s.values()) == {"met"}


def test_naive_worker_who_pays_and_hands_over_the_passport_scores_low():
    turns = _script(
        ("trust_me", "ঠিক আছে ভাই, আপনাকে বিশ্বাস করি।", "none"),
        ("lucrative_job", "আলহামদুলিল্লাহ, ভালো খবর।", "none"),
        ("passport_for_processing", "ঠিক আছে, নিয়ে যান।", "gave_passport"),
        ("pay_in_parts", "ঠিক আছে, এখনই দিচ্ছি।", "none"),
        ("no_receipt", "রসিদ লাগবে না, আপনি তো চেনা মানুষ।", "none"),
        ("contract_later", "চুক্তি পরে দিলেও চলবে।", "paid"),
    )
    score, s = _status(turns)
    assert score == 0
    assert s["kept_passport"] == "missed" and s["no_pay_on_spot"] == "missed" and s["receipt"] == "missed"


def test_contract_asked_after_paying_does_not_count():
    turns = _script(("trust_me", "নিন টাকা।", "paid"), ("contract_later", "এখন চুক্তিটা দেখান।", "none"))
    _, s = _status(turns)
    assert s["written_contract_first"] == "missed" and s["no_pay_on_spot"] == "missed"


@pytest.mark.parametrize(
    "reply, item, expected",
    [
        ("রসিদ লাগবে না", "receipt", False),
        ("receipt lagbe na bhai", "receipt", False),
        ("Will you give me a receipt?", "receipt", True),
        ("rosid diben to?", "receipt", True),
        ("can I see the contract first?", "written_contract_first", True),
        ("chukti age dekhan", "written_contract_first", True),
        ("চুক্তি দরকার নেই", "written_contract_first", False),
        ("is your agency licensed?", "licence", True),
        ("আপনি কি বিএমইটি-তে নিবন্ধিত?", "licence", True),
        ("what is the total cost? please write it down", "total_cost_in_writing", True),
        ("সব মিলিয়ে খরচ কত, কাগজে লিখে দেবেন?", "total_cost_in_writing", True),
        ("খরচ কত?", "total_cost_in_writing", False),  # not in writing
        ("passport dibo na", "kept_passport", True),
        ("I will keep my passport", "kept_passport", True),
    ],
)
def test_reply_patterns_bangla_english_banglish(reply, item, expected):
    i = next(x for x in rubric.items() if x.id == item)
    assert rubric.asks(i, reply) is expected


def test_passport_is_not_tested_unless_its_tactic_was_played_and_nothing_is_tested_without_replies():
    _, s = _status(_script(("trust_me", "লাইসেন্স আছে?", "none")))
    assert s["kept_passport"] == "not_tested"
    score, s = _status(_script(("trust_me", "", "none")))
    assert score == 0 and set(s.values()) == {"not_tested"}


def test_checklist_lists_missed_items_first_and_is_complete():
    _, items = rubric.score(_script(("trust_me", "রসিদ দেবেন?", "none")))
    lst = rubric.checklist(items)
    assert len(lst) == len(rubric.items())
    asks = {i.id: i.ask for i in rubric.items()}
    met = {i.id for i in items if i.status == "met"}
    assert met == {"receipt", "no_pay_on_spot"}  # asked for a receipt, and paid nothing
    assert {q.en for q in lst[-2:]} == {asks[m].en for m in met}  # what was done goes last
