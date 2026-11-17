"""Existing query-pagination modes use the same size on wire and when advancing (#973)."""

from dataclasses import replace

import pytest

from kpubdata.core.dataset import Dataset
from kpubdata.core.executor import SpecDatasetAdapter
from kpubdata.core.models import Query
from kpubdata.core.spec import SpecDefinition
from tests.unit.core.test_executor import (
    FakeTransport,
    _golden_spec,
    _make_executor,
    _ref,
    _standard_envelope,
)


def _spec(mode: str, max_size: int | None = None) -> SpecDefinition:
    base = _golden_spec("hospital_info")
    return replace(
        base,
        pagination=replace(
            base.pagination, type=mode, page_param=None, size_param=None, max_size=max_size
        ),
    )


@pytest.mark.parametrize("total", [21, None])
def test_page_display_default_fetches_the_next_page(total: int | None) -> None:
    spec = _spec("page_display")
    transport = FakeTransport(
        [
            _standard_envelope([{"id": i} for i in range(20)], total_count=total),
            _standard_envelope([{"id": 20}], total_count=total),
        ]
    )
    adapter = SpecDatasetAdapter(spec.provider, [spec], _make_executor(transport))
    batches = list(Dataset(_ref(spec), adapter).list_all())
    assert [item["id"] for batch in batches for item in batch.items] == list(range(21))
    assert [call["params"]["display"] for call in transport.calls] == ["20", "20"]
    assert [call["params"]["page"] for call in transport.calls] == ["1", "2"]


@pytest.mark.parametrize(
    ("mode", "size_name"), [("page_display", "display"), ("pindex_psize", "pSize")]
)
def test_query_pagination_caps_the_actual_request_size(mode: str, size_name: str) -> None:
    spec = _spec(mode, max_size=2)
    transport = FakeTransport([_standard_envelope([{"id": 1}, {"id": 2}], total_count=None)])
    batch = _make_executor(transport).query(spec, _ref(spec), Query(page_size=9))
    assert transport.calls[0]["params"][size_name] == "2"
    assert batch.next_page == 2


@pytest.mark.parametrize("mode", ["page_display", "pindex_psize"])
def test_custom_names_and_explicit_size_keep_advancing(mode: str) -> None:
    base = _spec(mode)
    spec = replace(
        base, pagination=replace(base.pagination, page_param="pageIndex", size_param="limit")
    )
    transport = FakeTransport([_standard_envelope([{"id": i} for i in range(7)], total_count=None)])
    batch = _make_executor(transport).query(spec, _ref(spec), Query(page=3, page_size=7))
    sent = transport.calls[0]["params"]
    assert sent["pageIndex"] == "3"
    assert sent["limit"] == "7"
    assert batch.next_page == 4
