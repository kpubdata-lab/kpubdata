"""A spec dataset's ``schema()`` returns the fields its spec declares (#643).

It returned ``None`` although every spec carries field names, types, units and
descriptions, so Engine and Studio had no official way to read column metadata.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from kpubdata import Client
from kpubdata.core.capability import Operation
from kpubdata.core.executor import SpecDatasetAdapter, build_spec_dataset_ref
from kpubdata.core.spec import FieldSpec, SpecDefinition, discover_specs
from kpubdata.exceptions import DatasetNotFoundError
from tests.unit.core.test_executor import FakeTransport, _golden_spec, _make_executor

SPECS = [spec for spec in discover_specs() if spec.fields]


def _adapter(spec: SpecDefinition) -> SpecDatasetAdapter:
    return SpecDatasetAdapter(spec.provider, [spec], _make_executor(FakeTransport()))


@pytest.mark.parametrize("spec", SPECS, ids=[spec.id for spec in SPECS])
def test_schema_lists_every_declared_field_in_order(spec: SpecDefinition) -> None:
    adapter = _adapter(spec)
    ref = adapter.get_dataset(spec.dataset_key)
    schema = adapter.get_schema(ref)
    assert schema is not None
    assert schema.dataset == ref
    assert [f.name for f in schema.fields] == [f.name for f in spec.fields]
    assert [f.type for f in schema.fields] == [f.type for f in spec.fields]
    assert [f.description for f in schema.fields] == [f.description for f in spec.fields]
    assert Operation.SCHEMA in ref.operations


def test_unit_and_source_name_travel_in_raw() -> None:
    spec = replace(
        _golden_spec("apt_trade"),
        fields=(
            FieldSpec(name="area", type="number", source_name="excluUseAr", unit="㎡"),
            FieldSpec(name="aptNm", type="string"),
        ),
    )
    schema = _adapter(spec).get_schema(build_spec_dataset_ref(spec))
    assert schema is not None
    area, name = schema.fields
    assert dict(area.raw) == {"unit": "㎡", "source_name": "excluUseAr"}
    assert dict(name.raw) == {}
    # No title or format is invented before the column contract decides them (#644).
    assert area.title is None
    assert area.constraints is None


def test_a_spec_without_fields_has_no_schema() -> None:
    spec = replace(_golden_spec("apt_trade"), fields=())
    ref = build_spec_dataset_ref(spec)
    assert _adapter(spec).get_schema(ref) is None
    assert Operation.SCHEMA not in ref.operations


def test_an_unknown_key_is_refused() -> None:
    spec = _golden_spec("apt_trade")
    other = build_spec_dataset_ref(replace(spec, id="datago.other"))
    with pytest.raises(DatasetNotFoundError):
        _adapter(spec).get_schema(other)


def test_client_path_returns_the_schema() -> None:
    schema = Client(provider_keys={"datago": "k"}).dataset("datago.apt_trade").schema()
    assert schema is not None
    assert "aptNm" in [f.name for f in schema.fields]
