"""SUPPORTED_DATA.md's level columns come from the evidence, and its table stays well-formed (#621).

Since #842 the evidence is written into ``dataset_metadata.json`` first and the document
from that file, so the package and the document answer from one source.

The "supported" level means a recorded live-API response (`meta.json`). The level used to be typed by
hand and drifted both ways; the table also had rows with text after the closing pipe,
which GitHub drops, and rows with a cell too many or a pipe missing.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "sync_supported_data.py"


def _load() -> Any:
    spec = importlib.util.spec_from_file_location("_sync_supported_data", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sync = _load()

ROW = "| {level} | {check} | {date} | 공공데이터포털 (`{provider}`) | `{dataset}` | 이름 | 키 | [문서](https://x) | 비고 |"


def _row(level: str, check: str, date: str, provider: str = "datago", dataset: str = "d") -> str:
    return ROW.format(level=level, check=check, date=date, provider=provider, dataset=dataset)


def _levels(line: str) -> list[str]:
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", line.strip())[1:4]]


def _entry(level: str, verification: str | None, checked_on: str | None = None) -> dict:
    return {"level": level, "verification": verification, "checked_on": checked_on}


class TestTheDocument:
    def test_the_metadata_matches_the_evidence(self) -> None:
        metadata = sync.load_metadata()
        assert sync.refresh(metadata, sync.recorded_dates(sync.FIXTURES)) == metadata, (
            "dataset_metadata.json differs from tests/fixtures — run scripts/sync_supported_data.py"
        )

    def test_it_matches_the_metadata(self) -> None:
        text = (_ROOT / "SUPPORTED_DATA.md").read_text(encoding="utf-8")
        assert sync.sync(text, sync.load_metadata()) == text, (
            "SUPPORTED_DATA.md differs from dataset_metadata.json — "
            "run scripts/sync_supported_data.py"
        )

    def test_every_dataset_row_has_nine_cells_and_closes_its_last_one(self) -> None:
        text = (_ROOT / "SUPPORTED_DATA.md").read_text(encoding="utf-8")
        bad = [
            (number, line[:80])
            for number, line in enumerate(text.split("\n"), 1)
            if sync.DATASET_ROW.match(line.strip())
            and (
                not line.rstrip().endswith("|")
                or len(re.split(r"(?<!\\)\|", line.strip())[1:-1]) != sync.COLUMNS
            )
        ]
        assert bad == []

    def test_every_level_cell_is_one_the_metadata_can_write(self) -> None:
        # A provider glued into the date cell once passed as a "date" (#842).
        text = (_ROOT / "SUPPORTED_DATA.md").read_text(encoding="utf-8")
        rows = [
            sync.split_cells(line)
            for line in text.split("\n")
            if sync.DATASET_ROW.match(line.strip())
        ]
        assert rows
        for cells in rows:
            assert cells[0] in sync.LEVEL_LABELS.values()
            assert cells[1] in {*sync.VERIFICATION_LABELS.values(), sync.RETIREMENT_CONFIRMED}
            assert re.fullmatch(r"-|\d{4}-\d{2}-\d{2}", cells[2])


class TestTheRules:
    def test_a_recorded_dataset_is_live_verified_on_its_latest_recording_date(self) -> None:
        metadata = {"datago.d": _entry("application_required", "fixture_verified")}

        refreshed = sync.refresh(metadata, {("datago", "d"): "2026-09-09"})

        assert refreshed == {"datago.d": _entry("live_verified", "live_verified", "2026-09-09")}
        assert _levels(sync.sync_row(_row("스키마만", "테스트 검증", "-"), refreshed)) == [
            "지원",
            "실API 검증",
            "2026-09-09",
        ]

    def test_live_verified_without_a_recording_is_fixture_verified(self) -> None:
        metadata = {"datago.d": _entry("live_verified", "live_verified", "2025-04-15")}

        refreshed = sync.refresh(metadata, {})

        assert refreshed == {"datago.d": _entry("fixture_verified", "fixture_verified")}
        assert _levels(sync.sync_row(_row("지원", "실API 검증", "2025-04-15"), refreshed)) == [
            "스키마만",
            "테스트 검증",
            "-",
        ]

    def test_a_human_judgement_is_kept(self) -> None:
        for level, label in (
            ("application_required", "활용신청 대기"),
            ("retired", "폐기"),
            ("in_progress", "진행 중"),
        ):
            metadata = {"datago.d": _entry(level, "fixture_verified")}
            assert sync.refresh(metadata, {}) == metadata
            assert _levels(sync.sync_row(_row("지원", "실API 검증", "-"), metadata))[0] == label

    def test_an_application_does_not_hide_the_verification(self) -> None:
        metadata = {"datago.d": _entry("application_required", "fixture_verified")}

        assert _levels(sync.sync_row(_row("지원", "-", "-"), metadata)) == [
            "활용신청 대기",
            "테스트 검증",
            "-",
        ]

    def test_a_retired_dataset_shows_when_its_retirement_was_confirmed(self) -> None:
        metadata = {"datago.d": _entry("retired", None, "2026-09-10")}

        assert sync.refresh(metadata, {}) == metadata
        assert _levels(sync.sync_row(_row("지원", "실API 검증", "-"), metadata)) == [
            "폐기",
            "폐기 확인",
            "2026-09-10",
        ]

    def test_the_document_cannot_overrule_the_metadata(self) -> None:
        metadata = {"datago.d": _entry("application_required", "fixture_verified")}

        line = sync.sync_row(_row("지원", "실API 검증", "2026-01-01"), metadata)

        assert _levels(line) == ["활용신청 대기", "테스트 검증", "-"]

    def test_a_row_without_a_metadata_entry_is_an_error(self) -> None:
        with pytest.raises(ValueError, match="datago.d: a row in SUPPORTED_DATA.md with no"):
            sync.sync_row(_row("지원", "실API 검증", "-"), {})

    def test_a_metadata_entry_without_a_row_is_an_error(self) -> None:
        metadata = {"datago.d": _entry("fixture_verified", "fixture_verified")}

        with pytest.raises(ValueError, match="no SUPPORTED_DATA.md row.*datago.d"):
            sync.sync("# 제목\n", metadata)

    def test_text_after_the_closing_pipe_moves_into_the_note(self) -> None:
        metadata = {"datago.d": _entry("application_required", "fixture_verified")}
        line = sync.sync_row(
            _row("활용신청 대기", "테스트 검증", "-") + " — 활용신청 필요", metadata
        )
        assert line.endswith("| 비고 — 활용신청 필요 |")

    def test_a_cell_too_many_joins_the_note(self) -> None:
        metadata = {"datago.d": _entry("fixture_verified", "fixture_verified")}
        line = sync.sync_row(_row("스키마만", "테스트 검증", "-")[:-1] + "| 실측 |", metadata)
        assert line.endswith("| 비고 — 실측 |")
        assert len(re.split(r"(?<!\\)\|", line.strip())[1:-1]) == sync.COLUMNS

    def test_a_missing_pipe_between_date_and_provider_is_restored(self) -> None:
        glued = "| 폐기 | 폐기 확인 | 2026-09-10  공공데이터포털 (`datago`) | `g2b` | 이름 | 키 | [문서](https://x) | 비고 |"
        metadata = {"datago.g2b": _entry("retired", None, "2026-09-10")}
        line = sync.sync_row(glued, metadata)
        assert _levels(line) == ["폐기", "폐기 확인", "2026-09-10"]
        assert "| 공공데이터포털 (`datago`) | `g2b` |" in line

    def test_recorded_dates_take_the_latest_recording(self, tmp_path: Path) -> None:
        for name, when in (("a", "2026-01-01T00:00:00+00:00"), ("b", "2026-03-01T00:00:00+00:00")):
            meta = tmp_path / "datago" / "d" / f"{name}.meta.json"
            meta.parent.mkdir(parents=True, exist_ok=True)
            meta.write_text(json.dumps({"recorded_at": when}), encoding="utf-8")
        assert sync.recorded_dates(tmp_path) == {("datago", "d"): "2026-03-01"}
