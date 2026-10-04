"""``DatasetRef.status`` reads the same table as SUPPORTED_DATA.md (#783).

A dataset awaiting an application looked the same at run time as one verified against
the live API. The status now ships with the package as ``dataset_status.json``; these
tests are the gate that keeps that file equal to the document it is generated from.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from kpubdata import Client, DatasetStatus
from kpubdata.core.status import SUPPORTED_DATA_LEVELS, dataset_status

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

ROW = "| {level} | 테스트 검증 | - | 공공데이터포털 (`datago`) | `{dataset}` | 이름 | 키 | [문서](https://x) | 비고 |"


class TestThePackagedMapMatchesTheDocument:
    def test_the_committed_file_is_what_the_generator_writes(self) -> None:
        assert gen.main(["--check"]) == 0

    def test_a_changed_level_fails_the_check(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        text = gen.DOC.read_text(encoding="utf-8")
        row = next(line for line in text.splitlines() if "`apt_trade`" in line)
        changed = tmp_path / "SUPPORTED_DATA.md"
        changed.write_text(
            text.replace(row, row.replace("| 지원 |", "| 활용신청 대기 |", 1)), encoding="utf-8"
        )
        monkeypatch.setattr(gen, "DOC", changed)

        assert gen.main(["--check"]) == 1

    def test_every_level_of_the_vocabulary_is_mapped(self) -> None:
        text = "\n".join(
            ROW.format(level=level, dataset=f"d{index}")
            for index, level in enumerate(SUPPORTED_DATA_LEVELS)
        )

        assert gen.build(text, {}) == {
            f"datago.d{index}": status.value
            for index, status in enumerate(SUPPORTED_DATA_LEVELS.values())
        }

    def test_an_unknown_level_is_an_error_not_a_missing_entry(self) -> None:
        with pytest.raises(ValueError, match="unknown SUPPORTED_DATA.md level '거의 지원'"):
            gen.build(ROW.format(level="거의 지원", dataset="x"), {})

    def test_a_spec_override_replaces_the_level(self) -> None:
        text = ROW.format(level="지원", dataset="x")

        assert gen.build(text, {"datago.x": "unstable"}) == {"datago.x": "unstable"}


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
