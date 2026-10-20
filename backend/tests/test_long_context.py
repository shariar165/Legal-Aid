"""Long documents and off-playbook depth: segmentation, map -> reduce Adversary, token pacing (offline, fake LLM)."""

import pytest

from ain import llm as llm_mod
from ain.agents import adversary, ingestion
from ain.agents.risk_analyst import load_rules
from ain.orchestrator import new_job, run_pipeline
from tests.conftest import RecordingLLM

LONG = "long_migrant_msa.txt"


def _clauses(docs, name):
    return ingestion.segment((docs / name).read_text(encoding="utf-8"))


def test_long_document_is_segmented_into_bounded_clauses(docs):
    clauses = _clauses(docs, LONG)
    assert len(clauses) > 150
    assert max(len(c.text) for c in clauses) <= ingestion.MAX_CLAUSE_CHARS
    # numbered sub-clauses and schedules start their own clause
    assert any(c.text.startswith("3.4 Passport.") for c in clauses)
    assert any(c.text.startswith("SCHEDULE 4") for c in clauses)
    assert len(adversary.chunks(clauses)) > 1


def test_over_long_clause_is_split_at_paragraphs():
    para = "The Worker shall follow the site rules. " * 40
    text = "1. Rules.\n" + "\n\n".join([para] * 4)
    clauses = ingestion.segment(text)
    assert len(clauses) >= 2 and all(len(c.text) <= ingestion.MAX_CLAUSE_CHARS for c in clauses)


def test_page_furniture_is_stripped():
    pages = [f"CONFIDENTIAL - Meghna Bridge\n{i}. Clause text number {i} goes on here.\nPage {i} of 5" for i in range(1, 6)]
    out = ingestion.strip_page_furniture(pages)
    assert all("CONFIDENTIAL" not in p and "Page" not in p for p in out)
    assert all(f"{i}. Clause text" in p for i, p in zip(range(1, 6), out))


def test_hero_documents_stay_one_part(docs):
    for name in ("migrant_my_contract.txt", "migrant_sa_contract.txt", "rmg_dhaka_epz.txt"):
        assert len(adversary.chunks(_clauses(docs, name))) == 1, name


async def test_long_document_map_reduce_finds_the_cross_part_trap(docs, monkeypatch):
    seen: dict = {}
    real = adversary._fake_reduce

    def spy(hyps, digests):
        seen["digests"] = digests
        return real(hyps, digests)

    monkeypatch.setattr(adversary, "_fake_reduce", spy)
    llm = RecordingLLM()
    r = await run_pipeline(new_job(LONG), (docs / LONG).read_bytes(), LONG, llm=llm, confirm_timeout=0.1)

    parts = adversary.chunks(_clauses(docs, LONG))
    maps = [p for p in llm.payloads if p["task"] == "adversary_map"]
    assert len(maps) == len(parts)
    # every part call stays within its budget (part text + the shared header)
    assert max(len(p["user"]) for p in maps) <= adversary.CHUNK_CHARS + 6000
    # the reduce step heard from every part
    assert len(seen["digests"]) == len(parts)
    assert sum(p["task"] == "adversary_reduce" for p in llm.payloads) == 1

    live = [k for k in r.risks if k.status != "dropped"]
    assert len(live) >= 3
    passport = next(c.id for c in r.document.clauses if c.text.startswith("3.4 Passport."))
    absconding = next(c.id for c in r.document.clauses if "Absconding." in c.text)
    trap = [k for k in live if k.origin == "adversary" and {passport, absconding} <= set(k.clause_ids)]
    assert trap, [k.title.en for k in live]
    ok = {v.claim.id for v in r.ledger if v.verdict in ("verified", "partial")}
    assert set(trap[0].claim_ids) & ok


@pytest.mark.parametrize("name", ["migrant_my_contract.txt", "migrant_sa_contract.txt", "rmg_dhaka_epz.txt"])
async def test_every_hero_document_has_three_off_playbook_risks(docs, name):
    r = await run_pipeline(new_job(name), (docs / name).read_bytes(), name, llm=RecordingLLM(), confirm_timeout=0.1)
    adv = [k for k in r.risks if k.status != "dropped" and k.origin == "adversary"]
    assert len(adv) >= 3, [k.title.en for k in adv]
    playbook = [k for k in r.risks if k.origin != "adversary"]
    rules = [x for x in load_rules() if x.active(r.route.pack_ids)]
    for k in adv:
        h = {"title_en": k.title.en, "finding": k.finding, "clause_ids": k.clause_ids, "category": k.category}
        assert adversary.duplicate_of(h, playbook, rules) is None, k.title.en


def test_hypotheses_that_restate_the_playbook_are_dropped():
    rules = load_rules()
    restated = [
        {"title_en": "No clause on minimum wage compliance", "category": "absence", "clause_ids": ["C3"], "finding": ""},
        {"title_en": "Extended payment term violates Bangladesh foreign exchange and export regulations", "category": "regime_conflict", "clause_ids": ["C3"], "finding": "Invoices are paid 150 days after shipment, beyond the period allowed for export proceeds."},
    ]
    for h in restated:
        assert adversary.duplicate_of(h, [], rules), h["title_en"]
    novel = {"title_en": "Passport held by the employer while the worker must renew his own iqama", "category": "interaction", "clause_ids": ["C4", "C5"], "finding": ""}
    assert adversary.duplicate_of(novel, [], rules) is None


def test_token_bucket_paces_and_resyncs():
    b = llm_mod._TokenBucket(8000)
    assert b.reserve(5000) == 0
    wait = b.reserve(5000)  # 2000 short: a quarter of a minute's refill
    assert 14 < wait < 16
    b2 = llm_mod._TokenBucket(8000)
    b2.sync("1000")  # the provider says only 1000 tokens are left this minute
    assert b2.reserve(2000) > 0
    assert llm_mod.estimate_tokens("a" * 400) < llm_mod.estimate_tokens("ক" * 400)


def test_messy_model_hypotheses_are_normalised():
    h = adversary._clean({"title_en": " Trap ", "queries": "one query only", "clause_ids": [3, "C4"], "key": None})
    assert h["title_en"] == "Trap" and h["queries"] == ["one query only"] and h["clause_ids"] == ["3", "C4"] and h["key"] == "h"
    assert adversary._clean({"title_en": None}) is None and adversary._clean("not a dict") is None


async def test_reduce_splits_into_a_tree_when_the_parts_do_not_fit_one_call(docs, monkeypatch):
    monkeypatch.setattr(adversary, "REDUCE_CHARS", 300)  # force the recursive path on the long sample
    llm = RecordingLLM()
    r = await run_pipeline(new_job(LONG), (docs / LONG).read_bytes(), LONG, llm=llm, confirm_timeout=0.1)
    reduces = [p for p in llm.payloads if p["task"] == "adversary_reduce"]
    assert len(reduces) > 1
    assert max(len(p["user"]) for p in reduces) < adversary.REDUCE_CHARS + 4000 + 6000
    assert any(k.origin == "adversary" and "abscond" in k.title.en.lower() for k in r.risks if k.status != "dropped")


async def test_a_failing_part_or_reduce_does_not_sink_the_analysis(docs):
    from ain.llm import LLMError

    def boom(role, user):
        if "PART 2 OF" in user or "CANDIDATE HYPOTHESES" in user:
            raise LLMError("every route failed (test)")
        return None

    class Flaky(RecordingLLM):
        async def json(self, *, role, system, user, task, agent, fake=None, **kw):
            if task in ("adversary_map", "adversary_reduce"):
                boom(role, user)
            return await super().json(role=role, system=system, user=user, task=task, agent=agent, fake=fake, **kw)

    r = await run_pipeline(new_job(LONG), (docs / LONG).read_bytes(), LONG, llm=Flaky(), confirm_timeout=0.1)
    assert [k for k in r.risks if k.status != "dropped"]
    assert any(e.data.get("skipped") for e in r.trace if e.agent == "Adversarial Counsel")
