"""Exportálási motor — Excel (.xlsx), CSV (UTF-8 BOM), HTML riport, JSON, Markdown."""

from __future__ import annotations

import csv
import html
import io
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

from .models import LegislativeItem


def _format_notes_and_comments(it: LegislativeItem) -> str:
    parts: list[str] = []
    if it.notes:
        parts.append(it.notes)
    for c in it.comments or []:
        author = c.get("author_name") or "Felhasználó"
        created = c.get("created_at") or ""
        body = c.get("body") or ""
        if body:
            parts.append(f"[{author} • {created}] {body}" if created else f"[{author}] {body}")
    return "\n".join(parts)


def export_items_csv(items: list[LegislativeItem]) -> bytes:
    """UTF-8 BOM CSV, amelyet a magyar Excel is ékezethelyesen nyit meg."""
    buf = io.StringIO()
    writer = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_MINIMAL)
    writer.writerow(
        [
            "Állapot",
            "Joghatóság",
            "Relevancia",
            "Törvényjavaslat",
            "Azonosító",
            "Kategóriák",
            "Cím",
            "Forrás",
            "Dátum",
            "Talált kulcsszavak",
            "Kivonat",
            "Link",
            "Jegyzet",
        ]
    )
    for it in items:
        state = "ÚJ" if it.is_new else ("FRISSÜLT" if it.is_updated else ("Fontos" if it.is_bookmarked else "Korábbi"))
        writer.writerow(
            [
                state,
                it.jurisdiction,
                it.relevance_score,
                "Igen" if it.is_bill else "Nem",
                it.document_ref,
                ", ".join(it.category_names),
                it.title,
                it.source_name,
                it.published_at,
                ", ".join(it.matched_keywords),
                it.summary,
                it.url,
                _format_notes_and_comments(it),
            ]
        )
    return buf.getvalue().encode("utf-8-sig")


def export_items_xlsx(
    items: list[LegislativeItem],
    latest_run: dict[str, Any] | None = None,
) -> bytes:
    """Formázott Excel (.xlsx) munkafüzet összefoglalóval, találatokkal és forrásállapottal."""
    wb = Workbook()

    # 1. Munkalap: Találatok
    ws = wb.active
    ws.title = "Adózási Találatok"

    header_fill = PatternFill(start_color="0F172A", end_color="0F172A", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=11)
    new_fill = PatternFill(start_color="DCFCE7", end_color="DCFCE7", fill_type="solid")
    upd_fill = PatternFill(start_color="FEF3C7", end_color="FEF3C7", fill_type="solid")
    link_font = Font(color="1D4ED8", underline="single")

    headers = [
        "Állapot",
        "Joghatóság",
        "Pontszám",
        "Törvényjavaslat?",
        "Iromány / Szám",
        "Kategóriák",
        "Cím",
        "Forrás",
        "Közzétéve",
        "Talált kulcsszavak",
        "Összefoglaló",
        "Forrás URL",
        "Saját jegyzet",
    ]
    ws.append(headers)
    for col_idx in range(1, len(headers) + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for it in items:
        state = "ÚJ" if it.is_new else ("FRISSÜLT" if it.is_updated else ("Kiemelt" if it.is_bookmarked else "Látott"))
        row_values = [
            state,
            it.jurisdiction,
            it.relevance_score,
            "Igen" if it.is_bill else "Nem",
            it.document_ref,
            ", ".join(it.category_names),
            it.title,
            it.source_name,
            it.published_at,
            ", ".join(it.matched_keywords),
            it.summary,
            it.url,
            _format_notes_and_comments(it),
        ]
        ws.append(row_values)
        r_idx = ws.max_row
        if it.is_new:
            ws.cell(row=r_idx, column=1).fill = new_fill
        elif it.is_updated:
            ws.cell(row=r_idx, column=1).fill = upd_fill

        url_cell = ws.cell(row=r_idx, column=12)
        if it.url.startswith(("http://", "https://")):
            url_cell.hyperlink = it.url
            url_cell.font = link_font

        for c_idx in range(1, len(headers) + 1):
            ws.cell(row=r_idx, column=c_idx).alignment = Alignment(vertical="top", wrap_text=True)

    widths = [12, 12, 10, 16, 18, 32, 48, 28, 16, 30, 52, 38, 26]
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = f"A1:{get_column_letter(len(headers))}{max(1, ws.max_row)}"

    # 2. Munkalap: Összesítő
    ws_sum = wb.create_sheet("Összesítő")
    ws_sum.append(["ADÓ Agent — Jelentés Összesítő", ""])
    ws_sum.cell(row=1, column=1).font = Font(bold=True, size=14)
    ws_sum.append(["Exportálás ideje", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
    ws_sum.append(["Összes exportált találat", len(items)])
    ws_sum.append(["Új találatok", sum(1 for x in items if x.is_new)])
    ws_sum.append(["Frissült találatok", sum(1 for x in items if x.is_updated)])
    ws_sum.append(["Törvényjavaslatok / tervezetek", sum(1 for x in items if x.is_bill)])
    ws_sum.append(["Magyar (HU) elemek", sum(1 for x in items if x.jurisdiction == "HU")])
    ws_sum.append(["EU elemek", sum(1 for x in items if x.jurisdiction == "EU")])
    ws_sum.column_dimensions["A"].width = 34
    ws_sum.column_dimensions["B"].width = 28

    # 3. Munkalap: Forrás állapotok
    ws_src = wb.create_sheet("Forrás Állapotok")
    src_headers = ["Forrás", "Joghatóság", "Állapot", "Nyers elemek", "Adózási találatok", "Új", "Idő (ms)", "Üzenet"]
    ws_src.append(src_headers)
    for col_idx in range(1, len(src_headers) + 1):
        c = ws_src.cell(row=1, column=col_idx)
        c.fill = header_fill
        c.font = header_font
    for sr in (latest_run or {}).get("source_results", []):
        ws_src.append(
            [
                sr.get("source_name", ""),
                sr.get("jurisdiction", ""),
                sr.get("status", ""),
                sr.get("fetched_candidates", 0),
                sr.get("matched_items", 0),
                sr.get("new_items", 0),
                sr.get("duration_ms", 0),
                sr.get("message", ""),
            ]
        )
    for i, w in enumerate([32, 12, 12, 14, 18, 10, 12, 56], start=1):
        ws_src.column_dimensions[get_column_letter(i)].width = w

    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def export_items_json(items: list[LegislativeItem]) -> bytes:
    payload = {
        "exported_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "count": len(items),
        "items": [it.to_dict() for it in items],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")


def export_items_markdown(items: list[LegislativeItem]) -> bytes:
    lines = [
        "# ADÓ Agent — Magyar és EU Adózási Törvényjavaslat Jelentés",
        f"_Generálva: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}_",
        f"_Találatok száma: {len(items)}_",
        "",
    ]
    for it in items:
        badges = [it.jurisdiction, f"Pontszám: {it.relevance_score}"]
        if it.is_new:
            badges.append("ÚJ")
        if it.is_updated:
            badges.append("FRISSÜLT")
        if it.is_bill:
            badges.append("Törvényjavaslat")
        if it.document_ref:
            badges.append(it.document_ref)

        lines.append(f"## [{it.title}]({it.url})")
        lines.append(f"**{' | '.join(badges)}** — _{it.source_name}_")
        if it.category_names:
            lines.append(f"- **Kategóriák:** {', '.join(it.category_names)}")
        if it.matched_keywords:
            lines.append(f"- **Kulcsszavak:** {', '.join(it.matched_keywords)}")
        if it.published_at:
            lines.append(f"- **Dátum:** {it.published_at}")
        if it.summary:
            lines.append(f"\n> {it.summary}")
        lines.append("")
    return "\n".join(lines).encode("utf-8")


def export_items_html(items: list[LegislativeItem]) -> bytes:
    rows_html: list[str] = []
    for it in items:
        badge = ""
        if it.is_new:
            badge = '<span class="badge new">ÚJ</span>'
        elif it.is_updated:
            badge = '<span class="badge upd">FRISSÜLT</span>'
        bill_badge = '<span class="badge bill">Törvényjavaslat</span>' if it.is_bill else ""
        cats = "".join(f'<span class="cat">{html.escape(c)}</span>' for c in it.category_names)
        rows_html.append(
            f"""
            <article class="card">
              <div class="meta">
                {badge} {bill_badge}
                <span class="jur">{html.escape(it.jurisdiction)}</span>
                <span class="src">{html.escape(it.source_name)}</span>
                <span class="score">Relevancia: {it.relevance_score}</span>
                {f'<span class="ref">{html.escape(it.document_ref)}</span>' if it.document_ref else ''}
                {f'<span class="date">{html.escape(it.published_at)}</span>' if it.published_at else ''}
              </div>
              <h2><a href="{html.escape(it.url)}" target="_blank" rel="noopener">{html.escape(it.title)}</a></h2>
              <div class="cats">{cats}</div>
              {f'<p class="summary">{html.escape(it.summary)}</p>' if it.summary else ''}
              <p class="kws"><strong>Kulcsszavak:</strong> {html.escape(', '.join(it.matched_keywords))}</p>
            </article>
            """
        )

    doc = f"""<!DOCTYPE html>
<html lang="hu">
<head>
<meta charset="utf-8">
<title>ADÓ Agent — Jelentés</title>
<style>
  body {{ font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 24px auto; max-width: 1020px; background: #f8fafc; color: #0f172a; padding: 0 16px; }}
  h1 {{ margin-bottom: 4px; }}
  .sub {{ color: #475569; margin-bottom: 24px; }}
  .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 16px; margin-bottom: 14px; }}
  .card h2 {{ margin: 8px 0; font-size: 1.08rem; }}
  .card h2 a {{ color: #1d4ed8; text-decoration: none; }}
  .card h2 a:hover {{ text-decoration: underline; }}
  .meta {{ display: flex; flex-wrap: wrap; gap: 8px; font-size: 0.82rem; color: #475569; align-items: center; }}
  .badge {{ padding: 2px 8px; border-radius: 999px; font-weight: 700; font-size: 0.75rem; }}
  .badge.new {{ background: #dcfce7; color: #166534; }}
  .badge.upd {{ background: #fef3c7; color: #92400e; }}
  .badge.bill {{ background: #fee2e2; color: #991b1b; }}
  .jur {{ background: #e0f2fe; color: #0369a1; padding: 2px 7px; border-radius: 6px; font-weight: 600; }}
  .cat {{ display: inline-block; background: #eef2ff; color: #3730a3; padding: 2px 8px; border-radius: 6px; font-size: 0.78rem; margin: 4px 6px 4px 0; }}
  .summary {{ color: #334155; font-size: 0.92rem; line-height: 1.45; }}
  .kws {{ color: #64748b; font-size: 0.82rem; margin-bottom: 0; }}
</style>
</head>
<body>
  <h1>ADÓ Agent — Összefoglaló Jelentés</h1>
  <p class="sub">Készült: {html.escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))} • Találatok: {len(items)}</p>
  {''.join(rows_html) if rows_html else '<p>Nincs megjeleníthető találat.</p>'}
</body>
</html>"""
    return doc.encode("utf-8")


def write_export_file(
    fmt: str,
    output_path: Path,
    items: list[LegislativeItem],
    latest_run: dict[str, Any] | None = None,
) -> Path:
    fmt_low = fmt.lower().lstrip(".")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if fmt_low == "xlsx":
        data = export_items_xlsx(items, latest_run=latest_run)
    elif fmt_low == "csv":
        data = export_items_csv(items)
    elif fmt_low == "html":
        data = export_items_html(items)
    elif fmt_low in ("md", "markdown"):
        data = export_items_markdown(items)
    elif fmt_low == "json":
        data = export_items_json(items)
    else:
        raise ValueError(f"Ismeretlen export formátum: {fmt}")

    output_path.write_bytes(data)
    return output_path
