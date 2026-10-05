"""Only a dataset that declares its terms can be published publicly (#785).

The decision is recorded in ``docs/policy/terms-matrix.md``. Builder enforces the publish
side; this holds the half kpubdata owns — that terms come from a spec and from nowhere
else, so a dataset without a spec reports ``license is None`` (unknown), never a guess.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from kpubdata import Client, DatasetRef, find_spec

_DOC = Path(__file__).resolve().parents[2] / "docs" / "policy" / "terms-matrix.md"


@pytest.fixture(scope="module")
def refs() -> list[DatasetRef]:
    return list(Client(provider_keys={}, env_keys=False).datasets.list())


def test_every_dataset_with_terms_is_spec_backed(refs: list[DatasetRef]) -> None:
    with_terms = [ref.id for ref in refs if ref.license is not None]

    assert with_terms
    assert [dataset_id for dataset_id in with_terms if find_spec(dataset_id) is None] == []


def test_a_catalogue_only_dataset_declares_nothing(refs: list[DatasetRef]) -> None:
    """None is unknown. A default filled in for these would read as permission."""
    catalogue_only = [ref for ref in refs if find_spec(ref.id) is None]

    assert catalogue_only
    assert [ref.id for ref in catalogue_only if ref.license is not None] == []


def test_the_serialised_reference_says_unknown_as_null(refs: list[DatasetRef]) -> None:
    ref = next(ref for ref in refs if find_spec(ref.id) is None)

    assert ref.to_dict()["license"] is None


def test_the_decision_is_written_down() -> None:
    text = _DOC.read_text(encoding="utf-8")

    assert "only a dataset that declares its terms can be published" in text
    assert "redistribution_unknown" in text


# --- allowed, but nobody confirmed it (#812) ---

_BASELINE = Path(__file__).resolve().parents[2] / "scripts" / "unconfirmed_terms_baseline.txt"


def _baseline_ids() -> list[str]:
    lines = _BASELINE.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip() and not line.startswith("#")]


def test_allowed_without_the_attribution_text_is_reported_unknown() -> None:
    from kpubdata.core.spec import LicenseSpec, reported_license

    declared = LicenseSpec(type="공공누리_1유형", redistribution="allowed", note="not confirmed")

    reported = reported_license(declared)

    assert reported is not None
    assert reported.redistribution == "unknown"
    # Nothing else about the declaration is touched, and the spec's own value is kept.
    assert (reported.type, reported.note) == (declared.type, declared.note)
    assert declared.redistribution == "allowed"


@pytest.mark.parametrize("attribution", ["", "   "])
def test_a_blank_attribution_confirms_nothing(attribution: str) -> None:
    from kpubdata.core.spec import LicenseSpec, reported_license

    reported = reported_license(LicenseSpec(redistribution="allowed", attribution=attribution))

    assert reported is not None
    assert reported.redistribution == "unknown"


@pytest.mark.parametrize("declared", ["non_commercial", "forbidden", "unknown", None])
def test_terms_that_already_restrict_are_reported_as_declared(declared: str | None) -> None:
    from kpubdata.core.spec import LicenseSpec, reported_license

    licence = LicenseSpec(redistribution=declared)

    assert reported_license(licence) is licence
    assert reported_license(None) is None


def test_no_dataset_reports_allowed_without_its_attribution(refs: list[DatasetRef]) -> None:
    unconfirmed = [
        ref.id
        for ref in refs
        if ref.license is not None
        and ref.license.redistribution == "allowed"
        and not (ref.license.attribution or "").strip()
    ]

    assert unconfirmed == []


def test_every_baseline_spec_reports_unknown_while_its_file_still_says_allowed(
    refs: list[DatasetRef],
) -> None:
    """The ratchet counts what the files declare; a reference reports what was confirmed."""
    by_id = {ref.id: ref for ref in refs}
    baseline = _baseline_ids()

    assert baseline
    for dataset_id in baseline:
        spec = find_spec(dataset_id)
        assert spec is not None and spec.license is not None
        assert spec.license.redistribution == "allowed"
        licence = by_id[dataset_id].license
        assert licence is not None
        assert licence.redistribution == "unknown"
        serialised = by_id[dataset_id].to_dict()["license"]
        assert isinstance(serialised, dict)
        assert serialised["redistribution"] == "unknown"


def test_a_confirmed_dataset_still_reports_allowed(refs: list[DatasetRef]) -> None:
    confirmed = [
        ref.id
        for ref in refs
        if ref.license is not None and ref.license.redistribution == "allowed"
    ]

    # If none were left, every assertion above would hold with the feature broken.
    assert "datago.apt_trade" in confirmed
