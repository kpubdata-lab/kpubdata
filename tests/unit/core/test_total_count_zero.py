"""A provider-reported total of 0 stays 0 (#642).

``coerced if coerced else None`` turned "the result has 0 rows" into "the count is
unknown", and a consumer showing "0 results" could not tell it from "we don't know".
"""

from __future__ import annotations

import pytest

from kpubdata.core.executor import SpecDatasetAdapter, _next_page, extract_total_count
from kpubdata.core.models import Query
from kpubdata.core.spec import SpecDefinition
from tests.unit.core.test_executor import (
    FakeTransport,
    _golden_spec,
    _make_executor,
    _ref,
    _standard_envelope,
)


@pytest.fixture()
def apt_spec() -> SpecDefinition:
    return _golden_spec("apt_trade")


def _envelope_payload(total: object) -> dict[str, object]:
    body: dict[str, object] = {"items": None}
    if total is not None:
        body["totalCount"] = total
    return {"response": {"header": {"resultCode": "00"}, "body": body}}


@pytest.mark.parametrize(("raw", "expected"), [(0, 0), ("0", 0), ("12", 12)])
def test_a_reported_count_is_kept(apt_spec: SpecDefinition, raw: object, expected: int) -> None:
    assert extract_total_count(apt_spec, _envelope_payload(raw)) == expected


@pytest.mark.parametrize("raw", [None, "", "n/a", True])
def test_a_missing_or_unreadable_count_is_unknown(apt_spec: SpecDefinition, raw: object) -> None:
    assert extract_total_count(apt_spec, _envelope_payload(raw)) is None


def test_query_keeps_zero(apt_spec: SpecDefinition) -> None:
    executor = _make_executor(FakeTransport([_standard_envelope(None, total_count=0)]))
    batch = executor.query(apt_spec, _ref(apt_spec), Query())
    assert batch.total_count == 0
    assert batch.next_page is None


def test_list_all_keeps_zero(apt_spec: SpecDefinition) -> None:
    transport = FakeTransport([_standard_envelope(None, total_count=0)])
    adapter = SpecDatasetAdapter("datago", [apt_spec], _make_executor(transport))
    batches = list(adapter.query_records_all(_ref(apt_spec), Query(page_size=2)))
    assert [batch.total_count for batch in batches] == [0]
    assert len(transport.calls) == 1


def test_zero_ends_paging_even_on_a_full_page(apt_spec: SpecDefinition) -> None:
    """The intent is written down: a reported 0 means no next page."""
    assert _next_page(apt_spec, Query(page_size=2), 0, 2) is None
    # Unknown count still falls back to "a full page means there may be more".
    assert _next_page(apt_spec, Query(page_size=2), None, 2) == 2
