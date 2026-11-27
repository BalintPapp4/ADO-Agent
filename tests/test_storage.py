"""Tesztek az SQLite perzisztencia réteghez."""

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
