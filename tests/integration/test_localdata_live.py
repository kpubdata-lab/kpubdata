"""Localdata (data.go.kr) real API integration tests.

Run with:
    export KPUBDATA_LOCALDATA_API_KEY="your-key"
    uv run pytest -m integration -k localdata -ra -v
"""

from __future__ import annotations

import pytest

from kpubdata.client import Client
from kpubdata.core.models import RecordBatch


# test general restaurant returns record batch scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_localdata_key")
def test_general_restaurant_returns_record_batch(live_client: Client) -> None:
    """Verify test general restaurant returns record batch scenario."""
    ds = live_client.dataset("localdata.general_restaurant")
    result = ds.list(page_size=5)

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0


# test general restaurant raw returns envelope scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_localdata_key")
def test_general_restaurant_raw_returns_envelope(live_client: Client) -> None:
    """Verify test general restaurant raw returns envelope scenario."""
    ds = live_client.dataset("localdata.general_restaurant")
    result = ds.call_raw("info", numOfRows="3")

    assert isinstance(result, dict)
    assert "response" in result


# test rest cafe returns record batch scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_localdata_key")
def test_rest_cafe_returns_record_batch(live_client: Client) -> None:
    """Verify test rest cafe returns record batch scenario."""
    ds = live_client.dataset("localdata.rest_cafe")
    result = ds.list(page_size=5)

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0


LOCALDATA_COMMON_KEYS = {"BPLC_NM", "SALS_STTS_NM", "ROAD_NM_ADDR", "STTUS_ADDR"}


# test general restaurant has required fields scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_localdata_key")
def test_general_restaurant_has_required_fields(live_client: Client) -> None:
    """Verify test general restaurant has required fields scenario."""
    ds = live_client.dataset("localdata.general_restaurant")
    result = ds.list(page_size=5)
    item = result.items[0]

    assert LOCALDATA_COMMON_KEYS.issubset(item.keys())


# test general restaurant total count scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_localdata_key")
def test_general_restaurant_total_count(live_client: Client) -> None:
    """Verify test general restaurant total count scenario."""
    ds = live_client.dataset("localdata.general_restaurant")
    result = ds.list(page_size=5)

    assert result.total_count is not None
    assert result.total_count > 0


ALL_DATASETS = [
    "localdata.general_restaurant",
    "localdata.rest_cafe",
]


# test all datasets return data scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_localdata_key")
@pytest.mark.parametrize("dataset_id", ALL_DATASETS)
def test_all_datasets_return_data(live_client: Client, dataset_id: str) -> None:
    """Verify test all datasets return data scenario."""
    ds = live_client.dataset(dataset_id)
    result = ds.list(page_size=3)

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert result.total_count is not None
    assert result.total_count > 0
