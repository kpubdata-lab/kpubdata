"""Test module.
semas live tests."""

from __future__ import annotations

import pytest

from kpubdata.client import Client
from kpubdata.core.models import RecordBatch


# test store radius returns record batch scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_semas_key")
def test_store_radius_returns_record_batch(live_client: Client) -> None:
    """Verify test store radius returns record batch scenario."""
    ds = live_client.dataset("semas.store_radius")

    result = ds.list(cx="127.02758", cy="37.49794", radius="500")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert isinstance(result.items[0], dict)


# test store radius raw returns envelope scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_semas_key")
def test_store_radius_raw_returns_envelope(live_client: Client) -> None:
    """Verify test store radius raw returns envelope scenario."""
    ds = live_client.dataset("semas.store_radius")

    raw = ds.call_raw("storeListInRadius", cx="127.02758", cy="37.49794", radius="500")

    assert isinstance(raw, dict)


# test store radius item has business name scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_semas_key")
def test_store_radius_item_has_business_name(live_client: Client) -> None:
    """Verify test store radius item has business name scenario."""
    ds = live_client.dataset("semas.store_radius")
    result = ds.list(cx="127.02758", cy="37.49794", radius="500")

    assert len(result.items) > 0
    item = result.items[0]
    assert "bizesNm" in item


# test upjong large returns categories scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_semas_key")
def test_upjong_large_returns_categories(live_client: Client) -> None:
    """Verify test upjong large returns categories scenario."""
    ds = live_client.dataset("semas.upjong_large")

    result = ds.list()

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0


# test zone one returns record batch scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_semas_key")
def test_zone_one_returns_record_batch(live_client: Client) -> None:
    """Verify test zone one returns record batch scenario."""
    ds = live_client.dataset("semas.zone_one")

    result = ds.list(key="D00001")

    assert isinstance(result, RecordBatch)
