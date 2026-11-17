"""Preflight regressions for declared required spec filters (#969)."""

from dataclasses import replace

import pytest

from kpubdata.core.dataset import Dataset
from kpubdata.core.executor import SpecDatasetAdapter
from kpubdata.core.models import Query
from kpubdata.core.spec import ParamSpec, SpecDefinition, discover_specs
from kpubdata.exceptions import InvalidRequestError
from tests.unit.core.test_executor import (
    FakeTransport,
    _golden_spec,
    _make_executor,
    _ref,
    _standard_envelope,
)


@pytest.mark.parametrize("filters", [{}, {"region": None}, {"DEAL_YMD": "202401"}])
def test_missing_required_alias_stops_before_network(filters: dict[str, object]) -> None:
    base = _golden_spec("apt_trade")
    spec = replace(base, params=(replace(base.params[0], alias="region"), *base.params[1:]))
    transport = FakeTransport()
    with pytest.raises(InvalidRequestError, match="region") as caught:
        _make_executor(transport).query(spec, _ref(spec), Query(filters=filters))
    assert caught.value.provider == "datago"
    assert caught.value.dataset_id == spec.id
    assert transport.calls == []


def test_complete_alias_and_explicit_empty_value_are_preserved() -> None:
    base = _golden_spec("apt_trade")
    spec = replace(base, params=(replace(base.params[0], alias="region"), *base.params[1:]))
    params = _make_executor(FakeTransport()).build_params(
        spec, Query(filters={"region": "", "DEAL_YMD": "202401"})
    )
    assert params["LAWD_CD"] == ""
    assert params["DEAL_YMD"] == "202401"
    assert "region" not in params


def test_required_automatic_parameters_do_not_need_user_filters() -> None:
    spec = replace(
        _golden_spec("hospital_info"),
        params=tuple(
            ParamSpec(name=name, required=True)
            for name in ("serviceKey", "_type", "pageNo", "numOfRows")
        ),
    )
    params = _make_executor(FakeTransport()).build_params(spec, Query())
    assert params == {
        "serviceKey": "test-key-datago",
        "_type": "json",
        "pageNo": "1",
        "numOfRows": "100",
    }


@pytest.mark.parametrize("bulk", [False, True])
def test_public_dataset_rejects_incomplete_query_before_transport(bulk: bool) -> None:
    spec = _golden_spec("apt_trade")
    transport = FakeTransport()
    adapter = SpecDatasetAdapter(spec.provider, [spec], _make_executor(transport))
    dataset = Dataset(_ref(spec), adapter)
    with pytest.raises(InvalidRequestError, match="DEAL_YMD"):
        if bulk:
            list(dataset.list_all(LAWD_CD="11110"))
        else:
            dataset.list(LAWD_CD="11110")
    assert transport.calls == []


def test_required_numeric_zero_is_a_supplied_value() -> None:
    spec = replace(_golden_spec("hospital_info"), params=(ParamSpec(name="count", required=True),))
    params = _make_executor(FakeTransport()).build_params(spec, Query(filters={"count": 0}))
    assert params["count"] == "0"


@pytest.mark.parametrize("spec", discover_specs(), ids=lambda spec: spec.id)
def test_all_bundled_examples_satisfy_declared_required_filters(spec: SpecDefinition) -> None:
    assert spec.examples
    executor = _make_executor(FakeTransport())
    for example in spec.examples:
        params = executor.build_params(
            spec,
            Query(filters=dict(example.params), page=example.page, page_size=example.page_size),
            format_hint=example.format,
        )
        for param in spec.params:
            if param.required:
                assert param.name in params, (spec.id, example.name, param.exposed_name)


@pytest.mark.parametrize("spec", discover_specs(), ids=lambda spec: spec.id)
def test_bundled_required_filters_are_not_filled_from_examples(spec: SpecDefinition) -> None:
    for param in spec.params:
        if not param.required:
            continue
        filters: dict[str, object] = dict(spec.examples[0].params)
        filters.pop(param.exposed_name)
        transport = FakeTransport()
        with pytest.raises(InvalidRequestError) as caught:
            _make_executor(transport).query(spec, _ref(spec), Query(filters=filters))
        assert param.exposed_name in str(caught.value)
        assert transport.calls == []


def test_raw_escape_hatch_does_not_enforce_normalized_required_filters() -> None:
    spec = _golden_spec("apt_trade")
    transport = FakeTransport([_standard_envelope([], total_count=0)])
    payload = _make_executor(transport).request_raw(spec, {"providerSpecific": "value"})
    assert "response" in payload
    assert len(transport.calls) == 1
    params = transport.calls[0]["params"]
    assert isinstance(params, dict)
    assert params["providerSpecific"] == "value"
