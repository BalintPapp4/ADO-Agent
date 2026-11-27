"""Alkalmazás-konfiguráció, adatkönyvtárak és alapértelmezett források kezelése."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import SourceConfig


def get_default_data_dir() -> Path:
    """Platformfüggetlen tartós adatkönyvtár (Windows/macOS/Linux, PyInstaller kompatibilis)."""
    override = os.environ.get("ADO_AGENT_HOME", "").strip()
    if override:
        return Path(override).expanduser().resolve()

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "ADO-Agent"
        return Path.home() / "AppData" / "Local" / "ADO-Agent"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "ADO-Agent"
    xdg = os.environ.get("XDG_DATA_HOME")
    if xdg:
        return Path(xdg) / "ado-agent"
    return Path.home() / ".local" / "share" / "ado-agent"


def get_default_sources() -> list[SourceConfig]:
    """Alapértelmezett magyar és EU-s adózási jogforrások."""
    return [
        SourceConfig(
            id="parlament_hu",
            name="Országgyűlés (parlament.hu)",
            adapter="parlament",
            url="https://www.parlament.hu/iromanyok-lekerdezese",
            extra_urls=[
                "https://www.parlament.hu/",
                "https://www.parlament.hu/web/guest/iromanyok-lekerdezese",
                "https://www.parlament.hu/web/guest/orszaggyulesi-iromanyok",
                "https://www.parlament.hu/web/guest/hirek",
            ],
            jurisdiction="HU",
            description="Benyújtott magyar törvényjavaslatok (T/ irományok), bizottsági módosítók és parlamenti hírek.",
            badge_color="#991b1b",
            enabled=True,
            is_builtin=True,
        ),
        SourceConfig(
            id="kormany_hu",
            name="Kormány.hu (Társadalmi egyeztetés & Minisztériumok)",
            adapter="kormany",
            url="https://kormany.hu/dokumentumtar",
            extra_urls=[
                "https://kormany.hu/hirek",
                "https://kormany.hu/nemzetgazdasagi-miniszterium",
                "https://kormany.hu/penzugyminiszterium",
            ],
            jurisdiction="HU",
            description="Társadalmi egyeztetésre bocsátott adótörvény-tervezetek, rendelettervezetek és kormányzati dokumentumok.",
            badge_color="#1d4ed8",
            enabled=True,
            is_builtin=True,
        ),
        SourceConfig(
            id="net_jogtar_hu",
            name="Netjogtár (net.jogtar.hu)",
            adapter="netjogtar",
            url="https://net.jogtar.hu/jogszabalyvaltozasok",
            extra_urls=[
                "https://net.jogtar.hu/friss-jogszabalyok",
                "https://net.jogtar.hu/",
                "https://net.jogtar.hu/jogszabaly?docid=a0700127.tv",
                "https://net.jogtar.hu/jogszabaly?docid=99500117.tv",
                "https://net.jogtar.hu/jogszabaly?docid=a0800067.tv",
                "https://net.jogtar.hu/jogszabaly?docid=99600081.tv",
                "https://net.jogtar.hu/jogszabaly?docid=a1700150.tv",
                "https://net.jogtar.hu/jogszabaly?docid=a2200197.kor",
                "https://net.jogtar.hu/jogszabaly?docid=99100082.tv",
                "https://net.jogtar.hu/jogszabaly?docid=99000100.tv",
                "https://net.jogtar.hu/jogszabaly?docid=99000093.tv",
                "https://net.jogtar.hu/jogszabaly?docid=a1700151.tv",
                "https://net.jogtar.hu/jogszabaly?docid=a1700153.tv",
                "https://net.jogtar.hu/jogszabaly?docid=99400053.tv",
                "https://net.jogtar.hu/jogszabaly?docid=a1800052.tv",
                "https://net.jogtar.hu/jogszabaly?docid=a1900122.tv",
                "https://net.jogtar.hu/jogszabaly?docid=a1200147.tv",
                "https://net.jogtar.hu/jogszabaly?docid=a1600068.tv",
                "https://net.jogtar.hu/jogszabaly?docid=a0000100.tv",
            ],
            jurisdiction="HU",
            description="Wolters Kluwer Netjogtár — friss jogszabályváltozások és a főbb adótörvények (Áfa, SZJA, Robin Hood, TAO, Art., Gjt., Htv., Vht.) követése.",
            badge_color="#0f766e",
            enabled=True,
            is_builtin=True,
        ),
        SourceConfig(
            id="njt_hu",
            name="Nemzeti Jogszabálytár (njt.jog.gov.hu)",
            adapter="njt",
            url="https://njt.jog.gov.hu/",
            extra_urls=[
                "https://njt.jog.gov.hu/jogszabaly/2007-127-00-00",
                "https://njt.jog.gov.hu/jogszabaly/1995-117-00-00",
                "https://njt.jog.gov.hu/jogszabaly/2008-67-00-00",
                "https://njt.jog.gov.hu/jogszabaly/1996-81-00-00",
                "https://njt.jog.gov.hu/jogszabaly/2017-150-00-00",
                "https://njt.jog.gov.hu/jogszabaly/2022-197-20-22",
                "https://njt.jog.gov.hu/jogszabaly/1991-82-00-00",
                "https://njt.jog.gov.hu/jogszabaly/1990-100-00-00",
                "https://njt.jog.gov.hu/jogszabaly/1990-93-00-00",
                "https://njt.jog.gov.hu/jogszabaly/2017-151-00-00",
                "https://njt.jog.gov.hu/jogszabaly/2017-153-00-00",
                "https://njt.jog.gov.hu/jogszabaly/1994-53-00-00",
                "https://njt.jog.gov.hu/jogszabaly/2018-52-00-00",
                "https://njt.jog.gov.hu/jogszabaly/2019-122-00-00",
                "https://njt.jog.gov.hu/jogszabaly/2012-147-00-00",
                "https://njt.jog.gov.hu/jogszabaly/2016-68-00-00",
                "https://njt.jog.gov.hu/jogszabaly/2000-100-00-00",
                "https://njt.hu/",
            ],
            jurisdiction="HU",
            description="A hivatalos Nemzeti Jogszabálytár (njt.jog.gov.hu) — adótörvények (Áfa, Szja, Tao, Art., Gjt., Htv., Vht., stb.) és hatályos szövegek.",
            badge_color="#15803d",
            enabled=True,
            is_builtin=True,
        ),
        SourceConfig(
            id="nav_gov_hu",
            name="NAV (nav.gov.hu)",
            adapter="nav",
            url="https://nav.gov.hu/ado",
            extra_urls=[
                "https://nav.gov.hu/hirek",
                "https://nav.gov.hu/ugyfeliranytu/jogszabalyok",
                "https://nav.gov.hu/rss",
            ],
            jurisdiction="HU",
            description="Nemzeti Adó- és Vámhivatal — hivatalos tájékoztatók, ÁFA/SZJA/különadó változások és közlemények.",
            badge_color="#16a34a",
            enabled=True,
            is_builtin=True,
            always_include_tax_context=True,
        ),
        SourceConfig(
            id="magyar_kozlony",
            name="Magyar Közlöny (magyarkozlony.hu)",
            adapter="magyarkozlony",
            url="https://magyarkozlony.hu/",
            extra_urls=[
                "https://www.magyarkozlony.hu/",
                "https://magyarkozlony.hu/hivatalos-lapok",
            ],
            jurisdiction="HU",
            description="Hivatalos Magyar Közlöny kiadások és a frissen kihirdetett törvények/rendeletek.",
            badge_color="#166534",
            enabled=True,
            is_builtin=True,
        ),
        SourceConfig(
            id="eur_lex_eu",
            name="EUR-Lex (eur-lex.europa.eu)",
            adapter="eurlex",
            url="https://eur-lex.europa.eu/search.html?scope=EURLEX&lang=hu&type=quick&text=ad%C3%B3",
            extra_urls=[
                "https://eur-lex.europa.eu/search.html?scope=EURLEX&lang=hu&type=quick&text=%C3%A1fa",
                "https://eur-lex.europa.eu/search.html?scope=EURLEX&lang=en&type=quick&text=taxation+proposal+directive",
                "https://eur-lex.europa.eu/EN/display-feed.rss?rssId=161",
                "https://taxation-customs.ec.europa.eu/news_en",
                "https://www.europarl.europa.eu/rss/doc/top-stories/hu.xml",
            ],
            jurisdiction="EU",
            description="Európai Uniós törvényjavaslatok (COM), irányelvek (ÁFA/ViDA, DAC, globális minimumadó, energiaadó) és EP/Bizottság hírek.",
            badge_color="#0369a1",
            enabled=True,
            is_builtin=True,
        ),
        SourceConfig(
            id="adozona_hu",
            name="Adózóna (adozona.hu)",
            adapter="adozona",
            url="https://adozona.hu/",
            extra_urls=[
                "https://adozona.hu/rss",
                "https://adozona.hu/rss.xml",
                "https://adozona.hu/feed",
            ],
            jurisdiction="HU",
            description="Szakmai adózási hírek és jogszabály-értelmezések (Cloudflare 403 esetén automatikus Google News RSS tükörrel).",
            badge_color="#6d28d9",
            enabled=False,
            is_builtin=True,
        ),
        SourceConfig(
            id="ado_hu",
            name="Adó Online (ado.hu)",
            adapter="web",
            url="https://ado.hu/feed/",
            extra_urls=["https://ado.hu/"],
            jurisdiction="HU",
            description="Adózási szakportál friss cikkei és törvényváltozási összefoglalói.",
            badge_color="#7c3aed",
            enabled=False,
            is_builtin=True,
        ),
    ]


@dataclass
class AppConfig:
    data_dir: Path
    sources: list[SourceConfig] = field(default_factory=get_default_sources)
    custom_keywords: list[str] = field(default_factory=list)
    request_timeout_sec: int = 20
    max_workers: int = 5
    auto_scan_interval_minutes: int = 0  # 0 = kikapcsolva
    verify_ssl: bool = True

    @property
    def config_path(self) -> Path:
        return self.data_dir / "config.json"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "ado_agent.db"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.exports_dir.mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": [s.to_dict() for s in self.sources],
            "custom_keywords": self.custom_keywords,
            "request_timeout_sec": self.request_timeout_sec,
            "max_workers": self.max_workers,
            "auto_scan_interval_minutes": self.auto_scan_interval_minutes,
            "verify_ssl": self.verify_ssl,
        }

    def save(self) -> None:
        self.ensure_dirs()
        self.config_path.write_text(
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, data_dir: Path | None = None) -> "AppConfig":
        target_dir = (data_dir or get_default_data_dir()).expanduser().resolve()
        cfg = cls(data_dir=target_dir)
        cfg.ensure_dirs()

        if cfg.config_path.exists():
            try:
                raw = json.loads(cfg.config_path.read_text(encoding="utf-8"))
                loaded_sources = [SourceConfig.from_dict(s) for s in raw.get("sources", [])]
                # Összefésülés: új beépített források hozzáadása és elavult URL-ek/nevek migrációja
                defaults_by_id = {s.id: s for s in get_default_sources()}
                by_id = {s.id: s for s in loaded_sources}
                migrated = False

                for existing in loaded_sources:
                    default_src = defaults_by_id.get(existing.id)
                    if default_src is None or not existing.is_builtin:
                        continue
                    if existing.name != default_src.name or existing.description != default_src.description:
                        existing.name = default_src.name
                        existing.description = default_src.description
                        migrated = True
                    if existing.adapter != default_src.adapter:
                        existing.adapter = default_src.adapter
                        migrated = True
                    # Elavult beépített elsődleges URL-ek frissítése (felhasználói kapcsolók és egyéni források megőrzésével)
                    if existing.id == "njt_hu" and "njt.hu" in existing.url and "njt.jog.gov.hu" not in existing.url:
                        existing.url = default_src.url
                        existing.extra_urls = list(default_src.extra_urls)
                        migrated = True
                    elif existing.id == "adozona_hu" and existing.url.rstrip("/").endswith("/rss"):
                        existing.url = default_src.url
                        existing.extra_urls = list(default_src.extra_urls)
                        migrated = True
                    elif existing.id == "parlament_hu" and (
                        "://parlament.hu" in existing.url
                        or existing.url.rstrip("/") == "https://www.parlament.hu/iromanyok"
                    ):
                        existing.url = default_src.url
                        existing.extra_urls = list(default_src.extra_urls)
                        migrated = True
                    elif existing.id == "magyar_kozlony" and "://magyarkozlony.hu" in existing.url:
                        existing.url = default_src.url
                        existing.extra_urls = list(default_src.extra_urls)
                        migrated = True
                    else:
                        for extra in default_src.extra_urls:
                            if extra != existing.url and extra not in existing.extra_urls:
                                existing.extra_urls.append(extra)
                                migrated = True

                for default_src in get_default_sources():
                    if default_src.id not in by_id:
                        loaded_sources.append(default_src)
                        migrated = True

                if loaded_sources:
                    cfg.sources = loaded_sources
                cfg.custom_keywords = [
                    str(k).strip() for k in raw.get("custom_keywords", []) if str(k).strip()
                ]
                cfg.request_timeout_sec = int(raw.get("request_timeout_sec", 20))
                cfg.max_workers = int(raw.get("max_workers", 5))
                cfg.auto_scan_interval_minutes = int(raw.get("auto_scan_interval_minutes", 0))
                cfg.verify_ssl = bool(raw.get("verify_ssl", True))
                if migrated:
                    cfg.save()
            except Exception:
                # Sérült config esetén biztonságos visszaállás alapértelmezettre
                cfg.save()
        else:
            cfg.save()
        return cfg
