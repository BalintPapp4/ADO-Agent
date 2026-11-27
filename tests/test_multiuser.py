"""Tesztek a többfelhasználós (csoportos) olvasott állapotokhoz és megjegyzésekhez."""

from pathlib import Path

from ado_agent.models import LegislativeItem
from ado_agent.storage import Database


def test_per_user_read_bookmarks_and_comments(tmp_path: Path):
    db = Database(tmp_path / "mu.db")

    u1 = db.create_user("balint", "Titok123", display_name="Papp Bálint", is_admin=True)
    u2 = db.create_user("anna", "Titok456", display_name="Kiss Anna", is_admin=False)

    assert db.authenticate_user("balint", "Titok123")["id"] == u1["id"]
    assert db.authenticate_user("balint", "rossz") is None

    item = LegislativeItem(
        item_key="item_1",
        title="ÁFA módosítás 2027",
        url="https://nav.gov.hu/afa-2027",
        source_id="nav_gov_hu",
        source_name="NAV",
        jurisdiction="HU",
        content_hash="hash_v1",
    )
    db.upsert_items([item])

    # Bálint elolvassa és kiemeli -> Annánál továbbra is olvasatlan és nincs kiemelve
    db.update_item_flags("item_1", is_read=True, is_bookmarked=True, user_id=u1["id"])
    assert db.get_stats(user_id=u1["id"])["unread_count"] == 0
    assert db.get_stats(user_id=u1["id"])["bookmarked_count"] == 1
    assert db.get_stats(user_id=u2["id"])["unread_count"] == 1
    assert db.get_stats(user_id=u2["id"])["bookmarked_count"] == 0

    # Szűrők ellenőrzése
    assert len(db.query_items(only_read=True, user_id=u1["id"])) == 1
    assert len(db.query_items(only_unread=True, user_id=u1["id"])) == 0
    assert len(db.query_items(only_unread=True, user_id=u2["id"])) == 1

    # Bálint visszateszi olvasatlanra
    db.update_item_flags("item_1", is_read=False, user_id=u1["id"])
    assert db.get_stats(user_id=u1["id"])["unread_count"] == 1

    # Nevesített megjegyzések
    c1 = db.add_comment("item_1", "Ezt nézzük meg pénteken!", user_id=u1["id"], author_name=u1["display_name"])
    c2 = db.add_comment("item_1", "Rendben, átnézem.", user_id=u2["id"], author_name=u2["display_name"])
    assert c1 is not None and c2 is not None

    loaded_for_anna = db.query_items(user_id=u2["id"])[0]
    assert len(loaded_for_anna.comments) == 2
    assert loaded_for_anna.comments[0]["author_name"] == "Papp Bálint"
    assert loaded_for_anna.comments[1]["author_name"] == "Kiss Anna"

    # Anna nem törölheti Bálint megjegyzését, csak a sajátját
    try:
        db.delete_comment(c1["id"], requester_user_id=u2["id"], is_admin=False)
        assert False, "PermissionError kellett volna"
    except PermissionError:
        pass
    assert db.delete_comment(c2["id"], requester_user_id=u2["id"], is_admin=False) is True


def test_multiuser_startup_reclassifies_custom_keywords_and_preserves_user_states(tmp_path: Path):
    from ado_agent.config import AppConfig
    from ado_agent.web.server import create_app

    cfg = AppConfig(data_dir=tmp_path)
    cfg.custom_keywords = ["e-nyugta"]
    cfg.save()

    db = Database(cfg.db_path)
    u1 = db.create_user("balint", "Titok123", display_name="Papp Bálint", is_admin=True)
    db.upsert_items(
        [
            LegislativeItem(
                item_key="enyugta_1",
                title="E-nyugtázás technikai útmutató",
                url="https://nav.gov.hu/ado/e-nyugta",
                source_id="nav_gov_hu",
                source_name="NAV",
                jurisdiction="HU",
                summary="Új e-nyugta követelmények az áfa alanyoknak.",
                categories=["egyeb_ado"],
                category_names=["Adózás általános"],
                matched_keywords=["áfa"],
                content_hash="hash_en",
            )
        ]
    )
    db.update_item_flags("enyugta_1", is_read=True, is_bookmarked=True, user_id=u1["id"])
    db.add_comment("enyugta_1", "Fontos az ügyfeleknek", user_id=u1["id"], author_name="Papp Bálint")

    # Szerver induláskor újracímkézi a meglévő adatbázist az elmentett egyéni kulcsszavak alapján
    app = create_app(cfg, db, auth_enabled=True)
    app.config["TESTING"] = True
    client = app.test_client()

    r_login = client.post("/api/auth/login", json={"username": "balint", "password": "Titok123"})
    assert r_login.status_code == 200

    r_state = client.get("/api/state?category=egyeni")
    assert r_state.status_code == 200
    data = r_state.get_json()
    assert data["stats"]["by_category"]["egyeni"] == 1
    assert len(data["items"]) == 1
    it = data["items"][0]
    assert it["is_read"] is True
    assert it["is_bookmarked"] is True
    assert len(it["comments"]) == 1

