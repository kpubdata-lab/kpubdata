"""BOK ECOS real API integration tests.

These tests call the live BOK ECOS API and verify that
the adapter correctly parses actual responses.

Run with:
    export KPUBDATA_BOK_API_KEY="your-key"
    uv run pytest -m integration -k bok -ra -v
"""

from __future__ import annotations

import pytest

from kpubdata.client import Client
from kpubdata.core.models import RecordBatch

# ---------------------------------------------------------------------------
# Basic connectivity & parsing
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_base_rate_returns_record_batch(live_client: Client) -> None:
    """list() returns a well-formed RecordBatch with items."""
    ds = live_client.dataset("bok.base_rate")

    result = ds.list(start_date="202401", end_date="202412")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert isinstance(result.items[0], dict)


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_base_rate_raw_returns_envelope(live_client: Client) -> None:
    """call_raw() returns the native BOK envelope with StatisticSearch key."""
    ds = live_client.dataset("bok.base_rate")

    result = ds.call_raw("StatisticSearch", start_date="202401", end_date="202412")

    assert isinstance(result, dict)
    assert "StatisticSearch" in result


# ---------------------------------------------------------------------------
# Response field structure
# ---------------------------------------------------------------------------

EXPECTED_ITEM_KEYS = {
    "STAT_CODE",
    "STAT_NAME",
    "ITEM_CODE1",
    "ITEM_NAME1",
    "UNIT_NAME",
    "TIME",
    "DATA_VALUE",
}


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_base_rate_item_has_required_fields(live_client: Client) -> None:
    """Each record contains the standard BOK ECOS field set."""
    ds = live_client.dataset("bok.base_rate")
    result = ds.list(start_date="202401", end_date="202412")

    item = result.items[0]
    assert EXPECTED_ITEM_KEYS.issubset(item.keys())


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_base_rate_stat_code_is_correct(live_client: Client) -> None:
    """base_rate dataset returns stat code 722Y001."""
    ds = live_client.dataset("bok.base_rate")
    result = ds.list(start_date="202401", end_date="202412")

    for item in result.items:
        assert item["STAT_CODE"] == "722Y001"


# ---------------------------------------------------------------------------
# total_count & pagination
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_base_rate_total_count_matches_items(live_client: Client) -> None:
    """total_count should equal the number of returned items for a full fetch."""
    ds = live_client.dataset("bok.base_rate")
    result = ds.list(start_date="202401", end_date="202412")

    assert result.total_count is not None
    assert result.total_count == len(result.items)


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_base_rate_monthly_count(live_client: Client) -> None:
    """12-month range should return 12 monthly records."""
    ds = live_client.dataset("bok.base_rate")
    result = ds.list(start_date="202401", end_date="202412")

    assert len(result.items) == 12


# ---------------------------------------------------------------------------
# Data value sanity
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_base_rate_data_value_is_numeric_string(live_client: Client) -> None:
    """DATA_VALUE should be a parseable numeric string."""
    ds = live_client.dataset("bok.base_rate")
    result = ds.list(start_date="202401", end_date="202412")

    for item in result.items:
        value = item["DATA_VALUE"]
        assert isinstance(value, str)
        _ = float(value)


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_base_rate_time_format(live_client: Client) -> None:
    """TIME field should be YYYYMM format matching the queried range."""
    ds = live_client.dataset("bok.base_rate")
    result = ds.list(start_date="202401", end_date="202412")

    times = [str(item["TIME"]) for item in result.items]
    for t in times:
        assert len(t) == 6
        assert t.startswith("2024")


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_base_rate_reasonable_range(live_client: Client) -> None:
    """Base rate should be between 0% and 20% (sanity check)."""
    ds = live_client.dataset("bok.base_rate")
    result = ds.list(start_date="202401", end_date="202412")

    for item in result.items:
        rate = float(str(item["DATA_VALUE"]))
        assert 0.0 <= rate <= 20.0


# ---------------------------------------------------------------------------
# Real-world usage patterns
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_usage_print_monthly_rates(live_client: Client) -> None:
    """Realistic usage: fetch and format monthly base rate table."""
    ds = live_client.dataset("bok.base_rate")
    result = ds.list(start_date="202401", end_date="202406")

    rows: list[tuple[str, str]] = []
    for item in result.items:
        period = str(item["TIME"])
        rate = str(item["DATA_VALUE"])
        rows.append((period, rate))

    assert len(rows) == 6
    assert all(len(period) == 6 for period, _ in rows)
    assert all(float(rate) > 0 for _, rate in rows)


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_usage_detect_rate_change(live_client: Client) -> None:
    """Realistic usage: detect whether base rate changed in a period."""
    ds = live_client.dataset("bok.base_rate")
    result = ds.list(start_date="202401", end_date="202412")

    rates = [float(str(item["DATA_VALUE"])) for item in result.items]
    unique_rates = set(rates)

    # Either stable or changed — both valid, but must be non-empty
    assert len(unique_rates) >= 1


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_usage_compare_year_over_year(live_client: Client) -> None:
    """Realistic usage: compare base rate between two different years."""
    ds = live_client.dataset("bok.base_rate")

    result_2023 = ds.list(start_date="202301", end_date="202312")
    result_2024 = ds.list(start_date="202401", end_date="202412")

    assert len(result_2023.items) == 12
    assert len(result_2024.items) == 12

    avg_2023 = sum(float(str(i["DATA_VALUE"])) for i in result_2023.items) / 12
    avg_2024 = sum(float(str(i["DATA_VALUE"])) for i in result_2024.items) / 12

    # Both should be valid positive rates
    assert avg_2023 > 0
    assert avg_2024 > 0


@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_usage_single_month_query(live_client: Client) -> None:
    """Realistic usage: query a single specific month."""
    ds = live_client.dataset("bok.base_rate")
    result = ds.list(start_date="202406", end_date="202406")

    assert len(result.items) == 1
    assert str(result.items[0]["TIME"]) == "202406"


# test usd krw daily returns record batch scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_usd_krw_daily_returns_record_batch(live_client: Client) -> None:
    """Verify test usd krw daily returns record batch scenario."""
    ds = live_client.dataset("bok.usd_krw")

    result = ds.list(start_date="20240101", end_date="20240105", frequency="D")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0


# test bond yield 3y daily returns record batch scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_bok_key")
def test_bond_yield_3y_daily_returns_record_batch(live_client: Client) -> None:
    """Verify test bond yield 3y daily returns record batch scenario."""
    ds = live_client.dataset("bok.bond_yield_3y")

    result = ds.list(start_date="20240102", end_date="20240108", frequency="D")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
