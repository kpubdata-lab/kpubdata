"""A ``{operation}`` placeholder in ``total_count_path`` is resolved at runtime too.

``extract_total_count`` (used by record and verify) resolved the placeholder, but the
executor's own copy did not, so verify read a count of 7 while ``query`` and
``list_all`` reported ``None`` for the same payload.
"""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from kpubdata.core.executor import SpecDatasetAdapter, extract_total_count
from kpubdata.core.models import Query
from kpubdata.core.spec import SpecDefinition
from tests.unit.core.test_executor import (
    FakeResponse,
    FakeTransport,
    _golden_spec,
    _make_executor,
    _ref,
)

FILTERS = {"LAWD_CD": "11680", "DEAL_YMD": "202401"}


@pytest.fixture()
def op_spec() -> SpecDefinition:
    spec = _golden_spec("apt_trade")
    response = replace(spec.response, total_count_path="{operation}.list_total_count")
    return replace(spec, response=response)


def _payload(spec: SpecDefinition) -> dict[str, object]:
    return {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "OK"},
            "body": {"items": {"item": [{"aptNm": "A"}]}},
        },
        spec.endpoint.operation: {"list_total_count": "7"},
    }


def _response(spec: SpecDefinition) -> FakeResponse:
    return FakeResponse(json.dumps(_payload(spec)).encode("utf-8"))


def test_module_function_resolves_operation(op_spec: SpecDefinition) -> None:
    assert extract_total_count(op_spec, _payload(op_spec)) == 7


def test_executor_method_matches_module_function(op_spec: SpecDefinition) -> None:
    executor = _make_executor(FakeTransport())
    assert executor._extract_total_count(op_spec, _payload(op_spec)) == 7


def test_query_reports_the_resolved_count(op_spec: SpecDefinition) -> None:
    executor = _make_executor(FakeTransport([_response(op_spec)]))
    batch = executor.query(op_spec, _ref(op_spec), Query(filters=FILTERS))
    assert batch.total_count == 7


def test_list_all_reports_the_resolved_count(op_spec: SpecDefinition) -> None:
    transport = FakeTransport([_response(op_spec)])
    adapter = SpecDatasetAdapter("datago", [op_spec], _make_executor(transport))
    batches = list(adapter.query_records_all(_ref(op_spec), Query(filters=FILTERS)))
    assert [batch.total_count for batch in batches] == [7]
