def test_restraint_of_trade_finds_contract_act_s27(corpus):
    top = corpus.search("agreement in restraint of trade void", k=3)
    assert top[0][0].citation_id == "BD-CONTRACT-1872-s27"


def test_bangla_query_finds_bangla_statute(corpus):
    top = corpus.search("পাসপোর্ট আটকাইয়া রাখিলে", k=3)
    assert top[0][0].citation_id == "BD-OEMA-2013-s31"


def test_pack_filter_restricts_results(corpus):
    hits = corpus.search("প্রসূতি কল্যাণ সুবিধা", packs={"bd_epz"}, k=5)
    assert hits and all("bd_epz" in s.packs for s, _ in hits)


def test_export_proceeds_query(corpus):
    ids = [s.citation_id for s, _ in corpus.search("export proceeds repatriation four months", k=4)]
    assert "BD-GFET-2018-ch8p13" in ids


def test_cross_references_follow_section_mentions(corpus):
    s126 = corpus.get("BD-LABOUR-2006-s126")  # refers to ধারা ১২৫
    refs = [s.citation_id for s in corpus.cross_refs(s126)]
    assert "BD-LABOUR-2006-s125" in refs
