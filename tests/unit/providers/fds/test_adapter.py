"""MFDS (FDS) adapter unit tests (#165)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import Query
from kpubdata.exceptions import AuthError
from kpubdata.providers.fds.adapter import FdsAdapter
from kpubdata.transport.http import HttpTransport
from tests.unit.providers.datago.conftest import FakeResponse

_FDS_FIXTURE_DIR = Path(__file__).parents[3] / "fixtures" / "fds"


def _load(name: str) -> bytes:
    return (_FDS_FIXTURE_DIR / name).read_bytes()


def _build_adapter(fixture_names: list[str]) -> tuple[FdsAdapter, object]:
    class _Transport:
        def __init__(self, names: list[str]) -> None:
            self._responses = [FakeResponse(_load(n)) for n in names]
            self.calls: list[dict[str, object]] = []

        def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
            self.calls.append({"method": method, "url": url, **kwargs})
            return self._responses.pop(0)

    transport = _Transport(fixture_names)
    adapter = FdsAdapter(
        config=KPubDataConfig(provider_keys={"fds": "FDS-KEY-1"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter, transport


def test_query_records_builds_fds_url_with_key_in_path() -> None:
    adapter, transport = _build_adapter(["traceability_item.json"])
    dataset = adapter.get_dataset("traceability_item")

    batch = adapter.query_records(dataset, Query(page_size=2))

    call = transport.calls[0]
    url = str(call["url"])
    # URL shape: /api/{KEY}/{service}/json/{start}/{end}
    assert "/FDS-KEY-1/I1200/json/1/2" in url
    # The path key is passed to the transport as secret_values so logs mask it (#354).
    assert call.get("secret_values") == ("FDS-KEY-1",)

    assert len(batch.items) == 2
    assert batch.items[0]["PRDLST_NM"] == "샘플우유 1L"


def test_query_records_next_page_from_full_page() -> None:
    adapter, _ = _build_adapter(["traceability_item.json"])
    dataset = adapter.get_dataset("traceability_item")

    batch = adapter.query_records(dataset, Query(page=1, page_size=1))

    # The real shape provides total_count (=2) — with page_size 1 there is a next page.
    assert batch.total_count == 2
    assert batch.next_page == 2


def test_query_records_auth_error_maps_to_auth_error() -> None:
    adapter, _ = _build_adapter(["auth_error.json"])
    dataset = adapter.get_dataset("traceability_item")

    try:
        adapter.query_records(dataset, Query())
    except AuthError:
        pass
    else:
        raise AssertionError("INFO-100은 AuthError로 매핑되어야 한다")


def test_call_raw_returns_full_payload() -> None:
    adapter, _ = _build_adapter(["traceability_item.json"])
    dataset = adapter.get_dataset("traceability_item")

    payload = adapter.call_raw(dataset, "I1200", {"start_idx": 1, "end_idx": 5})

    assert "I1200" in cast(dict, payload)  # Real shape: the service name is the top-level key
