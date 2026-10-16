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
    assert "Sunny, the Happy AI" in p["system"]
    assert risk.finding in p["user"] and "YOUR OPINION" in p["user"] and "Grey: Very." in p["user"]
    assert find_pii(p["system"] + p["user"]) == []


def test_replay_jobs_chat_live_only_when_keys_exist(monkeypatch):
    assert council.chat_mode("fake") == "fake"
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert council.chat_mode("replay") == "fake"
