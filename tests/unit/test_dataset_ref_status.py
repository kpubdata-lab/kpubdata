"""``DatasetRef.status`` reads the same table as SUPPORTED_DATA.md (#783).

A dataset awaiting an application looked the same at run time as one verified against
the live API. The status now ships with the package as ``dataset_status.json``; these
tests are the gate that keeps that file equal to the metadata it is generated from.

#842 split the one name into two axes that do not move each other: how far a dataset
has been checked (``verification``) and whether the provider wants an application
(``application_requirement``). ``status`` stays as it was for those who read it.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

from kpubdata import ApplicationRequirement, Client, DatasetStatus, VerificationLevel
from kpubdata.core.status import (
    SUPPORTED_DATA_LEVELS,
    application_requirement,
    dataset_status,
    dataset_verification,
)

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = _ROOT / "scripts"


def _load() -> Any:
    # The generator imports its sibling ``sync_supported_data`` as a script would.
    sys.path.insert(0, str(_SCRIPTS))
    try:
        spec = importlib.util.spec_from_file_location(
            "_gen_dataset_status", _SCRIPTS / "gen_dataset_status.py"
        )
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        sys.path.remove(str(_SCRIPTS))


gen = _load()


def _entry(level: str, verification: str | None = "fixture_verified") -> dict[str, str | None]:
    return {"level": level, "verification": verification, "checked_on": None}


class TestThePackagedMapMatchesTheMetadata:
    def test_the_committed_file_is_what_the_generator_writes(self) -> None:
        assert gen.main(["--check"]) == 0

    def test_a_changed_level_fails_the_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        metadata = json.loads(gen.METADATA.read_text(encoding="utf-8"))
        metadata["datago.apt_trade"]["level"] = "application_required"
        changed = tmp_path / "dataset_metadata.json"
        changed.write_text(json.dumps(metadata), encoding="utf-8")
        monkeypatch.setattr(gen, "METADATA", changed)

        assert gen.main(["--check"]) == 1

    def test_every_level_of_the_vocabulary_is_mapped(self) -> None:
        metadata = {
            f"datago.d{index}": _entry(status.value)
            for index, status in enumerate(SUPPORTED_DATA_LEVELS.values())
        }

        assert gen.build(metadata, {}) == {key: entry["level"] for key, entry in metadata.items()}

    def test_an_unknown_level_is_an_error_not_a_missing_entry(self) -> None:
        with pytest.raises(ValueError, match="datago.x: unknown dataset_metadata level 'almost'"):
            gen.build({"datago.x": _entry("almost")}, {})

    def test_a_spec_override_replaces_the_level(self) -> None:
        assert gen.build({"datago.x": _entry("live_verified")}, {"datago.x": "unstable"}) == {
            "datago.x": "unstable"
        }

    def test_the_metadata_lists_the_datasets_the_status_map_does(self) -> None:
        metadata = json.loads(gen.METADATA.read_text(encoding="utf-8"))
        statuses = json.loads(gen.OUTPUT.read_text(encoding="utf-8"))

        assert sorted(metadata) == sorted(statuses)
        assert all(
            sorted(entry) == ["checked_on", "level", "verification"] for entry in metadata.values()
        )


@pytest.fixture(scope="module")
def client() -> Client:
    return Client(provider_keys={}, env_keys=False)


class TestDatasetRefStatus:
    def test_statuses_tell_datasets_apart(self, client: Client) -> None:
        assert client.dataset("datago.apt_trade").ref.status is DatasetStatus.LIVE_VERIFIED
        assert client.dataset("datago.rh_trade").ref.status is DatasetStatus.APPLICATION_REQUIRED

    def test_a_spec_marked_unstable_says_so(self, client: Client) -> None:
        assert client.dataset("datago.ocean_buoy").ref.status is DatasetStatus.UNSTABLE

    def test_every_discovered_dataset_has_a_status_except_the_escape_hatch(
        self, client: Client
    ) -> None:
        without = sorted(ref.id for ref in client.datasets.list() if ref.status is None)

        assert without == ["datago.generic"]

    def test_an_unlisted_dataset_is_unknown_not_verified(self) -> None:
        assert dataset_status("nowhere.nothing") is None


class TestVerificationAndApplicationAreSeparateAxes:
    def test_an_awaited_application_does_not_hide_the_verification(self, client: Client) -> None:
        ref = client.dataset("datago.rh_trade").ref

        assert ref.status is DatasetStatus.APPLICATION_REQUIRED
        assert ref.verification is VerificationLevel.FIXTURE_VERIFIED
        assert ref.application_requirement is ApplicationRequirement.REQUIRED

    def test_a_live_verified_dataset_says_nothing_it_does_not_know(self, client: Client) -> None:
        ref = client.dataset("datago.apt_trade").ref

        assert ref.verification is VerificationLevel.LIVE_VERIFIED
        # Nothing recorded says whether an application is needed: unknown, not "none".
        assert ref.application_requirement is ApplicationRequirement.UNKNOWN

    def test_a_fault_leaves_the_verification_as_recorded(self, client: Client) -> None:
        ref = client.dataset("datago.ocean_buoy").ref

        assert ref.status is DatasetStatus.UNSTABLE
        assert ref.verification is VerificationLevel.IN_PROGRESS

    def test_a_retired_dataset_is_not_checked(self) -> None:
        assert dataset_status("datago.g2b_contract") is DatasetStatus.RETIRED
        assert dataset_verification("datago.g2b_contract") is None

    def test_an_unlisted_dataset_is_unknown_on_both_axes(self, client: Client) -> None:
        ref = client.dataset("datago.generic").ref

        assert ref.verification is None
        assert ref.application_requirement is ApplicationRequirement.UNKNOWN

    def test_a_declared_requirement_decides_whatever_the_level(self) -> None:
        # A dataset can need an application and be verified: the two do not exclude.
        assert (
            application_requirement("datago.apt_trade", {"required": True})
            is ApplicationRequirement.REQUIRED
        )
        assert (
            application_requirement("datago.rh_trade", {"required": False})
            is ApplicationRequirement.NOT_REQUIRED
        )

    def test_a_declaration_without_the_flag_decides_nothing(self) -> None:
        for declared in (None, {}, {"required": "yes"}, {"url": "https://x"}, "required"):
            assert (
                application_requirement("datago.apt_trade", declared)
                is ApplicationRequirement.UNKNOWN
            )

    def test_every_listed_dataset_has_one_value_on_each_axis(self, client: Client) -> None:
        for ref in client.datasets.list():
            assert isinstance(ref.application_requirement, ApplicationRequirement)
            if ref.status is DatasetStatus.APPLICATION_REQUIRED:
                assert ref.application_requirement is ApplicationRequirement.REQUIRED
                assert ref.verification is not None

    def test_the_verification_names_are_status_names(self) -> None:
        # One vocabulary: a consumer comparing the two strings is not misled.
        assert {level.value for level in VerificationLevel} <= {s.value for s in DatasetStatus}

    def test_the_license_is_not_inferred_from_either_axis(self, client: Client) -> None:
        # Verified is not "free to redistribute": the licence stays what the spec declares.
        for ref in client.datasets.list():
            payload = ref.to_dict()
            if ref.license is None:
                assert payload["license"] is None
            assert payload["verification"] == (
                None if ref.verification is None else ref.verification.value
            )
            assert payload["application_requirement"] == ref.application_requirement.value
