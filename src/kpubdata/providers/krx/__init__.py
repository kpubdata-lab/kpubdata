"""KPubData Python module.

This file contains the implementation at
``src/kpubdata/providers/krx/__init__.py``.
Key classes and functions serve as public API, transport layer, or provider
adapter.
"""

from __future__ import annotations

from .adapter import KrxAdapter

__all__ = ["KrxAdapter"]
