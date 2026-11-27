"""Flask + Waitress webes irányítópult, több felhasználós belépés és REST API."""

from __future__ import annotations

import logging
import os
import re
import secrets
import socket
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from flask import Flask, Response, jsonify, redirect, render_template, request, session, url_for
from waitress import create_server
from werkzeug.middleware.proxy_fix import ProxyFix

from .. import __app_name__, __version__
from ..classifier import TaxClassifier, get_category_catalog, normalize_whitespace
from ..config import AppConfig
from ..exporter import (
    export_items_csv,
    export_items_html,
    export_items_json,
    export_items_markdown,
    export_items_xlsx,
)
from ..models import SourceConfig
from ..scanner import TaxScanner
from ..storage import Database

logger = logging.getLogger("ado_agent.web")


def get_web_resource_dirs() -> tuple[Path, Path]:
    """PyInstaller (--onefile / --onedir / .app) és normál futás erőforrás-útvonalai."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        base = Path(sys._MEIPASS) / "ado_agent" / "web"
    else:
        base = Path(__file__).resolve().parent
    return base / "templates", base / "static"


def _load_or_create_secret_key(data_dir: Path) -> str:
    env_key = os.environ.get("ADO_SECRET_KEY", "").strip()
    if env_key:
        return env_key
    key_file = data_dir / ".secret_key"
    try:
        if key_file.exists():
            stored = key_file.read_text(encoding="utf-8").strip()
            if stored:
                return stored
        generated = secrets.token_hex(32)
        data_dir.mkdir(parents=True, exist_ok=True)
        key_file.write_text(generated, encoding="utf-8")
        return generated
    except Exception:
        return secrets.token_hex(32)


class ScanCoordinator:
    """Kezeli a háttérben futó ellenőrzéseket, az állapot-lekérdezést és az ütemezést."""

    def __init__(self, config: AppConfig, db: Database) -> None:
        self.config = config
        self.db = db
        self._lock = threading.Lock()
        self.running: bool = False
        self.progress_message: str = "Készen áll"
        self.progress_done: int = 0
        self.progress_total: int = 0
        self.last_error: str = ""
        self._stop_event = threading.Event()
        self._scheduler_thread: threading.Thread | None = None

    def start_background_scan(self, source_ids: list[str] | None = None) -> bool:
        with self._lock:
            if self.running:
                return False
            self.running = True
            self.progress_message = "Ellenőrzés indítása..."
            self.progress_done = 0
            self.progress_total = len([s for s in self.config.sources if s.enabled])
            self.last_error = ""

        def _worker() -> None:
            try:
                scanner = TaxScanner(self.config, self.db)

                def on_progress(msg: str, done: int, total: int) -> None:
                    with self._lock:
                        self.progress_message = msg
                        self.progress_done = done
                        self.progress_total = total

                summary = scanner.run_scan(source_ids=source_ids, progress_cb=on_progress)
                with self._lock:
                    self.progress_message = (
                        f"Befejezve: {summary.total_matched} találat "
                        f"({summary.new_items} új, {summary.updated_items} frissült)."
                    )
                    self.progress_done = summary.total_sources
                    self.progress_total = summary.total_sources
            except Exception as exc:
                logger.exception("Hiba az ellenőrzés során")
                with self._lock:
                    self.last_error = str(exc)
                    self.progress_message = f"Hiba történt: {exc}"
            finally:
                with self._lock:
                    self.running = False

        t = threading.Thread(target=_worker, daemon=True, name="ado-agent-scan")
        t.start()
        return True

    def start_scheduler(self) -> None:
        if self._scheduler_thread is not None:
            return

        def _loop() -> None:
            last_auto_run = time.monotonic()
            while not self._stop_event.wait(timeout=15.0):
                interval_min = self.config.auto_scan_interval_minutes
                if interval_min <= 0:
                    continue
                if time.monotonic() - last_auto_run >= interval_min * 60:
                    last_auto_run = time.monotonic()
                    self.start_background_scan()

        self._scheduler_thread = threading.Thread(target=_loop, daemon=True, name="ado-agent-scheduler")
        self._scheduler_thread.start()

    def stop_scheduler(self) -> None:
        self._stop_event.set()

    def get_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.running,
                "progress_message": self.progress_message,
                "progress_done": self.progress_done,
                "progress_total": self.progress_total,
                "last_error": self.last_error,
            }


def create_app(
    config: AppConfig,
    db: Database,
    shutdown_callback: Any | None = None,
    auth_enabled: bool = False,
) -> Flask:
    templates_dir, static_dir = get_web_resource_dirs()
    app = Flask(
        __name__,
        template_folder=str(templates_dir),
        static_folder=str(static_dir),
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)
    app.config["JSON_AS_ASCII"] = False
    app.secret_key = _load_or_create_secret_key(config.data_dir)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = (
        os.environ.get("ADO_COOKIE_SECURE", "").strip().lower() in ("1", "true", "yes")
    )

    if auth_enabled:
        db.ensure_users_from_env(os.environ.get("ADO_USERS", ""))

    # Induláskor a meglévő DB elemek szinkronizálása az elmentett egyéni kulcsszavakkal / forrásnevekkel
    if config.custom_keywords:
        try:
            db.reclassify_items(
                TaxClassifier(custom_keywords=config.custom_keywords),
                source_tax_context={s.id: s.always_include_tax_context for s in config.sources},
                source_names={s.id: s.name for s in config.sources},
            )
        except Exception:
            logger.exception("Hiba a tárolt elemek induláskori újracímkézésekor")

    web_mode = auth_enabled or os.environ.get("ADO_WEB_MODE", "").strip().lower() in ("1", "true", "yes")
    coordinator = ScanCoordinator(config, db)
    app.extensions["coordinator"] = coordinator

    def get_current_user() -> dict[str, Any] | None:
        if not auth_enabled:
            return None
        uid = session.get("user_id")
        if not uid:
            return None
        return db.get_user_by_id(int(uid))

    @app.before_request
    def enforce_auth() -> Any:
        if not auth_enabled:
            return None
        path = request.path
        if (
            path == "/api/health"
            or path == "/login"
            or path == "/api/auth/login"
            or path.startswith("/static/")
        ):
            return None
        user = get_current_user()
        if user is None:
            session.pop("user_id", None)
            if path.startswith("/api/"):
                return jsonify({"error": "Bejelentkezés szükséges."}), 401
            return redirect(url_for("login_page"))
        return None

    # ---------------- Bejelentkezés ----------------

    @app.route("/login", methods=["GET", "POST"])
    def login_page() -> Any:
        if not auth_enabled:
            return redirect(url_for("index"))
        if get_current_user() is not None:
            return redirect(url_for("index"))

        error = ""
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            user = db.authenticate_user(username, password)
            if user is not None:
                session["user_id"] = user["id"]
                return redirect(url_for("index"))
            error = "Hibás felhasználónév vagy jelszó."

        return render_template(
            "login.html",
            app_name=__app_name__,
            version=__version__,
            error=error,
            has_users=len(db.list_users()) > 0,
        )

    @app.post("/api/auth/login")
    def api_login() -> tuple[Response, int]:
        if not auth_enabled:
            return jsonify({"ok": True, "auth_enabled": False}), 200
        body = request.get_json(silent=True) or {}
        user = db.authenticate_user(str(body.get("username", "")), str(body.get("password", "")))
        if user is None:
            return jsonify({"error": "Hibás felhasználónév vagy jelszó."}), 401
        session["user_id"] = user["id"]
        return jsonify({"ok": True, "user": user}), 200

    @app.post("/api/auth/logout")
    def api_logout() -> Response:
        session.clear()
        return jsonify({"ok": True})

    @app.get("/api/auth/me")
    def api_me() -> Response:
        return jsonify({"auth_enabled": auth_enabled, "user": get_current_user()})

    # ---------------- Felhasználókezelés (Admin) ----------------

    @app.get("/api/users")
    def api_list_users() -> tuple[Response, int]:
        user = get_current_user()
        if auth_enabled and (not user or not user["is_admin"]):
            return jsonify({"error": "Admin jogosultság szükséges."}), 403
        return jsonify({"users": db.list_users()}), 200

    @app.post("/api/users")
    def api_create_user() -> tuple[Response, int]:
        user = get_current_user()
        if auth_enabled and (not user or not user["is_admin"]):
            return jsonify({"error": "Admin jogosultság szükséges."}), 403
        body = request.get_json(silent=True) or {}
        try:
            created = db.create_user(
                username=str(body.get("username", "")),
                password=str(body.get("password", "")),
                display_name=str(body.get("display_name", "")),
                is_admin=bool(body.get("is_admin", False)),
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify({"ok": True, "user": created}), 201

    @app.delete("/api/users/<int:target_user_id>")
    def api_delete_user(target_user_id: int) -> tuple[Response, int]:
        user = get_current_user()
        if auth_enabled and (not user or not user["is_admin"]):
            return jsonify({"error": "Admin jogosultság szükséges."}), 403
        if user and user["id"] == target_user_id:
            return jsonify({"error": "A saját fiókodat nem törölheted."}), 400
        if not db.delete_user(target_user_id):
            return jsonify({"error": "A felhasználó nem található."}), 404
        return jsonify({"ok": True}), 200

    # ---------------- Főoldal & Állapot ----------------

    @app.get("/")
    def index() -> str:
        return render_template(
            "index.html",
            app_name=__app_name__,
            version=__version__,
            data_dir=str(config.data_dir),
            auth_enabled=auth_enabled,
            web_mode=web_mode,
            current_user=get_current_user(),
        )

    @app.get("/api/health")
    def api_health() -> Response:
        return jsonify({"status": "ok", "app": __app_name__, "version": __version__})

    @app.get("/api/state")
    def api_state() -> Response:
        user = get_current_user()
        uid = user["id"] if user else None

        jurisdiction = request.args.get("jurisdiction", "")
        category = request.args.get("category", "")
        source_id = request.args.get("source_id", "")
        search = request.args.get("search", "")
        only_new = request.args.get("only_new", "").lower() in ("1", "true", "yes")
        only_unread = request.args.get("only_unread", "").lower() in ("1", "true", "yes")
        only_read = request.args.get("only_read", "").lower() in ("1", "true", "yes")
        only_bills = request.args.get("only_bills", "").lower() in ("1", "true", "yes")
        only_bookmarked = request.args.get("only_bookmarked", "").lower() in ("1", "true", "yes")
        sort_by = request.args.get("sort_by", "relevance")

        items = db.query_items(
            jurisdiction=jurisdiction,
            category=category,
            source_id=source_id,
            search=search,
            only_new=only_new,
            only_unread=only_unread,
            only_read=only_read,
            only_bills=only_bills,
            only_bookmarked=only_bookmarked,
            sort_by=sort_by,
            user_id=uid,
        )

        serialized_items = []
        for it in items:
            d = it.to_dict()
            for c in d["comments"]:
                c["can_delete"] = (
                    (not auth_enabled)
                    or (user is not None and (user["is_admin"] or c["user_id"] == user["id"]))
                )
            serialized_items.append(d)

        return jsonify(
            {
                "app": {
                    "name": __app_name__,
                    "version": __version__,
                    "data_dir": str(config.data_dir),
                    "web_mode": web_mode,
                },
                "auth": {"enabled": auth_enabled, "user": user},
                "scan_status": coordinator.get_status(),
                "latest_run": db.get_latest_scan_run(),
                "stats": db.get_stats(user_id=uid),
                "categories": get_category_catalog(),
                "sources": [s.to_dict() for s in config.sources],
                "custom_keywords": config.custom_keywords,
                "auto_scan_interval_minutes": config.auto_scan_interval_minutes,
                "items": serialized_items,
            }
        )

    @app.get("/api/scan/status")
    def api_scan_status() -> Response:
        return jsonify(
            {
                "scan_status": coordinator.get_status(),
                "latest_run": db.get_latest_scan_run(),
            }
        )

    @app.post("/api/scan")
    def api_scan_start() -> tuple[Response, int]:
        body = request.get_json(silent=True) or {}
        source_ids = body.get("source_ids")
        if body.get("sync"):
            scanner = TaxScanner(config, db)
            summary = scanner.run_scan(source_ids=source_ids)
            return jsonify({"started": True, "completed": True, "summary": summary.to_dict()}), 200

        started = coordinator.start_background_scan(source_ids=source_ids)
        if not started:
            return jsonify({"started": False, "message": "Már fut egy ellenőrzés."}), 409
        return jsonify({"started": True, "scan_status": coordinator.get_status()}), 202

    # ---------------- Felhasználónkénti állapotok & Megjegyzések ----------------

    @app.post("/api/items/<item_key>/flags")
    def api_item_flags(item_key: str) -> tuple[Response, int]:
        user = get_current_user()
        uid = user["id"] if user else None
        body = request.get_json(silent=True) or {}
        ok = db.update_item_flags(
            item_key=item_key,
            is_read=body.get("is_read") if "is_read" in body else None,
            is_bookmarked=body.get("is_bookmarked") if "is_bookmarked" in body else None,
            notes=body.get("notes") if "notes" in body else None,
            user_id=uid,
        )
        if not ok:
            return jsonify({"error": "A megadott elem nem található."}), 404
        return jsonify({"ok": True}), 200

    @app.post("/api/items/mark-all-read")
    def api_mark_all_read() -> Response:
        user = get_current_user()
        uid = user["id"] if user else None
        updated = db.mark_all_read(user_id=uid)
        return jsonify({"ok": True, "updated": updated})

    @app.post("/api/items/<item_key>/comments")
    def api_add_comment(item_key: str) -> tuple[Response, int]:
        user = get_current_user()
        body = request.get_json(silent=True) or {}
        text = str(body.get("body", "")).strip()
        author = (
            (user["display_name"] or user["username"])
            if user
            else str(body.get("author_name", "Helyi felhasználó")).strip() or "Helyi felhasználó"
        )
        try:
            comment = db.add_comment(
                item_key=item_key,
                body=text,
                user_id=user["id"] if user else None,
                author_name=author,
            )
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
        if comment is None:
            return jsonify({"error": "A megadott elem nem található."}), 404
        comment["can_delete"] = True
        return jsonify({"ok": True, "comment": comment}), 201

    @app.delete("/api/comments/<int:comment_id>")
    def api_delete_comment(comment_id: int) -> tuple[Response, int]:
        user = get_current_user()
        try:
            deleted = db.delete_comment(
                comment_id=comment_id,
                requester_user_id=user["id"] if user else None,
                is_admin=bool(user["is_admin"]) if user else True,
            )
        except PermissionError as exc:
            return jsonify({"error": str(exc)}), 403
        if not deleted:
            return jsonify({"error": "A megjegyzés nem található."}), 404
        return jsonify({"ok": True}), 200

    # ---------------- Források, Beállítások, Export ----------------

    @app.get("/api/sources")
    def api_get_sources() -> Response:
        return jsonify({"sources": [s.to_dict() for s in config.sources]})

    @app.post("/api/sources")
    def api_add_source() -> tuple[Response, int]:
        body = request.get_json(silent=True) or {}
        name = normalize_whitespace(str(body.get("name", "")))
        url = str(body.get("url", "")).strip()
        if not name or not url.startswith(("http://", "https://")):
            return jsonify({"error": "Érvényes név és http(s):// URL megadása kötelező."}), 400

        slug = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_") or "custom"
        existing_ids = {s.id for s in config.sources}
        src_id = f"custom_{slug}"
        idx = 2
        while src_id in existing_ids:
            src_id = f"custom_{slug}_{idx}"
            idx += 1

        raw_adapter = str(body.get("adapter", "web")).lower()
        src = SourceConfig(
            id=src_id,
            name=name,
            adapter=raw_adapter if raw_adapter in ("rss", "web") else "web",
            url=url,
            jurisdiction="EU" if str(body.get("jurisdiction", "HU")).upper() == "EU" else "HU",
            description=normalize_whitespace(str(body.get("description", "Egyéni felhasználói forrás"))),
            badge_color="#7c3aed",
            enabled=True,
            is_builtin=False,
        )
        config.sources.append(src)
        config.save()
        return jsonify({"ok": True, "source": src.to_dict()}), 201

    @app.patch("/api/sources/<source_id>")
    def api_patch_source(source_id: str) -> tuple[Response, int]:
        body = request.get_json(silent=True) or {}
        for src in config.sources:
            if src.id == source_id:
                if "enabled" in body:
                    src.enabled = bool(body["enabled"])
                if "name" in body and normalize_whitespace(str(body["name"])):
                    src.name = normalize_whitespace(str(body["name"]))
                if "url" in body and str(body["url"]).strip().startswith(("http://", "https://")):
                    src.url = str(body["url"]).strip()
                config.save()
                return jsonify({"ok": True, "source": src.to_dict()}), 200
        return jsonify({"error": "Ismeretlen forrás."}), 404

    @app.delete("/api/sources/<source_id>")
    def api_delete_source(source_id: str) -> tuple[Response, int]:
        for idx, src in enumerate(config.sources):
            if src.id == source_id:
                if src.is_builtin:
                    return jsonify({"error": "Beépített forrás nem törölhető, csak kikapcsolható."}), 400
                config.sources.pop(idx)
                config.save()
                return jsonify({"ok": True}), 200
        return jsonify({"error": "Ismeretlen forrás."}), 404

    @app.put("/api/settings")
    def api_update_settings() -> Response:
        body = request.get_json(silent=True) or {}
        if "custom_keywords" in body and isinstance(body["custom_keywords"], list):
            seen: set[str] = set()
            cleaned: list[str] = []
            for kw in body["custom_keywords"]:
                k = normalize_whitespace(str(kw))
                if k and k.lower() not in seen:
                    seen.add(k.lower())
                    cleaned.append(k)
            config.custom_keywords = cleaned
        if "auto_scan_interval_minutes" in body:
            try:
                config.auto_scan_interval_minutes = max(0, int(body["auto_scan_interval_minutes"]))
            except (TypeError, ValueError):
                pass
        config.save()

        reclassified = db.reclassify_items(
            TaxClassifier(custom_keywords=config.custom_keywords),
            source_tax_context={s.id: s.always_include_tax_context for s in config.sources},
            source_names={s.id: s.name for s in config.sources},
        )

        scan_started = False
        if bool(body.get("rescan", False)):
            scan_started = coordinator.start_background_scan()

        return jsonify(
            {
                "ok": True,
                "custom_keywords": config.custom_keywords,
                "auto_scan_interval_minutes": config.auto_scan_interval_minutes,
                "reclassified": reclassified,
                "scan_started": scan_started,
            }
        )

    @app.get("/api/export/<fmt>")
    def api_export(fmt: str) -> Response:
        user = get_current_user()
        uid = user["id"] if user else None

        items = db.query_items(
            jurisdiction=request.args.get("jurisdiction", ""),
            category=request.args.get("category", ""),
            source_id=request.args.get("source_id", ""),
            search=request.args.get("search", ""),
            only_new=request.args.get("only_new", "").lower() in ("1", "true", "yes"),
            only_unread=request.args.get("only_unread", "").lower() in ("1", "true", "yes"),
            only_read=request.args.get("only_read", "").lower() in ("1", "true", "yes"),
            only_bills=request.args.get("only_bills", "").lower() in ("1", "true", "yes"),
            only_bookmarked=request.args.get("only_bookmarked", "").lower() in ("1", "true", "yes"),
            user_id=uid,
        )
        fmt_low = fmt.lower()
        if fmt_low == "xlsx":
            data = export_items_xlsx(items, latest_run=db.get_latest_scan_run())
            mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            filename = "ado-agent-jelentes.xlsx"
        elif fmt_low == "csv":
            data = export_items_csv(items)
            mime = "text/csv; charset=utf-8"
            filename = "ado-agent-jelentes.csv"
        elif fmt_low == "html":
            data = export_items_html(items)
            mime = "text/html; charset=utf-8"
            filename = "ado-agent-jelentes.html"
        elif fmt_low == "md":
            data = export_items_markdown(items)
            mime = "text/markdown; charset=utf-8"
            filename = "ado-agent-jelentes.md"
        elif fmt_low == "json":
            data = export_items_json(items)
            mime = "application/json; charset=utf-8"
            filename = "ado-agent-jelentes.json"
        else:
            return jsonify({"error": "Nem támogatott formátum"}), 400

        return Response(
            data,
            mimetype=mime,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/api/shutdown")
    def api_shutdown() -> tuple[Response, int]:
        if web_mode:
            return jsonify({"error": "Webes szerver módban a leállítás le van tiltva."}), 403
        coordinator.stop_scheduler()
        if shutdown_callback is not None:
            threading.Timer(0.25, shutdown_callback).start()
        return jsonify({"ok": True, "message": "ADÓ Agent leáll..."}), 200

    return app


def find_free_port(host: str, preferred_port: int) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex((host if host != "0.0.0.0" else "127.0.0.1", preferred_port)) != 0:
            return preferred_port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, 0))
        return int(s.getsockname()[1])


def run_web_server(
    config: AppConfig,
    db: Database,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    scan_on_start: bool = False,
    auth_enabled: bool = False,
) -> None:
    chosen_port = port if host == "0.0.0.0" else find_free_port(host, port)
    server_holder: dict[str, Any] = {}

    def stop_server() -> None:
        srv = server_holder.get("server")
        if srv is not None:
            try:
                srv.close()
            except Exception:
                pass
        os._exit(0)

    app = create_app(
        config,
        db,
        shutdown_callback=None if auth_enabled else stop_server,
        auth_enabled=auth_enabled,
    )
    coordinator: ScanCoordinator = app.extensions["coordinator"]
    coordinator.start_scheduler()

    if scan_on_start:
        coordinator.start_background_scan()

    srv = create_server(app, host=host, port=chosen_port, threads=8)
    server_holder["server"] = srv

    display_host = "127.0.0.1" if host == "0.0.0.0" else host
    url = f"http://{display_host}:{chosen_port}"
    try:
        log_file = config.data_dir / "ado-agent.log"
        handlers: list[logging.Handler] = [logging.FileHandler(str(log_file), encoding="utf-8")]
        if host == "0.0.0.0":
            handlers.append(logging.StreamHandler(sys.stdout))
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=handlers,
        )
    except Exception:
        pass

    if sys.stdout is not None:
        print(f"\n  ADÓ Agent v{__version__} elindult! (Auth: {'BE' if auth_enabled else 'KI'})")
        print(f"  Felület:      {url}")
        print(f"  Adatkönyvtár: {config.data_dir}\n", flush=True)

    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()

    try:
        srv.run()
    except KeyboardInterrupt:
        print("\nADÓ Agent leállítva.", flush=True)
    finally:
        coordinator.stop_scheduler()
        try:
            srv.close()
        except Exception:
            pass
