"""Tesztek az SQLite perzisztencia réteghez."""

from datetime import date
from pathlib import Path

from ado_agent.classifier import TaxClassifier
from ado_agent.models import RawCandidate, SourceConfig
from ado_agent.storage import Database


def test_upsert_diff_bookmarks_notes_and_filters(tmp_path: Path):
    db = Database(tmp_path / "test.db")
    clf = TaxClassifier()
    src = SourceConfig(
        id="parlament_hu",
        name="Országgyűlés",
        adapter="parlament",
        url="https://www.parlament.hu/",
        jurisdiction="HU",
    )

    cand1 = RawCandidate(
        title="T/500 A Robin Hood adóról szóló törvényjavaslat",
        url="https://www.parlament.hu/iromany/500",
        summary="Energiaellátók jövedelemadója változás.",
        published_at="2026-11-20",
    )
    item1 = clf.enrich_candidate(cand1, src)
    assert item1 is not None

    n1, u1 = db.upsert_items([item1])
    assert (n1, u1) == (1, 0)

    loaded = db.query_items()
    assert len(loaded) == 1
    assert loaded[0].is_new is True
    assert loaded[0].is_updated is False

    # Könyvjelző + jegyzet mentése
    assert db.update_item_flags(item1.item_key, is_bookmarked=True, notes="Fontos ellenőrizni!") is True

    # Változatlan újrafeldolgozás -> megőrzi a könyvjelzőt és jegyzetet, már nem is_new
    item1_same = clf.enrich_candidate(cand1, src)
    assert item1_same is not None
    n2, u2 = db.upsert_items([item1_same])
    assert (n2, u2) == (0, 0)
    loaded2 = db.query_items(only_bookmarked=True)
    assert len(loaded2) == 1
    assert loaded2[0].notes == "Fontos ellenőrizni!"
    assert loaded2[0].is_new is False

    # Tartalommódosítás -> is_updated = True, könyvjelző megmarad
    cand1_mod = RawCandidate(
        title="T/500 A Robin Hood adóról szóló törvényjavaslat (módosított szöveg)",
        url="https://www.parlament.hu/iromany/500",
        summary="Új adókulcs 41%-ról 35%-ra csökken.",
        published_at="2026-11-24",
    )
    item1_mod = clf.enrich_candidate(cand1_mod, src)
    assert item1_mod is not None
    n3, u3 = db.upsert_items([item1_mod])
    assert (n3, u3) == (0, 1)
    loaded3 = db.query_items(only_new=True, category="robin_hood")
    assert len(loaded3) == 1
    assert loaded3[0].is_updated is True
    assert loaded3[0].is_bookmarked is True

    # Olvasottnak jelölés
    marked = db.mark_all_read()
    assert marked == 1
    assert db.query_items(only_new=True) == []


def test_flags_persist_across_db_reopen_and_rescan(tmp_path: Path):
    db_file = tmp_path / "persist.db"
    db1 = Database(db_file)
    clf = TaxClassifier()
    src = SourceConfig(
        id="nav_gov_hu",
        name="NAV",
        adapter="nav",
        url="https://nav.gov.hu/ado",
        jurisdiction="HU",
    )
    cand = RawCandidate(
        title="SZJA kedvezmények 2027",
        url="https://nav.gov.hu/ado/szja-2027",
        summary="Személyi jövedelemadó változások.",
        published_at="2026-11-26",
    )
    it = clf.enrich_candidate(cand, src)
    assert it is not None
    db1.upsert_items([it])
    db1.update_item_flags(it.item_key, is_read=True, is_bookmarked=True, notes="Következő havi ellenőrzés")

    # Új Database példány nyitása (szimulálja a program újraindítását)
    db2 = Database(db_file)
    rows = db2.query_items()
    assert len(rows) == 1
    assert rows[0].is_read is True
    assert rows[0].is_bookmarked is True
    assert rows[0].notes == "Következő havi ellenőrzés"

    # Újra-szkennelés változatlan tartalommal -> megmarad minden jelölés!
    it2 = clf.enrich_candidate(cand, src)
    assert it2 is not None
    db2.upsert_items([it2])
    rows_after = db2.query_items()
    assert rows_after[0].is_read is True
    assert rows_after[0].is_bookmarked is True
    assert rows_after[0].notes == "Következő havi ellenőrzés"
    stats = db2.get_stats()
    assert stats["read_count"] == 1
    assert stats["bookmarked_count"] == 1
    assert stats["noted_count"] == 1


def test_hungarian_case_accent_and_hyphen_insensitive_search(tmp_path: Path):
    db = Database(tmp_path / "search.db")
    clf = TaxClassifier(custom_keywords=["gépjárműadó"])
    src = SourceConfig(
        id="nav_gov_hu",
        name="NAV",
        adapter="nav",
        url="https://nav.gov.hu/",
        jurisdiction="HU",
    )

    cand_afa = RawCandidate(
        title="2007. évi CXXVII. törvény az általános forgalmi adóról (áfa)",
        url="https://nav.gov.hu/ado/afa-2027",
        summary="Visszaigénylési szabályok módosítása.",
        published_at="2026-11-26",
    )
    cand_gja = RawCandidate(
        title="Tájékoztató a Gépjármű-adó 2027. évi mértékéről",
        url="https://nav.gov.hu/ado/gepjarmuado-2027",
        summary="A személygépkocsik teljesítményalapú adótételei 2027.01.01-től módosulnak.",
        published_at="2026-11-26",
    )

    it_afa = clf.enrich_candidate(cand_afa, src)
    it_gja = clf.enrich_candidate(cand_gja, src)
    assert it_afa is not None and it_gja is not None
    db.upsert_items([it_afa, it_gja])

    # "Áfa" és "áfa" pontosan ugyanazt kell találja!
    res_upper = db.query_items(search="Áfa")
    res_lower = db.query_items(search="áfa")
    res_ascii = db.query_items(search="afa")
    assert len(res_upper) == 1
    assert [r.item_key for r in res_upper] == [r.item_key for r in res_lower] == [r.item_key for r in res_ascii]

    # "gépjárműadó" ékezettel, nagybetűvel, ékezet nélkül, kötőjel nélkül is találja a "Gépjármű-adó" elemet
    for q in ("gépjárműadó", "GÉPJÁRMŰADÓ", "gepjarmuado", "gépjármű adó"):
        hits = db.query_items(search=q)
        assert len(hits) == 1, f"Keresés sikertelen: {q}"
        assert hits[0].item_key == it_gja.item_key


def test_effective_date_lifecycle_transitions_diffing_and_nav_cleanup(tmp_path: Path):
    db = Database(tmp_path / "lifecycle.db")
    clf = TaxClassifier()
    src = SourceConfig(
        id="net_jogtar_hu",
        name="Netjogtár",
        adapter="netjogtar",
        url="https://net.jogtar.hu/",
        jurisdiction="HU",
    )

    user = db.create_user("anna", "pass123", display_name="Kiss Anna")

    # 1. Felvétel jövőbeli (2027.01.01) hatálybalépéssel
    cand = RawCandidate(
        title="2007. évi CXXVII. törvény az általános forgalmi adóról (Áfa tv.)",
        url="https://net.jogtar.hu/jogszabaly?docid=a0700127.tv",
        summary=(
            "Felhívjuk szíves figyelmét, hogy ha a NAV következő oldalain 2018. január 1-je után "
            "közzétett tájékoztatóknak megfelelően jár el, akkor az adózás rendjéről szóló 2017. évi CL. "
            "törvény 247. §-a alapján jogkövetkezmény az Ön részére nem állapítható meg. "
            "2027. január 1-jétől hatályba lép az e-nyugta adatszolgáltatási kötelezettség."
        ),
        published_at="2026-11-26",
    )
    it = clf.enrich_candidate(cand, src)
    assert it is not None
    assert it.effective_date == "2027-01-01"
    assert it.effective_status == "upcoming"
    assert "2017. évi CL." not in it.summary

    db.upsert_items([it])
    db.update_item_flags(it.item_key, is_read=True, user_id=user["id"])

    # Tartalmi változás a második ellenőrzéskor -> diff megjelenik a change_summary-ban
    cand_v2 = RawCandidate(
        title=cand.title,
        url=cand.url,
        summary=(
            "2027. január 1-jétől hatályba lép az e-nyugta adatszolgáltatási kötelezettség. "
            "A pénztárgépes nyugtaadás határideje 2027. július 1-re módosult."
        ),
        published_at="2026-11-27",
    )
    it_v2 = clf.enrich_candidate(cand_v2, src)
    assert it_v2 is not None
    db.upsert_items([it_v2])
    updated_items = db.query_items(only_effective_changes=True)
    assert len(updated_items) == 1
    assert any("Új / módosult szövegrész" in c for c in updated_items[0].change_summary)

    # Ha a felhasználó elolvassa, majd eljön 2027.01.01 -> automatikus 'in_force' + FRISSÜLT + olvasatlan!
    db.update_item_flags(it.item_key, is_read=True, user_id=user["id"])
    promoted = db.sync_effective_transitions(today=date(2027, 1, 1))
    assert promoted == 1

    user_items = db.query_items(user_id=user["id"], only_effective_changes=True)
    assert len(user_items) == 1
    assert user_items[0].effective_status == "in_force"
    assert user_items[0].is_updated is True
    assert user_items[0].is_read is False
    assert any("Hatályba lépett (2027-01-01)" in c for c in user_items[0].change_summary)

    stats = db.get_stats(user_id=user["id"])
    assert stats["in_force_changes_count"] == 1
    assert stats["upcoming_changes_count"] == 0
    assert stats["effective_changes_count"] == 1


def test_legacy_sqlite_schema_migrates_without_losing_data(tmp_path: Path):
    import sqlite3

    db_file = tmp_path / "legacy_fly.db"
    conn = sqlite3.connect(str(db_file))
    conn.executescript(
        """
        CREATE TABLE items (
            item_key TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            url TEXT NOT NULL,
            source_id TEXT NOT NULL,
            source_name TEXT NOT NULL,
            jurisdiction TEXT NOT NULL,
            summary TEXT NOT NULL DEFAULT '',
            published_at TEXT NOT NULL DEFAULT '',
            document_ref TEXT NOT NULL DEFAULT '',
            status_label TEXT NOT NULL DEFAULT '',
            relevance_score INTEGER NOT NULL DEFAULT 0,
            is_bill INTEGER NOT NULL DEFAULT 0,
            categories_json TEXT NOT NULL DEFAULT '[]',
            category_names_json TEXT NOT NULL DEFAULT '[]',
            matched_keywords_json TEXT NOT NULL DEFAULT '[]',
            content_hash TEXT NOT NULL DEFAULT '',
            first_seen_at TEXT NOT NULL,
            last_seen_at TEXT NOT NULL,
            is_new INTEGER NOT NULL DEFAULT 1,
            is_updated INTEGER NOT NULL DEFAULT 0,
            is_read INTEGER NOT NULL DEFAULT 0,
            is_bookmarked INTEGER NOT NULL DEFAULT 0,
            notes TEXT NOT NULL DEFAULT '',
            raw_metadata_json TEXT NOT NULL DEFAULT '{}'
        );
        INSERT INTO items (
            item_key, title, url, source_id, source_name, jurisdiction,
            summary, published_at, document_ref, status_label, relevance_score,
            is_bill, categories_json, category_names_json, matched_keywords_json,
            content_hash, first_seen_at, last_seen_at,
            is_new, is_updated, is_read, is_bookmarked, notes, raw_metadata_json
        ) VALUES (
            'legacy_key_1',
            '2007. évi CXXVII. törvény (Áfa tv.) — 2027.01.01-től hatályos változás',
            'https://nav.gov.hu/ado/afa-2027',
            'nav_gov_hu',
            'NAV',
            'HU',
            'Felhívjuk szíves figyelmét, hogy ha a NAV következő oldalain 2018. január 1-je után közzétett tájékoztatóknak megfelelően jár el, akkor az adózás rendjéről szóló 2017. évi CL. törvény 247. §-a alapján jogkövetkezmény az Ön részére nem állapítható meg. 2027.01.01-től hatályos áfa-módosítás.',
            '2026-11-26',
            '2007. évi CXXVII. törvény',
            '',
            80,
            0,
            '["afa_altalanos"]',
            '["ÁFA általános / eÁFA / ViDA"]',
            '["áfa"]',
            'abc123',
            '2026-11-26 10:00:00 UTC',
            '2026-11-26 10:00:00 UTC',
            0, 0, 1, 1, 'Megőrzött jegyzet', '{}'
        );
        """
    )
    conn.commit()
    conn.close()

    migrated_db = Database(db_file)
    migrated_db.reclassify_items(TaxClassifier())
    rows = migrated_db.query_items(search="Áfa")
    assert len(rows) == 1
    assert rows[0].notes == "Megőrzött jegyzet"
    assert rows[0].is_bookmarked is True
    assert rows[0].is_read is True
    assert "2017. évi CL." not in rows[0].summary
    assert rows[0].effective_date == "2027-01-01"
    assert rows[0].effective_status == "upcoming"
