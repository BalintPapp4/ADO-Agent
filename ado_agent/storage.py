"""SQLite perzisztencia az ADÓ Agent számára — találatok, felhasználók, állapotok és megjegyzések."""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from .classifier import TaxClassifier
from .models import LegislativeItem, ScanSummary


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def hash_password(password: str) -> str:
    """Sózott scrypt jelszó-hash külső csomag nélkül."""
    salt = secrets.token_hex(16)
    dk = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt.encode("ascii"),
        n=16384,
        r=8,
        p=1,
        dklen=32,
    )
    return f"scrypt${salt}${dk.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algo, salt, expected_hex = stored_hash.split("$", 2)
        if algo != "scrypt":
            return False
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt.encode("ascii"),
            n=16384,
            r=8,
            p=1,
            dklen=32,
        )
        return hmac.compare_digest(dk.hex(), expected_hex)
    except Exception:
        return False


class Database:
    """Szálbiztos SQLite adattár a jogszabály-találatokhoz, felhasználókhoz és megjegyzésekhez."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(str(self.db_path), timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        try:
            with conn:
                yield conn
        finally:
            conn.close()

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

                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_admin INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS user_item_states (
                    user_id INTEGER NOT NULL,
                    item_key TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    is_bookmarked INTEGER NOT NULL DEFAULT 0,
                    updated_at TEXT NOT NULL DEFAULT '',
                    PRIMARY KEY (user_id, item_key),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                    FOREIGN KEY (item_key) REFERENCES items(item_key) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_uis_user ON user_item_states(user_id);

                CREATE TABLE IF NOT EXISTS item_comments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_key TEXT NOT NULL,
                    user_id INTEGER,
                    author_name TEXT NOT NULL,
                    body TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (item_key) REFERENCES items(item_key) ON DELETE CASCADE,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
                );

                CREATE INDEX IF NOT EXISTS idx_comments_item ON item_comments(item_key, id ASC);
                """
            )

    # ---------------- Felhasználók ----------------

    def _row_to_user(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": int(row["id"]),
            "username": row["username"],
            "display_name": row["display_name"],
            "is_admin": bool(row["is_admin"]),
            "created_at": row["created_at"],
        }

    def create_user(
        self,
        username: str,
        password: str,
        display_name: str = "",
        is_admin: bool = False,
    ) -> dict[str, Any]:
        uname = username.strip().lower()
        if not uname or len(uname) < 2:
            raise ValueError("A felhasználónév legalább 2 karakter legyen.")
        if not password or len(password) < 4:
            raise ValueError("A jelszó legalább 4 karakter legyen.")
        dname = display_name.strip() or uname
        now = utc_now_iso()
        pw_hash = hash_password(password)
        with self._lock, self._connect() as conn:
            try:
                cur = conn.execute(
                    """
                    INSERT INTO users (username, display_name, password_hash, is_admin, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (uname, dname, pw_hash, 1 if is_admin else 0, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"A(z) '{uname}' felhasználónév már létezik.") from exc
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cur.lastrowid,)).fetchone()
            return self._row_to_user(row)

    def ensure_users_from_env(self, raw_spec: str) -> int:
        """
        Felhasználók betöltése ADO_USERS környezeti változóból.
        Formátum (vesszővel vagy pontosvesszővel elválasztva):
          felhasznalo:jelszo
          felhasznalo:jelszo:admin
          felhasznalo:jelszo:Megjelenített Név:admin
        Meglévő felhasználót nem ír felül.
        """
        created = 0
        if not raw_spec.strip():
            return 0
        entries = [e.strip() for e in raw_spec.replace(";", ",").split(",") if e.strip()]
        with self._lock, self._connect() as conn:
            for idx, entry in enumerate(entries):
                parts = entry.split(":")
                if len(parts) < 2:
                    continue
                uname = parts[0].strip().lower()
                pw = parts[1].strip()
                if not uname or not pw:
                    continue
                display_name = uname
                is_admin = idx == 0
                if len(parts) == 3:
                    if parts[2].strip().lower() in ("admin", "user"):
                        is_admin = parts[2].strip().lower() == "admin"
                    elif parts[2].strip():
                        display_name = parts[2].strip()
                elif len(parts) >= 4:
                    if parts[2].strip():
                        display_name = parts[2].strip()
                    is_admin = parts[3].strip().lower() == "admin"

                exists = conn.execute(
                    "SELECT id FROM users WHERE username = ?", (uname,)
                ).fetchone()
                if exists is None:
                    conn.execute(
                        """
                        INSERT INTO users (username, display_name, password_hash, is_admin, created_at)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (uname, display_name, hash_password(pw), 1 if is_admin else 0, utc_now_iso()),
                    )
                    created += 1
        return created

    def authenticate_user(self, username: str, password: str) -> dict[str, Any] | None:
        uname = username.strip().lower()
        if not uname or not password:
            return None
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (uname,)
            ).fetchone()
            if row is None:
                return None
            if not verify_password(password, row["password_hash"]):
                return None
            return self._row_to_user(row)

    def get_user_by_id(self, user_id: int) -> dict[str, Any] | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return self._row_to_user(row) if row else None

    def list_users(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT * FROM users ORDER BY is_admin DESC, username ASC").fetchall()
            return [self._row_to_user(r) for r in rows]

    def delete_user(self, user_id: int) -> bool:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            return cur.rowcount > 0

    def update_user_password(self, user_id: int, new_password: str) -> bool:
        if not new_password or len(new_password) < 4:
            raise ValueError("A jelszó legalább 4 karakter legyen.")
        with self._lock, self._connect() as conn:
            cur = conn.execute(
                "UPDATE users SET password_hash = ? WHERE id = ?",
                (hash_password(new_password), user_id),
            )
            return cur.rowcount > 0

    # ---------------- Elemek és futások ----------------

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
                    if changed:
                        conn.execute(
                            "UPDATE user_item_states SET is_read = 0, updated_at = ? WHERE item_key = ?",
                            (now, item.item_key),
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

    # ---------------- Megjegyzések ----------------

    def add_comment(
        self,
        item_key: str,
        body: str,
        user_id: int | None,
        author_name: str,
    ) -> dict[str, Any] | None:
        text = body.strip()
        if not text:
            raise ValueError("A megjegyzés nem lehet üres.")
        now = utc_now_iso()
        with self._lock, self._connect() as conn:
            exists = conn.execute("SELECT 1 FROM items WHERE item_key = ?", (item_key,)).fetchone()
            if exists is None:
                return None
            cur = conn.execute(
                """
                INSERT INTO item_comments (item_key, user_id, author_name, body, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (item_key, user_id, author_name.strip() or "Felhasználó", text, now),
            )
            row = conn.execute("SELECT * FROM item_comments WHERE id = ?", (cur.lastrowid,)).fetchone()
            return {
                "id": int(row["id"]),
                "item_key": row["item_key"],
                "user_id": row["user_id"],
                "author_name": row["author_name"],
                "body": row["body"],
                "created_at": row["created_at"],
            }

    def delete_comment(
        self,
        comment_id: int,
        requester_user_id: int | None = None,
        is_admin: bool = False,
    ) -> bool:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT id, user_id FROM item_comments WHERE id = ?", (comment_id,)).fetchone()
            if row is None:
                return False
            if requester_user_id is not None and not is_admin and row["user_id"] != requester_user_id:
                raise PermissionError("Csak a saját megjegyzésedet törölheted.")
            cur = conn.execute("DELETE FROM item_comments WHERE id = ?", (comment_id,))
            return cur.rowcount > 0

    def _get_comments_map(self, conn: sqlite3.Connection, item_keys: list[str]) -> dict[str, list[dict[str, Any]]]:
        if not item_keys:
            return {}
        placeholders = ",".join("?" for _ in item_keys)
        rows = conn.execute(
            f"SELECT * FROM item_comments WHERE item_key IN ({placeholders}) ORDER BY id ASC",
            item_keys,
        ).fetchall()
        result: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            result.setdefault(r["item_key"], []).append(
                {
                    "id": int(r["id"]),
                    "item_key": r["item_key"],
                    "user_id": r["user_id"],
                    "author_name": r["author_name"],
                    "body": r["body"],
                    "created_at": r["created_at"],
                }
            )
        return result

    # ---------------- Lekérdezés és állapotok ----------------

    def query_items(
        self,
        jurisdiction: str = "",
        category: str = "",
        source_id: str = "",
        search: str = "",
        only_new: bool = False,
        only_unread: bool = False,
        only_read: bool = False,
        only_bills: bool = False,
        only_bookmarked: bool = False,
        sort_by: str = "relevance",
        limit: int = 500,
        user_id: int | None = None,
    ) -> list[LegislativeItem]:
        clauses: list[str] = []
        params: list[Any] = []

        if user_id is not None:
            select_sql = (
                "SELECT items.*, COALESCE(uis.is_read, 0) AS u_is_read, "
                "COALESCE(uis.is_bookmarked, 0) AS u_is_bookmarked "
                "FROM items LEFT JOIN user_item_states uis "
                "ON uis.item_key = items.item_key AND uis.user_id = ?"
            )
            params.append(user_id)
            read_expr = "COALESCE(uis.is_read, 0)"
            bm_expr = "COALESCE(uis.is_bookmarked, 0)"
            new_expr = "(CASE WHEN COALESCE(uis.is_read, 0) = 0 AND items.is_new = 1 THEN 1 ELSE 0 END)"
            upd_expr = "(CASE WHEN COALESCE(uis.is_read, 0) = 0 AND items.is_updated = 1 THEN 1 ELSE 0 END)"
        else:
            select_sql = "SELECT items.* FROM items"
            read_expr = "items.is_read"
            bm_expr = "items.is_bookmarked"
            new_expr = "items.is_new"
            upd_expr = "items.is_updated"

        if jurisdiction and jurisdiction.upper() in ("HU", "EU"):
            clauses.append("items.jurisdiction = ?")
            params.append(jurisdiction.upper())
        if source_id:
            clauses.append("items.source_id = ?")
            params.append(source_id)
        if only_new:
            clauses.append(f"({new_expr} = 1 OR {upd_expr} = 1)")
        if only_unread:
            clauses.append(f"{read_expr} = 0")
        if only_read:
            clauses.append(f"{read_expr} = 1")
        if only_bills:
            clauses.append("items.is_bill = 1")
        if only_bookmarked:
            clauses.append(f"{bm_expr} = 1")
        if category:
            clauses.append("items.categories_json LIKE ?")
            params.append(f'%"{category}"%')
        if search:
            like = f"%{search.strip()}%"
            clauses.append(
                "(items.title LIKE ? OR items.summary LIKE ? OR items.document_ref LIKE ? "
                "OR items.matched_keywords_json LIKE ? OR items.notes LIKE ? "
                "OR EXISTS (SELECT 1 FROM item_comments ic WHERE ic.item_key = items.item_key AND ic.body LIKE ?))"
            )
            params.extend([like, like, like, like, like, like])

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        if sort_by == "newest":
            order = f"ORDER BY {new_expr} DESC, {upd_expr} DESC, items.first_seen_at DESC, items.relevance_score DESC"
        elif sort_by == "published":
            order = "ORDER BY items.published_at DESC, items.relevance_score DESC, items.first_seen_at DESC"
        else:
            order = (
                f"ORDER BY {bm_expr} DESC, {new_expr} DESC, {upd_expr} DESC, "
                "items.relevance_score DESC, items.last_seen_at DESC"
            )

        sql = f"{select_sql} {where} {order} LIMIT ?"
        params.append(limit)

        with self._lock, self._connect() as conn:
            rows = conn.execute(sql, params).fetchall()
            keys = [r["item_key"] for r in rows]
            comments_map = self._get_comments_map(conn, keys)
            return [
                self._row_to_item(r, comments=comments_map.get(r["item_key"], []), per_user=(user_id is not None))
                for r in rows
            ]

    def _row_to_item(
        self,
        row: sqlite3.Row,
        comments: list[dict[str, Any]] | None = None,
        per_user: bool = False,
    ) -> LegislativeItem:
        if per_user:
            eff_read = bool(row["u_is_read"])
            eff_bookmarked = bool(row["u_is_bookmarked"])
            eff_new = bool(row["is_new"]) and not eff_read
            eff_updated = bool(row["is_updated"]) and not eff_read
        else:
            eff_read = bool(row["is_read"])
            eff_bookmarked = bool(row["is_bookmarked"])
            eff_new = bool(row["is_new"])
            eff_updated = bool(row["is_updated"])

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
            is_new=eff_new,
            is_updated=eff_updated,
            is_read=eff_read,
            is_bookmarked=eff_bookmarked,
            notes=row["notes"] or "",
            comments=comments or [],
            raw_metadata=json.loads(row["raw_metadata_json"] or "{}"),
        )

    def update_item_flags(
        self,
        item_key: str,
        is_read: bool | None = None,
        is_bookmarked: bool | None = None,
        notes: str | None = None,
        user_id: int | None = None,
    ) -> bool:
        if user_id is not None:
            now = utc_now_iso()
            with self._lock, self._connect() as conn:
                exists = conn.execute("SELECT 1 FROM items WHERE item_key = ?", (item_key,)).fetchone()
                if exists is None:
                    return False
                if is_read is not None or is_bookmarked is not None:
                    cur_state = conn.execute(
                        "SELECT is_read, is_bookmarked FROM user_item_states WHERE user_id = ? AND item_key = ?",
                        (user_id, item_key),
                    ).fetchone()
                    new_read = int(is_read) if is_read is not None else (int(cur_state["is_read"]) if cur_state else 0)
                    new_bm = (
                        int(is_bookmarked)
                        if is_bookmarked is not None
                        else (int(cur_state["is_bookmarked"]) if cur_state else 0)
                    )
                    conn.execute(
                        """
                        INSERT INTO user_item_states (user_id, item_key, is_read, is_bookmarked, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                        ON CONFLICT(user_id, item_key) DO UPDATE SET
                            is_read = excluded.is_read,
                            is_bookmarked = excluded.is_bookmarked,
                            updated_at = excluded.updated_at
                        """,
                        (user_id, item_key, new_read, new_bm, now),
                    )
                if notes is not None:
                    conn.execute("UPDATE items SET notes = ? WHERE item_key = ?", (notes, item_key))
                return True

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

    def mark_all_read(self, user_id: int | None = None) -> int:
        if user_id is not None:
            now = utc_now_iso()
            with self._lock, self._connect() as conn:
                cur = conn.execute(
                    """
                    INSERT INTO user_item_states (user_id, item_key, is_read, is_bookmarked, updated_at)
                    SELECT ?, item_key, 1, 0, ? FROM items
                    ON CONFLICT(user_id, item_key) DO UPDATE SET
                        is_read = 1,
                        updated_at = excluded.updated_at
                    """,
                    (user_id, now),
                )
                return cur.rowcount
        with self._lock, self._connect() as conn:
            cur = conn.execute("UPDATE items SET is_read = 1, is_new = 0, is_updated = 0")
            return cur.rowcount

    def clear_items(self) -> int:
        with self._lock, self._connect() as conn:
            cur = conn.execute("DELETE FROM items")
            return cur.rowcount

    def reclassify_items(
        self,
        classifier: TaxClassifier,
        source_tax_context: dict[str, bool] | None = None,
        source_names: dict[str, str] | None = None,
    ) -> dict[str, int]:
        """Meglévő tárolt elemek újracímkézése (pl. egyéni kulcsszavak mentésekor) állapotok megőrzésével."""
        tax_ctx = source_tax_context or {}
        src_names = source_names or {}
        updated_rows = 0
        custom_matched = 0

        with self._lock, self._connect() as conn:
            rows = conn.execute(
                """
                SELECT item_key, title, url, source_id, source_name, jurisdiction,
                       summary, document_ref, relevance_score, is_bill,
                       categories_json, category_names_json, matched_keywords_json
                FROM items
                """
            ).fetchall()

            for row in rows:
                old_cats = json.loads(row["categories_json"] or "[]")
                old_cat_names = json.loads(row["category_names_json"] or "[]")
                old_kws = json.loads(row["matched_keywords_json"] or "[]")
                always_tax = bool(
                    tax_ctx.get(row["source_id"], "NAV / adóhatósági tájékoztató" in old_kws)
                )
                res = classifier.classify(
                    title=row["title"],
                    summary=row["summary"],
                    url=row["url"],
                    jurisdiction=row["jurisdiction"],
                    always_include_tax_context=always_tax,
                )

                if res.relevant:
                    new_cats = [m.category_id for m in res.category_matches]
                    new_cat_names = [m.category_name for m in res.category_matches]
                    new_kws = res.matched_keywords
                    new_score = res.relevance_score
                    new_bill = 1 if res.is_bill else 0
                    new_doc_ref = res.document_ref or row["document_ref"]
                else:
                    # Ha korábban csak törölt egyéni kulcsszó miatt volt releváns, ne töröljük a sort
                    # (olvasottság/megjegyzések megmaradnak), csak távolítsuk el az 'egyeni' címkét.
                    new_cats = [c for c in old_cats if c != "egyeni"]
                    new_cat_names = [n for n in old_cat_names if n != "Egyéni kulcsszavak"]
                    new_kws = old_kws if not new_cats else [k for k in old_kws]
                    new_score = int(row["relevance_score"])
                    new_bill = int(row["is_bill"])
                    new_doc_ref = row["document_ref"]

                if "egyeni" in new_cats:
                    custom_matched += 1

                new_source_name = src_names.get(row["source_id"], row["source_name"]) or row["source_name"]

                if (
                    new_cats != old_cats
                    or new_cat_names != old_cat_names
                    or new_kws != old_kws
                    or new_score != int(row["relevance_score"])
                    or new_bill != int(row["is_bill"])
                    or new_doc_ref != row["document_ref"]
                    or new_source_name != row["source_name"]
                ):
                    conn.execute(
                        """
                        UPDATE items SET
                            source_name = ?,
                            categories_json = ?,
                            category_names_json = ?,
                            matched_keywords_json = ?,
                            relevance_score = ?,
                            is_bill = ?,
                            document_ref = ?
                        WHERE item_key = ?
                        """,
                        (
                            new_source_name,
                            json.dumps(new_cats, ensure_ascii=False),
                            json.dumps(new_cat_names, ensure_ascii=False),
                            json.dumps(new_kws, ensure_ascii=False),
                            new_score,
                            new_bill,
                            new_doc_ref,
                            row["item_key"],
                        ),
                    )
                    updated_rows += 1

        return {
            "total_items": len(rows),
            "updated_rows": updated_rows,
            "custom_matched": custom_matched,
        }

    def get_stats(self, user_id: int | None = None) -> dict[str, Any]:
        with self._lock, self._connect() as conn:
            if user_id is not None:
                rows = conn.execute(
                    """
                    SELECT items.jurisdiction, items.source_id, items.is_bill,
                           items.is_new, items.is_updated, items.categories_json, items.notes,
                           COALESCE(uis.is_read, 0) AS eff_read,
                           COALESCE(uis.is_bookmarked, 0) AS eff_bookmarked
                    FROM items
                    LEFT JOIN user_item_states uis
                      ON uis.item_key = items.item_key AND uis.user_id = ?
                    """,
                    (user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT jurisdiction, source_id, is_bill, is_new, is_updated, categories_json, notes,
                           is_read AS eff_read, is_bookmarked AS eff_bookmarked
                    FROM items
                    """
                ).fetchall()

        total = len(rows)
        new_count = sum(1 for r in rows if r["is_new"] and not r["eff_read"])
        updated_count = sum(1 for r in rows if r["is_updated"] and not r["eff_read"])
        unread_count = sum(1 for r in rows if not r["eff_read"])
        read_count = sum(1 for r in rows if r["eff_read"])
        bookmarked_count = sum(1 for r in rows if r["eff_bookmarked"])
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
