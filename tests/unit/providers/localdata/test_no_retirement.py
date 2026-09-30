"""Regression: localdata must not regress to retirement (#618, #700).

Retirement was applied in #603 without evidence and reverted in #618 — the
data lives on data.go.kr (`apis.data.go.kr/1741000/...`), 403 means
activation required, not upstream closure. These tests keep the revert in
place: reintroducing a DeprecationWarning or a catalogue `lifecycle:
retired` field fails here.
"""

from __future__ import annotations

import json
import warnings
from pathlib import Path

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query, Representation
from kpubdata.providers.localdata.adapter import LocaldataAdapter
from kpubdata.transport.http import HttpTransport

_REPO = Path(__file__).resolve().parents[4]
_CATALOGUE = _REPO / "src" / "kpubdata" / "providers" / "localdata" / "catalogue.json"


def _no_retirement_dataset() -> DatasetRef:
    return DatasetRef(
        id="localdata.bakery",
        provider="localdata",
        dataset_key="bakery",
        name="Bakery Permits",
        representation=Representation.API_JSON,
    )


def test_query_records_emits_no_deprecation_warning() -> None:
    """Calling query_records must not raise a DeprecationWarning (#618, #700)."""
    adapter = LocaldataAdapter(
        config=KPubDataConfig(provider_keys={"datago": "test-key"}),
        transport=HttpTransport(),
    )
    dataset = _no_retirement_dataset()
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        try:
            adapter.query_records(dataset, Query())
        except Exception:
            pass  # network call fails in test — the point is no DeprecationWarning


def test_catalogue_has_no_retired_lifecycle() -> None:
    """No catalogue entry may declare retirement (#618, #700)."""
    entries = json.loads(_CATALOGUE.read_text(encoding="utf-8"))
    for entry in entries:
        assert "lifecycle" not in entry, (
            f"{entry.get('dataset_key', '?')}: lifecycle={entry['lifecycle']!r} — "
            "localdata was retired in #603 without evidence and un-retired in #618. "
            "Re-retiring needs a fresh live probe proving the endpoints are dead."
        )
        assert "retired_at" not in entry, (
            f"{entry.get('dataset_key', '?')}: retired_at={entry['retired_at']!r}"
        )
        assert "retirement_note" not in entry
