"""KPubData Python module.

This file contains implementation at path
``src/kpubdata/providers/law/__init__.py``. Key classes and functions serve
as public API, transport layer, or provider adapter.
"""

from __future__ import annotations

from .adapter import LawAdapter

__all__ = ["LawAdapter"]
