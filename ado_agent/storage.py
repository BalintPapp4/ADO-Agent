"""SQLite perzisztencia az ADÓ Agent számára — találatok, diffing, előzmények."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import LegislativeItem, ScanSummary, SourceScanResult


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


class Database:
    """Szálbiztos SQLite adattár a jogszabály-találatokhoz és futási előzményekhez."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS items (
                    item_key TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    source_id TEXT NOT NULL,
                    source_name TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    summary TEXT NOT NULL DEFAULT '',
                    published_at TEXT NOT NULL DEFAULT '',
                    document_ref TEXT NOT NULL DEFAULT '',
                    status_label TEXT NOT NULL DEFAULT '',
                    relevance_score INTEGER NOT NULL DEFAULT 0,
                    is_bill INTEGER NOT NULL DEFAULT 0,
                    categories_json TEXT NOT NULL DEFAULT '[]',
                    category_names_json TEXT NOT NULL DEFAULT '[]',
                    matched_keywords_json TEXT NOT NULL DEFAULT '[]',
                    content_hash TEXT NOT NULL DEFAULT '',
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL,
                    is_new INTEGER NOT NULL DEFAULT 1,
                    is_updated INTEGER NOT NULL DEFAULT 0,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    is_bookmarked INTEGER NOT NULL DEFAULT 0,
                    notes TEXT NOT NULL DEFAULT '',
                    raw_metadata_json TEXT NOT NULL DEFAULT '{}'
                );

                CREATE INDEX IF NOT EXISTS idx_items_source ON items(source_id);
                CREATE INDEX IF NOT EXISTS idx_items_jurisdiction ON items(jurisdiction);
                CREATE INDEX IF NOT EXISTS idx_items_score ON items(relevance_score DESC);
                CREATE INDEX IF NOT EXISTS idx_items_last_seen ON items(last_seen_at DESC);

                CREATE TABLE IF NOT EXISTS scan_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    total_sources INTEGER NOT NULL,
                    succeeded_sources INTEGER NOT NULL,
                    warning_sources INTEGER NOT NULL,
                    failed_sources INTEGER NOT NULL,
                    total_matched INTEGER NOT NULL,
                    new_items INTEGER NOT NULL,
                    updated_items INTEGER NOT NULL,
                    source_results_json TEXT NOT NULL DEFAULT '[]'
                );
                """
            )

    def upsert_items(self, items: list[LegislativeItem], seen_at: str | None = None) -> tuple[int, int]:
        """Elemek mentése, visszaadva az (új_db, frissült_db) párost."""
        now = seen_at or utc_now_iso()
        new_count = 0
        updated_count = 0

        with self._lock, self._connect() as conn:
            for item in items:
                existing = conn.execute(
                    "SELECT content_hash, first_seen_at, is_read, is_bookmarked, notes FROM items WHERE item_key = ?",
                    (item.item_key,),
                ).fetchone()

                if existing is None:
                    new_count += 1
                    item.first_seen_at = now
                    item.last_seen_at = now
                    item.is_new = True
                    item.is_updated = False
                    conn.execute(
                        """
                        INSERT INTO items (
                            item_key, title, url, source_id, source_name, jurisdiction,
                            summary, published_at, document_ref, status_label, relevance_score,
                            is_bill, categories_json, category_names_json, matched_keywords_json,
                            content_hash, first_seen_at, last_seen_at,
                            is_new, is_updated, is_read, is_bookmarked, notes, raw_metadata_json
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 0, 0, 0, '', ?)
                        """,
                        (
                            item.item_key,
                            item.title,
                            item.url,
                            item.source_id,
                            item.source_name,
                            item.jurisdiction,
                            item.summary,
                            item.published_at,
                            item.document_ref,
                            item.status_label,
                            item.relevance_score,
                            1 if item.is_bill else 0,
                            json.dumps(item.categories, ensure_ascii=False),
                            json.dumps(item.category_names, ensure_ascii=False),
                            json.dumps(item.matched_keywords, ensure_ascii=False),
                            item.content_hash,
                            now,
                            now,
                            json.dumps(item.raw_metadata, ensure_ascii=False),
                        ),
                    )
                else:
                    changed = existing["content_hash"] != item.content_hash
                    if changed:
                        updated_count += 1
                    item.first_seen_at = existing["first_seen_at"]
                    item.last_seen_at = now
                    item.is_new = False
                    item.is_updated = changed
                    item.is_read = False if changed else bool(existing["is_read"])
                    item.is_bookmarked = bool(existing["is_bookmarked"])
                    item.notes = existing["notes"]

                    conn.execute(
                        """
                        UPDATE items SET
                            title = ?,
                            url = ?,
                            source_name = ?,
                            jurisdiction = ?,
                            summary = ?,
                            published_at = ?,
                            document_ref = ?,
                            status_label = ?,
                            relevance_score = ?,
                            is_bill = ?,
                            categories_json = ?,
                            category_names_json = ?,
                            matched_keywords_json = ?,
                            content_hash = ?,
                            last_seen_at = ?,
                            is_new = 0,
                            is_updated = ?,
                            is_read = ?,
                            raw_metadata_json = ?
                        WHERE item_key = ?
                        """,
                        (
                            item.title,
                            item.url,
                            item.source_name,
                            item.jurisdiction,
                            item.summary,
                            item.published_at,
                            item.document_ref,
                            item.status_label,
                            item.relevance_score,
                            1 if item.is_bill else 0,
                            json.dumps(item.categories, ensure_ascii=False),
                            json.dumps(item.category_names, ensure_ascii=False),
                            json.dumps(item.matched_keywords, ensure_ascii=False),
                            item.content_hash,
                            now,
                            1 if changed else 0,
                            0 if changed else int(existing["is_read"]),
                            json.dumps(item.raw_metadata, ensure_ascii=False),
                            item.item_key,
                        ),
                    )
        return new_count, updated_count

    def save_scan_run(self, summary: ScanSummary) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO scan_runs (
                    started_at, finished_at, status,
                    total_sources, succeeded_sources, warning_sources, failed_sources,
                    total_matched, new_items, updated_items, source_results_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.started_at,
                    summary.finished_at,
                    summary.status,
                    summary.total_sources,
                    summary.succeeded_sources,
                    summary.warning_sources,
                    summary.failed_sources,
                    summary.total_matched,
                    summary.new_items,
                    summary.updated_items,
                    json.dumps([r.to_dict() for r in summary.source_results], ensure_ascii=False),
                ),
            )
            return int(cur.lastrowid)

    def get_latest_scan_run(self) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM scan_runs ORDER BY id DESC LIMIT 1"
            ).fetchone()
            if not row:
                return None
            return self._row_to_run(row)

    def get_scan_history(self, limit: int = 15) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM scan_runs ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [self._row_to_run(r) for r in rows]

    def _row_to_run(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
            "status": row["status"],
            "total_sources": row["total_sources"],
            "succeeded_sources": row["succeeded_sources"],
            "warning_sources": row["warning_sources"],
            "failed_sources": row["failed_sources"],
            "total_matched": row["total_matched"],
            "new_items": row["new_items"],
            "updated_items": row["updated_items"],
            "source_results": json.loads(row["source_results_json"] or "[]"),
        }

    def query_items(
        self,
        jurisdiction: str = "",
        category: str = "",
        source_id: str = "",
        search: str = "",
        only_new: bool = False,
        only_bills: bool = False,
        only_bookmarked: bool = False,
        sort_by: str = "relevance",
        limit: int = 500,
    ) -> list[LegislativeItem]:
        clauses: list[str] = []
        params: list[Any] = []

        if jurisdiction and jurisdiction.upper() in ("HU", "EU"):
            clauses.append("jurisdiction = ?")
            params.append(jurisdiction.upper())
        if source_id:
            clauses.append("source_id = ?")
            params.append(source_id)
        if only_new:
            clauses.append("(is_new = 1 OR is_updated = 1)")
        if only_bills:
            clauses.append("is_bill = 1")
        if only_bookmarked:
            clauses.append("is_bookmarked = 1")
        if category:
            clauses.append("categories_json LIKE ?")
            params.append(f'%"{category}"%')
        if search:
            like = f"%{search.strip()}%"
            clauses.append(
                "(title LIKE ? OR summary LIKE ? OR document_ref LIKE ? OR matched_keywords_json LIKE ? OR notes LIKE ?)"
            )
            params.extend([like, like, like, like, like])

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        if sort_by == "newest":
            order = "ORDER BY is_new DESC, is_updated DESC, first_seen_at DESC, relevance_score DESC"
        elif sort_by == "published":
            order = "ORDER BY published_at DESC, relevance_score DESC, first_seen_at DESC"
        else:
            order = "ORDER BY is_bookmarked DESC, is_new DESC, is_updated DESC, relevance_score DESC, last_seen_at DESC"

        sql = f"SELECT * FROM items {where} {order} LIMIT ?"
        params.append(limit)

        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_item(r) for r in rows]

    def _row_to_item(self, row: sqlite3.Row) -> LegislativeItem:
        return LegislativeItem(
            item_key=row["item_key"],
            title=row["title"],
            url=row["url"],
            source_id=row["source_id"],
            source_name=row["source_name"],
            jurisdiction=row["jurisdiction"],
            summary=row["summary"],
            published_at=row["published_at"],
            document_ref=row["document_ref"],
            status_label=row["status_label"],
            relevance_score=int(row["relevance_score"]),
            is_bill=bool(row["is_bill"]),
            categories=json.loads(row["categories_json"] or "[]"),
            category_names=json.loads(row["category_names_json"] or "[]"),
            matched_keywords=json.loads(row["matched_keywords_json"] or "[]"),
            content_hash=row["content_hash"],
            first_seen_at=row["first_seen_at"],
            last_seen_at=row["last_seen_at"],
            is_new=bool(row["is_new"]),
            is_updated=bool(row["is_updated"]),
            is_read=bool(row["is_read"]),
            is_bookmarked=bool(row["is_bookmarked"]),
            notes=row["notes"] or "",
            raw_metadata=json.loads(row["raw_metadata_json"] or "{}"),
        )

    def update_item_flags(
        self,
        item_key: str,
        is_read: bool | None = None,
        is_bookmarked: bool | None = None,
        notes: str | None = None,
    ) -> bool:
        updates: list[str] = []
        params: list[Any] = []
        if is_read is not None:
            updates.append("is_read = ?")
            params.append(1 if is_read else 0)
            if is_read:
                updates.append("is_new = 0")
                updates.append("is_updated = 0")
        if is_bookmarked is not None:
            updates.append("is_bookmarked = ?")
            params.append(1 if is_bookmarked else 0)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)

        if not updates:
            return False
        params.append(item_key)
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                f"UPDATE items SET {', '.join(updates)} WHERE item_key = ?",
                params,
            )
            return cur.rowcount > 0

    def mark_all_read(self) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute("UPDATE items SET is_read = 1, is_new = 0, is_updated = 0")
            return cur.rowcount

    def clear_items(self) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM items")
            return cur.rowcount

    def get_stats(self) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT jurisdiction, source_id, is_bill, is_new, is_updated, is_read, is_bookmarked, notes, categories_json FROM items"
            ).fetchall()

        total = len(rows)
        new_count = sum(1 for r in rows if r["is_new"])
        updated_count = sum(1 for r in rows if r["is_updated"])
        unread_count = sum(1 for r in rows if not r["is_read"])
        read_count = sum(1 for r in rows if r["is_read"])
        bookmarked_count = sum(1 for r in rows if r["is_bookmarked"])
        noted_count = sum(1 for r in rows if (r["notes"] or "").strip())
        bills_count = sum(1 for r in rows if r["is_bill"])

        by_jurisdiction: dict[str, int] = {"HU": 0, "EU": 0}
        by_category: dict[str, int] = {}
        by_source: dict[str, int] = {}
        for r in rows:
            j = r["jurisdiction"]
            by_jurisdiction[j] = by_jurisdiction.get(j, 0) + 1
            s = r["source_id"]
            by_source[s] = by_source.get(s, 0) + 1
            for c in json.loads(r["categories_json"] or "[]"):
                by_category[c] = by_category.get(c, 0) + 1

        return {
            "total": total,
            "new_count": new_count,
            "updated_count": updated_count,
            "unread_count": unread_count,
            "read_count": read_count,
            "bookmarked_count": bookmarked_count,
            "noted_count": noted_count,
            "bills_count": bills_count,
            "by_jurisdiction": by_jurisdiction,
            "by_category": by_category,
            "by_source": by_source,
        }
