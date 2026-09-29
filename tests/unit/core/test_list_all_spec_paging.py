"""The spec ``list_all`` path honours page_size, max_size and max_pages (#614).

``Dataset.list_all`` hands spec-backed datasets to
``SpecDatasetAdapter.query_records_all`` so that casting can be decided across
every page at once (#481). These tests pin the five defects that path had:

1. it was eager and undocumented about buffering,
2. ``page_size`` went out as a raw request parameter,
3. hitting ``max_pages`` truncated silently,
4. ``page_size > max_size`` ended the walk early,
5. per-page ``raw``/``meta``/``next_page``/``validation`` were dropped.

The ``Dataset`` is built directly on the adapter; the ``Client`` path is covered in
``test_list_all_client_path.py`` (#611).
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from kpubdata.core.dataset import Dataset
from kpubdata.core.executor import SpecDatasetAdapter
from kpubdata.core.models import Query
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
    return [{"aptNm": f"apt-{i}", "aptDong": str(i)} for i in range(start, start + count)]


def _adapter(
    spec: SpecDefinition, responses: list[FakeResponse]
) -> tuple[SpecDatasetAdapter, FakeTransport]:
    transport = FakeTransport(responses)
    return SpecDatasetAdapter("datago", [spec], _make_executor(transport)), transport


@pytest.fixture()
def apt_spec() -> SpecDefinition:
    return _golden_spec("apt_trade")


def test_buffering_is_lazy_and_bounded_by_max_pages(apt_spec: SpecDefinition) -> None:
    """Case 1: the path buffers by design, but only on iteration and at most max_pages.

    Streaming is impossible while casting is decided over the whole result, so
    the documented contract is: nothing is requested until iteration starts,
    and then every page (never more than ``max_pages``) is held before the
    first batch comes out.
    """
    adapter, transport = _adapter(
        apt_spec,
        [
            _standard_envelope(_rows(0, 2), total_count=6),
            _standard_envelope(_rows(2, 2), total_count=6),
            _standard_envelope(_rows(4, 2), total_count=6),
        ],
    )

    batches = adapter.query_records_all(_ref(apt_spec), Query(page_size=2), max_pages=5)
    assert transport.calls == []

    first = next(iter(batches))
    assert len(transport.calls) == 3
    assert [item["aptNm"] for item in first.items] == ["apt-0", "apt-1"]
    assert [len(batch.items) for batch in batches] == [2, 2]


def test_page_size_drives_paging_instead_of_being_a_filter(apt_spec: SpecDefinition) -> None:
    """Case 2: page_size reaches numOfRows, never the request as ``page_size``."""
    adapter, transport = _adapter(
        apt_spec,
        [
            _standard_envelope(_rows(0, 2), total_count=4),
            _standard_envelope(_rows(2, 2), total_count=4),
        ],
    )
    dataset = Dataset(_ref(apt_spec), adapter)

    batches = list(dataset.list_all(page_size=2, LAWD_CD="11680"))

    assert [len(batch.items) for batch in batches] == [2, 2]
    sent = [call["params"] for call in transport.calls]
    for params in sent:
        assert isinstance(params, dict)
        assert "page_size" not in params
        assert params["numOfRows"] == "2"
        assert params["LAWD_CD"] == "11680"
    assert [params["pageNo"] for params in sent] == ["1", "2"]  # type: ignore[index]


def test_max_pages_raises_like_the_legacy_path(apt_spec: SpecDefinition) -> None:
    """Case 3: more pages than max_pages raises InvalidRequestError, not a silent cut."""
    adapter, transport = _adapter(
        apt_spec,
        [
            _standard_envelope(_rows(0, 2), total_count=10),
            _standard_envelope(_rows(2, 2), total_count=10),
        ],
    )
    dataset = Dataset(_ref(apt_spec), adapter)

    received = []
    with pytest.raises(InvalidRequestError, match="Pagination limit exceeded"):
        for batch in dataset.list_all(max_pages=2, page_size=2):
            received.append(batch)

    # As in the legacy path, the pages already fetched are yielded first.
    assert [len(batch.items) for batch in received] == [2, 2]
    assert len(transport.calls) == 2


def test_page_size_above_max_size_is_capped_for_has_next(apt_spec: SpecDefinition) -> None:
    """Case 4: the next-page decision uses the capped size the request actually used."""
    spec = replace(apt_spec, pagination=replace(apt_spec.pagination, max_size=2))
    adapter, transport = _adapter(
        spec,
        [
            _standard_envelope(_rows(0, 2), total_count=5),
            _standard_envelope(_rows(2, 2), total_count=5),
            _standard_envelope(_rows(4, 1), total_count=5),
        ],
    )

    batches = list(adapter.query_records_all(_ref(spec), Query(page_size=5)))

    assert sum(len(batch.items) for batch in batches) == 5
    assert [call["params"]["numOfRows"] for call in transport.calls] == ["2", "2", "2"]  # type: ignore[index]


def test_each_batch_keeps_its_own_page_metadata(apt_spec: SpecDefinition) -> None:
    """Case 5: raw, provenance, next_page and validation are per page, plus a total."""
    page_one = _rows(0, 2)
    page_two = [{"aptNm": "apt-2", "aptDong": "A-dong"}, {"aptNm": "apt-3", "aptDong": "3"}]
    adapter, _ = _adapter(
        apt_spec,
        [
            _standard_envelope(page_one, total_count=4),
            _standard_envelope(page_two, total_count=4),
        ],
    )

    first, second = adapter.query_records_all(_ref(apt_spec), Query(page_size=2))

    assert first.next_page == 2
    assert second.next_page is None

    assert first.raw is not None and second.raw is not None
    assert first.raw != second.raw
    assert first.raw["response"]["body"]["items"]["item"] == page_one  # type: ignore[index]

    assert first.meta["provenance"]
    assert second.meta["provenance"]

    # Casting is still decided globally: page two cannot cast aptDong, so page
    # one keeps strings too (#481).
    assert first.items[0]["aptDong"] == "0"

    # Page one's own rows have no problem; page two's do; the total says why the
    # column stayed uncast everywhere.
    assert not first.validation.issues_of("uncastable")
    assert second.validation.issues_of("uncastable")
    total = first.meta["validation_total"]
    assert total is second.meta["validation_total"]
    assert total.issues_of("uncastable")  # type: ignore[attr-defined]
