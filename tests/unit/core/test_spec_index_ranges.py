"""Index-range requests retain canonical page and size context (#973)."""

from dataclasses import replace

import pytest

from kpubdata.core.capability import PaginationMode
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


def _spec(start: int = 1) -> SpecDefinition:
    base = _golden_spec("hospital_info")
    return replace(
        base,
        endpoint=replace(base.endpoint, path_template="{base_url}/{operation}/{start}/{end}"),
        pagination=replace(
            base.pagination,
            type="index_range",
            page_param=None,
            size_param=None,
            max_size=2,
            start_index_base=start,
        ),
    )


@pytest.mark.parametrize("recording", [False, True])
def test_second_page_uses_requested_capped_range(recording: bool) -> None:
    spec = _spec()
    transport = FakeTransport([_standard_envelope([{"id": 2}, {"id": 3}], total_count=6)])
    executor = _make_executor(transport)
    query = Query(page=2, page_size=9)
    if recording:
        executor.fetch(spec, query)
    else:
        result = executor.query(spec, _ref(spec), query)
        assert result.next_page == 3
    assert str(transport.calls[0]["url"]).endswith("/3/4")
    params = transport.calls[0]["params"]
    assert isinstance(params, dict)
    assert "pageNo" not in params and "numOfRows" not in params


@pytest.mark.parametrize("total", [5, None])
@pytest.mark.parametrize("start", [0, 1])
def test_public_bulk_advances_actual_ranges(total: int | None, start: int) -> None:
    spec = _spec(start)
    transport = FakeTransport(
        [
            _standard_envelope([{"id": 0}, {"id": 1}], total_count=total),
            _standard_envelope([{"id": 2}, {"id": 3}], total_count=total),
            _standard_envelope([{"id": 4}], total_count=total),
        ]
    )
    adapter = SpecDatasetAdapter(spec.provider, [spec], _make_executor(transport))
    dataset = Dataset(_ref(spec), adapter)
    batches = list(dataset.list_all(page_size=9))
    assert [item["id"] for batch in batches for item in batch.items] == list(range(5))
    suffixes = [str(call["url"]).rsplit("/", 2)[1:] for call in transport.calls]
    assert suffixes == [[str(start + n), str(start + n + 1)] for n in (0, 2, 4)]
    assert dataset.ref.query_support.pagination == PaginationMode.INDEX


def test_raw_range_defaults_keep_the_existing_low_level_behavior() -> None:
    spec = _spec()
    transport = FakeTransport([_standard_envelope([], total_count=0)])
    _make_executor(transport).request_raw(spec, {"providerSpecific": "value"})
    assert str(transport.calls[0]["url"]).endswith("/1/100")
