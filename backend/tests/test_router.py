import pytest

from ain.agents.ingestion import build_document
from ain.agents.router import decide
from ain.models import DocFacts


def _route(path):
    data = path.read_bytes()
    doc, facts, _ = build_document(data, path.name)
    return decide(facts, doc.text.lower())


def test_epz_document_switches_labour_act_to_bepz(docs):
    route = _route(docs / "rmg_dhaka_epz.txt")
    assert "bd_epz" in route.pack_ids
    assert "bd_labour" not in route.pack_ids
    assert [p.pack for p in route.excluded] == ["bd_labour"]
    assert "Dhaka EPZ" in route.excluded[0].reason


def test_non_epz_domestic_employment_uses_labour_act():
    facts = DocFacts(doc_type="employment", is_epz=False)
    route = decide(facts, "appointment letter gazipur factory")
    assert "bd_labour" in route.pack_ids and "bd_epz" not in route.pack_ids


def test_document_outside_the_niche_gets_a_scope_note():
    route = decide(DocFacts(doc_type="commercial"), "mutual non-disclosure agreement between two software companies")
    assert route.scope_note and "employment" in route.scope_note.en and route.scope_note.bn


@pytest.mark.parametrize("name", ["migrant_my_contract.txt", "migrant_sa_contract.txt", "rmg_dhaka_epz.txt", "long_migrant_msa.txt"])
def test_niche_documents_have_no_scope_note(docs, name):
    assert _route(docs / name).scope_note is None


def test_outside_epz_wording_is_not_mistaken_for_epz(docs):
    _, facts, _ = build_document((docs / "control_clean.txt").read_bytes(), "control_clean.txt")
    assert facts.is_epz is False


def test_malaysia_migrant_contract_routes_migration_ilo_and_malaysian_law(docs):
    route = _route(docs / "migrant_my_contract.txt")
    assert {"bd_migration", "ilo", "my_employment", "bd_contract"} <= route.pack_ids
    assert "bd_labour" not in route.pack_ids  # the job is abroad


def test_export_contract_routes_fx(docs):
    assert "bd_fx" in _route(docs / "rmg_dhaka_epz.txt").pack_ids
