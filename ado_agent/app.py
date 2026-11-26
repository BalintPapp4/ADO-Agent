"""Fő belépési pont (Asztali webes felület + CLI) az ADÓ Agent alkalmazáshoz."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __app_name__, __version__
from .config import AppConfig
from .exporter import write_export_file
from .scanner import TaxScanner
from .storage import Database
from .web.server import run_web_server


def _configure_console_utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ado-agent",
        description="ADÓ Agent — Magyar és EU-s adózási törvényjavaslat-figyelő (Windows & macOS)",
    )
    parser.add_argument("--version", action="version", version=f"{__app_name__} {__version__}")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help="Egyéni adatkönyvtár az adatbázishoz, konfigurációhoz és exportokhoz.",
    )
    parser.add_argument(
        "--scan",
        action="store_true",
        help="Parancssori (headless) ellenőrzés futtatása webszerver nélkül.",
    )
    parser.add_argument(
        "--sources",
        type=str,
        default="",
        help="Csak megadott forrásazonosítók ellenőrzése vesszővel elválasztva (pl. parlament_hu,kormany_hu).",
    )
    parser.add_argument(
        "--export",
        type=Path,
        default=None,
        help="Eredmények exportálása fájlba (.xlsx, .csv, .html, .md, .json).",
    )
    parser.add_argument(
        "--list-sources",
        action="store_true",
        help="Konfigurált források listázása és kilépés.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Webes irányítópult figyelési címe (alapértelmezett: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="Webes irányítópult portja (alapértelmezett: 8765).",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Ne nyissa meg automatikusan a böngészőt induláskor.",
    )
    parser.add_argument(
        "--no-auto-scan",
        action="store_true",
        help="Első induláskor ne indítson automatikus háttér-ellenőrzést.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    _configure_console_utf8()
    parser = build_parser()
    args = parser.parse_args(argv)

    config = AppConfig.load(data_dir=args.data_dir)
    db = Database(config.db_path)

    if args.list_sources:
        print(f"Konfigurált források ({len(config.sources)}):")
        for src in config.sources:
            status = "AKTÍV" if src.enabled else "kikapcsolva"
            print(f"  - [{src.jurisdiction}] {src.id:18s} ({status}) -> {src.url}")
        return 0

    if args.scan or args.export:
        if args.scan:
            source_ids = [s.strip() for s in args.sources.split(",") if s.strip()] or None
            scanner = TaxScanner(config, db)

            def cli_progress(msg: str, done: int, total: int) -> None:
                print(f"[{done}/{total}] {msg}", flush=True)

            summary = scanner.run_scan(source_ids=source_ids, progress_cb=cli_progress)
            print(
                f"\nKész: {summary.total_matched} találat "
                f"({summary.new_items} új, {summary.updated_items} frissült) | "
                f"Sikeres: {summary.succeeded_sources}, Figyelmeztetés: {summary.warning_sources}, "
                f"Hiba: {summary.failed_sources}"
            )
            for sr in summary.source_results:
                print(f"  * {sr.source_name}: [{sr.status.upper()}] {sr.message}")

        if args.export:
            fmt = args.export.suffix.lstrip(".").lower() or "xlsx"
            items = db.query_items()
            out_path = write_export_file(
                fmt=fmt,
                output_path=args.export,
                items=items,
                latest_run=db.get_latest_scan_run(),
            )
            print(f"Export elkészült ({len(items)} tétel): {out_path}")
        return 0

    # Alapértelmezett asztali / böngészős mód
    first_run = db.get_latest_scan_run() is None
    should_auto_scan = (first_run or config.scan_on_every_start) and not args.no_auto_scan
    run_web_server(
        config=config,
        db=db,
        host=args.host,
        port=args.port,
        open_browser=not args.no_browser,
        scan_on_start=should_auto_scan,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
