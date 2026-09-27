"""Test module.
law live tests."""

from __future__ import annotations

import pytest

from kpubdata.client import Client
from kpubdata.core.models import RecordBatch


# test law search returns record batch scenario
@pytest.mark.integration
def test_law_search_returns_record_batch(live_client: Client) -> None:
    """Verify test law search returns record batch scenario."""
    ds = live_client.dataset("law.law_search")

    result = ds.list(query="민법")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert isinstance(result.items[0], dict)


# test law search raw returns envelope scenario
@pytest.mark.integration
def test_law_search_raw_returns_envelope(live_client: Client) -> None:
    """Verify test law search raw returns envelope scenario."""
    ds = live_client.dataset("law.law_search")

    raw = ds.call_raw("list", query="헌법")

    assert isinstance(raw, dict)


# test law search item has law name scenario
@pytest.mark.integration
def test_law_search_item_has_law_name(live_client: Client) -> None:
    """Verify test law search item has law name scenario."""
    ds = live_client.dataset("law.law_search")
    result = ds.list(query="민법")

    item = result.items[0]
    assert any(key in item for key in ("법령명한글", "lawNameKorean", "법령명"))


# test law search pagination scenario
@pytest.mark.integration
def test_law_search_pagination(live_client: Client) -> None:
    """Verify test law search pagination scenario."""
    ds = live_client.dataset("law.law_search")

    result = ds.list(query="법", page_size=5)

    assert isinstance(result, RecordBatch)
    assert len(result.items) <= 5


# test ordin search returns record batch scenario
@pytest.mark.integration
def test_ordin_search_returns_record_batch(live_client: Client) -> None:
    """Verify test ordin search returns record batch scenario."""
    ds = live_client.dataset("law.ordin_search")

    result = ds.list(query="서울")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
