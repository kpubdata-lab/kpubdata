"""``SpecDefinition`` is public: the type ``find_spec`` returns (#913)."""

from __future__ import annotations

import kpubdata
from kpubdata import SpecDefinition, discover_specs, find_spec
from kpubdata.core import spec as core_spec


def test_spec_definition_is_exported() -> None:
    assert "SpecDefinition" in kpubdata.__all__
    assert SpecDefinition is core_spec.SpecDefinition


def test_find_spec_returns_the_exported_type() -> None:
    spec = find_spec("datago.apt_trade")
    assert isinstance(spec, SpecDefinition)
    assert spec.id == "datago.apt_trade"
    assert spec.provider == "datago"
    assert spec.dataset_key == "apt_trade"
    assert spec.pagination.type
    assert spec.endpoint.base_url
    assert spec.auth.type
    assert spec.examples


def test_discover_specs_returns_the_exported_type() -> None:
    specs = discover_specs()
    assert specs
    assert all(isinstance(spec, SpecDefinition) for spec in specs)
