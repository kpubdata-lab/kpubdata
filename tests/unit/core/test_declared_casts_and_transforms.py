"""Declared ``boolean`` types and ``to_int``/``to_float`` transforms are applied.

``_try_cast_field`` had no ``boolean`` branch, so every value "cast" and stayed as
it came; ``to_int`` and ``to_float`` did nothing; and the runtime loader accepted a
``transform`` that ``schema.json`` does not list.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from kpubdata.core.executor import SpecExecutor
from kpubdata.core.spec import FieldSpec, SpecDefinition, find_spec, from_mapping
from kpubdata.exceptions import InvalidRequestError

SCHEMA = Path(__file__).resolve().parents[3] / "src" / "kpubdata" / "specs" / "schema.json"
MINIMAL_SPEC = Path(__file__).resolve().parents[2] / "fixtures" / "specs" / "valid_minimal.yaml"


def _probe(*fields: FieldSpec) -> SpecDefinition:
    spec = find_spec("datago.apt_trade")
    assert spec is not None
    return replace(spec, fields=fields)


def _normalize(
    spec: SpecDefinition, items: list[dict[str, object]]
) -> tuple[list[dict[str, object]], list[str]]:
    out, report = SpecExecutor._normalize_fields(spec, items)
    return out, [issue.field for issue in report.issues_of("uncastable")]


def test_boolean_casts_bools_and_true_false_strings() -> None:
    spec = _probe(FieldSpec(name="flag", type="boolean"))
    items = [
        {"flag": "true"},
        {"flag": "FALSE"},
        {"flag": " True "},
        {"flag": False},
        {"flag": None},
    ]
    out, uncastable = _normalize(spec, items)
    assert [item["flag"] for item in out] == [True, False, True, False, None]
    assert uncastable == []


@pytest.mark.parametrize("bad", ["Y", "1", 1, 0, "", "yes"])
def test_boolean_rejects_anything_else_for_the_whole_column(bad: object) -> None:
    spec = _probe(FieldSpec(name="flag", type="boolean"))
    out, uncastable = _normalize(spec, [{"flag": "true"}, {"flag": bad}])
    # All-or-nothing: the castable "true" is left alone too.
    assert [item["flag"] for item in out] == ["true", bad]
    assert uncastable == ["flag"]


def test_to_int_casts_through_the_integer_cast() -> None:
    spec = _probe(FieldSpec(name="n", type="string", transform="to_int"))
    out, uncastable = _normalize(spec, [{"n": "1,200"}, {"n": "7"}, {"n": ""}])
    assert [item["n"] for item in out] == [1200, 7, None]
    assert uncastable == []


def test_to_int_reports_a_non_integer_column() -> None:
    spec = _probe(FieldSpec(name="n", type="number", transform="to_int"))
    out, uncastable = _normalize(spec, [{"n": "3"}, {"n": "3.5"}])
    assert [item["n"] for item in out] == ["3", "3.5"]
    assert uncastable == ["n"]


def test_to_float_casts_through_the_number_cast() -> None:
    spec = _probe(FieldSpec(name="x", type="string", transform="to_float"))
    out, uncastable = _normalize(spec, [{"x": "1.5"}, {"x": "2"}])
    assert [item["x"] for item in out] == [1.5, 2.0]
    assert uncastable == []


def test_to_float_reports_a_non_numeric_column() -> None:
    spec = _probe(FieldSpec(name="x", type="string", transform="to_float"))
    out, uncastable = _normalize(spec, [{"x": "1.5"}, {"x": "n/a"}])
    assert [item["x"] for item in out] == ["1.5", "n/a"]
    assert uncastable == ["x"]


def test_loader_rejects_an_unknown_transform() -> None:
    data = yaml.safe_load(MINIMAL_SPEC.read_text(encoding="utf-8"))
    data["fields"] = [{"name": "x", "transform": "to_upper"}]
    with pytest.raises(InvalidRequestError, match="fields.x: transform"):
        from_mapping(data)


def _schema_transforms() -> list[str]:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    transforms = schema["properties"]["fields"]["items"]["properties"]["transform"]["enum"]
    return [str(transform) for transform in transforms]


@pytest.mark.parametrize("transform", _schema_transforms())
def test_loader_accepts_every_schema_transform(transform: str) -> None:
    data = yaml.safe_load(MINIMAL_SPEC.read_text(encoding="utf-8"))
    data["fields"] = [{"name": "x", "type": "integer", "transform": transform}]
    spec = from_mapping(data)
    assert spec.fields[0].transform == transform
