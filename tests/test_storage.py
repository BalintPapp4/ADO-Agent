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
