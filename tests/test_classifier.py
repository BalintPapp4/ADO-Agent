"""Tesztek a magyar és EU-s adózási osztályozó motorhoz."""

from ado_agent.classifier import TaxClassifier


def test_robin_hood_and_extraprofit_detection():
    clf = TaxClassifier()
    res = clf.classify(
        title="T/10452 Az energiaellátók jövedelemadójáról (Robin Hood adó) és az extraprofitadóról szóló törvényjavaslat",
        summary="A javaslat módosítja a 2008. évi LXVII. törvény adókulcsait.",
    )
    assert res.relevant is True
    assert res.is_bill is True
    assert res.document_ref == "T/10452"
    cat_ids = [m.category_id for m in res.category_matches]
    assert "robin_hood" in cat_ids
    assert res.relevance_score >= 70


def test_szja_detection_with_hungarian_suffixes():
    clf = TaxClassifier()
    res = clf.classify(
        title="A személyi jövedelemadóról szóló 1995. évi CXVII. törvény módosítása",
        summary="Bővül a családi adókedvezmény és az átalányadózás értékhatára.",
    )
    assert res.relevant is True
    cat_ids = [m.category_id for m in res.category_matches]
    assert "szja" in cat_ids


def test_refundable_vs_non_refundable_vat():
    clf = TaxClassifier()

    refundable = clf.classify(
        title="Módosul a visszatérítendő ÁFA kiutalási határideje és az áfa-visszaigénylés szabálya",
        summary="Az előzetesen felszámított adó levonási joga egyszerűsödik.",
    )
    assert refundable.relevant is True
    assert "afa_visszateritendo" in [m.category_id for m in refundable.category_matches]

    non_refundable = clf.classify(
        title="Vissza nem térítendő ÁFA és levonási tilalom személygépkocsi beszerzésénél",
        summary="A nem levonható áfa elszámolása és az arányosítás változásai.",
    )
    assert non_refundable.relevant is True
    assert "afa_nem_visszateritendo" in [m.category_id for m in non_refundable.category_matches]


def test_non_refundable_grant_without_vat_is_not_false_positive():
    clf = TaxClassifier()
    grant = clf.classify(
        title="Vissza nem térítendő támogatás kisvállalkozásoknak eszközbeszerzésre",
        summary="A pályázati keretösszeg 5 milliárd forint.",
    )
    assert grant.relevant is False

    grant_with_vat = clf.classify(
        title="Vissza nem térítendő támogatás és az ÁFA levonási tilalom szabályai",
        summary="A projektben felmerült általános forgalmi adó nem igényelhető vissza.",
    )
    assert grant_with_vat.relevant is True
    assert "afa_nem_visszateritendo" in [m.category_id for m in grant_with_vat.category_matches]


def test_false_positive_hungarian_words_are_ignored():
    clf = TaxClassifier()
    for title in (
        "Eladó családi ház Budapesten kedvező áron",
        "Esti Híradó: sporthírek és időjárás-jelentés",
        "Kiadó egyetemi tankönyvek vására",
        "Előadó: Dr. Minta Géza kulturális estje",
    ):
        res = clf.classify(title=title, summary="Általános közlemény.")
        assert res.relevant is False, f"Fals pozitív találat: {title} -> {res.matched_keywords}"


def test_eu_tax_proposal_classification():
    clf = TaxClassifier()
    res = clf.classify(
        title="COM(2025) 142 Proposal for a Council Directive on VAT in the Digital Age (ViDA)",
        summary="Modernising VAT refund rules and non-deductible VAT reporting across Member States.",
        jurisdiction="EU",
    )
    assert res.relevant is True
    assert res.is_bill is True
    assert "COM(2025) 142" in res.document_ref
    cats = {m.category_id for m in res.category_matches}
    assert "eu_ado" in cats
    assert "afa_visszateritendo" in cats
    assert "afa_nem_visszateritendo" in cats


def test_custom_keywords():
    clf = TaxClassifier(custom_keywords=["e-nyugta", "széndioxid-kvóta adó"])
    res = clf.classify(
        title="Új szabályozás az e-nyugta bevezetéséről",
        summary="Műszaki előírások a pénztárgépekhez.",
    )
    assert res.relevant is True
    assert "egyeni" in [m.category_id for m in res.category_matches]
    assert "e-nyugta" in res.matched_keywords
