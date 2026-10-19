"""LLM Council chat: in-character members, grounded only in the finished analysis (offline, fake LLM)."""

import pytest

from ain.agents import council
from ain.agents.pii import find_pii
from ain.llm import LLM
from ain.models import ChatTurn
from ain.orchestrator import new_job, run_pipeline
from tests.conftest import RecordingLLM


@pytest.fixture
async def result(docs):
    name = "rmg_dhaka_epz.txt"
    return await run_pipeline(new_job(name), (docs / name).read_bytes(), name, llm=RecordingLLM())


def _benched(r):
    return next(k for k in r.risks if k.bench and k.status != "dropped")


def test_members_are_the_three_personalities_in_seat_order():
    ms = council.members(LLM(mode="fake"))
    assert [(m.id, m.name, m.seat) for m in ms] == [("happy", "Sunny", "Justice A"), ("proud", "Regal", "Justice B"), ("gloomy", "Grey", "Justice C")]
    assert all(m.tagline and m.model for m in ms)


async def test_ask_all_three_gets_three_in_character_replies(result):
    risk = _benched(result)
    replies = await council.chat(RecordingLLM(), result, "Should I sign this?", ["happy", "proud", "gloomy"], risk, [])
    assert [x.member for x in replies] == ["happy", "proud", "gloomy"]
    assert replies[0].text.startswith("Good news") and "I fear" in replies[2].text
    allowed = {v.section.citation_id for v in result.ledger if v.claim.risk_id == risk.id and v.verdict in ("verified", "partial") and v.section}
    assert all(set(x.citations) <= allowed for x in replies)


async def test_ask_one_member_without_a_risk(result):
    replies = await council.chat(RecordingLLM(), result, "What worries you most?", ["gloomy"], None, [])
    assert len(replies) == 1 and replies[0].name == "Grey" and replies[0].text


async def test_citations_outside_the_context_are_stripped(result):
    risk = _benched(result)
    _, allowed = council.build_context(result, risk, council.BY_ID["proud"])
    llm = RecordingLLM(overrides={"council_chat": {"reply": "Per s.999.", "citations": ["BD-MADEUP-2099-s999", allowed[0]]}})
    [reply] = await council.chat(llm, result, "Cite it.", ["proud"], risk, [])
    assert reply.citations == [allowed[0]]


async def test_member_sees_redacted_context_own_opinion_and_history(result):
    risk = _benched(result)
    llm = RecordingLLM()
    history = [ChatTurn(speaker="user", text="Is this bad?"), ChatTurn(speaker="gloomy", text="Very.")]
    await council.chat(llm, result, "Do you agree with Grey?", ["happy"], risk, history)
    [p] = [x for x in llm.payloads if x["task"] == "council_chat"]
    assert "Sunny, the Happy AI" in p["system"] and council.BY_ID["happy"].lens in p["system"]
    assert risk.finding in p["user"] and "YOUR OPINION" in p["user"] and "Grey: Very." in p["user"]
    assert find_pii(p["system"] + p["user"]) == []


def test_replay_jobs_chat_live_only_when_keys_exist(monkeypatch):
    assert council.chat_mode("fake") == "fake"
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert council.chat_mode("replay") == "fake"


# ------------------------------------------------------------------ structured replies, Bangla, deliberation


async def test_replies_carry_a_position_and_confidence(result):
    risk = _benched(result)
    replies = await council.chat(RecordingLLM(), result, "Should I sign?", ["happy", "proud", "gloomy"], risk, [])
    assert all(x.position and x.confidence in ("high", "medium", "low") and x.round == 1 for x in replies)


async def test_bangla_answers_are_requested_and_returned(result):
    risk = _benched(result)
    llm = RecordingLLM()
    [reply] = await council.chat(llm, result, "সই করব?", ["gloomy"], risk, [], language="bn")
    [p] = [x for x in llm.payloads if x["task"] == "council_chat"]
    assert "Bangla" in p["system"]
    assert any("ঀ" <= ch <= "৿" for ch in reply.text + reply.position)


async def test_citation_ids_pasted_into_prose_are_removed(result):
    risk = _benched(result)
    _, allowed = council.build_context(result, risk, council.BY_ID["proud"])
    llm = RecordingLLM(overrides={"council_chat": {"position": "Clear", "reply": f"The text ({allowed[0]}) is plain.", "citations": [allowed[0]]}})
    [reply] = await council.chat(llm, result, "Cite it.", ["proud"], risk, [])
    assert allowed[0] not in reply.text and reply.text == "The text is plain." and reply.citations == [allowed[0]]


async def test_deliberation_round_two_and_chief_justice_ruling(result):
    risk = _benched(result)
    first = await council.chat(RecordingLLM(), result, "Should I sign?", ["happy", "proud", "gloomy"], risk, [])
    llm = RecordingLLM()
    rebuttals, ruling = await council.deliberate(llm, result, "Should I sign?", first, risk, [])
    assert [x.member for x in rebuttals] == ["happy", "proud", "gloomy"]
    assert all(x.round == 2 and x.responds_to in council.BY_ID and x.responds_to != x.member for x in rebuttals)
    assert ruling.agreement in ("unanimous", "majority", "split") and ruling.consensus and ruling.next_step
    tasks = [p["task"] for p in llm.payloads]
    assert tasks.count("council_rebuttal") == 3 and tasks.count("council_ruling") == 1
    # each member sees the colleagues' answers but is not shown its own as a colleague
    sunny = next(p for p in llm.payloads if p["task"] == "council_rebuttal" and "Sunny, the Happy AI" in p["system"])
    colleagues = sunny["user"].split("COLLEAGUES' ANSWERS:")[1]
    assert "Regal (proud)" in colleagues and "Grey (gloomy)" in colleagues and "Sunny (happy)" not in colleagues
    # the Chief Justice gets a neutral context (no member's "YOUR OPINION") and both rounds
    chair = next(p for p in llm.payloads if p["task"] == "council_ruling")
    assert "YOUR OPINION" not in chair["user"] and "ROUND 1" in chair["user"] and "ROUND 2" in chair["user"]
    assert all(find_pii(p["system"] + p["user"]) == [] for p in llm.payloads)


async def test_ruling_is_grounded_and_sanitised(result):
    risk = _benched(result)
    _, allowed = council.build_context(result, risk, None)
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])
    llm = RecordingLLM(
        overrides={
            "council_ruling": {
                "agreement": "unanimous",
                "consensus": f"All agree ({allowed[0]}).",
                "disagreements": [{"point": "x", "members": ["happy"]}],
                "next_step": "Ask for a change.",
                "citations": ["BD-MADEUP-2099-s1", allowed[0]],
            },
            "council_rebuttal": {"position": "p", "reply": "r", "revised": True, "responds_to": "happy", "citations": ["BD-MADEUP-2099-s1"]},
        }
    )
    rebuttals, ruling = await council.deliberate(llm, result, "Sign?", first, risk, [])
    assert ruling.citations == [allowed[0]] and allowed[0] not in ruling.consensus
    assert ruling.disagreements == []  # unanimous rulings carry no dispute list
    assert all(x.citations == [] for x in rebuttals)
    sunny = next(x for x in rebuttals if x.member == "happy")
    assert sunny.responds_to is None and sunny.revised  # a member cannot "respond to" itself
