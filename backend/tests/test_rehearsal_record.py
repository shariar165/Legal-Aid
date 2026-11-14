"""Rehearsal Council: the Promise Record. Law checks are verbatim and gated, names and phones never reach a model and
are stored only encrypted, and the DOCX carries no figure that is not the worker's own or the corpus's."""

import io
import re

from docx import Document as Docx

from ain import config
from ain.agents.pii import BN_DIGITS
from ain.models import PromiseContacts, PromisedTerms, RehearsalSetup, RehearsalTurn
from ain.rehearsal import record, session, store
from ain.retrieval import get_corpus, nfc
from tests.conftest import RecordingLLM

NAME, PHONE, AGENCY = "রহিম উদ্দিন", "01712345678", "সোনালী ভ্রমণ"


def test_promise_checks_and_paths_are_verbatim_and_in_force(corpus):
    raw = record.checks()
    claims = [c for ch in raw["checks"] for c in ch["claims"]] + raw["paths"]
    for c in claims:
        sec = corpus.get(c["citation_id"])
        assert sec is not None and sec.status == "in_force", c["citation_id"]
        assert nfc(c["quote"]) in nfc(sec.text), f"quote not verbatim in {c['citation_id']}"
        assert not re.search(r"ধারা|section|s\.\d", c["proposition"], re.I), "a proposition names a section"
    assert [p["citation_id"] for p in raw["paths"]][0] == "BD-OEMA-2013-s41"  # the complaint section comes first


async def test_record_shows_only_gated_law_and_no_cost_ceiling():
    setup = RehearsalSetup(country="Malaysia", promises=PromisedTerms(salary="৪০,০০০ টাকা", total_cost="৫ লাখ", passport_keeper="agent"))
    r = await record.build(RecordingLLM(), setup, PromiseContacts())
    fields = {row.field: row for row in r.rows}
    assert {"passport_keeper", "has_contract", "through_dalal", "salary", "total_cost"} <= set(fields)
    for row in r.rows:
        assert all(v.verdict in ("verified", "partial") for v in row.checks)
    passport = [v.claim.citation_id for v in fields["passport_keeper"].checks]
    assert "BD-OEMA-2013-s31" in passport
    # the destination's playbook anchor was checked too, but its proposition gives "RM100,000" where the statute uses
    # words, so it is held back: no figure that is not in the section's own text
    assert any(c.startswith("MY-") for c in fields["passport_keeper"].unverified)
    salary = [v.claim.citation_id for v in fields["salary"].checks]
    assert "MY-MWO-2024-p3" in salary  # the minimum wage from countries.yaml, a figure the order states
    assert [v.claim.citation_id for v in fields["total_cost"].checks] == ["BD-OEMA-2013-s21"]
    assert {p.id for p in r.paths} == {"complaint", "recovery", "civil_suit", "legal_aid", "mission"}
    assert not re.search(r"\d", record.cost_note().bn.translate(BN_DIGITS) + record.cost_note().en)


async def test_a_claim_that_fails_the_gates_is_not_shown(monkeypatch):
    raw = record.checks()
    bad = {**raw, "checks": [{**raw["checks"][0], "claims": [{"citation_id": "BD-OEMA-2013-s31", "quote": "এই কথা আইনে নেই কোথাও", "proposition": "পাসপোর্ট রাখলে এজেন্টের ফাঁসি হয়।"}]}]}
    monkeypatch.setattr(record, "checks", lambda: bad)
    r = await record.build(RecordingLLM(), RehearsalSetup(promises=PromisedTerms(passport_keeper="agent")), PromiseContacts())
    assert r.rows[0].checks == [] and r.rows[0].unverified == ["BD-OEMA-2013-s31"]
    assert "BD-OEMA-2013-s31" in r.unverified


def _session_with_pii():
    s = session.create("u-test", RehearsalSetup(promises=PromisedTerms(salary="৪০,০০০ টাকা")))
    return s


async def test_contacts_and_typed_names_never_reach_a_model_and_are_encrypted(monkeypatch):
    from ain import auth

    with auth._db() as c:
        c.execute("INSERT OR IGNORE INTO users (id, created_at, is_guest) VALUES ('u-test', 0, 1)")
    llm = RecordingLLM()
    monkeypatch.setattr(session.Runner, "llm", lambda self: llm)
    r = _session_with_pii()
    await session.open_turn(r)
    # the record's contacts are typed first, then the worker mentions the agent in a reply
    contacts = session.set_contacts(r, PromiseContacts(agent_name=NAME, agent_phone=PHONE, agency_name=AGENCY, notes=f"{NAME} বলেছেন সব ঠিক"))
    assert NAME not in contacts.model_dump_json() and PHONE not in contacts.model_dump_json()
    await session.answer(r, f"{NAME} ভাই, রসিদ দেবেন? আমার নাম করিম মিয়া, ফোন {PHONE}", "none")
    await session.finish(r)
    sent = " ".join(p["system"] + p["user"] for p in llm.payloads)
    assert llm.payloads and all(v not in sent for v in (NAME, PHONE, AGENCY, "করিম মিয়া"))
    raw = (config.RUNS_DIR / f"rehearsal-{r.session.id}.json.enc").read_bytes()
    assert all(v.encode() not in raw for v in (NAME, PHONE, "করিম"))
    assert store.load(r.session.id).mapping  # the mapping is kept, but only inside the encrypted file

    r.session.record.contacts = contacts
    doc = Docx(io.BytesIO(record.record_docx(r.session)))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert NAME in text and PHONE in text  # rendered on this machine for the worker
    assert "BD-OEMA-2013-s41" not in text and "অভিযোগ" in text  # pathways by label, not by id
    session.forget(r.session.id)


async def test_docx_has_no_figure_that_is_not_the_workers_or_the_corpus(monkeypatch):
    from ain import auth

    with auth._db() as c:
        c.execute("INSERT OR IGNORE INTO users (id, created_at, is_guest) VALUES ('u-test', 0, 1)")
    r = session.create("u-test", RehearsalSetup(country="Malaysia", promises=PromisedTerms(salary="৪০,০০০ টাকা", total_cost="৫ লাখ", passport_keeper="agent")))
    r.session.turns.append(RehearsalTurn(n=1, tactic_id="trust_me", dalal_line="x", worker_reply="রসিদ দেবেন?"))
    await session.finish(r)
    doc = Docx(io.BytesIO(record.record_docx(r.session)))
    text = "\n".join(p.text for p in doc.paragraphs).translate(BN_DIGITS)
    allowed = " ".join(
        [r.session.record.created_at, "40,000 5", " ".join(s.text + s.section + s.url + str(s.year) for s in get_corpus().sections if s.citation_id.startswith(("BD-OEMA", "MY-")))]
    ).translate(BN_DIGITS)
    seen = set(re.findall(r"\d+", allowed))
    stray = [n for n in re.findall(r"\d+", text) if n not in seen]
    assert not stray, f"unsourced figures in the record: {stray}"
    session.forget(r.session.id)
