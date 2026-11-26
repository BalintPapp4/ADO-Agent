"""EUR-Lex, DG TAXUD és Európai Parlament (EU adózási javaslatok) forrásadapter."""

from __future__ import annotations

import re

from ..classifier import normalize_whitespace
from ..fetcher import FetchResult
from ..models import RawCandidate
from .base import AdapterOutput, BaseSourceAdapter, parse_generic_response

CELEX_OR_COM_RE = re.compile(r"\b(COM\s*\(\d{4}\)\s*\d+|CELEX[:\s]*[0-9A-Z]+)\b", re.IGNORECASE)


class EurLexAdapter(BaseSourceAdapter):
    """EU adózási irányelvek, COM-javaslatok és parlamenti hírek feldolgozója."""

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        cands = parse_generic_response(res, out)
        for cand in cands:
            combined = f"{cand.title} {cand.summary} {cand.url}"
            m = CELEX_OR_COM_RE.search(combined)
            if m and not cand.document_ref:
                cand.document_ref = normalize_whitespace(m.group(1))
            if not cand.status_label:
                if "com(" in combined.lower() or "proposal" in combined.lower() or "javaslat" in combined.lower():
                    cand.status_label = "EU Törvényjavaslat"
                elif "directive" in combined.lower() or "irányelv" in combined.lower():
                    cand.status_label = "EU Irányelv"
                else:
                    cand.status_label = "EU Adózási dokumentum"
        return cands
