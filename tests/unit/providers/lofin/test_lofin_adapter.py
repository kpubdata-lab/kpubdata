"""Test module.

This file defines test scenarios and helper objects at
``tests/unit/providers/lofin/test_lofin_adapter.py``.
It verifies core flows, exceptions, and edge cases for regression
prevention and public contract validation.
"""

from __future__ import annotations

import json
import logging
from types import MappingProxyType
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.exceptions import ProviderResponseError
from kpubdata.providers.lofin.adapter import LofinAdapter
from kpubdata.transport.http import HttpTransport


class FakeResponse:
    """
    Class that encapsulates FakeResponse role and state.

    This class manages FakeResponse state and behavior together at
    ``tests/unit/providers/lofin/test_lofin_adapter.py``. Main method: __init__.

    Attributes:
        Properties defined in constructor and class body are shared as
        common context by downstream methods.
    """

    def __init__(self, payload: dict[str, object]) -> None:
        """
        Initialize internal state for instance.

        Args:
            payload (dict[str, object]): Input value provided by caller.

        Returns:
            None: Computed result or return value from downstream calls.

        Raises:
            Exceptions from implementation or downstream dependencies may be
            raised as-is.
        """
        self.headers: dict[str, str] = {"content-type": "application/json"}
        self.text: str = json.dumps(payload)
        self.content: bytes = self.text.encode()


class FakeTransport:
    """
    Class that encapsulates FakeTransport role and state.

    This class manages FakeTransport state and behavior together at
    ``tests/unit/providers/lofin/test_lofin_adapter.py``. Main methods: __init__, request.

    Attributes:
        Properties defined in constructor and class body are shared as
        common context by downstream methods.
    """

    def __init__(self, responses: list[FakeResponse]) -> None:
        """
        Initialize internal state for instance.

        Args:
            responses (list[FakeResponse]): Input value provided by caller.

        Returns:
            None: Computed result or return value from downstream calls.

        Raises:
            Exceptions from implementation or downstream dependencies may be
            raised as-is.
        """
        self._responses: list[FakeResponse] = list(responses)
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> FakeResponse:
        """
        Perform request operation.

        Args:
            method (str): Input value provided by caller.
            url (str): Input value provided by caller.
            **kwargs (object): Input value provided by caller.

        Returns:
            FakeResponse: Computed result or return value from downstream
            calls.

        Raises:
            Exceptions from implementation or downstream dependencies may be
            raised as-is.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        return self._responses.pop(0)


def _success_payload(*, items: object, total_count: object) -> dict[str, object]:
    """"""
    return {
        "AJGCF": [
            {
                "head": [
                    {"list_total_count": total_count},
                    {"RESULT": {"CODE": "INFO-000", "MESSAGE": "OK"}},
                ]
            },
            {"row": items},
        ]
    }


def _build_adapter_with_transport(
    responses: list[FakeResponse],
) -> tuple[LofinAdapter, DatasetRef, FakeTransport]:
    """
    Internal helper to process build adapter with transport.

    Args:
        responses (list[FakeResponse]): Input value provided by caller.

    Returns:
        tuple[LofinAdapter, DatasetRef, FakeTransport]: Computed result or
        return value from downstream calls.

    Raises:
        Exceptions from implementation or downstream dependencies may be
        raised as-is.
    """
    transport = FakeTransport(responses)
    adapter = LofinAdapter(
        config=KPubDataConfig(provider_keys={"datago": "test-key"}),
        transport=cast(HttpTransport, cast(object, transport)),
    )
    dataset = adapter.get_dataset("expenditure_budget")
    return adapter, dataset, transport


# Verifies scenario tested by test_query_records_returns_single_page_and_sets_next_page.
def test_query_records_returns_single_page_and_sets_next_page() -> None:
    """"""
    payload = _success_payload(items=[{"id": 1}, {"id": 2}], total_count=5)
    adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

    batch = adapter.query_records(dataset, Query(page=1, page_size=2))

    assert batch.items == [{"id": 1}, {"id": 2}]
    assert batch.total_count == 5
    assert batch.next_page == 2
    assert batch.raw == payload
    assert len(transport.calls) == 1


# Verifies scenario tested by test_query_records_uses_default_page_size_100.
def test_query_records_uses_default_page_size_100() -> None:
    """"""
    payload = _success_payload(items=[{"id": 1}], total_count=1)
    adapter, dataset, transport = _build_adapter_with_transport([FakeResponse(payload)])

    _ = adapter.query_records(dataset, Query())

    request_url = cast(str, transport.calls[0]["url"])
    assert "pSize=100" in request_url


# Verifies scenario tested by test_query_records_uses_heuristic_next_page_without_total_count.
def test_query_records_uses_heuristic_next_page_without_total_count() -> None:
    """"""
    payload = _success_payload(items=[{"id": 1}, {"id": 2}], total_count=None)
    adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

    batch = adapter.query_records(dataset, Query(page=1, page_size=2))

    assert batch.total_count is None
    assert batch.next_page == 2


# Verifies scenario tested by test_build_request_url_missing_base_url_logs_debug.
def test_build_request_url_missing_base_url_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """"""
    adapter, dataset, _ = _build_adapter_with_transport([])
    dataset = DatasetRef(
        id=dataset.id,
        provider=dataset.provider,
        dataset_key=dataset.dataset_key,
        name=dataset.name,
        representation=dataset.representation,
        operations=dataset.operations,
        raw_metadata=MappingProxyType(
            {k: v for k, v in dataset.raw_metadata.items() if k != "base_url"}
        ),
        query_support=dataset.query_support,
    )

    caplog.set_level(logging.DEBUG, logger="kpubdata.provider.lofin")
    with pytest.raises(ProviderResponseError, match="base_url"):
        adapter.query_records(dataset, Query())

    record = next(
        record
        for record in caplog.records
        if record.getMessage() == "LOFIN dataset metadata missing base_url"
    )
    assert record.__dict__["dataset_id"] == dataset.id


# Verifies scenario tested by test_query_records_zero_items_logs_debug.
def test_query_records_zero_items_logs_debug(caplog: pytest.LogCaptureFixture) -> None:
    """"""
    payload = _success_payload(items=[], total_count=0)
    adapter, dataset, _ = _build_adapter_with_transport([FakeResponse(payload)])

    caplog.set_level(logging.DEBUG, logger="kpubdata.provider.lofin")
    batch = adapter.query_records(dataset, Query(page=1, page_size=10))

    assert batch.items == []
    record = next(
        record for record in caplog.records if record.getMessage() == "LOFIN envelope: zero items"
    )
    assert record.__dict__["dataset_id"] == dataset.id
    assert record.__dict__["page"] == 1
    assert record.__dict__["page_size"] == 10
    assert record.__dict__["total_count"] == 0


def test_transport_requirements_includes_ssl_context_factory() -> None:
    """LofinAdapter exposes transport_requirements with an SSL context factory."""
    reqs = LofinAdapter.transport_requirements
    assert reqs is not None
    assert reqs.ssl_context_factory is not None

    ctx = reqs.ssl_context_factory()
    import ssl

    assert isinstance(ctx, ssl.SSLContext)


def test_client_applies_lofin_ssl_context() -> None:
    """Client detects LofinAdapter.transport_requirements and builds custom transport."""
    from unittest.mock import patch

    from kpubdata.client import Client
    from kpubdata.transport.http import HttpTransport

    with patch.object(
        HttpTransport, "with_requirements", wraps=HttpTransport.with_requirements
    ) as spy:
        client = Client()
        _ = client.datasets.list()

    assert spy.call_count >= 1
    for call in spy.call_args_list:
        reqs = call[0][1] if len(call[0]) > 1 else call.kwargs.get("requirements")
        if reqs and reqs.ssl_context_factory is not None:
            return
    raise AssertionError(
        "HttpTransport.with_requirements was never called with ssl_context_factory"
    )


class TestLofinVerifiesCertificates:
    """Verify Lofin context does not disable certificate validation."""

    def test_hostname_checking_stays_on(self) -> None:
        import ssl

        from kpubdata.providers.lofin.adapter import _lofin_ssl_context

        ctx = _lofin_ssl_context()

        assert ctx.check_hostname is True
        assert ctx.verify_mode is ssl.CERT_REQUIRED

    def test_the_cipher_relaxation_is_still_there(self) -> None:
        """This is why this custom context exists — removing it brings back original issue."""
        from kpubdata.providers.lofin.adapter import _lofin_ssl_context

        ciphers = {entry["name"] for entry in _lofin_ssl_context().get_ciphers()}

        # Legacy cipher only negotiated at SECLEVEL=1.
        assert "AES256-SHA256" in ciphers
