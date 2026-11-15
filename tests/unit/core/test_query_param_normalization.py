"""Regression tests for safe public-API filter serialization (#968)."""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal
from types import MappingProxyType
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core._params import scalar_filter_value
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.representation import Representation
from kpubdata.core.spec import ParamSpec
from kpubdata.exceptions import InvalidRequestError
from kpubdata.providers._datago_family import DataGoFamilyAdapter
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.transport.http import HttpTransport
from tests.unit.core.test_executor import (
    FakeTransport,
    _golden_spec,
    _make_executor,
    _standard_envelope,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("00220", "00220"),
        (1200, "1200"),
        (12.5, "12.5"),
        (Decimal("1.25"), "1.25"),
    ],
)
def test_supported_scalar_values_preserve_their_spelling(value: object, expected: str) -> None:
    assert scalar_filter_value("amount", value) == expected


def test_none_is_absent_rather_than_the_literal_none() -> None:
    assert scalar_filter_value("optional", None) is None


@pytest.mark.parametrize("value", [True, False, [1, 2], {"a": 1}, date(2026, 1, 2)])
def test_unexpected_filter_types_fail_before_serialization(value: object) -> None:
    with pytest.raises(InvalidRequestError, match="Filter"):
        scalar_filter_value("filter", value)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), Decimal("Infinity")])
def test_nonfinite_numbers_are_rejected(value: object) -> None:
    with pytest.raises(InvalidRequestError, match="finite"):
        scalar_filter_value("amount", value)


@pytest.mark.parametrize(("value", "expected"), [(True, "true"), (False, "false")])
def test_boolean_is_serialized_only_when_explicitly_declared(
    value: bool, expected: str
) -> None:
    assert scalar_filter_value("includeClosed", value, allow_bool=True) == expected


def test_spec_omits_none_optional_and_keeps_scalar_filters() -> None:
    spec = _golden_spec("apt_trade")
    transport = FakeTransport()
    params = _make_executor(transport).build_params(
        spec, Query(filters={"optional": None, "LAWD_CD": "00220", "amount": 12.5})
    )
    assert "optional" not in params
    assert params["LAWD_CD"] == "00220"
    assert params["amount"] == "12.5"
    assert transport.calls == []


def test_spec_rejects_explicitly_none_required_filter() -> None:
    spec = _golden_spec("apt_trade")
    transport = FakeTransport()
    with pytest.raises(InvalidRequestError, match="Required filter"):
        _make_executor(transport).build_params(spec, Query(filters={"LAWD_CD": None}))
    assert transport.calls == []


def test_spec_boolean_needs_a_boolean_parameter_declaration() -> None:
    base = _golden_spec("apt_trade")
    spec = replace(
        base, params=(*base.params, ParamSpec(name="includeClosed", type="boolean"))
    )
    params = _make_executor(FakeTransport()).build_params(
        spec, Query(filters={"includeClosed": True})
    )
    assert params["includeClosed"] == "true"
    with pytest.raises(InvalidRequestError, match="boolean"):
        _make_executor(FakeTransport()).build_params(
            base, Query(filters={"includeClosed": True})
        )


def test_spec_rejects_list_and_raw_list_without_transport_calls() -> None:
    spec = _golden_spec("apt_trade")
    transport = FakeTransport()
    executor = _make_executor(transport)
    with pytest.raises(InvalidRequestError, match="list"):
        executor.build_params(spec, Query(filters={"LAWD_CD": [11, 22]}))
    with pytest.raises(InvalidRequestError, match="list"):
        executor.request_raw(spec, {"LAWD_CD": [11, 22]})
    assert transport.calls == []


def _test_dataset(provider: str) -> DatasetRef:
    return DatasetRef(
        id=f"{provider}.example",
        provider=provider,
        dataset_key="example",
        name="Fixture-only dataset",
        representation=Representation.API_JSON,
        raw_metadata=MappingProxyType(
            {"base_url": "https://apis.data.go.kr/example", "default_operation": "test"}
        ),
    )


@pytest.mark.parametrize("provider", ["datago", "localdata"])
def test_legacy_adapters_reject_unsupported_filters_before_transport(provider: str) -> None:
    dataset = _test_dataset(provider)
    transport = FakeTransport()
    config = KPubDataConfig(provider_keys={"datago": "test-key"}, env_fallback=False)
    if provider == "datago":
        adapter = DataGoAdapter(
            config=config,
            transport=cast(HttpTransport, cast(object, transport)),
            catalogue=[dataset],
        )
    else:
        class Localdata(DataGoFamilyAdapter):
            provider_name = "localdata"
            catalogue_package = "kpubdata.providers.localdata"

        adapter = Localdata(
            config=config,
            transport=cast(HttpTransport, cast(object, transport)),
            catalogue=[dataset],
        )
    with pytest.raises(InvalidRequestError, match="list"):
        adapter.query_records(dataset, Query(filters={"district": [1, 2]}))
    with pytest.raises(InvalidRequestError, match="boolean"):
        adapter.call_raw(dataset, "test", {"district": True})
    assert transport.calls == []


@pytest.mark.parametrize("provider", ["datago", "localdata"])
def test_legacy_none_filter_does_not_go_on_wire(provider: str) -> None:
    dataset = _test_dataset(provider)
    transport = FakeTransport([_standard_envelope([{"value": "ok"}], total_count=1)])
    config = KPubDataConfig(provider_keys={"datago": "test-key"}, env_fallback=False)
    if provider == "datago":
        adapter = DataGoAdapter(
            config=config,
            transport=cast(HttpTransport, cast(object, transport)),
            catalogue=[dataset],
        )
    else:
        class Localdata(DataGoFamilyAdapter):
            provider_name = "localdata"
            catalogue_package = "kpubdata.providers.localdata"

        adapter = Localdata(
            config=config,
            transport=cast(HttpTransport, cast(object, transport)),
            catalogue=[dataset],
        )
    adapter.query_records(dataset, Query(filters={"district": None, "year": 2026}))
    assert len(transport.calls) == 1
    sent = transport.calls[0]["params"]
    assert isinstance(sent, dict)
    assert "district" not in sent
    assert sent["year"] == "2026"
