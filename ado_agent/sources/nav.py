"""NAV (nav.gov.hu) forrásadapter."""

from __future__ import annotations

from ..fetcher import FetchResult
from ..models import RawCandidate
from .base import AdapterOutput, BaseSourceAdapter, parse_generic_response


class NavAdapter(BaseSourceAdapter):
    """Nemzeti Adó- és Vámhivatal hivatalos hírek, adójogszabály-változások és RSS."""

    def parse_response(self, res: FetchResult, out: AdapterOutput) -> list[RawCandidate]:
        cands = parse_generic_response(res, out)
        for cand in cands:
            if not cand.status_label:
                cand.status_label = "NAV tájékoztató / jogszabályváltozás"
        return cands
