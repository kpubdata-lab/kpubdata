"""KIPRIS (Patent Office) adapter unit tests (#223)."""

from __future__ import annotations

from pathlib import Path
from typing import cast

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import Query
from kpubdata.exceptions import InvalidRequestError
from kpubdata.providers.kipris.adapter import KiprisAdapter
from kpubdata.transport.http import HttpTransport
from tests.unit.providers.datago.conftest import FakeResponse

_FIXTURE_DIR = Path(__file__).parents[3] / "fixtures" / "kipris"


def _load(name: str) -> bytes:
    return (_FIXTURE_DIR / name).read_bytes()


def _build_adapter(fixture_names: list[str]) -> tuple[KiprisAdapter, object]:
    class _Transport:
        def __init__(self, names: list[str]) -> None:
            self._responses = [FakeResponse(_load(n)) for n in names]
            self.calls: list[dict[str, object]] = []

        def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
            self.calls.append({"method": method, "url": url, **kwargs})
            return self._responses.pop(0)

    transport = _Transport(fixture_names)
    adapter = KiprisAdapter(
        config=KPubDataConfig(provider_keys={"kipris": "KIPI-KEY-1"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter, transport


def test_query_records_builds_kipi_url() -> None:
    """Verify patFamInfoSearchService URL shape."""
    adapter, transport = _build_adapter(["patent_family.json"])
    dataset = adapter.get_dataset("patent_family")

    batch = adapter.query_records(
        dataset,
        Query(filters={"applicationNumber": "1020050082226"}),
    )

    call = transport.calls[0]
    url = str(call["url"])
    assert url.startswith(
        "http://kipo-api.kipi.or.kr/openapi/service/patFamInfoSearchService/"
        "getAppNoPatFamInfoSearch?"
    )
    assert "_type=json" in url
    assert "applicationNumber=1020050082226" in url

    assert len(batch.items) == 2
    assert batch.items[0]["docdbFamilyID"] == "35462403"
    assert batch.items[1]["applicationCountryCode"] == "CN"
    assert batch.total_count == 2


def test_query_records_missing_application_number_raises() -> None:
    """Missing required filter applicationNumber raises InvalidRequestError."""
    adapter, _ = _build_adapter(["patent_family.json"])
    dataset = adapter.get_dataset("patent_family")

    try:
        adapter.query_records(dataset, Query())
    except InvalidRequestError as exc:
        assert "applicationNumber" in str(exc)
    else:
        raise AssertionError("Missing applicationNumber should raise exception")


def test_empty_items_returns_empty_batch() -> None:
    """When items is empty string, normal response returns empty batch."""
    adapter, _ = _build_adapter(["empty.json"])
    dataset = adapter.get_dataset("patent_family")

    batch = adapter.query_records(dataset, Query(filters={"applicationNumber": "1020050082226"}))

    assert batch.items == []
    assert batch.total_count is None


def test_full_page_sets_next_page() -> None:
    """next_page computed via full-page heuristic when totalCount absent."""
    adapter, _ = _build_adapter(["patent_family.json"])
    dataset = adapter.get_dataset("patent_family")

    batch = adapter.query_records(
        dataset, Query(filters={"applicationNumber": "1020050082226"}, page_size=2)
    )

    assert batch.next_page == 2


def test_call_raw_returns_full_envelope() -> None:
    """call_raw returns the complete response envelope."""
    adapter, _ = _build_adapter(["patent_family.json"])
    dataset = adapter.get_dataset("patent_family")

    payload = adapter.call_raw(
        dataset, "getAppNoPatFamInfoSearch", {"applicationNumber": "1020050082226"}
    )

    assert "response" in cast(dict, payload)
