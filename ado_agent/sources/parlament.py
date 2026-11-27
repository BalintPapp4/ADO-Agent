"""Országgyűlés (parlament.hu) forrásadapter — törvényjavaslatok és irományok."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..classifier import normalize_whitespace
from ..fetcher import DATE_RE, FetchResult, extract_html_candidates
from ..models import RawCandidate
from .base import AdapterOutput, BaseSourceAdapter, parse_generic_response

BILL_NUM_RE = re.compile(r"\b([THKJB]/\d{3,6}(?:/\d+)?)\b", re.IGNORECASE)


class ParlamentAdapter(BaseSourceAdapter):
    """Parlament.hu törvényjavaslatok (T/), irományok és hírek feldolgozása."""

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        cands = parse_generic_response(res, out)
        # Speciális parlament.hu táblázatos vagy iromány-kártyás finomítás
        soup = BeautifulSoup(res.text, "lxml")
        for tag_name in ("script", "style", "noscript", "svg", "nav", "header", "footer"):
            for tag in soup.find_all(tag_name):
                tag.decompose()
        extra: list[RawCandidate] = []

        for link in soup.find_all("a", href=True):
            href = (link["href"] or "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            txt = normalize_whitespace(link.get_text(" ", strip=True))
            if not txt:
                continue
            is_iromany_link = any(
                tok in href.lower()
                for tok in ("iromany", "egyes-iromany", "p_ckl", "p_izon", "/documents/")
            )
            bill_match = BILL_NUM_RE.search(txt)
            if not (is_iromany_link or bill_match):
                continue

            parent = link.find_parent(["tr", "li", "article", "div", "p"])
            context = normalize_whitespace(parent.get_text(" ", strip=True)) if parent else txt
            if len(context) > 1500:
                context = txt
            title = txt
            doc_ref = bill_match.group(1).upper() if bill_match else ""
            if len(title) < 16 and len(context) > len(title):
                title = context[:280]
            if not doc_ref:
                cm = BILL_NUM_RE.search(context)
                if cm:
                    doc_ref = cm.group(1).upper()

            dm = DATE_RE.search(context)
            pub = normalize_whitespace(dm.group(1)) if dm else ""
            status = "Törvényjavaslat" if doc_ref.startswith("T/") else ""

            from urllib.parse import urljoin

            full_url = urljoin(res.final_url, href)
            if full_url.startswith(("http://", "https://")) and len(title) >= 8:
                extra.append(
                    RawCandidate(
                        title=title,
                        url=full_url,
                        summary=context[:800],
                        published_at=pub,
                        document_ref=doc_ref,
                        status_label=status,
                    )
                )

        # Összefésülés, prioritással a gazdagabb adatokra
        merged: dict[tuple[str, str], RawCandidate] = {}
        for item in extra + cands:
            key = (item.url.lower(), item.title.lower())
            if key not in merged:
                merged[key] = item
        return list(merged.values())
