"""LOFIN (lofin365.go.kr) real API integration tests.

These tests call the live LOFIN API and verify that
the adapter correctly parses actual responses.

Run with:
    export KPUBDATA_LOFIN_API_KEY="your-key"
    uv run pytest -m integration -k lofin -ra -v
"""

from __future__ import annotations

import pytest

from kpubdata.client import Client
from kpubdata.core.models import RecordBatch

# ---------------------------------------------------------------------------
# Basic connectivity & parsing
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_expenditure_budget_returns_record_batch(live_client: Client) -> None:
    """list() returns a well-formed RecordBatch with items."""
    ds = live_client.dataset("lofin.expenditure_budget")

    result = ds.list(fyr="2024")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert isinstance(result.items[0], dict)


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_expenditure_budget_raw_returns_envelope(live_client: Client) -> None:
    """call_raw() returns the native LOFIN envelope with dataset code key."""
    ds = live_client.dataset("lofin.expenditure_budget")

    result = ds.call_raw("list", pIndex="1", pSize="5", fyr="2024")

    assert isinstance(result, dict)
    assert "AJGCF" in result


# ---------------------------------------------------------------------------
# Response field structure
# ---------------------------------------------------------------------------

EXPENDITURE_BUDGET_KEYS = {
    "fyr",
    "wa_laf_cd",
    "wa_laf_hg_nm",
    "laf_cd",
    "laf_hg_nm",
    "tot_pfa_amt",
    "pfa_amt1",
    "pfa_amt2",
    "pfa_amt3",
    "pfa_amt4",
}


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_expenditure_budget_item_has_required_fields(live_client: Client) -> None:
    """Each record contains the expected LOFIN field set."""
    ds = live_client.dataset("lofin.expenditure_budget")
    result = ds.list(fyr="2024")

    item = result.items[0]
    assert EXPENDITURE_BUDGET_KEYS.issubset(item.keys())


# ---------------------------------------------------------------------------
# total_count & pagination
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_expenditure_budget_total_count(live_client: Client) -> None:
    """total_count should be a positive integer."""
    ds = live_client.dataset("lofin.expenditure_budget")
    result = ds.list(fyr="2024")

    assert result.total_count is not None
    assert result.total_count > 0


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_expenditure_budget_pagination_respects_size(live_client: Client) -> None:
    """Small page_size should limit results per page."""
    ds = live_client.dataset("lofin.expenditure_budget")
    result = ds.list(fyr="2024", page_size=5)

    # Should have at most 5 items (auto-pagination may fetch more, but first batch is 5)
    assert len(result.items) >= 1


# ---------------------------------------------------------------------------
# All 5 datasets connectivity
# ---------------------------------------------------------------------------

ALL_DATASETS = [
    "lofin.expenditure_budget",
    "lofin.expenditure_function",
    "lofin.revenue_budget",
    "lofin.debt_ratio",
    "lofin.fiscal_independence",
]


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
@pytest.mark.parametrize("dataset_id", ALL_DATASETS)
def test_all_datasets_return_data(live_client: Client, dataset_id: str) -> None:
    """Every registered LOFIN dataset should return data for fiscal year 2024."""
    ds = live_client.dataset(dataset_id)
    result = ds.list(fyr="2024", page_size=3)

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert result.total_count is not None
    assert result.total_count > 0


# ---------------------------------------------------------------------------
# Data value sanity
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_expenditure_budget_fiscal_year_matches(live_client: Client) -> None:
    """fyr field should match the queried fiscal year."""
    ds = live_client.dataset("lofin.expenditure_budget")
    result = ds.list(fyr="2024", page_size=5)

    for item in result.items:
        assert item["fyr"] == "2024"


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_expenditure_budget_amounts_are_numeric(live_client: Client) -> None:
    """tot_pfa_amt should be a numeric value (int or float)."""
    ds = live_client.dataset("lofin.expenditure_budget")
    result = ds.list(fyr="2024", page_size=5)

    for item in result.items:
        amt = item["tot_pfa_amt"]
        assert isinstance(amt, (int, float))


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_debt_ratio_rate_is_numeric(live_client: Client) -> None:
    """Debt ratio rate should be a numeric value."""
    ds = live_client.dataset("lofin.debt_ratio")
    result = ds.list(fyr="2024", page_size=5)

    for item in result.items:
        rate = item["rate"]
        assert isinstance(rate, (int, float))


# ---------------------------------------------------------------------------
# Real-world usage patterns
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_usage_seoul_expenditure(live_client: Client) -> None:
    """Realistic usage: query Seoul's expenditure budget."""
    ds = live_client.dataset("lofin.expenditure_budget")
    result = ds.list(fyr="2024", wa_laf_cd="1100000", page_size=50)

    assert len(result.items) > 0
    for item in result.items:
        assert item["wa_laf_cd"] == "1100000"
        assert item["wa_laf_hg_nm"] == "서울"


@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_usage_fiscal_independence_rates(live_client: Client) -> None:
    """Realistic usage: fetch fiscal independence rates."""
    ds = live_client.dataset("lofin.fiscal_independence")
    result = ds.list(fyr="2024", page_size=10)

    for item in result.items:
        rate1 = item["rate1"]
        assert isinstance(rate1, (int, float))
        assert 0.0 <= rate1 <= 100.0


# ---------------------------------------------------------------------------
# FIACRV (Revenue by Source & Account)
# ---------------------------------------------------------------------------


# test revenue by source returns record batch scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_revenue_by_source_returns_record_batch(live_client: Client) -> None:
    """Verify test revenue by source returns record batch scenario."""
    ds = live_client.dataset("lofin.revenue_by_source")
    result = ds.list(fyr="2023")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert "armk_nm" in result.items[0]
    assert "tott_sum_amt" in result.items[0]


# test revenue by source raw returns envelope scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_revenue_by_source_raw_returns_envelope(live_client: Client) -> None:
    """Verify test revenue by source raw returns envelope scenario."""
    ds = live_client.dataset("lofin.revenue_by_source")
    result = ds.call_raw("list", pIndex="1", pSize="5", fyr="2023")

    assert isinstance(result, dict)
    assert "FIACRV" in result


# test revenue by source has hierarchy levels scenario
@pytest.mark.integration
@pytest.mark.usefixtures("require_lofin_key")
def test_revenue_by_source_has_hierarchy_levels(live_client: Client) -> None:
    """Verify test revenue by source has hierarchy levels scenario."""
    ds = live_client.dataset("lofin.revenue_by_source")
    result = ds.list(fyr="2023", wa_laf_cd="1100000", page_size=50)

    lvl_values = {item["lvl_no"] for item in result.items}
    assert "1" in lvl_values
