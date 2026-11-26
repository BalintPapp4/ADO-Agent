"""Tesztek a parancssori (CLI) interfészhez."""

from pathlib import Path
from unittest.mock import patch

import httpx

from ado_agent.app import main
from ado_agent.fetcher import HttpFetcher


def test_cli_list_sources(tmp_path: Path, capsys):
    rc = main(["--data-dir", str(tmp_path), "--list-sources"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "parlament_hu" in out
    assert "njt_hu" in out
    assert "eur_lex_eu" in out


def test_cli_scan_and_export(tmp_path: Path, capsys):
    def mock_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            text="""<html><body><a href="/tervezet">Társadalmi egyeztetés: Robin Hood adó és nem levonható ÁFA tervezet</a></body></html>""",
            headers={"content-type": "text/html; charset=utf-8"},
        )

    mock_fetcher = HttpFetcher(client=httpx.Client(transport=httpx.MockTransport(mock_handler)))
    export_file = tmp_path / "jelentes.xlsx"

    with patch("ado_agent.scanner.HttpFetcher", return_value=mock_fetcher):
        rc = main(
            [
                "--data-dir",
                str(tmp_path),
                "--scan",
                "--sources",
                "kormany_hu",
                "--export",
                str(export_file),
            ]
        )

    assert rc == 0
    assert export_file.exists() and export_file.stat().st_size > 1000
    out = capsys.readouterr().out
    assert "Export elkészült" in out
