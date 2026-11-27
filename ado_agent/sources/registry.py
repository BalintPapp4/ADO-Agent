"""Forrásadapter nyilvántartás (registry)."""

from __future__ import annotations

from ..fetcher import HttpFetcher
from ..models import SourceConfig
from .adozona import AdozonaAdapter
from .base import BaseSourceAdapter, GenericWebAdapter
from .eurlex import EurLexAdapter
from .kormany import KormanyAdapter
from .magyarkozlony import MagyarKozlonyAdapter
from .nav import NavAdapter
from .netjogtar import NetJogtarAdapter
from .njt import NjtAdapter
from .parlament import ParlamentAdapter

ADAPTER_MAP: dict[str, type[BaseSourceAdapter]] = {
    "parlament": ParlamentAdapter,
    "kormany": KormanyAdapter,
    "netjogtar": NetJogtarAdapter,
    "njt": NjtAdapter,
    "nav": NavAdapter,
    "magyarkozlony": MagyarKozlonyAdapter,
    "eurlex": EurLexAdapter,
    "adozona": AdozonaAdapter,
    "rss": GenericWebAdapter,
    "web": GenericWebAdapter,
}


def build_adapter(source: SourceConfig, fetcher: HttpFetcher) -> BaseSourceAdapter:
    adapter_key = (source.adapter or "web").lower()
    if adapter_key in ("web", "rss"):
        low_url = (source.url or "").lower()
        if "net.jogtar.hu" in low_url:
            adapter_key = "netjogtar"
        elif "njt.jog.gov.hu" in low_url or "njt.hu" in low_url:
            adapter_key = "njt"
        elif "adozona.hu" in low_url:
            adapter_key = "adozona"
        elif "parlament.hu" in low_url:
            adapter_key = "parlament"
        elif "magyarkozlony.hu" in low_url:
            adapter_key = "magyarkozlony"
        elif "nav.gov.hu" in low_url:
            adapter_key = "nav"
        elif "kormany.hu" in low_url:
            adapter_key = "kormany"
        elif "eur-lex.europa.eu" in low_url:
            adapter_key = "eurlex"
    cls = ADAPTER_MAP.get(adapter_key, GenericWebAdapter)
    return cls(source=source, fetcher=fetcher)
