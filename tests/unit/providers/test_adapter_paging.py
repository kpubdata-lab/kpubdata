"""Adapters page the way the provider does, so ``list_all`` neither loses nor repeats rows.

Each test drives the public ``Client().dataset(id)`` path against a fake server that
serves row windows in the provider's response shape and, like the real service, cuts a
page at the catalogue's declared ``max_page_size``. ``HttpTransport.request`` is
replaced on the class, so no request can reach the network.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from urllib.parse import parse_qs, urlsplit

import pytest

from kpubdata import Client
from kpubdata.exceptions import InvalidRequestError
from kpubdata.transport.http import HttpTransport

Row = dict[str, object]
Shape = Callable[[list[Row], int | None], object]


class _Resp:
    def __init__(self, payload: object) -> None:
        self.content = json.dumps(payload, ensure_ascii=False).encode()
        self.status_code = 200
        self.headers = {"content-type": "application/json"}
        self.text = self.content.decode()


class _Server:
    """Serves ``total`` rows, never more than ``cap`` per request."""

    def __init__(
        self,
        *,
        total: int,
        cap: int,
        window: Callable[[str], tuple[int, int]],
        shape: Shape,
        send_total: bool = True,
    ) -> None:
        self.rows: list[Row] = [{"ID": str(n)} for n in range(1, total + 1)]
        self.cap = cap
        self.window = window
        self.shape = shape
        self.send_total = send_total
        self.urls: list[str] = []

    def request(self, method: str, url: str, **kwargs: object) -> _Resp:
        params = kwargs.get("params")
        if isinstance(params, dict) and params:
            url = f"{url}?" + "&".join(f"{k}={v}" for k, v in params.items())
        self.urls.append(url)
        start, size = self.window(url)
        size = min(size, self.cap)
        chunk = self.rows[start : start + size]
        return _Resp(self.shape(chunk, len(self.rows) if self.send_total else None))


@pytest.fixture
def serve(monkeypatch: pytest.MonkeyPatch) -> Iterator[Callable[[_Server], None]]:
    def install(server: _Server) -> None:
        def fake(_self: HttpTransport, method: str, url: str, **kwargs: object) -> _Resp:
            return server.request(method, url, **kwargs)

        monkeypatch.setattr(HttpTransport, "request", fake)

    def refuse(_self: HttpTransport, method: str, url: str, **kwargs: object) -> object:
        raise AssertionError(f"unexpected network request: {url}")

    monkeypatch.setattr(HttpTransport, "request", refuse)
    yield install


def _client(*providers: str) -> Client:
    return Client(provider_keys={name: "K" for name in providers}, env_keys=False)


def _query(url: str) -> dict[str, str]:
    return {k: v[0] for k, v in parse_qs(urlsplit(url).query).items()}


def _page_window(page_key: str, size_key: str) -> Callable[[str], tuple[int, int]]:
    def window(url: str) -> tuple[int, int]:
        q = _query(url)
        page, size = int(q[page_key]), int(q[size_key])
        return (page - 1) * size, size

    return window


def _datago_shape(rows: list[Row], total: int | None) -> object:
    body: dict[str, object] = {"items": {"item": rows}}
    if total is not None:
        body["totalCount"] = total
    return {"response": {"header": {"resultCode": "00", "resultMsg": "OK"}, "body": body}}


def _ids(client: Client, dataset_id: str, **kwargs: object) -> list[str]:
    batches = client.dataset(dataset_id).list_all(**kwargs)
    return [str(row["ID"]) for batch in batches for row in batch.items]


# 1. A page size above the declared maximum is cut to it, so no row is skipped.


@pytest.mark.parametrize(
    ("dataset_id", "cap"),
    [("localdata.clinic", 100), ("datago.dur_product_info", 1000), ("semas.zone_one", 99999)],
)
def test_datago_family_caps_page_size(
    serve: Callable[[_Server], None], dataset_id: str, cap: int
) -> None:
    server = _Server(
        total=cap * 2 + 50,
        cap=cap,
        window=_page_window("pageNo", "numOfRows"),
        shape=_datago_shape,
    )
    serve(server)
    client = _client("datago", "localdata", "semas")
    filters: dict[str, object] = {}
    if dataset_id == "semas.zone_one":
        filters = {"key": "1"}
    ids = _ids(client, dataset_id, page_size=cap + 50, **filters)
    assert ids == [str(n) for n in range(1, cap * 2 + 51)]
    assert all(_query(url)["numOfRows"] == str(cap) for url in server.urls)


def test_bok_caps_page_size(serve: Callable[[_Server], None]) -> None:
    def window(url: str) -> tuple[int, int]:
        parts = urlsplit(url).path.split("/")
        at = parts.index("StatisticSearch")
        start, end = int(parts[at + 4]), int(parts[at + 5])
        return start - 1, end - start + 1

    def shape(rows: list[Row], total: int | None) -> object:
        return {"StatisticSearch": {"list_total_count": total, "row": rows}}

    server = _Server(total=2050, cap=1000, window=window, shape=shape)
    serve(server)
    ids = _ids(_client("bok"), "bok.base_rate", page_size=1500, start_date="2000", end_date="2024")
    assert ids == [str(n) for n in range(1, 2051)]


def _lofin_shape(rows: list[Row], total: int | None) -> object:
    return {
        "AJGCF": [
            {
                "head": [
                    {"list_total_count": total},
                    {"RESULT": {"CODE": "INFO-000", "MESSAGE": "OK"}},
                ]
            },
            {"row": rows},
        ]
    }


def test_lofin_caps_page_size(serve: Callable[[_Server], None]) -> None:
    server = _Server(
        total=2050, cap=1000, window=_page_window("pIndex", "pSize"), shape=_lofin_shape
    )
    serve(server)
    ids = _ids(_client("lofin"), "lofin.expenditure_budget", page_size=1500, fyr="2024")
    assert ids == [str(n) for n in range(1, 2051)]


def test_law_caps_page_size(serve: Callable[[_Server], None]) -> None:
    def shape(rows: list[Row], total: int | None) -> object:
        return {"target": "law", "totalCnt": total, "law": rows}

    server = _Server(total=250, cap=100, window=_page_window("page", "display"), shape=shape)
    serve(server)
    ids = _ids(_client("law"), "law.law_search", page_size=150, query="법")
    assert ids == [str(n) for n in range(1, 251)]


# 2-3. Adapters that declare no pagination refuse a page they cannot serve.


def test_krx_refuses_page_other_than_one(
    serve: Callable[[_Server], None], monkeypatch: pytest.MonkeyPatch
) -> None:
    from kpubdata.providers.krx.adapter import KrxAdapter

    def no_pykrx(_self: KrxAdapter) -> object:
        raise AssertionError("pykrx must not be reached")

    monkeypatch.setattr(KrxAdapter, "_import_pykrx", no_pykrx)
    dataset = _client("krx").dataset("krx.kospi_index")
    assert dataset.ref.query_support is not None
    assert dataset.ref.query_support.pagination.value == "none"
    with pytest.raises(InvalidRequestError, match="does not paginate"):
        dataset.list(page=2, start_date="20240101", end_date="20240105")


def test_sgis_declares_and_enforces_no_pagination(serve: Callable[[_Server], None]) -> None:
    client = _client("sgis")
    for ref in client.datasets.list(provider="sgis"):
        assert ref.query_support is not None
        assert ref.query_support.pagination.value == "none"
        assert ref.query_support.max_page_size is None
    with pytest.raises(InvalidRequestError, match="does not paginate"):
        client.dataset("sgis.boundary.sido").list(page=2)


# 4-6. A total the provider omits is unknown, and a full page means another may follow.


def _seoul_window(url: str) -> tuple[int, int]:
    parts = [part for part in urlsplit(url).path.split("/") if part]
    at = parts.index("GetParkInfo")
    start, end = int(parts[at + 1]), int(parts[at + 2])
    return start - 1, end - start + 1


def _seoul_shape(rows: list[Row], total: int | None) -> object:
    body: dict[str, object] = {"RESULT": {"CODE": "INFO-000", "MESSAGE": "OK"}, "row": rows}
    if total is not None:
        body["list_total_count"] = total
    return {"GetParkInfo": body}


def test_seoul_without_total_keeps_paging_on_full_pages(serve: Callable[[_Server], None]) -> None:
    server = _Server(
        total=250, cap=1000, window=_seoul_window, shape=_seoul_shape, send_total=False
    )
    serve(server)
    client = _client("seoul")
    first = client.dataset("seoul.park_info").list(page_size=100)
    assert first.total_count is None
    assert first.next_page == 2
    ids = _ids(client, "seoul.park_info", page_size=100)
    assert ids == [str(n) for n in range(1, 251)]


def test_seoul_with_total_still_stops_on_it(serve: Callable[[_Server], None]) -> None:
    server = _Server(total=200, cap=1000, window=_seoul_window, shape=_seoul_shape)
    serve(server)
    ids = _ids(_client("seoul"), "seoul.park_info", page_size=100)
    assert ids == [str(n) for n in range(1, 201)]
    assert len(server.urls) == 2


def _korean_window(url: str) -> tuple[int, int]:
    q = _query(url)
    return int(q["start"]) - 1, int(q["num"])


def _korean_shape(rows: list[Row], total: int | None) -> object:
    # Two senses per headword: one headword becomes two rows.
    items = [
        {"ID": row["ID"], "word": f"w{row['ID']}", "sense": [{"n": 1}, {"n": 2}]} for row in rows
    ]
    channel: dict[str, object] = {"item": items}
    if total is not None:
        channel["total"] = str(total)
    return {"channel": channel}


@pytest.mark.parametrize("send_total", [True, False])
def test_korean_pages_by_headword_not_by_sense(
    serve: Callable[[_Server], None], send_total: bool
) -> None:
    server = _Server(
        total=25, cap=100, window=_korean_window, shape=_korean_shape, send_total=send_total
    )
    serve(server)
    client = _client("korean")
    first = client.dataset("korean.dict_search").list(page_size=10, q="나무")
    assert len(first.items) == 20
    assert first.total_count == (25 if send_total else None)
    assert first.next_page == 2
    server.urls.clear()
    ids = _ids(client, "korean.dict_search", page_size=10, q="나무")
    assert ids == [str(n) for n in range(1, 26) for _ in range(2)]
    # The last page holds 5 headwords (10 rows): counting rows would ask for a page 4.
    assert len(server.urls) == 3


def test_neis_reads_a_string_total(serve: Callable[[_Server], None]) -> None:
    def shape(rows: list[Row], total: int | None) -> object:
        head = [{"list_total_count": str(total)}, {"RESULT": {"CODE": "INFO-000"}}]
        return {"schoolInfo": [[{"head": head}], [{"head": head, "row": rows}]]}

    server = _Server(total=150, cap=100, window=_page_window("pIndex", "pSize"), shape=shape)
    serve(server)
    client = _client("neis")
    first = client.dataset("neis.school_info").list(page_size=100)
    assert first.total_count == 150
    ids = _ids(client, "neis.school_info", page_size=100)
    assert ids == [str(n) for n in range(1, 151)]
