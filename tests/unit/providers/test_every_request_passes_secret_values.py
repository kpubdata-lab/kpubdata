"""Every request a provider makes hands the transport its credential's value (#805).

The transport masks a credential by parameter name and by value. An adapter that passes
no value relies on the name alone, so a key sent under a name the sensitive list lacks
appears in logs and tracebacks. Two paths were found that way; this keeps a third from
being added: each ``self._transport.request(...)`` under ``src/kpubdata`` must pass
``secret_values``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import kpubdata

_SRC = Path(kpubdata.__file__).resolve().parent
#: Where requests to providers are made. The transport package itself is the callee.
_SCANNED = ("providers", "core")


def _transport_requests(tree: ast.AST) -> list[ast.Call]:
    """Calls of the form ``<...>._transport.request(...)``."""
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "request"
        and isinstance(node.func.value, ast.Attribute)
        and node.func.value.attr == "_transport"
    ]


def _without_secret_values(source: str) -> list[int]:
    return [
        call.lineno
        for call in _transport_requests(ast.parse(source))
        if not any(keyword.arg == "secret_values" for keyword in call.keywords)
    ]


def _files() -> list[Path]:
    return sorted(path for name in _SCANNED for path in (_SRC / name).rglob("*.py"))


def test_every_transport_request_passes_secret_values() -> None:
    missing = [
        f"{path.relative_to(_SRC)}:{line}"
        for path in _files()
        for line in _without_secret_values(path.read_text(encoding="utf-8"))
    ]

    assert missing == []


def test_the_scan_finds_the_requests_it_is_meant_to_cover() -> None:
    """If a rename made nothing match, the check above would pass on nothing."""
    found = sum(
        len(_transport_requests(ast.parse(p.read_text(encoding="utf-8")))) for p in _files()
    )

    assert found >= 14


def test_a_request_without_the_value_is_reported() -> None:
    source = (
        "class A:\n"
        "    def go(self):\n"
        "        self._transport.request('GET', 'u', params={})\n"
        "        self._transport.request('GET', 'u', secret_values=('k',))\n"
    )

    assert _without_secret_values(source) == [3]
