"""Forrásadapter nyilvántartás (registry)."""

from __future__ import annotations

from ..fetcher import HttpFetcher
from ..models import SourceConfig
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
    "rss": GenericWebAdapter,
    "web": GenericWebAdapter,
}


def build_adapter(source: SourceConfig, fetcher: HttpFetcher) -> BaseSourceAdapter:
    cls = ADAPTER_MAP.get(source.adapter.lower(), GenericWebAdapter)
    return cls(source=source, fetcher=fetcher)
