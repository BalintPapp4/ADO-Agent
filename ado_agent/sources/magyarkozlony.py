"""Magyar Közlöny (magyarkozlony.hu — hivatalos lap) forrásadapter."""

from __future__ import annotations

import re

from bs4 import BeautifulSoup

from ..classifier import normalize_whitespace
from ..fetcher import DATE_RE, FetchResult
from ..models import RawCandidate
from .base import AdapterOutput, BaseSourceAdapter, parse_generic_response

ISSUE_RE = re.compile(r"(\d{4}\.\s*évi\s*\d+\.\s*szám|Magyar Közlöny\s*\d+\.\s*szám)", re.IGNORECASE)


class MagyarKozlonyAdapter(BaseSourceAdapter):
    """Magyar Közlöny friss számai és kihirdetett jogszabályok."""

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        cands = parse_generic_response(res, out)
        soup = BeautifulSoup(res.text, "lxml")
        for tag_name in ("script", "style", "noscript", "svg", "nav", "header", "footer"):
            for tag in soup.find_all(tag_name):
                tag.decompose()

        for a in soup.find_all("a", href=True):
            href = (a.get("href") or "").strip()
            if not href or href.startswith(("#", "javascript:", "mailto:")):
                continue
            txt = normalize_whitespace(a.get_text(" ", strip=True))
            if len(txt) < 8 or len(txt) > 320:
                continue
            parent = a.find_parent(["tr", "li", "article", "section", "div", "p"]) or a.parent
            parent_txt = normalize_whitespace(parent.get_text(" ", strip=True)) if parent else txt
            if len(parent_txt) > 1500:
                parent_txt = txt
            if any(tok in parent_txt.lower() for tok in ("közlöny", "törvény", "rendelet", "kihirdet")):
                from urllib.parse import urljoin

                full_url = urljoin(res.final_url, href)
                if not full_url.startswith(("http://", "https://")):
                    continue
                im = ISSUE_RE.search(parent_txt)
                dm = DATE_RE.search(parent_txt)
                cands.append(
                    RawCandidate(
                        title=txt if len(txt) >= 16 else parent_txt[:260],
                        url=full_url,
                        summary=parent_txt[:800],
                        published_at=normalize_whitespace(dm.group(1)) if dm else "",
                        document_ref=normalize_whitespace(im.group(1)) if im else "",
                        status_label="Kihirdetve (Magyar Közlöny)",
                    )
                )

        for cand in cands:
            if not cand.status_label:
                cand.status_label = "Magyar Közlöny"
        return cands
