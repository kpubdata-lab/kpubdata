"""KIPRIS asks for the page it means, and stops when there is no next one (#837).

The adapter worked out ``next_page`` and never sent a page number: every "next page" was
the same request. A full first page made ``list_all`` fetch it again and again, up to its
page limit, and hand back the same rows each time.

Whether the provider's service pages at all has **not** been checked against the real
API. These tests therefore cover both a provider that honours ``pageNo`` and one that
ignores it and answers page 1 whatever is asked.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import cast
from urllib.parse import parse_qs, urlsplit

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.dataset import Dataset
from kpubdata.core.models import Query
from kpubdata.exceptions import InvalidRequestError
from kpubdata.providers.kipris.adapter import KiprisAdapter
from kpubdata.transport.http import HttpTransport
from tests.unit.providers.datago.conftest import FakeResponse

#: (page asked for, rows asked for) -> the envelope to answer with.
Provider = Callable[[int, int], dict[str, object]]


def _envelope(rows: list[int], *, page: int | None) -> dict[str, object]:
    """An envelope holding ``rows`` (as family ids); ``page`` is the ``pageNo`` it echoes."""
    body: dict[str, object] = {
        "items": {"item": [{"docdbFamilyID": str(row)} for row in rows]} if rows else "",
        "numOfRows": 100,
    }
    if page is not None:
        body["pageNo"] = page
    header = {"resultCode": "00", "resultMsg": "NORMAL SERVICE."}
    return {"response": {"header": header, "body": body}}


def _paging(total: int) -> Provider:
    """A provider that honours ``pageNo``/``numOfRows`` over ``total`` rows."""

    def answer(page: int, size: int) -> dict[str, object]:
        start = (page - 1) * size
        return _envelope(list(range(start, min(start + size, total))), page=page)

    return answer


def _ignoring_page(total: int, *, echo: bool = True) -> Provider:
    """A provider that answers its first page whatever page is asked for."""

    def answer(_page: int, size: int) -> dict[str, object]:
        return _envelope(list(range(min(size, total))), page=1 if echo else None)

    return answer


class _Transport:
    def __init__(self, provider: Provider) -> None:
        self._provider = provider
        self.asked: list[tuple[int, int]] = []

    def request(self, method: str, url: str, **_kwargs: object) -> FakeResponse:
        query = parse_qs(urlsplit(url).query)
        page, size = int(query["pageNo"][0]), int(query["numOfRows"][0])
        self.asked.append((page, size))
        return FakeResponse(json.dumps(self._provider(page, size)).encode("utf-8"))


def _dataset(provider: Provider) -> tuple[Dataset, _Transport, KiprisAdapter]:
    transport = _Transport(provider)
    adapter = KiprisAdapter(
        config=KPubDataConfig(provider_keys={"kipris": "placeholder"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    ref = adapter.get_dataset("patent_family")
    return Dataset(ref=ref, adapter=adapter), transport, adapter


def _ids(dataset: Dataset, page_size: int | None = None) -> list[str]:
    number = "1020050082226"
    batches = (
        dataset.list_all(applicationNumber=number)
        if page_size is None
        else dataset.list_all(applicationNumber=number, page_size=page_size)
    )
    return [str(item["docdbFamilyID"]) for batch in batches for item in batch.items]


def test_the_page_and_the_page_size_are_sent() -> None:
    _dataset_, transport, adapter = _dataset(_paging(5))
    ref = adapter.get_dataset("patent_family")

    adapter.query_records(ref, Query(filters={"applicationNumber": "1"}, page=3, page_size=20))

    assert transport.asked == [(3, 20)]


def test_a_page_size_over_the_limit_is_sent_as_the_limit() -> None:
    _dataset_, transport, adapter = _dataset(_paging(5))
    ref = adapter.get_dataset("patent_family")

    adapter.query_records(ref, Query(filters={"applicationNumber": "1"}, page_size=500))

    assert transport.asked == [(1, 100)]


@pytest.mark.parametrize(
    ("total", "requests"),
    [
        (0, [(1, 100)]),
        (99, [(1, 100)]),
        # Exactly one full page: the next one has to be asked for to learn it is empty.
        (100, [(1, 100), (2, 100)]),
        (101, [(1, 100), (2, 100)]),
        (250, [(1, 100), (2, 100), (3, 100)]),
    ],
)
def test_a_provider_that_pages_is_read_to_its_end_once(
    total: int, requests: list[tuple[int, int]]
) -> None:
    dataset, transport, _adapter = _dataset(_paging(total))

    ids = _ids(dataset)

    assert ids == [str(row) for row in range(total)]
    assert transport.asked == requests


def test_the_callers_page_size_is_the_one_sent_on_every_page() -> None:
    dataset, transport, _adapter = _dataset(_paging(5))

    assert _ids(dataset, page_size=2) == ["0", "1", "2", "3", "4"]
    assert transport.asked == [(1, 2), (2, 2), (3, 2)]


def test_a_provider_that_ignores_the_page_is_read_once_not_until_the_limit() -> None:
    """It answers page 1 again and says so in ``pageNo``: that is not page 2."""
    dataset, transport, _adapter = _dataset(_ignoring_page(100))

    ids = _ids(dataset)

    assert ids == [str(row) for row in range(100)]
    assert transport.asked == [(1, 100), (2, 100)]


def test_a_page_the_provider_did_not_answer_holds_no_rows() -> None:
    _dataset_, _transport, adapter = _dataset(_ignoring_page(100))
    ref = adapter.get_dataset("patent_family")

    batch = adapter.query_records(ref, Query(filters={"applicationNumber": "1"}, page=2))

    assert (batch.items, batch.next_page) == ([], None)
    # "There is no page 2" is not "there are no rows": page 1 held a hundred.
    assert batch.total_count is None


def test_the_same_rows_twice_stop_list_all_when_the_envelope_names_no_page() -> None:
    """Without a ``pageNo`` to check, the repeat is caught where the pages are read."""
    dataset, transport, _adapter = _dataset(_ignoring_page(100, echo=False))

    with pytest.raises(InvalidRequestError, match="repeated page"):
        _ids(dataset)

    # Two requests, not the 1,000 the page limit allows.
    assert transport.asked == [(1, 100), (2, 100)]


def test_an_empty_page_after_a_full_one_does_not_report_zero_rows() -> None:
    """Now that the page is sent, an empty answer can be a later page (#827, #837)."""
    _dataset_, _transport, adapter = _dataset(_paging(100))
    ref = adapter.get_dataset("patent_family")

    first = adapter.query_records(ref, Query(filters={"applicationNumber": "1"}, page=1))
    second = adapter.query_records(ref, Query(filters={"applicationNumber": "1"}, page=2))

    assert (len(first.items), first.total_count, first.next_page) == (100, None, 2)
    assert (second.items, second.total_count, second.next_page) == ([], None, None)


def test_only_an_empty_first_page_reports_zero_rows() -> None:
    _dataset_, _transport, adapter = _dataset(_paging(0))
    ref = adapter.get_dataset("patent_family")

    first = adapter.query_records(ref, Query(filters={"applicationNumber": "1"}))
    later = adapter.query_records(ref, Query(filters={"applicationNumber": "1"}, page=3))

    assert (first.items, first.total_count) == ([], 0)
    assert (later.items, later.total_count) == ([], None)
