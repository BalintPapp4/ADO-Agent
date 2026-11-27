"""Párhuzamos jogszabály-ellenőrző vezérlő (Scanner)."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from .classifier import TaxClassifier
from .config import AppConfig
from .fetcher import HttpFetcher
from .models import LegislativeItem, ScanSummary, SourceConfig, SourceScanResult
from .sources.registry import build_adapter
from .storage import Database, utc_now_iso

ProgressCallback = Callable[[str, int, int], None]


class TaxScanner:
    """Összefogja a forrásadaptereket, a magyar/EU osztályozót és az SQLite tárhelyet."""

    def __init__(
        self,
        config: AppConfig,
        db: Database,
        fetcher: HttpFetcher | None = None,
    ) -> None:
        self.config = config
        self.db = db
        self.fetcher = fetcher or HttpFetcher(
            timeout_sec=config.request_timeout_sec,
            verify_ssl=config.verify_ssl,
        )

    def run_scan(
        self,
        source_ids: list[str] | None = None,
        progress_cb: ProgressCallback | None = None,
    ) -> ScanSummary:
        started_at = utc_now_iso()
        classifier = TaxClassifier(custom_keywords=self.config.custom_keywords)

        enabled_sources = [s for s in self.config.sources if s.enabled]
        if source_ids:
            allowed = set(source_ids)
            enabled_sources = [s for s in self.config.sources if s.id in allowed]

        total_sources = len(enabled_sources)
        source_results: list[SourceScanResult] = []
        all_items: list[LegislativeItem] = []

        if total_sources == 0:
            finished_at = utc_now_iso()
            summary = ScanSummary(
                run_id=0,
                started_at=started_at,
                finished_at=finished_at,
                status="empty",
                total_sources=0,
                succeeded_sources=0,
                warning_sources=0,
                failed_sources=0,
                total_matched=0,
                new_items=0,
                updated_items=0,
                source_results=[],
            )
            summary.run_id = self.db.save_scan_run(summary)
            return summary

        def scan_single(src: SourceConfig) -> tuple[SourceScanResult, list[LegislativeItem]]:
            t0 = time.monotonic()
            adapter = build_adapter(src, self.fetcher)
            out = adapter.collect()
            matched: list[LegislativeItem] = []
            seen_keys: set[str] = set()
            for cand in out.candidates:
                item = classifier.enrich_candidate(cand, src)
                if item is not None and item.item_key not in seen_keys:
                    seen_keys.add(item.item_key)
                    matched.append(item)

            duration_ms = int((time.monotonic() - t0) * 1000)

            if out.ok_requests == 0 and out.errors:
                status = "error"
                msg = "; ".join(out.errors[:3])
            elif out.warnings:
                status = "warning"
                parts = list(out.warnings[:2]) + list(out.errors[:2])
                msg = " | ".join(parts)
            elif out.errors and len(out.candidates) == 0:
                status = "warning"
                msg = " | ".join(out.errors[:3])
            elif len(out.candidates) == 0:
                status = "warning"
                msg = "Az oldal válaszolt, de nem találtunk feldolgozható listaelemet."
            else:
                status = "ok"
                msg = (
                    f"{len(out.candidates)} nyers elem feldolgozva, "
                    f"{len(matched)} adózási találat."
                )
                if out.errors:
                    msg += f" ({len(out.errors)} másodlagos URL sikertelen)"

            res = SourceScanResult(
                source_id=src.id,
                source_name=src.name,
                jurisdiction=src.jurisdiction,
                status=status,
                fetched_candidates=len(out.candidates),
                matched_items=len(matched),
                duration_ms=duration_ms,
                message=msg,
                checked_urls=out.checked_urls,
            )
            return res, matched

        workers = max(1, min(self.config.max_workers, total_sources))
        completed_count = 0
        per_source_items: dict[str, list[LegislativeItem]] = {}

        if progress_cb:
            progress_cb(f"Ellenőrzés indítása ({total_sources} forrás)...", 0, total_sources)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            future_map = {pool.submit(scan_single, src): src for src in enabled_sources}
            for fut in as_completed(future_map):
                src = future_map[fut]
                completed_count += 1
                try:
                    src_res, items = fut.result()
                except Exception as exc:
                    src_res = SourceScanResult(
                        source_id=src.id,
                        source_name=src.name,
                        jurisdiction=src.jurisdiction,
                        status="error",
                        message=f"Váratlan hiba: {exc}",
                    )
                    items = []
                source_results.append(src_res)
                per_source_items[src.id] = items
                all_items.extend(items)
                if progress_cb:
                    progress_cb(
                        f"Kész: {src.name} ({src_res.matched_items} találat)",
                        completed_count,
                        total_sources,
                    )

        # Rendezés a config sorrendje szerint
        order_idx = {s.id: idx for idx, s in enumerate(enabled_sources)}
        source_results.sort(key=lambda r: order_idx.get(r.source_id, 999))

        # Adatbázisba mentés és új/frissült számlálók frissítése forrásonként
        now = utc_now_iso()
        total_new = 0
        total_updated = 0
        for src_res in source_results:
            src_items = per_source_items.get(src_res.source_id, [])
            if src_items:
                n_cnt, u_cnt = self.db.upsert_items(src_items, seen_at=now)
                src_res.new_items = n_cnt
                src_res.updated_items = u_cnt
                total_new += n_cnt
                total_updated += u_cnt

        # Régebbi tárolt elemek címkéinek frissítése (pl. egyéni kulcsszavak / forrásnevek)
        self.db.reclassify_items(
            classifier,
            source_tax_context={s.id: s.always_include_tax_context for s in self.config.sources},
            source_names={s.id: s.name for s in self.config.sources},
        )

        succeeded = sum(1 for r in source_results if r.status == "ok")
        warnings = sum(1 for r in source_results if r.status == "warning")
        failed = sum(1 for r in source_results if r.status == "error")

        if failed == total_sources:
            overall_status = "error"
        elif failed > 0 or warnings > 0:
            overall_status = "partial"
        else:
            overall_status = "ok"

        summary = ScanSummary(
            run_id=0,
            started_at=started_at,
            finished_at=utc_now_iso(),
            status=overall_status,
            total_sources=total_sources,
            succeeded_sources=succeeded,
            warning_sources=warnings,
            failed_sources=failed,
            total_matched=len(all_items),
            new_items=total_new,
            updated_items=total_updated,
            source_results=source_results,
        )
        summary.run_id = self.db.save_scan_run(summary)
        return summary
