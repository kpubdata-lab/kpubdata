"""Declared ``boolean`` types are cast and unknown transforms are rejected.

``_try_cast_field`` had no ``boolean`` branch, so every value "cast" and stayed as
it came, and the runtime loader accepted a ``transform`` that ``schema.json`` does
not list. ``to_int`` and ``to_float`` keep main's behaviour: the column is cast to
the declared ``type`` and the transform adds nothing to that.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest
import yaml

from kpubdata.core.executor import SpecExecutor
from kpubdata.core.spec import (
    _FIELD_TRANSFORMS,
    FieldSpec,
    SpecDefinition,
    find_spec,
    from_mapping,
)
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


@pytest.mark.parametrize(
    ("field_type", "transform", "values", "expected"),
    [
        # The three pairs where casting to the transform's type diverged from main.
        ("integer", "to_float", ["3"], [3]),
        ("number", "to_int", ["3", "3.5"], [3.0, 3.5]),
        ("string", "to_int", ["12"], ["12"]),
        ("string", "to_float", ["1.5"], ["1.5"]),
        ("integer", "to_int", ["1,200", "7", ""], [1200, 7, None]),
        ("number", "to_float", ["1.5", "2"], [1.5, 2.0]),
    ],
)
def test_to_int_and_to_float_leave_the_declared_cast_alone(
    field_type: str, transform: str, values: list[str], expected: list[object]
) -> None:
    """``to_int``/``to_float`` add nothing to the cast to the declared ``type``."""
    spec = _probe(FieldSpec(name="n", type=field_type, transform=transform))
    out, uncastable = _normalize(spec, [{"n": value} for value in values])
    assert [item["n"] for item in out] == expected
    assert [type(item["n"]) for item in out] == [type(value) for value in expected]
    assert uncastable == []


def test_a_numeric_transform_does_not_rescue_an_uncastable_column() -> None:
    spec = _probe(FieldSpec(name="n", type="integer", transform="to_int"))
    out, report = SpecExecutor._normalize_fields(spec, [{"n": "3"}, {"n": "3.5"}])
    assert [item["n"] for item in out] == ["3", "3.5"]
    issues = report.issues_of("uncastable")
    assert [(issue.field, issue.declared_type) for issue in issues] == [("n", "integer")]


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


def test_loader_transforms_match_the_schema() -> None:
    assert set(_FIELD_TRANSFORMS) == set(_schema_transforms())
