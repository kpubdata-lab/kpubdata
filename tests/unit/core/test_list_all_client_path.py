"""``Client`` reaches the spec ``list_all`` path with global casting (#611).

Every provider with specs is wrapped in ``CompositeProviderAdapter``, which had no
``query_records_all``. So ``Client(...).dataset(...).list_all()`` always took the
per-page casting path, and a column could come back as ``int`` on one page and
``str`` on the next — the split 0.7.0 recorded as fixed (#481). The other tests
build ``Dataset`` on the spec adapter directly and never saw this.
"""

from __future__ import annotations

import pytest

from kpubdata import Client
from kpubdata.core.bridge import CompositeProviderAdapter
from kpubdata.core.models import DatasetRef, Query
from tests.unit.core.test_executor import FakeTransport, _standard_envelope


def _client_with(responses: list) -> tuple[Client, FakeTransport]:
    client = Client(provider_keys={"datago": "test-key"})
    adapter = client._registry.get("datago")
    assert isinstance(adapter, CompositeProviderAdapter)
    transport = FakeTransport(responses)
    adapter.spec_adapter._executor._transport = transport  # type: ignore[assignment]
    return client, transport


def test_client_list_all_casts_one_type_across_pages() -> None:
    client, transport = _client_with(
        [
            _standard_envelope([{"aptDong": "1"}, {"aptDong": "2"}], total_count=4),
            _standard_envelope([{"aptDong": "A-dong"}, {"aptDong": "3"}], total_count=4),
        ]
    )

    batches = list(client.dataset("datago.apt_trade").list_all(page_size=2, LAWD_CD="11680"))

    values = [item["aptDong"] for batch in batches for item in batch.items]
    assert len(values) == 4
    assert {type(value) for value in values} == {str}, values
    assert len(transport.calls) == 2


def _catalogue_only_ref(adapter: CompositeProviderAdapter) -> DatasetRef:
    spec_keys = {ref.dataset_key for ref in adapter.spec_adapter.list_datasets()}
    return next(ref for ref in adapter.inner.list_datasets() if ref.dataset_key not in spec_keys)


def test_catalogue_keys_keep_the_per_page_path() -> None:
    client, _ = _client_with([])
    adapter = client._registry.get("datago")
    assert isinstance(adapter, CompositeProviderAdapter)
    assert adapter.supports_query_records_all("apt_trade")
    assert not adapter.supports_query_records_all(_catalogue_only_ref(adapter).dataset_key)


def test_unsupported_key_is_refused_rather_than_guessed() -> None:
    client, _ = _client_with([])
    adapter = client._registry.get("datago")
    assert isinstance(adapter, CompositeProviderAdapter)
    with pytest.raises(NotImplementedError):
        adapter.query_records_all(_catalogue_only_ref(adapter), Query())
