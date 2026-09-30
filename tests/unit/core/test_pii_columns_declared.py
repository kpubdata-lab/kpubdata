"""Declared pii_columns must exist in fixture responses (#693).

A typo in a pii_columns declaration silently publishes PII in the clear —
this test fails before that can happen.
"""

from __future__ import annotations

import json
from pathlib import Path

from kpubdata.core.spec import discover_specs

_REPO = Path(__file__).resolve().parents[2]
_SPECS = _REPO / "src" / "kpubdata" / "specs"
_FIXTURES = _REPO / "tests" / "fixtures"


def test_declared_pii_columns_exist_in_fixtures() -> None:
    for spec in discover_specs():
        if spec.license is None or not spec.license.pii_columns:
            continue
        provider_dir = _FIXTURES / spec.provider
        dataset_dir = provider_dir / spec.dataset_key
        if not dataset_dir.exists():
            continue
        for raw_file in dataset_dir.glob("*.raw.json"):
            data = json.loads(raw_file.read_text(encoding="utf-8"))
            items = _extract_items(data)
            if not items:
                continue
            available = set(items[0].keys())
            for col in spec.license.pii_columns:
                assert col in available, (
                    f"{spec.id}: pii_column {col!r} declared but not in "
                    f"fixture {raw_file.name}. Available: {sorted(available)[:10]}..."
                )


def _extract_items(payload: object) -> list[dict[str, object]]:
    if not isinstance(payload, dict):
        return []
    body = payload.get("response", {})
    if not isinstance(body, dict):
        return []
    inner = body.get("body", {})
    if not isinstance(inner, dict):
        return []
    items = inner.get("items", {})
    if isinstance(items, dict):
        item = items.get("item", [])
        return item if isinstance(item, list) else [item] if isinstance(item, dict) else []
    if isinstance(items, list):
        return items
    return []
