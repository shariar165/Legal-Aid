"""LLM Council chat: in-character members, grounded only in the finished analysis (offline, fake LLM)."""

import pytest

from ain.agents import council
from ain.agents.pii import find_pii
from ain.llm import LLM
from ain.models import ChatTurn, CouncilDeliberateResponse
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
    assert "Sunny, the Constructive AI" in p["system"] and council.BY_ID["happy"].lens in p["system"]
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
    sunny = next(p for p in llm.payloads if p["task"] == "council_rebuttal" and "Sunny, the Constructive AI" in p["system"])
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


# ------------------------------------------------------------------ evidence gate: a change of view must rest on new law


ROLE_OF = {"bench_a": "happy", "bench_b": "proud", "bench_c": "gloomy"}


def _multi(r):
    """A benched risk with more than one verified citation, so a member can have something new to cite."""
    return next(k for k in r.risks if k.bench and k.status != "dropped" and len(council.build_context(r, k, council.BY_ID["proud"])[1]) > 1)


async def _revise(result, risk, sunny: dict, first=None):
    """Round 2 where Sunny answers `sunny` and the other two keep their view."""
    first = first or await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])

    def answer(role, user):
        if ROLE_OF[role] == "happy":
            return {"reply": "r", "responds_to": "gloomy", **sunny}
        mine = next(x for x in first if x.member == ROLE_OF[role])
        return {"position": mine.position, "reply": "r", "revised": False, "severity": mine.severity, "responds_to": "happy", "citations": []}

    llm = RecordingLLM(overrides={"council_rebuttal": answer})
    rebuttals, ruling = await council.deliberate(llm, result, "Sign?", first, risk, [])
    return first, rebuttals[0], ruling, llm


def _new_law(result, risk):
    _, allowed = council.build_context(result, risk, council.BY_ID["happy"])
    return allowed[1], council._fake_quote(council._sections(result, allowed)[allowed[1]])


async def test_revision_on_a_new_citation_with_a_real_quote_counts(result):
    risk = _multi(result)
    cid, quote = _new_law(result, risk)
    first, sunny, ruling, _ = await _revise(result, risk, {"position": "Heavier than I said", "revised": True, "severity": "critical", "changed_because": {"citation_id": cid, "quote": quote}})
    assert cid not in first[0].citations
    assert sunny.flip_basis == "evidence" and sunny.changed_because.citation_id == cid and cid in sunny.citations
    assert ruling.votes[0].severity == "critical" and ruling.votes[0].position == "Heavier than I said"


async def test_revision_citing_a_section_already_cited_in_round_one_is_pressure(result):
    risk = _multi(result)
    _, allowed = council.build_context(result, risk, council.BY_ID["happy"])
    quote = council._fake_quote(council._sections(result, allowed)[allowed[0]])
    first, sunny, ruling, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "severity": "critical", "changed_because": {"citation_id": allowed[0], "quote": quote}})
    assert allowed[0] in first[0].citations and sunny.flip_basis == "pressure" and "already cited" in sunny.flip_note
    assert ruling.votes[0].severity == first[0].severity and ruling.votes[0].position == first[0].position


async def test_revision_with_a_fabricated_quote_is_pressure_and_shows_no_evidence(result):
    risk = _multi(result)
    cid, _ = _new_law(result, risk)
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "severity": "critical", "changed_because": {"citation_id": cid, "quote": "the employer must pay a penalty of ten million taka at once"}})
    assert sunny.flip_basis == "pressure" and sunny.changed_because is None and "not found" in sunny.flip_note
    assert sunny.revised  # it is still shown as a claimed change


@pytest.mark.parametrize("quote", ["", "the", "law"])
async def test_empty_or_trivial_quotes_do_not_pass_the_fidelity_gate(result, quote):
    risk = _multi(result)
    cid, _ = _new_law(result, risk)
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "changed_because": {"citation_id": cid, "quote": quote}})
    assert sunny.flip_basis == "pressure"


async def test_revision_citing_outside_allowed_is_pressure(result):
    risk = _multi(result)
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "severity": "critical", "changed_because": {"citation_id": "BD-MADEUP-2099-s1", "quote": "a perfectly long quotation"}})
    assert sunny.flip_basis == "pressure" and sunny.changed_because is None and "outside" in sunny.flip_note
    assert "BD-MADEUP-2099-s1" not in sunny.citations


async def test_a_revision_with_no_evidence_at_all_is_pressure(result):
    risk = _multi(result)
    _, sunny, _, _ = await _revise(result, risk, {"position": "You are right", "revised": True})
    assert sunny.flip_basis == "pressure" and "no new section" in sunny.flip_note


async def test_undeclared_severity_change_is_pressure(result):
    risk = _multi(result)
    first, sunny, ruling, _ = await _revise(result, risk, {"position": None, "revised": False, "severity": "low"})
    assert first[0].severity != "low" and not sunny.revised and sunny.flip_basis == "pressure" and "without declaring" in sunny.flip_note
    assert sunny.severity == "low" and ruling.votes[0].severity == first[0].severity  # shown as claimed; round 1 is what counts




async def test_a_missing_round_two_severity_is_not_a_flip_and_round_one_stands(result):
    risk = _multi(result)
    first, sunny, ruling, _ = await _revise(result, risk, {"position": None, "revised": False, "severity": "extreme"})
    assert sunny.severity is None and sunny.flip_basis is None and ruling.votes[0].severity == first[0].severity


async def test_the_ruling_context_lists_which_revisions_counted_and_why(result):
    risk = _multi(result)
    cid, quote = _new_law(result, risk)
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])

    def answer(role, user):
        if ROLE_OF[role] == "happy":
            return {"position": "Heavier", "reply": "r", "revised": True, "severity": "critical", "changed_because": {"citation_id": cid, "quote": quote}}
        if ROLE_OF[role] == "gloomy":
            return {"position": "CLAIMED-POSITION", "reply": "r", "revised": True, "severity": "low"}
        return {"position": first[1].position, "reply": "r", "revised": False, "severity": first[1].severity}

    llm = RecordingLLM(overrides={"council_rebuttal": answer})
    _, ruling = await council.deliberate(llm, result, "Sign?", first, risk, [])
    chair = next(p for p in llm.payloads if p["task"] == "council_ruling")
    assert "COUNTED POSITIONS" in chair["system"] and "do not weigh the position they claimed" in chair["system"]
    block = chair["user"].split("COUNTED POSITIONS:")[1]
    assert f"Sunny (happy) revised, and it COUNTS: it rests on {cid}" in block
    assert "Grey (gloomy) claimed a change of view that does NOT count" in block and "Gave no new section" in block
    assert "CLAIMED-POSITION" not in chair["user"]  # never read as the member's own, in any block
    assert first[2].position in block
    assert [v.flip_basis for v in ruling.votes] == ["evidence", None, "pressure"]
    assert ruling.votes[2].severity == first[2].severity


async def test_ruling_context_says_when_nobody_changed_their_view(result):
    risk = _benched(result)
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])
    llm = RecordingLLM(overrides={"council_rebuttal": lambda role, user: {"reply": "r", "revised": False}})
    await council.deliberate(llm, result, "Sign?", first, risk, [])
    assert "No member changed their view." in next(p for p in llm.payloads if p["task"] == "council_ruling")["user"]


async def test_severity_is_asked_for_only_when_a_risk_is_in_focus(result):
    risk = _benched(result)
    llm = RecordingLLM()
    [focused] = await council.chat(llm, result, "How bad?", ["proud"], risk, [])
    [general] = await council.chat(llm, result, "How bad?", ["proud"], None, [])
    systems = [p["system"] for p in llm.payloads if p["task"] == "council_chat"]
    assert '"severity"' in systems[0] and '"severity"' not in systems[1]
    assert focused.severity in ("low", "medium", "high", "critical") and general.severity is None


async def test_a_bad_severity_from_the_model_never_reaches_the_reply(result):
    risk = _benched(result)
    [reply] = await council.chat(RecordingLLM(overrides={"council_chat": {"reply": "r", "severity": " HIGH "}}), result, "?", ["proud"], risk, [])
    assert reply.severity == "high"


async def test_the_offline_stand_in_walks_both_paths_through_the_gate(result):
    risk = _multi(result)
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])
    rebuttals, ruling = await council.deliberate(RecordingLLM(), result, "Sign?", first, risk, [])
    assert [x.flip_basis for x in rebuttals] == ["evidence", None, "pressure"]
    assert rebuttals[0].changed_because and rebuttals[2].changed_because is None
    assert rebuttals[2].severity != first[2].severity and ruling.votes[2].severity == first[2].severity



async def test_whole_contract_round_two_shows_text_to_quote_within_a_budget(result):
    plain, allowed = council.build_context(result, None, council.BY_ID["proud"])
    assert "TEXT:" not in plain
    shown, same = council.build_context(result, None, council.BY_ID["proud"], excerpts=True)
    assert same == allowed
    excerpts = [x for x in shown.split("\n") if x.startswith("  TEXT: ")]
    assert len(excerpts) == len(allowed) and all(len(x) <= council.EXCERPT_CHARS + 8 for x in excerpts)

    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], None, [])
    llm = RecordingLLM()
    rebuttals, _ = await council.deliberate(llm, result, "Sign?", first, None, [])
    assert "  TEXT: " in next(p for p in llm.payloads if p["task"] == "council_rebuttal")["user"]
    assert "  TEXT: " not in next(p for p in llm.payloads if p["task"] == "council_ruling")["user"]
    assert all(x.flip_basis is None and x.severity is None for x in rebuttals)


async def test_a_whole_contract_revision_can_quote_the_excerpt_it_was_shown(result):
    _, allowed = council.build_context(result, None, council.BY_ID["happy"])
    shown = council.build_context(result, None, council.BY_ID["happy"], excerpts=True)[0]
    excerpt = next(x for x in shown.split("\n") if x.startswith("  TEXT: "))[8:]
    cid = allowed[0]
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], None, [])
    first[0].citations = []
    _, sunny, _, _ = await _revise_whole(result, first, {"position": "Heavier", "revised": True, "changed_because": {"citation_id": cid, "quote": excerpt[:40]}})
    assert sunny.flip_basis == "evidence"


async def _revise_whole(result, first, sunny):
    def answer(role, user):
        mine = next(x for x in first if x.member == ROLE_OF[role])
        return {"reply": "r", **sunny} if ROLE_OF[role] == "happy" else {"position": mine.position, "reply": "r", "revised": False}

    rebuttals, ruling = await council.deliberate(RecordingLLM(overrides={"council_rebuttal": answer}), result, "Sign?", first, None, [])
    return first, rebuttals[0], ruling, None


async def test_a_section_known_only_to_the_job_can_be_evidence(result):
    """An uploaded policy's clauses live in the job's overlay, not the corpus: the quote is checked against the ledger's copy."""
    risk = _multi(result)
    _, allowed = council.build_context(result, risk, council.BY_ID["happy"])
    row = next(v for v in result.ledger if v.section and v.section.citation_id == allowed[1])
    row.section = row.section.model_copy(update={"citation_id": "POLICY-JOB-ONLY-c7", "text": "The employer shall return every identity document on the day it is asked for."})
    first, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "changed_because": {"citation_id": "POLICY-JOB-ONLY-c7", "quote": "return every identity document"}})
    assert sunny.flip_basis == "evidence"


async def test_bangla_quotes_are_matched_after_nfc_normalisation(result):
    import unicodedata

    risk = _multi(result)
    _, allowed = council.build_context(result, risk, council.BY_ID["happy"])
    row = next(v for v in result.ledger if v.section and v.section.citation_id == allowed[1])
    row.section = row.section.model_copy(update={"text": unicodedata.normalize("NFC", "কোনো মালিক শ্রমিকের পাসপোর্ট আটকাইয়া রাখিতে পারিবে না।")})
    quote = unicodedata.normalize("NFD", "শ্রমিকের পাসপোর্ট আটকাইয়া")
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "changed_because": {"citation_id": allowed[1], "quote": quote}})
    assert sunny.flip_basis == "evidence"


async def test_the_deliberate_endpoint_shape_round_trips_the_new_fields(result):
    risk = _multi(result)
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])
    rebuttals, ruling = await council.deliberate(RecordingLLM(), result, "Sign?", first, risk, [])
    data = CouncilDeliberateResponse(rebuttals=rebuttals, ruling=ruling).model_dump()
    assert data["rebuttals"][0]["changed_because"]["citation_id"] and data["ruling"]["votes"][2]["flip_basis"] == "pressure"


# ------------------------------------------------------------------ an undeclared flip is read from structured fields


async def test_a_quiet_change_of_verdict_is_pressure(result):
    risk = _multi(result)
    first, sunny, ruling, _ = await _revise(result, risk, {"position": None, "revised": False, "verdict": "rejects"})
    assert first[0].verdict == "supports" and sunny.flip_basis == "pressure" and "without declaring" in sunny.flip_note
    assert sunny.verdict == "rejects" and ruling.votes[0].verdict == "supports"


async def test_a_quiet_change_of_stance_on_the_whole_contract_is_pressure(result):
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], None, [])
    assert first[0].stance == "renegotiate"
    _, sunny, ruling, _ = await _revise_whole(result, first, {"position": None, "revised": False, "stance": "sign"})
    assert sunny.flip_basis == "pressure" and ruling.votes[0].stance == "renegotiate"


@pytest.mark.parametrize(
    "said, now",
    [
        ("Do not sign clause 16", "Do not sign clause 16. The restraint-of-trade clause may be void unless a court finds the limit reasonable."),
        ("Severity remains high; no action required.", "Severity remains high"),
        ("Sign only if 120-day notice is added", "I maintain a high-severity risk"),
    ],
)
async def test_restating_the_same_view_is_never_a_flip(result, said, now):
    """Real pairs from the first live pressure trap: each was wrongly labelled while position text was compared."""
    risk = _multi(result)
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])
    first[0].position = said
    _, sunny, _, _ = await _revise(result, risk, {"position": now, "revised": False, "severity": first[0].severity, "verdict": first[0].verdict}, first)
    assert sunny.flip_basis is None and sunny.flip_note == ""


async def test_the_stance_fields_match_the_question(result):
    llm = RecordingLLM()
    risk = _benched(result)
    [focused] = await council.chat(llm, result, "How bad?", ["proud"], risk, [])
    [general] = await council.chat(llm, result, "How bad?", ["proud"], None, [])
    systems = [p["system"] for p in llm.payloads if p["task"] == "council_chat"]
    assert '"verdict"' in systems[0] and '"stance"' not in systems[0] and '"stance"' in systems[1] and '"verdict"' not in systems[1]
    assert focused.verdict == "supports" and focused.stance is None and general.stance == "renegotiate" and general.verdict is None


async def test_a_bad_verdict_or_stance_from_the_model_is_no_comparison(result):
    risk = _multi(result)
    first, sunny, ruling, _ = await _revise(result, risk, {"position": None, "revised": False, "verdict": ["rejects"]})
    assert sunny.verdict is None and sunny.flip_basis is None and ruling.votes[0].verdict == first[0].verdict


# ------------------------------------------------------------------ wider evidence: retrieved sections


async def test_round_two_gets_three_to_five_more_sections_that_are_in_force_and_apply(result):
    risk = _benched(result)
    _, allowed = council.build_context(result, risk, None)
    extras = await council.extra_sections(result, risk, allowed)
    assert 3 <= len(extras) <= 5
    assert not {s.citation_id for s in extras} & set(allowed)
    assert all(s.status != "repealed" and set(s.packs) & result.route.pack_ids for s in extras)
    assert not any(s.citation_id.startswith("BD-LABOUR-2006") for s in extras)  # the EPZ sample switches the Labour Act off


async def test_every_member_sees_the_further_law_but_the_chief_justice_cannot_cite_it(result):
    risk = _benched(result)
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])
    llm = RecordingLLM()
    _, ruling = await council.deliberate(llm, result, "Sign?", first, risk, [])
    members = [p["user"] for p in llm.payloads if p["task"] == "council_rebuttal"]
    assert len(members) == 3 and all("FURTHER LAW" in u and "CONTRACT CLAUSES:" in u for u in members)
    chair = next(p for p in llm.payloads if p["task"] == "council_ruling")["user"]
    assert "FURTHER LAW" not in chair and "CONTRACT CLAUSES:" not in chair


async def test_a_retrieved_section_can_be_evidence_and_is_marked_unverified(result):
    risk = _benched(result)
    _, allowed = council.build_context(result, risk, None)
    extra = (await council.extra_sections(result, risk, allowed))[0]
    quote = council._fake_quote(extra)
    _, sunny, ruling, llm = await _revise(result, risk, {"position": "Heavier", "revised": True, "severity": "critical", "changed_because": {"citation_id": extra.citation_id, "quote": quote}})
    assert sunny.flip_basis == "evidence" and sunny.changed_because.verified is False and sunny.changed_because.label and sunny.changed_because.url == extra.url
    assert extra.citation_id not in ruling.citations
    chair = next(p for p in llm.payloads if p["task"] == "council_ruling")["user"]
    assert extra.citation_id in chair and "has not been checked against this risk" in chair


async def test_a_ledger_section_stays_marked_verified(result):
    risk = _multi(result)
    cid, quote = _new_law(result, risk)
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "changed_because": {"citation_id": cid, "quote": quote}})
    assert sunny.changed_because.verified is True


async def test_a_section_verified_for_another_risk_is_not_in_this_members_list(result):
    risk = _multi(result)
    _, allowed = council.build_context(result, risk, None)
    extras = {s.citation_id for s in await council.extra_sections(result, risk, allowed)}
    other = next(v for v in result.ledger if v.section and v.verdict == "verified" and v.claim.risk_id != risk.id and v.section.citation_id not in allowed and v.section.citation_id not in extras)
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "changed_because": {"citation_id": other.section.citation_id, "quote": council._fake_quote(other.section)}})
    assert sunny.flip_basis == "pressure" and "outside" in sunny.flip_note


async def test_a_repealed_section_is_never_offered(result, monkeypatch):
    risk = _benched(result)
    corpus = council.get_corpus()
    repealed = next(s for s in corpus.sections if s.status == "repealed")
    in_force = next(s for s in corpus.sections if s.status == "in_force")
    monkeypatch.setattr(type(corpus), "search", lambda self, q, packs=None, k=8, include_repealed=True: [(repealed, 1.0), (in_force, 0.9)])
    assert [s.citation_id for s in await council.extra_sections(result, risk, [])] == [in_force.citation_id]


async def test_a_whole_contract_deliberation_retrieves_nothing_extra(result):
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], None, [])
    llm = RecordingLLM()
    await council.deliberate(llm, result, "Sign?", first, None, [])
    assert all("FURTHER LAW" not in p["user"] for p in llm.payloads)


async def test_round_two_prompts_stay_within_a_budget(result):
    risk = _multi(result)
    extras = await council.extra_sections(result, risk, council.build_context(result, risk, None)[1])
    further = council._further_material(result, risk, extras)
    assert len(further) < council.EXTRA_SECTIONS * (council.EXTRA_CHARS + 200) + council.CLAUSE_BUDGET + 400


# ------------------------------------------------------------------ wider evidence: the contract's own words


def _clause(result, risk):
    return next(c for c in result.document.clauses if c.id == risk.clause_ids[0])


async def test_a_quote_from_a_new_contract_clause_counts(result):
    risk = _benched(result)
    c = _clause(result, risk)
    quote = " ".join(c.text.split()[:9])
    first, sunny, ruling, llm = await _revise(result, risk, {"position": "Heavier", "revised": True, "severity": "critical", "changed_because": {"clause_id": c.id, "quote": quote}})
    assert sunny.flip_basis == "evidence" and sunny.changed_because.clause_id == c.id and sunny.changed_because.citation_id is None
    assert sunny.changed_because.label == f"Clause {c.id}" and ruling.votes[0].severity == "critical"
    assert sunny.citations == []  # a clause is not a law: it never becomes a citation
    assert f"contract clause {c.id}" in next(p for p in llm.payloads if p["task"] == "council_ruling")["user"]


async def test_a_clause_already_relied_on_in_round_one_is_pressure(result):
    risk = _benched(result)
    c = _clause(result, risk)
    first = await council.chat(RecordingLLM(overrides={"council_chat": {"reply": "r", "clause_ids": [c.id, "C999"]}}), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])
    assert first[0].clause_ids == [c.id]  # one that is not in the contract is dropped
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "changed_because": {"clause_id": c.id, "quote": " ".join(c.text.split()[:9])}}, first)
    assert sunny.flip_basis == "pressure" and "already relied" in sunny.flip_note and sunny.changed_because is None


async def test_a_fabricated_clause_quote_is_pressure(result):
    risk = _benched(result)
    c = _clause(result, risk)
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "changed_because": {"clause_id": c.id, "quote": "the worker shall forfeit ten years of wages at once"}})
    assert sunny.flip_basis == "pressure" and "clause's text" in sunny.flip_note


async def test_a_clause_that_is_not_in_the_contract_is_pressure(result):
    risk = _benched(result)
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "changed_because": {"clause_id": "C999", "quote": "a perfectly long quotation"}})
    assert sunny.flip_basis == "pressure" and "not in this contract" in sunny.flip_note


async def test_a_trivial_clause_quote_is_pressure(result):
    risk = _benched(result)
    c = _clause(result, risk)
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "changed_because": {"clause_id": c.id, "quote": "the"}})
    assert sunny.flip_basis == "pressure"


async def test_a_section_wins_when_a_model_gives_both_sources(result):
    risk = _multi(result)
    cid, quote = _new_law(result, risk)
    _, sunny, _, _ = await _revise(result, risk, {"position": "Heavier", "revised": True, "changed_because": {"citation_id": cid, "clause_id": "C999", "quote": quote}})
    assert sunny.flip_basis == "evidence" and sunny.changed_because.citation_id == cid and sunny.changed_because.clause_id is None


async def test_clause_text_sent_to_the_models_is_redacted(result):
    risk = _benched(result)
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])
    llm = RecordingLLM()
    await council.deliberate(llm, result, "Sign?", first, risk, [])
    assert all(find_pii(p["system"] + p["user"]) == [] for p in llm.payloads)


async def test_the_offline_stand_in_moves_on_the_contract_on_an_adversary_risk(result):
    risk = next(k for k in result.risks if k.origin == "adversary" and k.bench and k.status != "dropped")
    first = await council.chat(RecordingLLM(), result, "Sign?", ["happy", "proud", "gloomy"], risk, [])
    rebuttals, _ = await council.deliberate(RecordingLLM(), result, "Sign?", first, risk, [])
    assert rebuttals[1].flip_basis == "evidence" and rebuttals[1].changed_because.clause_id
