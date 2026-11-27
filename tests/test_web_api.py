"""Tesztek a Flask webes REST API-hoz és felhasználói felülethez."""

from pathlib import Path
from unittest.mock import patch

import httpx

from ado_agent.config import AppConfig, get_default_sources
from ado_agent.fetcher import HttpFetcher
from ado_agent.storage import Database
from ado_agent.web.server import create_app


def _test_client(tmp_path: Path):
    cfg = AppConfig(data_dir=tmp_path, sources=get_default_sources())
    db = Database(cfg.db_path)
    app = create_app(cfg, db)
    app.config["TESTING"] = True
    return app.test_client(), cfg, db


def test_web_ui_and_api_crud(tmp_path: Path):
    client, cfg, _ = _test_client(tmp_path)

    # Főoldal HTML betöltése
    r_home = client.get("/")
    assert r_home.status_code == 200
    assert "ADÓ Agent" in r_home.get_data(as_text=True)

    # Health & State
    assert client.get("/api/health").get_json()["status"] == "ok"
    state = client.get("/api/state").get_json()
    assert len(state["sources"]) >= 7

    # Egyéni kulcsszó és ütemezés mentése
    r_set = client.put(
        "/api/settings",
        json={"custom_keywords": ["e-nyugta", "kiskereskedelmi adó"], "auto_scan_interval_minutes": 60},
    )
    assert r_set.status_code == 200
    assert r_set.get_json()["auto_scan_interval_minutes"] == 60

    # Új egyéni forrás felvétele, módosítása és törlése
    r_add = client.post(
        "/api/sources",
        json={"name": "Teszt Adó RSS", "url": "https://example.org/rss.xml", "jurisdiction": "HU", "adapter": "rss"},
    )
    assert r_add.status_code == 201
    new_id = r_add.get_json()["source"]["id"]

    r_toggle = client.patch(f"/api/sources/{new_id}", json={"enabled": False})
    assert r_toggle.status_code == 200
    assert r_toggle.get_json()["source"]["enabled"] is False

    # Beépített forrás nem törölhető
    assert client.delete("/api/sources/parlament_hu").status_code == 400
    # Egyéni forrás törölhető
    assert client.delete(f"/api/sources/{new_id}").status_code == 200


def test_web_sync_scan_and_export(tmp_path: Path):
    client, cfg, _ = _test_client(tmp_path)

    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="""<?xml version="1.0"?><rss version="2.0"><channel><item>
            <title>Új SZJA és visszatérítendő ÁFA törvényjavaslat T/9999</title>
            <link>https://nav.gov.hu/ado/9999</link>
            <description>Személyi jövedelemadó és áfa-visszaigénylés.</description>
            </item></channel></rss>""",
            headers={"content-type": "application/rss+xml"},
        )

    mock_http_client = httpx.Client(transport=httpx.MockTransport(mock_handler))
    mock_fetcher = HttpFetcher(client=mock_http_client)

    with patch("ado_agent.scanner.HttpFetcher", return_value=mock_fetcher):
        r_scan = client.post("/api/scan", json={"sync": True, "source_ids": ["nav_gov_hu"]})
        assert r_scan.status_code == 200
        body = r_scan.get_json()
        assert body["summary"]["total_matched"] >= 1

    # Exportálás Excelbe és CSV-be az API-n keresztül
    r_xlsx = client.get("/api/export/xlsx")
    assert r_xlsx.status_code == 200
    assert len(r_xlsx.data) > 1000

    r_csv = client.get("/api/export/csv")
    assert r_csv.status_code == 200
    assert "T/9999" in r_csv.data.decode("utf-8-sig")


def test_custom_keywords_reclassify_existing_items_and_preserve_flags(tmp_path: Path):
    from ado_agent.classifier import TaxClassifier
    from ado_agent.models import RawCandidate

    client, cfg, db = _test_client(tmp_path)
    clf = TaxClassifier()
    nav_src = next(s for s in cfg.sources if s.id == "nav_gov_hu")

    item1 = clf.enrich_candidate(
        RawCandidate(
            title="SZJA és nyugdíjas kedvezmények 2027",
            url="https://nav.gov.hu/ado/nyugdijas-szja",
            summary="A különadóról és az adómentességről.",
        ),
        nav_src,
    )
    item2 = clf.enrich_candidate(
        RawCandidate(
            title="ÁFA bevallási határidő",
            url="https://nav.gov.hu/ado/afa-hatarido",
            summary="Általános forgalmi adó tudnivalók.",
        ),
        nav_src,
    )
    assert item1 is not None and item2 is not None
    db.upsert_items([item1, item2])
    db.update_item_flags(item1.item_key, is_read=True, is_bookmarked=True, notes="Fontos")

    # Kezdetben az Egyéni kulcsszavak számláló 0
    s0 = client.get("/api/state?category=egyeni").get_json()
    assert s0["stats"]["by_category"].get("egyeni", 0) == 0
    assert s0["items"] == []

    # Felhasználó utólag hozzáad egyéni kulcsszót -> meglévő adatbázis azonnal újracímkéződik!
    r_put = client.put("/api/settings", json={"custom_keywords": ["nyugdíj", "kulonado"]})
    assert r_put.status_code == 200
    assert r_put.get_json()["reclassified"]["custom_matched"] == 1

    s1 = client.get("/api/state?category=egyeni").get_json()
    assert s1["stats"]["by_category"]["egyeni"] == 1
    assert len(s1["items"]) == 1
    assert s1["items"][0]["item_key"] == item1.item_key
    assert "nyugdíj" in s1["items"][0]["matched_keywords"]
    assert "kulonado" in s1["items"][0]["matched_keywords"]
    assert s1["items"][0]["is_read"] is True
    assert s1["items"][0]["is_bookmarked"] is True
    assert s1["items"][0]["notes"] == "Fontos"

    # Kulcsszó eltávolításakor az 'egyeni' címke eltűnik, de a tétel és állapotok megmaradnak
    r_clear = client.put("/api/settings", json={"custom_keywords": []})
    assert r_clear.status_code == 200
    assert r_clear.get_json()["reclassified"]["custom_matched"] == 0

    s2 = client.get("/api/state?category=egyeni").get_json()
    assert s2["stats"]["by_category"].get("egyeni", 0) == 0
    assert s2["items"] == []
    s_all = client.get("/api/state").get_json()
    assert len(s_all["items"]) == 2

