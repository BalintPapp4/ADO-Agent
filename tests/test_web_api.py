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
