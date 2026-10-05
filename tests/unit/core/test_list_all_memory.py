"""``list_all`` on a spec dataset holds one page in memory, not the result (#789).

Global casting (#481) needs every page before any can be cast, and the pages used to
wait in a list: memory grew with the row count. They now wait on disk. These measure
that, pin that the result is what it was, and pin what a failing page does.
"""

from __future__ import annotations

import gc
import tracemalloc

import pytest

from kpubdata.core.executor import SpecDatasetAdapter, _CastingDecision, _PageSpool
from kpubdata.core.models import Query
from kpubdata.core.spec import SpecDefinition
from kpubdata.exceptions import TransportError
from tests.unit.core.test_executor import (
    FakeResponse,
    FakeTransport,
    _golden_spec,
    _make_executor,
    _ref,
    _standard_envelope,
)

_PAGE_SIZE = 500


class _LazyTransport(FakeTransport):
    """Builds each page when it is asked for, so the test holds no result itself."""

    def __init__(self, pages: int, *, fail_on: int | None = None) -> None:
        super().__init__()
        self._pages = pages
        self._fail_on = fail_on
        self.requests = 0

    def request(self, method: str, url: str, **_kwargs: object) -> FakeResponse:
        self.requests += 1
        if self._fail_on == self.requests:
            raise TransportError("boom", provider="datago", status_code=500)
        start = (self.requests - 1) * _PAGE_SIZE
        rows: list[dict[str, object]] = [
            {"aptNm": f"apt-{index}", "dealAmount": str(index), "excluUseAr": "84.9"}
            for index in range(start, start + _PAGE_SIZE)
        ]
        return _standard_envelope(rows, total_count=self._pages * _PAGE_SIZE)


@pytest.fixture()
def apt_spec() -> SpecDefinition:
    return _golden_spec("apt_trade")


def _peak_bytes(spec: SpecDefinition, pages: int) -> tuple[int, int]:
    """Peak traced memory while every batch is consumed and dropped, and the row count."""
    transport = _LazyTransport(pages)
    adapter = SpecDatasetAdapter("datago", [spec], _make_executor(transport))
    gc.collect()
    tracemalloc.start()
    try:
        rows = 0
        for batch in adapter.query_records_all(_ref(spec), Query(page_size=_PAGE_SIZE)):
            rows += len(batch.items)
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return peak, rows


def test_memory_follows_the_page_size_not_the_row_count(apt_spec: SpecDefinition) -> None:
    small_peak, small_rows = _peak_bytes(apt_spec, pages=4)
    large_peak, large_rows = _peak_bytes(apt_spec, pages=40)

    assert (small_rows, large_rows) == (4 * _PAGE_SIZE, 40 * _PAGE_SIZE)
    # Ten times the rows. Held in memory, the peak was ten times as high; one page at a
    # time it barely moves. The bound leaves room for allocator noise.
    assert large_peak < small_peak * 2.5, (small_peak, large_peak)


def test_a_failing_page_yields_nothing_and_raises(apt_spec: SpecDefinition) -> None:
    """Pages 1 and 2 were fetched; page 3 fails; no batch comes out (#789)."""
    transport = _LazyTransport(5, fail_on=3)
    adapter = SpecDatasetAdapter("datago", [apt_spec], _make_executor(transport))
    seen: list[int] = []

    with pytest.raises(TransportError, match="boom"):
        for batch in adapter.query_records_all(_ref(apt_spec), Query(page_size=_PAGE_SIZE)):
            seen.append(len(batch.items))

    assert seen == []
    assert transport.requests == 3


def test_the_decision_made_from_evidence_equals_the_one_made_from_all_rows(
    apt_spec: SpecDefinition,
) -> None:
    """A dirty value on the last page leaves the column uncast on every page."""
    from kpubdata.core.executor import SpecExecutor

    pages = [
        [{"aptNm": "a", "dealAmount": "100"}, {"aptNm": "b", "dealAmount": "200"}],
        [{"aptNm": "c", "dealAmount": "300"}],
        [{"aptNm": "d", "dealAmount": "not-a-number"}],
    ]
    together = [dict(row) for page in pages for row in page]
    expected_rows, expected_report = SpecExecutor._finalize_casting(apt_spec, together)

    decision = _CastingDecision(apt_spec)
    copies = [[dict(row) for row in page] for page in pages]
    for page in copies:
        decision.observe(page)
    for page in copies:
        decision.apply(page)

    assert [row for page in copies for row in page] == expected_rows
    assert decision.report() == expected_report


def test_a_spooled_page_comes_back_as_it_went_in() -> None:
    from kpubdata.core.executor import _FetchedPage

    page = _FetchedPage(
        staged=[
            {"a": "01", "n": 1, "f": 1.5, "none": None, "nested": {"k": ["v", 2]}, "한글": "값"}
        ],
        payload={"response": {"body": {"items": [1, 2]}}},
        provenance={"url": "https://example.test", "cached": False},
        next_page=2,
    )
    unserialisable = _FetchedPage([{"v": object()}], {}, {}, None)
    spool = _PageSpool()
    try:
        spool.append(page)
        spool.append(unserialisable)
        first, second = list(spool)
    finally:
        spool.close()

    assert first == page
    # A page JSON cannot hold is kept as it is rather than altered.
    assert second is unserialisable


# --- A lone surrogate in a page (#804) ---

#: What a broken character in a provider's text decodes to: half of a surrogate pair.
#: ``json.dumps(..., ensure_ascii=False)`` passes it through, and strict UTF-8 refuses it.
_LONE = "\ud800"


def test_a_spooled_page_with_a_lone_surrogate_comes_back_as_it_went_in() -> None:
    from kpubdata.core.executor import _FetchedPage

    page = _FetchedPage(
        staged=[{"name": f"broken{_LONE}name", _LONE: "as a key too"}],
        payload={"raw": f"<v>{_LONE}</v>"},
        provenance={"url": "https://example.test"},
        next_page=None,
    )
    after = _FetchedPage([{"name": "한글"}], {}, {}, None)
    spool = _PageSpool()
    try:
        spool.append(page)
        spool.append(after)
        first, second = list(spool)
    finally:
        spool.close()

    assert first == page
    # The page after it is read from where it was written.
    assert second == after


class _SurrogateTransport(FakeTransport):
    """Two pages; the first row of the first page holds a lone surrogate."""

    def __init__(self) -> None:
        super().__init__()
        self.requests = 0

    def request(self, method: str, url: str, **_kwargs: object) -> FakeResponse:
        self.requests += 1
        rows: list[dict[str, object]] = [
            {
                "aptNm": f"apt{_LONE}{self.requests}-{index}",
                "dealAmount": str(index),
                "excluUseAr": "84.9",
            }
            for index in range(2)
        ]
        return _standard_envelope(rows, total_count=4)


def test_list_all_returns_rows_holding_a_lone_surrogate_unchanged(apt_spec: SpecDefinition) -> None:
    transport = _SurrogateTransport()
    adapter = SpecDatasetAdapter("datago", [apt_spec], _make_executor(transport))

    batches = list(adapter.query_records_all(_ref(apt_spec), Query(page_size=2)))

    assert transport.requests == 2
    names = [str(row["aptNm"]) for batch in batches for row in batch.items]
    assert names == [f"apt{_LONE}1-0", f"apt{_LONE}1-1", f"apt{_LONE}2-0", f"apt{_LONE}2-1"]
