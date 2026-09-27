"""KPubData Python module.

This file contains the implementation at ``src/kpubdata/providers/seoul/__init__.py``.
Key classes and functions are part of the public API, transport layer,
or provider adapter.
"""

from .adapter import SeoulAdapter

__all__ = ["SeoulAdapter"]
