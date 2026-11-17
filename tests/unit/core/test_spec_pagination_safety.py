"""Regression tests for safety checks on spec-backed pagination (#965)."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kpubdata.core.dataset import Dataset
from kpubdata.core.executor import SpecDatasetAdapter
from kpubdata.core.models import Query, RecordBatch
from kpubdata.core.spec import SpecDefinition
from kpubdata.exceptions import InvalidRequestError
from tests.unit.core.test_executor import (
    FakeResponse,
    FakeTransport,
    _golden_spec,
    _make_executor,
    _ref,
    _standard_envelope,
)


def _rows(start: int, count: int) -> list[dict[str, object]]:
    return [{"aptNm": f"apt-{n}", "aptDong": str(n)} for n in range(start, start + count)]


def _adapter(
    spec: SpecDefinition, responses: list[FakeResponse]
) -> tuple[SpecDatasetAdapter, FakeTransport]:
    transport = FakeTransport(responses)
    return SpecDatasetAdapter("datago", [spec], _make_executor(transport)), transport


def test_none_pagination_stops_after_one_full_page() -> None:
    """A complete first page never implies another call for a non-paged API."""
    base = _golden_spec("apt_trade")
    spec = replace(base, pagination=replace(base.pagination, type="none"))
    adapter, transport = _adapter(spec, [_standard_envelope(_rows(0, 2), total_count=500)])
    batches = list(
        Dataset(_ref(spec), adapter).list_all(LAWD_CD="11680", DEAL_YMD="202401", page_size=2)
    )

    assert len(batches) == 1
    assert len(batches[0].items) == 2
    assert batches[0].next_page is None
    assert len(transport.calls) == 1


def test_single_query_none_pagination_has_no_next_page() -> None:
    """The single-page public query uses the same paging policy as list_all."""
    base = _golden_spec("apt_trade")
    spec = replace(base, pagination=replace(base.pagination, type="none"))
    adapter, transport = _adapter(spec, [_standard_envelope(_rows(0, 2), total_count=500)])

    result = adapter.query_records(
        _ref(spec), Query(filters={"LAWD_CD": "11680", "DEAL_YMD": "202401"}, page_size=2)
    )
    assert result.next_page is None
    assert len(transport.calls) == 1


@pytest.mark.parametrize("partial", [False, True])
def test_repeated_nonempty_page_fails_without_returning_duplicate(partial: bool) -> None:
    """A provider ignoring pageNo must not silently produce repeated records."""
    spec = _golden_spec("apt_trade")
    repeated = _rows(0, 2)
    adapter, transport = _adapter(
        spec,
        [
            _standard_envelope(repeated, total_count=500),
            _standard_envelope(repeated, total_count=500),
        ],
    )
    already_yielded: list[RecordBatch] = []

    with pytest.raises(InvalidRequestError, match="Detected repeated page"):
        for batch in Dataset(_ref(spec), adapter).list_all(
            LAWD_CD="11680", DEAL_YMD="202401", page_size=2, partial=partial
        ):
            already_yielded.append(batch)

    assert len(transport.calls) == 2
    # Default mode retains the existing all-or-nothing casting contract.
    assert len(already_yielded) == (1 if partial else 0)
    if partial:
        assert already_yielded[0].items[0]["aptNm"] == "apt-0"


def test_three_empty_pages_with_advertised_total_fail_safely() -> None:
    """An inconsistent total count cannot make us spend the full API quota."""
    spec = _golden_spec("apt_trade")
    adapter, transport = _adapter(
        spec,
        [_standard_envelope(None, total_count=500) for _ in range(3)],
    )

    with pytest.raises(InvalidRequestError, match="3 consecutive empty pages"):
        list(Dataset(_ref(spec), adapter).list_all(LAWD_CD="11680", DEAL_YMD="202401", page_size=2))

    assert len(transport.calls) == 3


def test_distinct_pages_still_yield_in_order() -> None:
    """The safety guard cannot reject legitimate different pages."""
    spec = _golden_spec("apt_trade")
    adapter, transport = _adapter(
        spec,
        [
            _standard_envelope(_rows(0, 2), total_count=4),
            _standard_envelope(_rows(2, 2), total_count=4),
        ],
    )

    batches = list(
        Dataset(_ref(spec), adapter).list_all(LAWD_CD="11680", DEAL_YMD="202401", page_size=2)
    )
    assert len(transport.calls) == 2
    assert [row["aptNm"] for batch in batches for row in batch.items] == [
        "apt-0",
        "apt-1",
        "apt-2",
        "apt-3",
    ]
