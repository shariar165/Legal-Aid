"""Who is bound by an international instrument (spec 29 step 2.1)."""

import io

import pytest
from docx import Document as Docx

from ain import countries, ratification
from ain.export import memo_docx
from ain.orchestrator import new_job, run_pipeline

MY = "migrant_my_contract.txt"


def test_every_ilo_convention_in_the_corpus_has_a_row_for_bangladesh_and_every_destination(corpus):
    codes = ["BD"] + [c.code for c in countries.load_countries()]
    instruments = {ratification.instrument(s.act_key) for s in corpus.sections if s.kind == "law"} - {None}
    assert instruments  # C029, C095, C181
    for inst in instruments:
        rows = ratification.table()[inst]
        assert rows["url"].startswith("https://normlex.ilo.org/") and rows["checked"]
        for code in codes:
            row = rows["countries"][code]
            assert isinstance(row["ratified"], bool)
            assert bool(row.get("date")) == row["ratified"], f"{inst} {code}: a ratification has a date, a non-ratification none"


def test_a_ratified_and_an_unratified_instrument():
    c029 = ratification.status("ILO-C029", ["BD", "MY"])
    assert not c029.persuasive and c029.note.en == "Ratified by Bangladesh and Malaysia."
    c181 = ratification.status("ILO-C181", ["BD", "MY"])
    assert c181.persuasive and [p.ratified for p in c181.parties] == [False, False]
    assert "not ratified by bangladesh or malaysia" in c181.note.en.lower() and "persuasive" in c181.note.en
    c095 = ratification.status("ILO-C095", ["BD", "MY"])
    assert c095.note.en == "Ratified by Malaysia; not by Bangladesh." and not c095.persuasive


def test_national_law_and_supervisory_comments_have_no_ratification():
    assert ratification.status("BD-LABOUR-2006", ["BD"]) is None
    assert ratification.status("ILO-CEACR-C029-2021", ["BD"]) is None


@pytest.mark.parametrize(("code", "parties"), [(None, ["BD"]), ("MY", ["BD", "MY"]), ("BD", ["BD"])])
def test_parties(code, parties):
    assert ratification.parties(code) == parties


async def test_c181_reads_not_ratified_in_the_checks_the_result_and_the_docx(docs):
    r = await run_pipeline(new_job(MY), (docs / MY).read_bytes(), MY, "sample", "fake")
    assert r.route.parties == ["BD", "MY"]
    v = next(v for v in r.ledger if v.claim.citation_id == "ILO-C181-a7")
    g1 = next(g for g in v.gates if g.gate == "existence")
    assert g1.status == "pass" and "Not ratified by Bangladesh or Malaysia" in g1.detail
    assert v.verdict == "verified"  # informs, decides nothing
    assert r.ratification["ILO-C181-a7"].persuasive
    assert "ILO-C181-a7" in r.model_dump()["ratification"]  # sent to the UI
    assert not any(cid.startswith(("BD-", "MY-")) for cid in r.ratification)
    doc = Docx(io.BytesIO(memo_docx(r)))
    text = " ".join([p.text for p in doc.paragraphs] + [c.text for t in doc.tables for row in t.rows for c in row.cells])
    assert "Not ratified by Bangladesh or Malaysia" in text
