"""A spec's licence terms reach ``DatasetRef`` (#609).

``LicenseSpec`` was parsed into ``SpecDefinition`` and stopped there, so a downstream
reading the public model had no way to see redistribution terms or the provider's quota.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from kpubdata import Client, LicenseSpec
from kpubdata.core.executor import build_spec_dataset_ref
from kpubdata.core.spec import load_spec_file

_SPECS = Path(__file__).parents[3] / "src" / "kpubdata" / "specs" / "datago"


def test_the_declared_terms_are_carried_as_declared() -> None:
    spec = replace(
        load_spec_file(_SPECS / "apt_trade.yaml"),
        license=LicenseSpec(
            redistribution="non_commercial",
            attribution="출처: 국토교통부",
            quota="개발계정 일 10,000건",
            pii_columns=("buyer_name",),
        ),
    )

    terms = build_spec_dataset_ref(spec).license

    # Every field, not only the four set above, is carried unchanged.
    assert terms == spec.license
    assert terms is not None
    assert terms.quota == "개발계정 일 10,000건"
    assert terms.redistribution == "non_commercial"
    assert terms.attribution == "출처: 국토교통부"
    assert terms.pii_columns == ("buyer_name",)


def test_an_undeclared_licence_is_none_not_an_empty_one() -> None:
    """Negative: no licence section means unknown, never zero or empty terms."""
    spec = load_spec_file(_SPECS / "air_station.yaml")
    assert spec.license is None

    assert build_spec_dataset_ref(spec).license is None


def test_an_undeclared_quota_stays_none() -> None:
    """Negative: a licence without a quota does not invent one."""
    spec = load_spec_file(_SPECS / "air_quality.yaml")
    terms = build_spec_dataset_ref(spec).license

    # The bundled spec's declared terms arrive whole; which KOGL type it should declare
    # is a separate question (kpubdata-builder#759), so the value is not pinned here.
    assert terms == spec.license
    assert terms is not None
    assert terms.type is not None
    assert terms.quota is None


@pytest.mark.parametrize(
    ("dataset_id", "declared"),
    [("datago.air_quality", True), ("datago.air_station", False)],
)
def test_the_client_ref_exposes_it(
    monkeypatch: pytest.MonkeyPatch, dataset_id: str, declared: bool
) -> None:
    monkeypatch.delenv("KPUBDATA_REPLAY_DIR", raising=False)

    terms = Client().dataset(dataset_id).ref.license

    assert (terms is not None) is declared
