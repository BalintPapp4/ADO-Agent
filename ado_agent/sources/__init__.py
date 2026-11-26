"""Forrásadapterek az ADÓ Agent számára."""

from .registry import ADAPTER_MAP, build_adapter

__all__ = ["ADAPTER_MAP", "build_adapter"]
