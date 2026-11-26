"""Netjogtár (net.jogtar.hu) forrásadapter — friss változások és kulcs adótörvények."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..classifier import normalize_whitespace
from ..fetcher import DATE_RE, FetchResult
from ..models import RawCandidate
from .base import AdapterOutput, BaseSourceAdapter, parse_generic_response

LAW_HEADER_RE = re.compile(r"\d{4}\.\s*évi\s+[IVXLCDM]+\.\s*törvény|\d+/\d{4}\.\s*\([^)]+\)\s*Korm\.", re.IGNORECASE)


class NetJogtarAdapter(BaseSourceAdapter):
    """Wolters Kluwer Netjogtár változásfigyelő és törvénymonitor."""

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        if "docid=" in res.final_url.lower():
            return self._parse_law_page(res)
        return parse_generic_response(res, out)

    def _parse_law_page(self, res: FetchResult) -> list[RawCandidate]:
        soup = BeautifulSoup(res.text, "lxml")
        h1 = soup.find("h1")
        title_tag = soup.find("title")
        heading = normalize_whitespace(h1.get_text(" ", strip=True) if h1 else "")
        page_title = normalize_whitespace(title_tag.get_text(" ", strip=True) if title_tag else "")
        title = heading or page_title
        if not title or len(title) < 6:
            return []

        body_text = normalize_whitespace(soup.get_text(" ", strip=True))
        # Keressük a hatályosságra / módosításra utaló metaadat-részeket az oldal tetején
        snippet_parts: list[str] = []
        for el in soup.find_all(["h1", "h2", "p", "div", "span"], limit=60):
            txt = normalize_whitespace(el.get_text(" ", strip=True))
            if any(k in txt.lower() for k in ("hatályos", "módosít", "kihirdet", "netjogtár")) and 10 <= len(txt) <= 280:
                if txt not in snippet_parts:
                    snippet_parts.append(txt)
        summary = " | ".join(snippet_parts[:4]) if snippet_parts else body_text[:450]

        dm = DATE_RE.search(summary)
        pub = normalize_whitespace(dm.group(1)) if dm else ""
        doc_match = LAW_HEADER_RE.search(f"{title} {summary}")
        doc_ref = normalize_whitespace(doc_match.group(0)) if doc_match else ""

        return [
            RawCandidate(
                title=title,
                url=res.final_url,
                summary=summary[:800],
                published_at=pub,
                document_ref=doc_ref,
                status_label="Hatályos törvényszöveg (Netjogtár)",
            )
        ]
