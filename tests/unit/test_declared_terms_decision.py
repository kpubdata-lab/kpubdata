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
