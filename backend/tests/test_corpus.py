"""The corpus is the ground truth: every playbook anchor must resolve to real, verbatim statute text."""

import re
import unicodedata

from ain.agents.risk_analyst import load_rules


def _norm(t: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", t)).strip()


def test_corpus_size_and_shape(corpus):
    assert len(corpus.sections) > 1000
    acts = {s.act_key for s in corpus.sections}
    for key in ("BD-CONTRACT-1872", "BD-LABOUR-2006", "BD-EPZLABOUR-2019", "BD-OEMA-2013", "BD-TRAFFICKING-2026", "ILO-C181", "MY-EA-1955", "EU-CSDDD-2024"):
        assert key in acts
    for s in corpus.sections:
        assert s.text.strip(), s.citation_id
        assert s.url.startswith("http"), s.citation_id
        assert s.packs, s.citation_id


def test_bdlaws_sections_link_to_official_pages(corpus):
    s27 = corpus.get("BD-CONTRACT-1872-s27")
    assert s27.url.startswith("http://bdlaws.minlaw.gov.bd/act-26/section-")
    assert "restrained from exercising a lawful profession" in s27.text


def test_every_playbook_anchor_exists_with_verbatim_quote(corpus):
    rules = load_rules()
    assert len(rules) >= 12
    checked = 0
    for rule in rules:
        groups = list(rule.anchors_by_pack.values()) + list(rule.pack_anchors.values())
        anchors = list(rule.anchors) + [a for group in groups for a in group]
        assert anchors, rule.id
        for a in anchors:
            sec = corpus.get(a["citation_id"])
            assert sec is not None, f"{rule.id}: {a['citation_id']} missing from corpus"
            assert _norm(a["quote"]) in _norm(sec.text), f"{rule.id}: quote not verbatim in {a['citation_id']}"
            checked += 1
    assert checked >= 20


def test_repealed_acts_point_to_a_successor_in_the_corpus(corpus):
    repealed = [s for s in corpus.sections if s.status == "repealed"]
    assert repealed, "the 2012 Trafficking Act should be present and marked repealed"
    for s in repealed:
        assert s.superseded_by and any(x.act_key == s.superseded_by for x in corpus.sections)


def test_labour_act_text_is_the_2026_amended_version(corpus):
    s46 = corpus.get("BD-LABOUR-2006-s46")
    assert "৬০ (ষাট) দিন" in s46.text  # 60 days before / after, inserted in 2026
    assert any("২০২৬" in n for n in s46.amendment_notes) or "[" in s46.text


def test_ilo_supervisory_observations_are_verbatim_and_marked_interpretive(corpus):
    from ain.agents.verifier import gate_currency
    from ain.naming import label

    sup = [s for s in corpus.sections if s.kind == "supervisory"]
    assert {s.citation_id for s in sup} >= {"ILO-CEACR-C087-2023-EPZ", "ILO-CEACR-C098-2023-EPZ", "ILO-CEACR-C029-2021-FL"}
    for s in sup:
        assert s.packs == ["ilo_supervisory"]
        assert "►Compilation" not in s.text and "https://" not in s.text  # page furniture of the source PDF is cut out
        assert "interpretive" in label(s).en
        g4 = gate_currency(s)
        assert g4.status == "pass" and "not binding" in g4.detail


def test_every_act_has_a_short_desk_label_whose_number_is_the_corpus_record(corpus):
    """Spec 29 step 3.1: the Case Desk's law cell. The act name is short; the section number is read from the record,
    and the Bangla form has Bangla digits."""
    from ain.naming import EN_TO_BN_DIGITS, SHORT_ACT, label, short_label

    keys = {s.act_key for s in corpus.sections if s.kind != "company_policy"}
    assert keys <= set(SHORT_ACT), f"no short name for {sorted(keys - set(SHORT_ACT))}"
    for s in corpus.sections:
        short, full = short_label(s), label(s)
        assert len(short.en) <= len(full.en) and len(short.bn) <= len(full.bn), short.en
        if s.kind == "law":  # same "· s.31" tail as the full label, which comes from the record
            assert short.en.split(" · ")[-1] == full.en.split(" · ")[-1]
            assert short.bn.split(" · ")[-1] == full.bn.split(" · ")[-1]
        if s.lang == "bn" or s.kind == "law":
            assert not any(c.isascii() and c.isdigit() for c in short.bn.split(" · ")[0]), short.bn
        if s.kind == "standard":
            assert "voluntary" in short.en and "স্বেচ্ছামূলক" in short.bn
        if s.kind == "supervisory":
            assert "interpretive" in short.en
    oema = corpus.get("BD-OEMA-2013-s31")
    assert short_label(oema).en == "OEMA 2013 · s.31"
    assert short_label(oema).bn == "অভিবাসী আইন ২০১৩ · ধারা " + "31".translate(EN_TO_BN_DIGITS)
