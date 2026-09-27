"""KOSIS real API integration tests.

These tests call the live KOSIS API and verify that
the adapter correctly parses actual responses.

Run with:
    export KPUBDATA_KOSIS_API_KEY="your-key"
    uv run pytest -m integration -k kosis -ra -v
"""

from __future__ import annotations

from typing import cast

import pytest

from kpubdata.client import Client
from kpubdata.core.models import RecordBatch

# ---------------------------------------------------------------------------
# Basic connectivity & parsing
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_population_migration_returns_record_batch(live_client: Client) -> None:
    """list() returns a well-formed RecordBatch with items."""
    ds = live_client.dataset("kosis.population_migration")

    result = ds.list(start_date="202401", end_date="202403")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert isinstance(result.items[0], dict)


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_population_migration_raw_returns_list(live_client: Client) -> None:
    """call_raw() returns a list (KOSIS array response)."""
    ds = live_client.dataset("kosis.population_migration")

    result = ds.call_raw(
        "statisticsParameterData",
        startPrdDe="202401",
        endPrdDe="202403",
    )

    assert isinstance(result, list)
    result_list = cast(list[object], result)
    assert len(result_list) > 0


# ---------------------------------------------------------------------------
# Response field structure
# ---------------------------------------------------------------------------

EXPECTED_ITEM_KEYS = {
    "TBL_ID",
    "TBL_NM",
    "ORG_ID",
    "C1_NM",
    "C2_NM",
    "ITM_NM",
    "DT",
    "PRD_DE",
    "PRD_SE",
    "UNIT_NM",
}


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_item_has_required_fields(live_client: Client) -> None:
    """Each record contains the standard KOSIS field set."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202401")

    item = result.items[0]
    assert EXPECTED_ITEM_KEYS.issubset(item.keys())


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_tbl_id_is_correct(live_client: Client) -> None:
    """population_migration dataset returns table ID DT_1B26003_A01."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202401")

    for item in result.items:
        assert item["TBL_ID"] == "DT_1B26003_A01"


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_org_id_is_correct(live_client: Client) -> None:
    """population_migration dataset returns org ID 101 (Statistics Korea)."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202401")

    for item in result.items:
        assert item["ORG_ID"] == "101"


# ---------------------------------------------------------------------------
# total_count & data volume
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_total_count_matches_items(live_client: Client) -> None:
    """total_count should equal the number of returned items."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202401")

    assert result.total_count is not None
    assert result.total_count == len(result.items)


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_multi_month_returns_more_data(live_client: Client) -> None:
    """Querying more months returns proportionally more data."""
    ds = live_client.dataset("kosis.population_migration")

    result_1m = ds.list(start_date="202401", end_date="202401")
    result_3m = ds.list(start_date="202401", end_date="202403")

    assert len(result_3m.items) > len(result_1m.items)


# ---------------------------------------------------------------------------
# Data value sanity
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_dt_is_numeric_string(live_client: Client) -> None:
    """DT (data value) should be a parseable numeric string."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202401")

    for item in result.items[:20]:
        value = str(item["DT"])
        if value != "-":
            _ = int(value.replace(",", ""))


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_prd_de_format(live_client: Client) -> None:
    """PRD_DE (period) should be YYYYMM format matching the queried range."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202403")

    periods = {str(item["PRD_DE"]) for item in result.items}
    assert periods.issubset({"202401", "202402", "202403"})


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_unit_is_person(live_client: Client) -> None:
    """Unit should be person (named) for migration data."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202401")

    units = {str(item["UNIT_NM"]) for item in result.items}
    assert "명" in units


# ---------------------------------------------------------------------------
# Real-world usage patterns
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_usage_nationwide_monthly_migration(live_client: Client) -> None:
    """Realistic usage: extract nationwide total migration by month."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202403")

    nationwide = [
        item
        for item in result.items
        if str(item["C1_NM"]) == "전국"
        and str(item["C2_NM"]) == "전국"
        and str(item["ITM_NM"]) == "이동자수"
    ]

    assert len(nationwide) == 3
    for item in nationwide:
        assert int(str(item["DT"]).replace(",", "")) > 0


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_usage_seoul_migration(live_client: Client) -> None:
    """Realistic usage: find Seoul migration data."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202401")

    seoul_items = [item for item in result.items if str(item["C1_NM"]) == "서울특별시"]

    assert len(seoul_items) > 0


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_usage_net_migration(live_client: Client) -> None:
    """Realistic usage: extract net migration data."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202401")

    net_migration = [item for item in result.items if str(item["ITM_NM"]) == "순이동자수"]

    assert len(net_migration) > 0


@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_usage_region_ranking(live_client: Client) -> None:
    """Realistic usage: rank regions by migration volume."""
    ds = live_client.dataset("kosis.population_migration")
    result = ds.list(start_date="202401", end_date="202401")

    region_totals: dict[str, int] = {}
    for item in result.items:
        region = str(item["C1_NM"])
        itm = str(item["ITM_NM"])
        if region != "전국" and str(item["C2_NM"]) == "전국" and itm == "이동자수":
            region_totals[region] = int(str(item["DT"]).replace(",", ""))

    assert len(region_totals) > 0
    top_region = max(region_totals.items(), key=lambda item: item[1])[0]
    assert isinstance(top_region, str)


# # test industrial production returns record batch scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_kosis_key")
def test_industrial_production_returns_record_batch(live_client: Client) -> None:
    """Verify test industrial production returns record batch scenario."""
    ds = live_client.dataset("kosis.industrial_production")

    result = ds.list(start_date="202401", end_date="202401")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert result.items[0]["TBL_ID"] == "DT_1J22003"
    assert result.items[0]["C1"] == "T10"
    assert result.items[0]["ITM_ID"] == "T"
