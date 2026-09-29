"""Code columns keep their leading zeros (#613).

Zip codes, lot numbers and station codes were declared ``integer``, so "06102"
reached users as 6102 and a region-code JOIN went quietly wrong. Replay did not
notice because it compared values before normalization.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest

from kpubdata.core.executor import SpecExecutor, extract_items, normalize_items
from kpubdata.core.spec import FieldSpec, find_spec

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

CODE_FIELDS = [
    ("datago.apt_trade", "bonbun"),
    ("datago.apt_trade", "roadNmSeq"),
    ("datago.hospital_info", "postNo"),
    ("datago.metro_fare", "arvlStnCd"),
    ("datago.tour_kor_area", "zipcode"),
    ("datago.village_fcst", "fcstTime"),
]


def _fixture_items(dataset_id: str) -> list[dict[str, object]]:
    spec = find_spec(dataset_id)
    assert spec is not None
    provider, key = dataset_id.split(".", 1)
    items: list[dict[str, object]] = []
    for raw in sorted((FIXTURES / provider / key).glob("*.json")):
        if raw.name.endswith((".meta.json", ".expected.json")):
            continue
        items.extend(extract_items(spec, json.loads(raw.read_text(encoding="utf-8"))))
    return items


@pytest.mark.parametrize(("dataset_id", "field_name"), CODE_FIELDS)
def test_fixture_codes_survive_normalization(dataset_id: str, field_name: str) -> None:
    spec = find_spec(dataset_id)
    assert spec is not None
    items = _fixture_items(dataset_id)
    zero_led = [item for item in items if str(item.get(field_name, "")).startswith("0")]
    assert zero_led, f"no zero-led {field_name} in the {dataset_id} fixtures"
    for raw, out in zip(items, normalize_items(spec, items), strict=True):
        if field_name in raw:
            assert out[field_name] == raw[field_name]


@pytest.mark.parametrize("field_type", ["integer", "number"])
def test_a_zero_led_value_keeps_a_numeric_column_as_text(field_type: str) -> None:
    """The safety net for the next code column someone declares numeric."""
    spec = find_spec("datago.apt_trade")
    assert spec is not None
    probe = replace(spec, fields=(FieldSpec(name="code", type=field_type),))
    staged = [{"code": "06102"}, {"code": "1080"}]
    items, report = SpecExecutor._finalize_casting(probe, staged)
    assert [item["code"] for item in items] == ["06102", "1080"]
    assert [issue.field for issue in report.issues_of("uncastable")] == ["code"]


@pytest.mark.parametrize("value", ["0", "-0", "0.5", "10", "1,000"])
def test_ordinary_numbers_still_cast(value: str) -> None:
    spec = find_spec("datago.apt_trade")
    assert spec is not None
    probe = replace(spec, fields=(FieldSpec(name="n", type="number"),))
    items, report = SpecExecutor._finalize_casting(probe, [{"n": value}])
    assert not isinstance(items[0]["n"], str)
    assert not report.issues_of("uncastable")
