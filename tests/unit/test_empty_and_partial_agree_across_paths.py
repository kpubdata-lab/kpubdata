"""An empty answer and a failed later page mean the same on every provider path (#843).

#787 made NODATA an empty result and #789 settled what a failed page leaves behind,
each on the path it was reported for. This holds the four paths that read a
data.go.kr envelope — the spec executor, and the datago, localdata and semas
adapters — to one answer, so a fix on one cannot drift from the others again.
"""

from __future__ import annotations

import json
from collections.abc import Callable

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.dataset import Dataset
from kpubdata.core.executor import SpecDatasetAdapter, SpecExecutor
from kpubdata.core.models import Query, RecordBatch
from kpubdata.exceptions import (
    IncompleteListError,
    InvalidRequestError,
    PublicDataError,
    TransportError,
)
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.providers.localdata.adapter import LocaldataAdapter
from kpubdata.providers.semas.adapter import SemasAdapter
from tests.unit.core.test_executor import FakeResponse, FakeTransport, _golden_spec, _ref

_CONFIG = KPubDataConfig(provider_keys={"datago": "k"})
_SPEC_FILTERS = {"LAWD_CD": "11110", "DEAL_YMD": "202401"}

_Opened = tuple[Dataset, dict[str, str]]


def _legacy(adapter_type: type) -> Callable[[FakeTransport], _Opened]:
    def open_with(transport: FakeTransport) -> _Opened:
        adapter = adapter_type(config=_CONFIG, transport=transport)
        ref = adapter.list_datasets()[0]
        required = ref.raw_metadata.get("required_query_filters") or []
        return Dataset(ref=ref, adapter=adapter), {name: "1" for name in required}

    return open_with


def _spec(transport: FakeTransport) -> _Opened:
    spec = _golden_spec("apt_trade")
    adapter = SpecDatasetAdapter("datago", [spec], SpecExecutor(transport, _CONFIG))
    return Dataset(ref=_ref(spec), adapter=adapter), dict(_SPEC_FILTERS)


_PATHS: dict[str, Callable[[FakeTransport], _Opened]] = {
    "spec": _spec,
    "datago": _legacy(DataGoAdapter),
    "localdata": _legacy(LocaldataAdapter),
    "semas": _legacy(SemasAdapter),
}


def _envelope(code: object, body: object = None) -> dict[str, object]:
    response: dict[str, object] = {"header": {"resultCode": code, "resultMsg": "NODATA_ERROR"}}
    if body is not None:
        response["body"] = body
    return {"response": response}


def _ask(path: str, payload: dict[str, object]) -> RecordBatch:
    transport = FakeTransport([FakeResponse(json.dumps(payload).encode())])
    dataset, filters = _PATHS[path](transport)
    return dataset.list(**filters)


#: Every way the provider says "nothing matched", with the count it implies.
_EMPTY_ANSWERS: dict[str, tuple[dict[str, object], int | None]] = {
    "03 with a count": (_envelope("03", {"totalCount": 0}), 0),
    "03 without a body": (_envelope("03"), None),
    "00 with blank items": (_envelope("00", {"items": "", "totalCount": 0}), 0),
    "00 with no items key": (_envelope("00", {"totalCount": 0}), 0),
    "00 with an empty body": (_envelope("00", {}), None),
}


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("answer", _EMPTY_ANSWERS)
def test_an_empty_answer_is_the_same_empty_batch(path: str, answer: str) -> None:
    payload, total = _EMPTY_ANSWERS[answer]

    batch = _ask(path, payload)

    assert batch.items == []
    assert batch.total_count == total
    assert (batch.next_page, batch.next_cursor) == (None, None)


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("code", ["03", "3", "003", " 03 ", 3])
def test_nodata_is_read_as_the_number_three_however_it_is_written(path: str, code: object) -> None:
    # One path compared the code to "03" and another to the number 3; "3" was an empty
    # result on the datago adapter and a provider error on the other three.
    batch = _ask(path, _envelope(code, {"totalCount": 0}))

    assert (batch.items, batch.total_count, batch.next_page) == ([], 0, None)


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("code", ["00", "000", "0", 0])
def test_success_is_read_as_zero_however_it_is_written(path: str, code: object) -> None:
    batch = _ask(path, _envelope(code, {"totalCount": 0}))

    assert (batch.items, batch.total_count) == ([], 0)


@pytest.mark.parametrize("path", _PATHS)
@pytest.mark.parametrize("code", ["3.0", "30", "13", "", True, None])
def test_a_code_that_is_not_three_is_not_an_empty_result(path: str, code: object) -> None:
    # "30" is an auth failure and the rest a provider error; none is an empty batch.
    with pytest.raises(PublicDataError):
        _ask(path, _envelope(code, {"totalCount": 0}))


class _FailsOnPage(FakeTransport):
    """Three full pages of two rows; the request for ``failing`` does not come back."""

    def __init__(self, failing: int) -> None:
        super().__init__()
        self.failing = failing
        self.sent = 0

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        self.sent += 1
        if self.sent == self.failing:
            raise TransportError("connection reset", provider="datago", status_code=500)
        rows = [{"n": f"{self.sent}-{i}"} for i in range(2)]
        body = {"items": {"item": rows}, "totalCount": 6, "pageNo": self.sent, "numOfRows": 2}
        return FakeResponse(json.dumps(_envelope("00", body)).encode())


def _collect(path: str, failing: int) -> tuple[list[int], int, BaseException | None]:
    transport = _FailsOnPage(failing)
    dataset, filters = _PATHS[path](transport)
    seen: list[int] = []
    try:
        for batch in dataset.list_all(page_size=2, **filters):
            seen.append(len(batch.items))
    except TransportError as error:
        return seen, transport.sent, error
    return seen, transport.sent, None


@pytest.mark.parametrize("path", _PATHS)
def test_a_failed_later_page_raises_and_is_not_an_early_end(path: str) -> None:
    # The error reaches the caller on every path: a short list is never handed back
    # as though the provider had run out of records.
    _, sent, error = _collect(path, failing=2)

    assert isinstance(error, TransportError)
    assert sent == 2  # nothing was asked for after the failure


@pytest.mark.parametrize("path", ["datago", "localdata", "semas"])
def test_an_adapter_path_hands_over_the_pages_read_before_the_failure(path: str) -> None:
    seen, _, error = _collect(path, failing=3)

    assert seen == [2, 2]
    assert isinstance(error, TransportError)


def test_the_spec_path_hands_over_nothing_before_the_failure() -> None:
    # It casts columns over all pages together (#481), so it holds every page until
    # the last is read; a failure leaves the caller with the error alone (#789).
    seen, _, error = _collect("spec", failing=3)

    assert seen == []
    assert isinstance(error, TransportError)


@pytest.mark.parametrize("path", _PATHS)
def test_a_caller_that_stops_early_is_not_charged_for_later_pages(path: str) -> None:
    transport = _FailsOnPage(failing=99)
    dataset, filters = _PATHS[path](transport)

    pages = dataset.list_all(page_size=2, **filters)
    first = next(pages)
    pages.close()

    assert len(first.items) == 2
    # An adapter path has read one page; the spec path reads all three before the first.
    assert transport.sent == (3 if path == "spec" else 1)


@pytest.mark.parametrize("path", _PATHS)
def test_every_page_arrives_when_nothing_fails(path: str) -> None:
    seen, sent, error = _collect(path, failing=99)

    assert error is None
    assert sum(seen) == 6
    assert sent == 3


def test_query_records_agrees_with_list_on_an_empty_answer() -> None:
    spec = _golden_spec("apt_trade")
    transport = FakeTransport([FakeResponse(json.dumps(_envelope("3")).encode())])

    batch = SpecExecutor(transport, _CONFIG).query(spec, _ref(spec), Query(filters=_SPEC_FILTERS))

    assert (batch.items, batch.total_count, batch.next_page) == ([], None, None)


# --- partial=True: keep what was read (#876) ------------------------------------------


def _collect_partial(path: str, failing: int) -> tuple[list[list[str]], int, BaseException | None]:
    transport = _FailsOnPage(failing)
    dataset, filters = _PATHS[path](transport)
    seen: list[list[str]] = []
    try:
        for batch in dataset.list_all(page_size=2, partial=True, **filters):
            seen.append([str(row.get("n", row)) for row in batch.items])
    except PublicDataError as error:
        return seen, transport.sent, error
    return seen, transport.sent, None


@pytest.mark.parametrize("path", _PATHS)
def test_partial_hands_over_the_pages_read_then_says_the_list_is_incomplete(path: str) -> None:
    seen, sent, error = _collect_partial(path, failing=3)

    assert len(seen) == 2
    assert [len(page) for page in seen] == [2, 2]
    assert sent == 3  # nothing was asked for after the failure
    assert isinstance(error, IncompleteListError)
    assert error.pages == 2
    assert isinstance(error.__cause__, TransportError)
    # What a caller judges the failure by travels with it.
    assert (error.provider, error.status_code, error.retryable) == ("datago", 500, True)


@pytest.mark.parametrize("path", _PATHS)
def test_partial_raises_a_failed_first_page_as_it_is(path: str) -> None:
    seen, sent, error = _collect_partial(path, failing=1)

    assert seen == []
    assert sent == 1
    assert type(error) is TransportError


@pytest.mark.parametrize("path", _PATHS)
def test_partial_changes_nothing_when_nothing_fails(path: str) -> None:
    seen, sent, error = _collect_partial(path, failing=99)

    assert error is None
    assert sum(len(page) for page in seen) == 6
    assert sent == 3


def test_without_partial_the_spec_path_still_hands_over_nothing() -> None:
    seen, _, error = _collect("spec", failing=3)

    assert seen == []
    assert type(error) is TransportError


def test_partial_casts_over_the_pages_it_kept() -> None:
    # The casting decision is made from the pages read; the pages yielded carry the
    # report of that decision, as a complete listing's pages do.
    transport = _FailsOnPage(failing=3)
    dataset, filters = _PATHS["spec"](transport)

    batches = []
    with pytest.raises(IncompleteListError):
        for batch in dataset.list_all(page_size=2, partial=True, **filters):
            batches.append(batch)

    assert len(batches) == 2
    assert all("validation_total" in batch.meta for batch in batches)


@pytest.mark.parametrize("value", [1, "yes", None])
def test_partial_must_be_a_boolean(value: object) -> None:
    dataset, filters = _PATHS["spec"](_FailsOnPage(failing=99))

    with pytest.raises(InvalidRequestError, match="partial must be True or False"):
        list(dataset.list_all(partial=value, **filters))  # type: ignore[arg-type]
