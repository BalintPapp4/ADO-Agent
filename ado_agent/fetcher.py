"""Hálózati lekérdező és HTML/RSS/JSON/Next.js tartalomkinyerő segédréteg."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse

import feedparser
import httpx
from bs4 import BeautifulSoup

from .classifier import normalize_whitespace
from .models import RawCandidate

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36 ADO-Agent/1.0"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,application/json;q=0.8,*/*;q=0.7",
    "Accept-Language": "hu-HU,hu;q=0.9,en-US;q=0.8,en;q=0.7",
}

NOISE_TITLES = {
    "adatvédelem",
    "adatvédelmi tájékoztató",
    "impresszum",
    "kapcsolat",
    "cookie",
    "sütik",
    "belépés",
    "bejelentkezés",
    "regisztráció",
    "főoldal",
    "kezdőlap",
    "tovább",
    "részletek",
    "összes",
    "keresés",
    "ugrás a tartalomra",
    "nyomtatás",
    "megosztás",
    "skip to content",
    "privacy policy",
    "terms of use",
    "contact",
    "home",
    "login",
}

DATE_RE = re.compile(
    r"\b(\d{4}[.\-/]\s*\d{1,2}[.\-/]\s*\d{1,2}\.?|\d{1,2}\.\s*(?:január|február|március|április|május|június|július|augusztus|szeptember|október|november|december)\s*\d{4}?)\b",
    re.IGNORECASE,
)


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content_type: str
    text: str
    ok: bool
    error: str = ""


class HttpFetcher:
    """Robusztus HTTP kliens újrapróbálkozással és magyar kódolás-felismeréssel."""

    def __init__(
        self,
        timeout_sec: int = 20,
        verify_ssl: bool = True,
        client: httpx.Client | None = None,
    ) -> None:
        self.timeout_sec = timeout_sec
        self.verify_ssl = verify_ssl
        self._external_client = client

    def _build_client(self) -> httpx.Client:
        return httpx.Client(
            headers=DEFAULT_HEADERS,
            timeout=httpx.Timeout(self.timeout_sec),
            follow_redirects=True,
            verify=self.verify_ssl,
        )

    def fetch(self, url: str, retries: int = 2) -> FetchResult:
        last_err = ""
        for attempt in range(retries + 1):
            try:
                if self._external_client is not None:
                    resp = self._external_client.get(url, headers=DEFAULT_HEADERS, follow_redirects=True)
                else:
                    with self._build_client() as client:
                        resp = client.get(url)

                ct = (resp.headers.get("content-type") or "").lower()
                text = decode_response_text(resp.content, ct, resp.encoding)
                ok = 200 <= resp.status_code < 400
                err = "" if ok else f"HTTP {resp.status_code}"
                return FetchResult(
                    url=url,
                    final_url=str(resp.url),
                    status_code=resp.status_code,
                    content_type=ct,
                    text=text,
                    ok=ok,
                    error=err,
                )
            except Exception as exc:
                last_err = str(exc)
                if attempt < retries:
                    time.sleep(0.4 * (attempt + 1))

        return FetchResult(
            url=url,
            final_url=url,
            status_code=0,
            content_type="",
            text="",
            ok=False,
            error=last_err or "Ismeretlen hálózati hiba",
        )


def decode_response_text(raw: bytes, content_type: str, declared_encoding: str | None) -> str:
    if not raw:
        return ""
    if declared_encoding:
        try:
            return raw.decode(declared_encoding, errors="replace")
        except LookupError:
            pass
    for enc in ("utf-8", "iso-8859-2", "windows-1250", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def is_feed_response(text: str, content_type: str = "") -> bool:
    ct = (content_type or "").lower()
    if any(t in ct for t in ("rss", "atom", "xml")) and "<html" not in text[:500].lower():
        return True
    head = text.lstrip()[:400].lower()
    return head.startswith("<?xml") and ("<rss" in head or "<feed" in head or "<rdf:rdf" in head)


def is_spa_empty_shell(html: str) -> bool:
    if not html:
        return False
    soup = BeautifulSoup(html, "lxml")
    body = soup.body
    visible_text = normalize_whitespace(body.get_text(" ", strip=True) if body else "")
    has_spa_root = bool(
        soup.find("app-root")
        or soup.find(id="app")
        or soup.find(id="root")
    )
    return has_spa_root and len(visible_text) < 120


def parse_feed_candidates(xml_text: str, base_url: str) -> list[RawCandidate]:
    parsed = feedparser.parse(xml_text)
    candidates: list[RawCandidate] = []
    for entry in getattr(parsed, "entries", []):
        title = normalize_whitespace(getattr(entry, "title", "") or "")
        link = normalize_whitespace(getattr(entry, "link", "") or "")
        if not title or not link:
            continue
        link = urljoin(base_url, link)
        raw_summary = (
            getattr(entry, "summary", "")
            or getattr(entry, "description", "")
            or ""
        )
        summary = normalize_whitespace(BeautifulSoup(raw_summary, "lxml").get_text(" ", strip=True))
        published = normalize_whitespace(
            getattr(entry, "published", "")
            or getattr(entry, "updated", "")
            or ""
        )
        candidates.append(
            RawCandidate(
                title=title,
                url=link,
                summary=summary[:800],
                published_at=published[:60],
            )
        )
    return candidates


def extract_next_data_candidates(html: str, base_url: str) -> list[RawCandidate]:
    """Next.js __NEXT_DATA__ JSON objektumok rekurzív kinyerése (pl. kormany.hu)."""
    soup = BeautifulSoup(html, "lxml")
    script = soup.find("script", id="__NEXT_DATA__")
    if not script or not script.string:
        return []
    try:
        data = json.loads(script.string)
    except Exception:
        return []

    candidates: list[RawCandidate] = []
    seen_urls: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            title = node.get("title") or node.get("name") or node.get("subject")
            raw_url = (
                node.get("url")
                or node.get("slug")
                or node.get("path")
                or node.get("link")
                or node.get("href")
            )
            if isinstance(title, str) and isinstance(raw_url, str) and len(title.strip()) >= 8:
                full_url = _resolve_next_url(raw_url.strip(), base_url)
                if full_url and full_url not in seen_urls:
                    seen_urls.add(full_url)
                    summary = ""
                    for key in ("lead", "summary", "description", "excerpt", "teaser"):
                        val = node.get(key)
                        if isinstance(val, str) and val.strip():
                            summary = normalize_whitespace(BeautifulSoup(val, "lxml").get_text(" ", strip=True))
                            break
                    pub = ""
                    for key in ("publishedAt", "published_at", "date", "createdAt", "updatedAt"):
                        val = node.get(key)
                        if isinstance(val, str) and val.strip():
                            pub = normalize_whitespace(val)[:40]
                            break
                    candidates.append(
                        RawCandidate(
                            title=normalize_whitespace(title),
                            url=full_url,
                            summary=summary[:800],
                            published_at=pub,
                        )
                    )
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for item in node:
                walk(item)

    walk(data)
    return candidates


def _resolve_next_url(raw: str, base_url: str) -> str:
    if raw.startswith(("http://", "https://")):
        return raw
    if raw.startswith("/"):
        return urljoin(base_url, raw)
    # Next.js slug esetekben pl. "tarsadalmi-egyeztetes/..."
    if "/" in raw or "-" in raw:
        return urljoin(base_url, "/" + raw.lstrip("/"))
    return ""


def extract_json_candidates(json_text: str, base_url: str) -> list[RawCandidate]:
    try:
        data = json.loads(json_text)
    except Exception:
        return []

    candidates: list[RawCandidate] = []
    seen: set[str] = set()

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            title = node.get("title") or node.get("cim") or node.get("name") or node.get("megnevezes")
            raw_url = node.get("url") or node.get("link") or node.get("href") or node.get("id")
            if isinstance(title, str) and len(title.strip()) >= 8 and raw_url is not None:
                url_str = str(raw_url).strip()
                if url_str.startswith(("http://", "https://", "/")):
                    full_url = urljoin(base_url, url_str)
                elif "njt.hu" in base_url and re.match(r"^\d{4}-\d+-\d+-\d+$", url_str):
                    full_url = f"https://njt.hu/jogszabaly/{url_str}"
                else:
                    full_url = ""
                if full_url and full_url not in seen:
                    seen.add(full_url)
                    summary = ""
                    for key in ("summary", "leiras", "description", "lead", "kivonat"):
                        val = node.get(key)
                        if isinstance(val, str) and val.strip():
                            summary = normalize_whitespace(val)
                            break
                    pub = ""
                    for key in ("published_at", "date", "datum", "hatalybalepes", "createdAt"):
                        val = node.get(key)
                        if isinstance(val, str) and val.strip():
                            pub = normalize_whitespace(val)[:40]
                            break
                    candidates.append(
                        RawCandidate(
                            title=normalize_whitespace(title),
                            url=full_url,
                            summary=summary[:800],
                            published_at=pub,
                        )
                    )
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for el in node:
                walk(el)

    walk(data)
    return candidates


def extract_html_candidates(
    html: str,
    base_url: str,
    link_must_contain: tuple[str, ...] = (),
    min_title_len: int = 10,
) -> list[RawCandidate]:
    """Általános szemantikus HTML cikk-, táblázat- és linkkinyerő."""
    soup = BeautifulSoup(html, "lxml")

    # Navigációs zaj eltávolítása a pontosabb kinyeréshez (de csak ha marad tartalom)
    for tag_name in ("script", "style", "noscript", "svg"):
        for tag in soup.find_all(tag_name):
            tag.decompose()

    candidates: list[RawCandidate] = []
    seen_keys: set[tuple[str, str]] = set()

    def push_candidate(
        title: str,
        href: str,
        summary: str = "",
        published_at: str = "",
        document_ref: str = "",
    ) -> None:
        clean_title = normalize_whitespace(title)
        if len(clean_title) < min_title_len:
            return
        if clean_title.lower() in NOISE_TITLES:
            return
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:")):
            return
        full_url = urljoin(base_url, href.strip())
        parsed = urlparse(full_url)
        if parsed.scheme not in ("http", "https"):
            return
        if link_must_contain and not any(tok in full_url.lower() for tok in link_must_contain):
            return

        dedup_key = (full_url.lower(), clean_title.lower())
        if dedup_key in seen_keys:
            return
        seen_keys.add(dedup_key)

        if not published_at:
            dm = DATE_RE.search(f"{clean_title} {summary}")
            if dm:
                published_at = normalize_whitespace(dm.group(1))

        candidates.append(
            RawCandidate(
                title=clean_title[:350],
                url=full_url,
                summary=normalize_whitespace(summary)[:800],
                published_at=published_at[:60],
                document_ref=document_ref,
            )
        )

    # 1. Cikkek / kártyák / listaelemek
    for container in soup.find_all(["article", "section", "li", "div"], class_=re.compile(r"(card|item|news|article|doc|result|hit|entry|list|iromany|kozlony)", re.I)):
        a = container.find("a", href=True)
        if not a:
            continue
        heading = container.find(["h1", "h2", "h3", "h4", "strong"])
        title = heading.get_text(" ", strip=True) if heading else a.get_text(" ", strip=True)
        if len(normalize_whitespace(title)) < min_title_len:
            title = a.get_text(" ", strip=True)
        container_text = normalize_whitespace(container.get_text(" ", strip=True))
        summary = container_text.replace(normalize_whitespace(title), "", 1).strip(" -|–:")
        time_tag = container.find("time")
        pub = ""
        if time_tag:
            pub = time_tag.get("datetime") or time_tag.get_text(" ", strip=True)
        push_candidate(title, a["href"], summary=summary, published_at=pub)

    # 2. Táblázatsorok (pl. Parlament.hu irományok, Közlöny)
    for row in soup.find_all("tr"):
        a = row.find("a", href=True)
        if not a:
            continue
        cells = [normalize_whitespace(td.get_text(" ", strip=True)) for td in row.find_all(["td", "th"])]
        row_text = " | ".join(c for c in cells if c)
        link_text = normalize_whitespace(a.get_text(" ", strip=True))
        # Ha a link szövege csak egy rövid irományszám (pl. "T/12345"), akkor a sor leírását használjuk címként!
        if len(link_text) < min_title_len or re.fullmatch(r"[THKJB]/\d+(?:/\d+)?", link_text, re.I):
            longest = max(cells, key=len, default=link_text)
            title = f"{link_text} — {longest}" if longest and longest != link_text else row_text
            doc_ref = link_text if re.fullmatch(r"[THKJB]/\d+(?:/\d+)?", link_text, re.I) else ""
        else:
            title = link_text
            doc_ref = ""
        push_candidate(title, a["href"], summary=row_text, document_ref=doc_ref)

    # 3. Általános linkek a fő tartalomban (navigáción kívül)
    for a in soup.find_all("a", href=True):
        if a.find_parent(["nav", "footer"]):
            continue
        title = a.get_text(" ", strip=True)
        parent_text = ""
        if a.parent:
            parent_text = normalize_whitespace(a.parent.get_text(" ", strip=True))
        push_candidate(title, a["href"], summary=parent_text)

    return candidates
