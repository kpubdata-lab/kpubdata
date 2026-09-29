"""SUPPORTED_DATA.md's level columns come from the evidence, and its table stays well-formed (#621).

"지원" means a recorded live-API response (`meta.json`). The level used to be typed by
hand and drifted both ways; the table also had rows with text after the closing pipe,
which GitHub drops, and rows with a cell too many or a pipe missing.
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path
from typing import Any

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


class TestTheDocument:
    def test_it_matches_the_evidence(self) -> None:
        text = (_ROOT / "SUPPORTED_DATA.md").read_text(encoding="utf-8")
        assert sync.sync(text, sync.recorded_dates(sync.FIXTURES)) == text, (
            "SUPPORTED_DATA.md differs from tests/fixtures — run scripts/sync_supported_data.py"
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


class TestTheRules:
    def test_a_recorded_dataset_is_supported_with_its_latest_recording_date(self) -> None:
        line = sync.sync_row(_row("스키마만", "테스트 검증", "-"), {("datago", "d"): "2026-09-09"})
        assert _levels(line) == ["지원", "실API 검증", "2026-09-09"]

    def test_supported_without_a_recording_is_schema_only(self) -> None:
        line = sync.sync_row(_row("지원", "실API 검증", "2025-04-15"), {})
        assert _levels(line) == ["스키마만", "테스트 검증", "-"]

    def test_a_human_judgement_is_kept(self) -> None:
        for level in ("활용신청 대기", "폐기", "진행 중"):
            assert _levels(sync.sync_row(_row(level, "테스트 검증", "-"), {}))[0] == level

    def test_text_after_the_closing_pipe_moves_into_the_note(self) -> None:
        line = sync.sync_row(_row("활용신청 대기", "테스트 검증", "-") + " — 활용신청 필요", {})
        assert line.endswith("| 비고 — 활용신청 필요 |")

    def test_a_cell_too_many_joins_the_note(self) -> None:
        line = sync.sync_row(_row("스키마만", "테스트 검증", "-")[:-1] + "| 실측 |", {})
        assert line.endswith("| 비고 — 실측 |")
        assert len(re.split(r"(?<!\\)\|", line.strip())[1:-1]) == sync.COLUMNS

    def test_a_missing_pipe_between_date_and_provider_is_restored(self) -> None:
        glued = "| 폐기 | 폐기 확인 | 2026-09-10  공공데이터포털 (`datago`) | `g2b` | 이름 | 키 | [문서](https://x) | 비고 |"
        assert _levels(sync.sync_row(glued, {})) == ["폐기", "폐기 확인", "2026-09-10"]

    def test_recorded_dates_take_the_latest_recording(self, tmp_path: Path) -> None:
        for name, when in (("a", "2026-01-01T00:00:00+00:00"), ("b", "2026-03-01T00:00:00+00:00")):
            meta = tmp_path / "datago" / "d" / f"{name}.meta.json"
            meta.parent.mkdir(parents=True, exist_ok=True)
            meta.write_text(json.dumps({"recorded_at": when}), encoding="utf-8")
        assert sync.recorded_dates(tmp_path) == {("datago", "d"): "2026-03-01"}
