"""Forrásadapterek alapértelmezett ősosztálya és generikus web/RSS adapter."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..classifier import normalize_whitespace
from ..fetcher import (
    FetchResult,
    HttpFetcher,
    extract_html_candidates,
    extract_json_candidates,
    extract_next_data_candidates,
    is_feed_response,
    is_spa_empty_shell,
    parse_feed_candidates,
)
from ..models import RawCandidate, SourceConfig


@dataclass
class AdapterOutput:
    candidates: list[RawCandidate] = field(default_factory=list)
    checked_urls: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ok_requests: int = 0


class BaseSourceAdapter:
    """Minden forrásadapter közös alapja."""

    def __init__(self, source: SourceConfig, fetcher: HttpFetcher) -> None:
        self.source = source
        self.fetcher = fetcher

    def target_urls(self) -> list[str]:
        urls = [self.source.url] + list(self.source.extra_urls or [])
        seen: set[str] = set()
        unique: list[str] = []
        for u in urls:
            u_clean = u.strip()
            if u_clean and u_clean not in seen:
                seen.add(u_clean)
                unique.append(u_clean)
        return unique

    def collect(self) -> AdapterOutput:
        out = AdapterOutput()
        seen_candidates: set[tuple[str, str]] = set()

        for url in self.target_urls():
            out.checked_urls.append(url)
            res = self.fetcher.fetch(url)
            if not res.ok:
                out.errors.append(f"{url}: {res.error}")
                continue
            out.ok_requests += 1
            extracted = self.parse_response(res, out)
            for cand in extracted:
                key = (cand.url.lower(), normalize_whitespace(cand.title).lower())
                if key not in seen_candidates:
                    seen_candidates.add(key)
                    out.candidates.append(cand)
        return out

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        return parse_generic_response(res, out)


def parse_generic_response(res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
    """Általános válaszfeldolgozó: RSS/Atom -> JSON -> Next.js -> HTML."""
    ct = res.content_type.lower()
    if is_feed_response(res.text, ct):
        return parse_feed_candidates(res.text, res.final_url)

    stripped = res.text.lstrip()
    if "application/json" in ct or stripped.startswith(("{", "[")):
        cands = extract_json_candidates(res.text, res.final_url)
        if cands:
            return cands

    if is_spa_empty_shell(res.text):
        out.warnings.append(
            f"{res.final_url}: Kliensoldali JavaScript-alkalmazás (SPA) üres váza érkezett; "
            "a közvetlen API- vagy törvényszintű végpontok adatai látszanak."
        )

    cands = extract_next_data_candidates(res.text, res.final_url)
    html_cands = extract_html_candidates(res.text, res.final_url)
    return cands + html_cands


class GenericWebAdapter(BaseSourceAdapter):
    """Egyéni weboldalak és RSS/Atom hírfolyamok gyűjtője."""

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        cands = parse_generic_response(res, out)
        if cands:
            return cands
        # Ha egy egyoldalas cikket vagy jogszabályt adott meg a felhasználó (nincs lista),
        # vegyük fel magát az oldalt a <h1> vagy <title> alapján!
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(res.text, "lxml")
        h1 = soup.find("h1")
        title_tag = soup.find("title")
        title = normalize_whitespace(
            (h1.get_text(" ", strip=True) if h1 else "")
            or (title_tag.get_text(" ", strip=True) if title_tag else "")
        )
        for tag_name in ("script", "style", "noscript", "svg", "nav", "header", "footer"):
            for tag in list(soup.find_all(tag_name)):
                if tag.parent is not None:
                    tag.decompose()
        if len(title) >= 8:
            body = normalize_whitespace(soup.get_text(" ", strip=True))
            return [
                RawCandidate(
                    title=title[:280],
                    url=res.final_url,
                    summary=body[:700],
                )
            ]
        return []
