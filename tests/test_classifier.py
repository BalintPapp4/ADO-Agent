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


def test_custom_keywords_hungarian_suffixes_and_accent_fallback():
    clf = TaxClassifier(custom_keywords=["nyugdíj", "kulonado", "számla"])

    # Magyar ragozás ("nyugdíj" -> "nyugdíjas", "nyugdíjak")
    res_suf = clf.classify(
        title="A nyugdíjasok kedvezményei és az SZJA változása",
        summary="Részletek a nyugdíjak adómentességéről.",
    )
    assert res_suf.relevant is True
    assert "egyeni" in [m.category_id for m in res_suf.category_matches]
    assert "nyugdíj" in res_suf.matched_keywords

    # Ékezet nélküli kulcsszó ("kulonado" -> "különadót", "különadóról")
    res_acc = clf.classify(
        title="Tájékoztató a kiskereskedelmi különadóról",
        summary="Hogyan érinti a szektort a különadó?",
    )
    assert res_acc.relevant is True
    assert "egyeni" in [m.category_id for m in res_acc.category_matches]
    assert "kulonado" in res_acc.matched_keywords

    # Szóvégi a -> á nyúlás magyar ragozáskor ("számla" -> "számlát", "számlázás")
    res_stem = clf.classify(
        title="Kötelező elektronikus számlázás 2027-től",
        summary="Minden kiállított számlát be kell jelenteni.",
    )
    assert res_stem.relevant is True
    assert "egyeni" in [m.category_id for m in res_stem.category_matches]
    assert "számla" in res_stem.matched_keywords


def test_effective_date_change_summary_and_nav_boilerplate_cleanup():
    from datetime import date

    from ado_agent.classifier import compute_effective_status, extract_effective_date, strip_nav_boilerplate

    raw_nav = (
        "Felhívjuk szíves figyelmét, hogy ha a NAV következő oldalain 2018. január 1-je után közzétett "
        "tájékoztatóknak megfelelően jár el, akkor az adózás rendjéről szóló 2017. évi CL. törvény "
        "247. §-a alapján jogkövetkezmény az Ön részére nem állapítható meg. "
        "2027. január 1-jétől hatályos az ÁFA tv. 82. § módosítása, amely a kedvezményes kulcsot érinti."
    )
    cleaned = strip_nav_boilerplate(raw_nav)
    assert "2017. évi CL." not in cleaned
    assert "2027. január 1-jétől" in cleaned

    eff = extract_effective_date("Áfa tv. módosítás", cleaned)
    assert eff == "2027-01-01"
    assert compute_effective_status(eff, today=date(2026, 11, 26)) == "upcoming"
    assert compute_effective_status(eff, today=date(2027, 1, 1)) == "in_force"
    assert compute_effective_status("2025-01-01", today=date(2026, 11, 26)) == ""

    clf = TaxClassifier()
    res = clf.classify(
        title="2007. évi CXXVII. törvény az általános forgalmi adóról (Áfa tv.)",
        summary="Módosítja a 2026. évi LXXV. törvény. 2027. január 1-jétől hatályos a nyugtaadatszolgáltatás bővítése.",
        today=date(2026, 11, 26),
    )
    assert res.effective_date == "2027-01-01"
    assert res.effective_status == "upcoming"
    assert len(res.change_summary) >= 1
    assert any("2026. évi LXXV. törvény" in c or "2027." in c for c in res.change_summary)


def test_njt_boilerplate_roman_numeral_split_and_core_laws():
    from ado_agent.classifier import extract_change_summary, strip_nav_boilerplate

    raw_njt = (
        "Nemzeti Jogszabálytár Ugrás a keresőre Ugrás a tartalomra Nemzeti Jogszabálytár "
        "Magyar Jogi Információs Portál Magyar Közlöny Portál Céginformációs Portál EUR-LEX "
        "Nemzeti Jogszabálytár Megnyitott jogszabályok "
        "197/2022. (VI. 4.) Korm. rendelet az extraprofit adókról, amely 2027. január 1-jétől módosul."
    )
    cleaned = strip_nav_boilerplate(raw_njt)
    assert "Ugrás a keresőre" not in cleaned
    assert "Céginformációs Portál" not in cleaned
    assert "197/2022. (VI. 4.) Korm. rendelet az extraprofit adókról" in cleaned

    bullets = extract_change_summary(
        "197/2022. (VI. 4.) Korm. rendelet az extraprofit adókról",
        raw_njt,
    )
    assert bullets
    assert not any(b.startswith("4.)") for b in bullets)
    assert any("197/2022. (VI. 4.) Korm. rendelet" in b for b in bullets)

    clf = TaxClassifier()
    for law_title in (
        "1991. évi LXXXII. törvény",
        "1990. évi C. törvény",
        "1994. évi LIII. törvény",
        "2000. évi C. törvény",
    ):
        res = clf.classify(title=law_title, summary="")
        assert res.relevant is True, f"A törvény nem kapott relevanciát: {law_title}"


def test_hungarian_search_statutory_abbreviations_and_compact_queries():
    from ado_agent.classifier import match_hungarian_search

    gjt_text = "1991. évi LXXXII. törvény a gépjárműadóról"
    art_text = "2017. évi CL. törvény az adózás rendjéről (Art.)"
    afa_tartalom = "2007. évi CXXVII. törvény a számla tartalmi követelményeiről"
    htv_text = "1990. évi C. törvény a helyi adókról és a HIPA szabályairól"
    szt_text = "2000. évi C. törvény a számvitelről"
    vht_text = "1994. évi LIII. törvény a bírósági végrehajtásról"

    assert match_hungarian_search(gjt_text, "1991.Évi gepjarműadó") is True
    assert match_hungarian_search(gjt_text, "Gjt") is True
    assert match_hungarian_search(afa_tartalom, "Gjt") is False

    # 'Art' megtalálja az Art. törvényt, de NEM találja meg a 'tartalmi' szót!
    assert match_hungarian_search(art_text, "Art") is True
    assert match_hungarian_search("2017. évi CL. törvény az adózás rendjéről", "Art") is True
    assert match_hungarian_search(afa_tartalom, "Art") is False

    # Htv vs Szt (mindkettő 'C. törvény', eltérő évszámmal)
    assert match_hungarian_search(htv_text, "Htv") is True
    assert match_hungarian_search(szt_text, "Htv") is False
    assert match_hungarian_search(szt_text, "Szt") is True

    # Vht
    assert match_hungarian_search(vht_text, "Vht") is True
    assert match_hungarian_search(art_text, "Vht") is False

    # Hrt, Hvt szóhatáros egyezés (nem talál meg hamis részszavakat)
    assert match_hungarian_search("Módosult a Hrt. 12. § szabálya", "Hrt") is True
    assert match_hungarian_search("A hírtelevízió adása", "Hrt") is False
    assert match_hungarian_search("A Hvt. szerinti kötelezettség", "Hvt") is True
    assert match_hungarian_search("A miniszter hívta össze az ülést", "Hvt") is False
