"""Kormány.hu forrásadapter — társadalmi egyeztetés, dokumentumtár, minisztériumok."""

from __future__ import annotations

from ..fetcher import FetchResult, extract_html_candidates, extract_next_data_candidates
from ..models import RawCandidate
from .base import AdapterOutput, BaseSourceAdapter, parse_generic_response


class KormanyAdapter(BaseSourceAdapter):
    """Kormány.hu Next.js (__NEXT_DATA__) + HTML + PDF tervezet-kinyerő."""

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        next_cands = extract_next_data_candidates(res.text, res.final_url)
        html_cands = extract_html_candidates(res.text, res.final_url)
        generic = parse_generic_response(res, out) if not (next_cands or html_cands) else []

        results: list[RawCandidate] = []
        for cand in next_cands + html_cands + generic:
            url_low = cand.url.lower()
            text_low = f"{cand.title} {cand.summary}".lower()
            if (
                "tarsadalmi-egyeztetes" in url_low
                or "társadalmi egyeztetés" in text_low
                or "tervezet" in text_low
            ) and not cand.status_label:
                cand.status_label = "Társadalmi egyeztetés / Tervezet"
            results.append(cand)
        return results
