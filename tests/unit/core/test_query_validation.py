"""Spec query validation: refused canonical options, enum bypass, strict loader and casts."""

from __future__ import annotations

from dataclasses import replace

import pytest

from kpubdata.core.executor import _try_cast_field
from kpubdata.core.models import Query
from kpubdata.core.spec import ParamSpec, SpecDefinition, from_mapping
from kpubdata.exceptions import InvalidRequestError
from tests.unit.core.test_executor import FakeTransport, _golden_spec, _make_executor


def _enum_spec() -> SpecDefinition:
    base = _golden_spec("apt_trade")
    param = ParamSpec(
        name="dataTerm", alias="term", required=False, enum=("DAILY", "MONTH"), type="string"
    )
    return replace(base, params=(replace(base.params[0], required=False), param))


@pytest.mark.parametrize(
    "query",
    [
        Query(start_date="20250101"),
        Query(end_date="20250131"),
        Query(sort=["x"]),
        Query(fields=["a"]),
        Query(cursor="c"),
    ],
)
def test_spec_dataset_refuses_unsupported_canonical_options(query: Query) -> None:
    with pytest.raises(InvalidRequestError, match="do not support"):
        _make_executor(FakeTransport()).build_params(_enum_spec(), query)


def test_provider_name_cannot_bypass_enum() -> None:
    spec = _enum_spec()
    with pytest.raises(InvalidRequestError) as caught:
        _make_executor(FakeTransport()).build_params(spec, Query(filters={"dataTerm": "bogus"}))
    assert "bogus" not in str(caught.value)


def test_provider_name_with_valid_enum_still_works() -> None:
    params = _make_executor(FakeTransport()).build_params(
        _enum_spec(), Query(filters={"dataTerm": "DAILY"})
    )
    assert params["dataTerm"] == "DAILY"


def test_alias_and_provider_name_together_are_refused() -> None:
    with pytest.raises(InvalidRequestError, match="both") as caught:
        _make_executor(FakeTransport()).build_params(
            _enum_spec(), Query(filters={"term": "DAILY", "dataTerm": "MONTH"})
        )
    assert "MONTH" not in str(caught.value)


@pytest.mark.parametrize("value", ["12_34", "-nan", "+nan", "1_000", "١٢"])
def test_number_cast_rejects_odd_lexemes(value: str) -> None:
    assert _try_cast_field(value, "number") == (False, value)


@pytest.mark.parametrize(("value", "expected"), [("12.5", 12.5), ("-3", -3.0), (".5", 0.5)])
def test_number_cast_accepts_plain_decimals(value: str, expected: float) -> None:
    assert _try_cast_field(value, "number") == (True, expected)


_BASE: dict[str, object] = {
    "id": "x.y",
    "provider": "x",
    "title": "t",
    "endpoint": {"base_url": "https://apis.data.go.kr/x", "operation": "op"},
    "auth": {"type": "none"},
    "response": {
        "format": "json",
        "envelope": "datago_standard",
        "error": {"style": "result_code", "code_path": "response.header.resultCode"},
    },
    "pagination": {"type": "page_no_rows", "max_size": 100},
}


@pytest.mark.parametrize(
    "extra",
    [
        {"params": [{"name": "k", "required": "false"}]},
        {"params": [{"name": "k", "enum": [1, 2]}]},
        {"params": [{"name": "a", "alias": "k"}, {"name": "b", "alias": "k"}]},
        {"params": [{"name": "k"}, {"name": "b", "alias": "k"}]},
        {"fields": [{"name": "cnt", "type": "int"}]},
    ],
)
def test_loader_rejects_silent_coercions(extra: dict[str, object]) -> None:
    with pytest.raises(InvalidRequestError):
        from_mapping({**_BASE, **extra})
