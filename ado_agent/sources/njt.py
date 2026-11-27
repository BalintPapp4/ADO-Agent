"""Nemzeti Jogszabálytár (njt.hu — hivatalos lap) forrásadapter."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..classifier import normalize_whitespace
from ..fetcher import DATE_RE, FetchResult, is_spa_empty_shell
from ..models import RawCandidate
from .base import AdapterOutput, BaseSourceAdapter, parse_generic_response

NJT_LAW_TITLES = {
    "2007-127-00-00": "2007. évi CXXVII. törvény az általános forgalmi adóról (Áfa tv.)",
    "1995-117-00-00": "1995. évi CXVII. törvény a személyi jövedelemadóról (Szja tv.)",
    "2008-67-00-00": "2008. évi LXVII. törvény (Robin Hood adó — energiaellátók jövedelemadója)",
    "1996-81-00-00": "1996. évi LXXXI. törvény a társasági adóról és az osztalékadóról (Tao tv.)",
    "2017-150-00-00": "2017. évi CL. törvény az adózás rendjéről (Art.)",
    "2022-197-20-22": "197/2022. (VI. 4.) Korm. rendelet az extraprofit adókról",
}


class NjtAdapter(BaseSourceAdapter):
    """Nemzeti Jogszabálytár (njt.hu) figyelő."""

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        if "/jogszabaly/" in res.final_url.lower():
            return self._parse_njt_law_page(res, out)
        return parse_generic_response(res, out)

    def _parse_njt_law_page(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        # Ha Angular SPA üres héjként jön le JS nélkül, a törvényazonosító alapján is megőrizzük a figyelő linket,
        # ha viszont SSR/meta adat van benne, kinyerjük!
        soup = BeautifulSoup(res.text, "lxml")
        h1 = soup.find("h1")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        title_tag = soup.find("title")

        slug = res.final_url.rstrip("/").split("/")[-1]
        fallback_title = NJT_LAW_TITLES.get(slug, "")

        raw_title = normalize_whitespace(
            (h1.get_text(" ", strip=True) if h1 else "")
            or (title_tag.get_text(" ", strip=True) if title_tag else "")
        )
        # Ha csak generikus "Nemzeti Jogszabálytár" a cím (SPA), használjuk az ismert nevet
        if not raw_title or raw_title.lower() in {"nemzeti jogszabálytár", "njt"}:
            raw_title = fallback_title

        if not raw_title:
            return []

        desc = normalize_whitespace(meta_desc.get("content", "") if meta_desc else "")
        body_text = normalize_whitespace(soup.get_text(" ", strip=True))
        if is_spa_empty_shell(res.text):
            summary = desc or (
                "NJT közvetlen jogszabály-figyelő (kliensoldali Angular felület; "
                "kattints a linkre a legfrissebb hatályos szöveghez)."
            )
            if not any("SPA" in w for w in out.warnings):
                out.warnings.append(
                    "Az njt.hu kliensoldali Angular alkalmazást használ — a kulcstörvények közvetlen linkjei "
                    "felvételre kerültek, de a dinamikus keresési lista csak böngészőben töltődik be."
                )
        else:
            summary = desc or body_text[:500]

        dm = DATE_RE.search(summary)
        pub = normalize_whitespace(dm.group(1)) if dm else ""
        doc_match = re.search(r"(\d{4}\.\s*évi\s+[IVXLCDM]+\.\s*törvény|\d+/\d{4}\.\s*\([^)]+\)\s*Korm\.\s*rendelet)", raw_title, re.I)

        return [
            RawCandidate(
                title=raw_title,
                url=res.final_url,
                summary=summary[:800],
                published_at=pub,
                document_ref=normalize_whitespace(doc_match.group(1)) if doc_match else "",
                status_label="Nemzeti Jogszabálytár (zöld)",
            )
        ]
