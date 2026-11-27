"""Adózóna (adozona.hu) forrásadapter — közvetlen elérés + Cloudflare 403 tartalék."""

from __future__ import annotations

from ..classifier import normalize_whitespace
from ..fetcher import is_feed_response, parse_feed_candidates
from .base import AdapterOutput, BaseSourceAdapter, parse_generic_response

ADOZONA_GOOGLE_NEWS_RSS = (
    "https://news.google.com/rss/search?q=site:adozona.hu+ad%C3%B3&hl=hu&gl=HU&ceid=HU:hu"
)


class AdozonaAdapter(BaseSourceAdapter):
    """Adózóna.hu figyelő automatikus RSS/Google News tartalékkal Cloudflare 403 esetére."""

    def collect(self) -> AdapterOutput:
        out = super().collect()
        if out.ok_requests > 0 and len(out.candidates) > 0:
            return out

        # Ha az adozona.hu közvetlen URL-jei HTTP 403-at (Cloudflare / felhős IP tiltás) vagy hibát adtak,
        # próbáljuk meg a nyilvános Google News (site:adozona.hu) RSS hírfolyamot tartalékként.
        has_403_or_block = any("403" in e or "bontotta" in e.lower() for e in out.errors) or out.ok_requests == 0
        if has_403_or_block:
            out.checked_urls.append(ADOZONA_GOOGLE_NEWS_RSS)
            res = self.fetcher.fetch(ADOZONA_GOOGLE_NEWS_RSS)
            if res.ok and is_feed_response(res.text, res.content_type):
                cands = parse_feed_candidates(res.text, res.final_url)
                if cands:
                    out.ok_requests += 1
                    seen = {(c.url.lower(), normalize_whitespace(c.title).lower()) for c in out.candidates}
                    for cand in cands:
                        cand.status_label = cand.status_label or "Adózóna (tükör RSS)"
                        key = (cand.url.lower(), normalize_whitespace(cand.title).lower())
                        if key not in seen:
                            seen.add(key)
                            out.candidates.append(cand)
                    out.warnings.append(
                        "Az adozona.hu közvetlenül HTTP 403 védelmet adott (Cloudflare); "
                        "a cikkek a Google News (site:adozona.hu) RSS tükörből töltődtek be."
                    )
        return out

    def parse_response(self, res, out):
        return parse_generic_response(res, out)
