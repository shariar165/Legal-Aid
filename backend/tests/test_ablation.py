"""The plain-chatbot comparison counts only what Jukti can check (spec 29 step 2.2)."""

import pytest

from ain.agents import ablation
from ain.llm import LLM
from ain.orchestrator import new_job, run_pipeline
from tests.conftest import RecordingLLM

MY, EPZ = "migrant_my_contract.txt", "rmg_dhaka_epz.txt"


async def _result(docs, name):
    return await run_pipeline(new_job(name), (docs / name).read_bytes(), name, "sample", "fake")


def _plain(*citations):
    """a plain answer citing (act, section, claim) triples"""
    return {"ablation_plain": {"risks": [{"risk": "R", "citations": [{"act": a, "section": s, "claim": c} for a, s, c in citations]}]}}


async def _rows(corpus, result, *citations):
    ab = await ablation.run(RecordingLLM(_plain(*citations)), corpus, result)
    return ab, [(r["outcome"], r.get("why")) for r in ab.rows]


@pytest.mark.parametrize("section", ["s.28A", "28(A)", "২৮ক", "section 28A"])
def test_a_real_lettered_section_resolves_in_every_form(corpus, section):
    assert ablation.lookup(corpus, "Bangladesh Labour Act 2006", section) == ("BD-LABOUR-2006", "BD-LABOUR-2006-s28A")


@pytest.mark.parametrize(("section", "no"), [("s.12(1)(f)", "12"), ("28(a)", "28"), ("Art. 7", "7"), ("Article 9", "9"), ("২৭", "27")])
def test_a_clause_in_brackets_is_not_part_of_the_section_number(section, no):
    assert ablation.section_no(section) == no


async def test_law_outside_the_corpus_is_never_called_wrong(docs, corpus):
    result = await _result(docs, MY)
    ab, rows = await _rows(corpus, result,
                           ("Passports Act 1966 (Malaysia)", "12(1)(f)", "It is an offence for an employer to keep a worker's passport."),
                           ("Employment Act 1955 (Malaysia)", "999", "An excerpt of this act is held, but not this section."))
    assert rows == [("outside_corpus", None), ("outside_corpus", None)]
    assert "possible hallucination" not in " ".join(r["detail"] for r in ab.rows)
    assert (ab.outside_corpus, ab.checkable, ab.wrong, ab.fabricated) == (2, 0, 0, 0)


async def test_a_missing_section_of_an_act_held_in_full_is_fabricated(docs, corpus):
    result = await _result(docs, MY)
    ab, rows = await _rows(corpus, result,
                           ("Bangladesh Labour Act 2006", "999", "Workers get a bonus every month."),
                           ("Bangladesh Labour Act 2006", "২৮ক", "A real lettered section is never fabricated."))
    assert rows[0] == ("fabricated", None)
    assert rows[1][0] != "fabricated"
    assert ab.fabricated == 1 and ab.checkable == 2


async def test_wrong_regime_and_repealed_law_are_wrong(docs, corpus):
    result = await _result(docs, EPZ)  # inside an EPZ the Labour Act does not apply
    ab, rows = await _rows(corpus, result,
                           ("Bangladesh Labour Act 2006", "46", "Women workers are entitled to 16 weeks of paid maternity leave."),
                           ("Prevention and Suppression of Human Trafficking Act 2012", "9", "Forced labour is punishable with 5 to 12 years' imprisonment."))
    assert rows == [("wrong", "wrong_regime"), ("wrong", "repealed")]
    assert (ab.wrong, ab.checkable, ab.supported) == (2, 2, 0)


async def test_the_offline_migrant_baseline(docs, corpus):
    result = await _result(docs, MY)
    ab = await ablation.run(LLM(mode="fake"), corpus, result)
    by_cited = {r["cited"]: r["outcome"] for r in ab.rows}
    assert by_cited["Passports Act 1966 (Malaysia) s.12(1)(f)"] == "outside_corpus"
    assert by_cited["Prevention and Suppression of Human Trafficking Act 2012 s.9"] == "wrong"
    assert ab.checkable == ab.supported + ab.wrong + ab.fabricated
    assert ab.checkable + ab.outside_corpus == ab.citations_found
