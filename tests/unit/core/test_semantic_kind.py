"""Spec fields declare what they mean, and a contradiction is refused (#651, ADR 0006).

Storage type (``type``) and meaning (``semantic_kind``) used to share one word, which is
how zip codes were declared ``integer`` and lost their leading zeros (#613).
"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from kpubdata.core.executor import build_spec_dataset_ref, spec_schema
from kpubdata.core.spec import (
    SEMANTIC_KIND_TYPES,
    SpecDefinition,
    discover_specs,
    field_conflicts,
    from_mapping,
)
from kpubdata.exceptions import InvalidRequestError

REPO_ROOT = Path(__file__).resolve().parents[3]
SPEC_PATH = REPO_ROOT / "src" / "kpubdata" / "specs" / "datago" / "apt_trade.yaml"


def _base() -> dict[str, Any]:
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def _with_field(**field: object) -> dict[str, Any]:
    data = copy.deepcopy(_base())
    data["fields"] = [{"name": "probe", "type": "string", **field}]
    return data


@pytest.mark.parametrize(
    ("field", "message"),
    [
        ({"type": "integer", "semantic_kind": "code"}, "needs type"),
        ({"type": "string", "semantic_kind": "measure"}, "needs type"),
        ({"type": "string", "semantic_kind": "code", "transform": "to_int"}, "keeps its source"),
        ({"type": "string", "semantic_kind": "code", "unit": "원"}, "unit belongs to a measure"),
        ({"type": "string", "semantic_kind": "identifier"}, "unknown semantic_kind"),
    ],
)
def test_the_loader_refuses_each_conflict(field: dict[str, object], message: str) -> None:
    with pytest.raises(InvalidRequestError, match=message):
        from_mapping(_with_field(**field))


@pytest.mark.parametrize(
    "field",
    [
        {"type": "string", "semantic_kind": "code"},
        {"type": "number", "semantic_kind": "measure", "unit": "㎡"},
        {"type": "string", "semantic_kind": "date", "transform": "date_yyyymmdd"},
        {"type": "boolean", "semantic_kind": "flag"},
        {"type": "integer", "unit": "원"},  # undeclared meaning is not checked
    ],
)
def test_consistent_declarations_load(field: dict[str, object]) -> None:
    assert isinstance(from_mapping(_with_field(**field)), SpecDefinition)


def test_validate_spec_reports_the_same_conflicts(tmp_path: Path) -> None:
    script = REPO_ROOT / "scripts" / "validate_spec.py"
    spec = importlib.util.spec_from_file_location("_validate_spec_651", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_validate_spec_651"] = module
    spec.loader.exec_module(module)

    bad = tmp_path / "datago" / "apt_trade.yaml"
    bad.parent.mkdir()
    bad.write_text(yaml.safe_dump(_with_field(type="integer", semantic_kind="code")), "utf-8")
    schema = json.loads((REPO_ROOT / "src/kpubdata/specs/schema.json").read_text("utf-8"))
    result = module.validate_spec_file(bad, schema, {})
    assert any("needs type" in error for error in result.errors), result.errors


def test_schema_enum_matches_the_code() -> None:
    schema = json.loads((REPO_ROOT / "src/kpubdata/specs/schema.json").read_text("utf-8"))
    items = schema["properties"]["fields"]["items"]["properties"]
    assert set(items["semantic_kind"]["enum"]) == set(SEMANTIC_KIND_TYPES)


def test_get_schema_carries_meaning_title_and_format() -> None:
    data = _with_field(type="string", semantic_kind="period", title="계약 연월", format="YYYY-MM")
    spec = from_mapping(data)
    schema = spec_schema(spec, build_spec_dataset_ref(spec))
    assert schema is not None
    (probe,) = schema.fields
    assert probe.semantic_kind == "period"
    assert probe.title == "계약 연월"
    assert probe.constraints is not None and probe.constraints.format == "YYYY-MM"


def test_the_code_columns_found_in_613_are_declared_codes() -> None:
    codes = {
        (spec.id, field.name)
        for spec in discover_specs()
        for field in spec.fields
        if field.semantic_kind == "code"
    }
    assert ("datago.tour_kor_area", "zipcode") in codes
    assert ("datago.apt_trade", "bonbun") in codes
    assert ("datago.bus_arrival", "stationId") in codes
    assert ("datago.bus_arrival", "routeTypeCd") in codes
    assert len(codes) == 22
    for spec in discover_specs():
        for field in spec.fields:
            assert not field_conflicts(
                {
                    "name": field.name,
                    "type": field.type,
                    "semantic_kind": field.semantic_kind,
                    "transform": field.transform,
                    "unit": field.unit,
                }
            )
