"""Tesztek az exportáló réteghez (.xlsx, .csv, .html, .md, .json)."""

from io import BytesIO
import json
from pathlib import Path

from openpyxl import load_workbook

from ado_agent.classifier import TaxClassifier
from ado_agent.exporter import (
    export_items_csv,
    export_items_html,
    export_items_json,
    export_items_markdown,
    export_items_xlsx,
    write_export_file,
)
from ado_agent.models import RawCandidate, SourceConfig


def _sample_items():
    clf = TaxClassifier()
    src = SourceConfig(
        id="parlament_hu",
        name="Országgyűlés",
        adapter="parlament",
        url="https://www.parlament.hu/",
        jurisdiction="HU",
    )
    item = clf.enrich_candidate(
        RawCandidate(
            title="T/1234 Visszatérítendő ÁFA és SZJA módosítás",
            url="https://www.parlament.hu/iromany/1234",
            summary="Áfa-visszatérítés és személyi jövedelemadó kedvezmény.",
            published_at="2026-11-25",
        ),
        src,
    )
    assert item is not None
    item.is_new = True
    return [item]


def test_xlsx_export_structure(tmp_path: Path):
    items = _sample_items()
    raw = export_items_xlsx(items, latest_run={"source_results": [{"source_name": "Országgyűlés", "status": "ok"}]})
    wb = load_workbook(BytesIO(raw))
    assert wb.sheetnames == ["Adózási Találatok", "Összesítő", "Forrás Állapotok"]
    ws = wb["Adózási Találatok"]
    assert ws["A2"].value == "ÚJ"
    assert "Visszatérítendő ÁFA" in ws["G2"].value
    assert ws["L2"].hyperlink is not None

    out = write_export_file("xlsx", tmp_path / "out.xlsx", items)
    assert out.exists() and out.stat().st_size > 1000


def test_csv_utf8_bom_and_other_formats():
    items = _sample_items()
    csv_bytes = export_items_csv(items)
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    assert "Visszatérítendő ÁFA" in csv_bytes.decode("utf-8-sig")

    html_text = export_items_html(items).decode("utf-8")
    assert "ADÓ Agent" in html_text
    assert "T/1234" in html_text

    md_text = export_items_markdown(items).decode("utf-8")
    assert "# ADÓ Agent" in md_text

    json_obj = json.loads(export_items_json(items).decode("utf-8"))
    assert json_obj["count"] == 1
