"""Adatmodellek az ADÓ Agent alkalmazáshoz."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CategoryMatch:
    """Egy felismert adózási kategória és a hozzá tartozó találatok."""

    category_id: str
    category_name: str
    score: int
    matched_keywords: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "category_name": self.category_name,
            "score": self.score,
            "matched_keywords": self.matched_keywords,
        }


@dataclass
class LegislativeItem:
    """Egy begyűjtött jogszabályi / törvényjavaslati vagy adózási elem."""

    item_key: str
    title: str
    url: str
    source_id: str
    source_name: str
    jurisdiction: str  # "HU" | "EU"
    summary: str = ""
    published_at: str = ""
    document_ref: str = ""  # pl. "T/12345" vagy "COM(2025) 123"
    status_label: str = ""  # pl. "Törvényjavaslat", "Társadalmi egyeztetés", "Kihirdetve"
    relevance_score: int = 0
    is_bill: bool = False
    categories: list[str] = field(default_factory=list)
    category_names: list[str] = field(default_factory=list)
    matched_keywords: list[str] = field(default_factory=list)
    content_hash: str = ""
    first_seen_at: str = ""
    last_seen_at: str = ""
    is_new: bool = False
    is_updated: bool = False
    is_read: bool = False
    is_bookmarked: bool = False
    notes: str = ""
    raw_metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_key": self.item_key,
            "title": self.title,
            "url": self.url,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "jurisdiction": self.jurisdiction,
            "summary": self.summary,
            "published_at": self.published_at,
            "document_ref": self.document_ref,
            "status_label": self.status_label,
            "relevance_score": self.relevance_score,
            "is_bill": self.is_bill,
            "categories": self.categories,
            "category_names": self.category_names,
            "matched_keywords": self.matched_keywords,
            "content_hash": self.content_hash,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "is_new": self.is_new,
            "is_updated": self.is_updated,
            "is_read": self.is_read,
            "is_bookmarked": self.is_bookmarked,
            "notes": self.notes,
            "raw_metadata": self.raw_metadata,
        }


@dataclass
class SourceConfig:
    """Egy figyelt jogszabály- vagy hírforrás konfigurációja."""

    id: str
    name: str
    adapter: str  # parlament | kormany | netjogtar | njt | nav | magyarkozlony | eurlex | rss | web
    url: str
    jurisdiction: str = "HU"  # "HU" | "EU"
    description: str = ""
    badge_color: str = "#1f6feb"
    enabled: bool = True
    is_builtin: bool = True
    extra_urls: list[str] = field(default_factory=list)
    always_include_tax_context: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "adapter": self.adapter,
            "url": self.url,
            "jurisdiction": self.jurisdiction,
            "description": self.description,
            "badge_color": self.badge_color,
            "enabled": self.enabled,
            "is_builtin": self.is_builtin,
            "extra_urls": self.extra_urls,
            "always_include_tax_context": self.always_include_tax_context,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SourceConfig":
        return cls(
            id=str(data["id"]),
            name=str(data["name"]),
            adapter=str(data.get("adapter", "web")),
            url=str(data["url"]),
            jurisdiction=str(data.get("jurisdiction", "HU")),
            description=str(data.get("description", "")),
            badge_color=str(data.get("badge_color", "#1f6feb")),
            enabled=bool(data.get("enabled", True)),
            is_builtin=bool(data.get("is_builtin", False)),
            extra_urls=list(data.get("extra_urls", [])),
            always_include_tax_context=bool(data.get("always_include_tax_context", False)),
        )


@dataclass
class RawCandidate:
    """Egy forrásadapter által kinyert nyers dokumentumjelölt osztályozás előtt."""

    title: str
    url: str
    summary: str = ""
    published_at: str = ""
    document_ref: str = ""
    status_label: str = ""
    raw_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SourceScanResult:
    """Egyetlen forrás ellenőrzésének eredménye."""

    source_id: str
    source_name: str
    jurisdiction: str
    status: str  # "ok" | "warning" | "error" | "skipped"
    fetched_candidates: int = 0
    matched_items: int = 0
    new_items: int = 0
    updated_items: int = 0
    duration_ms: int = 0
    message: str = ""
    checked_urls: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_name": self.source_name,
            "jurisdiction": self.jurisdiction,
            "status": self.status,
            "fetched_candidates": self.fetched_candidates,
            "matched_items": self.matched_items,
            "new_items": self.new_items,
            "updated_items": self.updated_items,
            "duration_ms": self.duration_ms,
            "message": self.message,
            "checked_urls": self.checked_urls,
        }


@dataclass
class ScanSummary:
    """Teljes ellenőrzési futás összefoglalója."""

    run_id: int
    started_at: str
    finished_at: str
    status: str
    total_sources: int
    succeeded_sources: int
    warning_sources: int
    failed_sources: int
    total_matched: int
    new_items: int
    updated_items: int
    source_results: list[SourceScanResult] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "status": self.status,
            "total_sources": self.total_sources,
            "succeeded_sources": self.succeeded_sources,
            "warning_sources": self.warning_sources,
            "failed_sources": self.failed_sources,
            "total_matched": self.total_matched,
            "new_items": self.new_items,
            "updated_items": self.updated_items,
            "source_results": [r.to_dict() for r in self.source_results],
        }
