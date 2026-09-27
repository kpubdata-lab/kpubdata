"""Test module.
sgis live tests."""

from __future__ import annotations

import pytest

from kpubdata.client import Client
from kpubdata.core.models import RecordBatch


# test boundary sido returns record batch scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_sgis_key")
def test_boundary_sido_returns_record_batch(live_client: Client) -> None:
    """Verify test boundary sido returns record batch scenario."""
    ds = live_client.dataset("sgis.boundary.sido")

    result = ds.list()

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0


# test boundary sido has geometry scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_sgis_key")
def test_boundary_sido_has_geometry(live_client: Client) -> None:
    """Verify test boundary sido has geometry scenario."""
    ds = live_client.dataset("sgis.boundary.sido")
    result = ds.list()

    item = result.items[0]
    assert "geometry" in item or "adm_cd" in item


# test boundary sido raw returns geojson scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_sgis_key")
def test_boundary_sido_raw_returns_geojson(live_client: Client) -> None:
    """Verify test boundary sido raw returns geojson scenario."""
    ds = live_client.dataset("sgis.boundary.sido")

    raw = ds.call_raw("list")

    assert isinstance(raw, dict)
    assert "features" in raw


# test boundary sigungu returns record batch scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_sgis_key")
def test_boundary_sigungu_returns_record_batch(live_client: Client) -> None:
    """Verify test boundary sigungu returns record batch scenario."""
    ds = live_client.dataset("sgis.boundary.sigungu")

    result = ds.list()

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0


# test boundary sido count is reasonable scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_sgis_key")
def test_boundary_sido_count_is_reasonable(live_client: Client) -> None:
    """Verify test boundary sido count is reasonable scenario."""
    ds = live_client.dataset("sgis.boundary.sido")
    result = ds.list()

    assert 15 <= len(result.items) <= 20
