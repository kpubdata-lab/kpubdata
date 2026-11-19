"""The monthly report quotes the status snapshot's per-family pass rate (#899)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load() -> Any:
    path = REPO_ROOT / "scripts" / "monthly_report.py"
    spec = importlib.util.spec_from_file_location("_monthly_report", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_monthly_report"] = module
    spec.loader.exec_module(module)
    return module


report = _load()


def test_report_lists_every_family_and_the_as_of_date(monkeypatch: Any) -> None:
    monkeypatch.setattr(report, "collect_drift_issues", lambda month: [])
    families = report.collect_spec_status()["family_pass_rate"]
    text = report.build_report("2026-10", as_of="2026-10-11")
    assert "기준일: 2026-10-11" in text
    for name, f in families.items():
        assert f"| {name} | {f['total']} | {f['live_passing']} | {f['pass_rate']}% |" in text


def test_failed_issue_lookup_does_not_mean_no_drift(monkeypatch: pytest.MonkeyPatch) -> None:
    result = subprocess.CompletedProcess(
        args=["gh"], returncode=1, stdout="", stderr="private-canary"
    )
    monkeypatch.setattr(report.subprocess, "run", lambda *args, **kwargs: result)
    with pytest.raises(RuntimeError, match="evidence") as caught:
        report.collect_drift_issues("2026-10")
    assert "private-canary" not in str(caught.value)


def test_missing_gh_is_unavailable_evidence(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*args: object, **kwargs: object) -> None:
        raise FileNotFoundError("private-canary")

    monkeypatch.setattr(report.subprocess, "run", missing)
    with pytest.raises(RuntimeError, match="evidence") as caught:
        report.collect_drift_issues("2026-10")
    assert "private-canary" not in str(caught.value)


@pytest.mark.parametrize("payload", ["", "not-json", "{}", '[{"number": 1}]'])
def test_invalid_issue_evidence_is_rejected(payload: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report, "_gh", lambda args: payload)
    with pytest.raises(RuntimeError, match="evidence"):
        report.collect_drift_issues("2026-10")


def test_verified_empty_issue_result_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report, "_gh", lambda args: "[]")
    assert report.collect_drift_issues("2026-10") == []


def test_failed_report_keeps_the_existing_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    target = tmp_path / "docs/internal/monthly-2026-10.md"
    target.parent.mkdir(parents=True)
    target.write_text("previous evidence")
    monkeypatch.setattr(report, "REPO_ROOT", tmp_path)
    result = subprocess.CompletedProcess(
        args=["gh"], returncode=1, stdout="", stderr="private-canary"
    )
    monkeypatch.setattr(report.subprocess, "run", lambda *args, **kwargs: result)
    assert report.main(["--month", "2026-10"]) == 1
    assert target.read_text() == "previous evidence"
    assert "private-canary" not in capsys.readouterr().err


def test_undated_pilot_rows_include_skips(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "docs/internal/pilot-log.md"
    target.parent.mkdir(parents=True)
    target.write_text("| 1 | #1 | test.a | 1 | ✅ |\n| 2 | #2 | test.b | - | ➖ |\n")
    monkeypatch.setattr(report, "REPO_ROOT", tmp_path)
    assert report.collect_pilot_stats("2026-10") == {
        "total": 2,
        "passed": 1,
        "skipped": 1,
        "failed": 0,
    }


def test_report_distinguishes_snapshot_and_cumulative_from_monthly_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(report, "collect_drift_issues", lambda month: [])
    monkeypatch.setattr(
        report, "collect_spec_status", lambda: {"generated_at": "2026-10-12T03:39:19+00:00"}
    )
    text = report.build_report("2026-10")
    assert "날짜 없는 누적 기록" in text
    assert "2026-10-12T03:39:19+00:00" in text
    assert "월간 실행 통과율은 계산하지 않습니다" in text


def test_issue_limit_is_explicit_and_saturated_results_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import json

    arguments: list[str] = []

    def saturated(args: list[str]) -> str:
        arguments.extend(args)
        return json.dumps([{"number": n, "title": "drift", "state": "OPEN"} for n in range(1000)])

    monkeypatch.setattr(report, "_gh", saturated)
    with pytest.raises(RuntimeError, match="truncated"):
        report.collect_drift_issues("2026-10")
    assert arguments[arguments.index("--limit") + 1] == "1000"


def test_nonempty_issue_evidence_is_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    title = "[drift] datago.hospital_info: live_verified → unstable (UNKNOWN)"
    monkeypatch.setattr(
        report, "_gh", lambda args: json.dumps([{"number": 943, "title": title, "state": "OPEN"}])
    )
    assert report.collect_drift_issues("2026-10") == [
        {"number": 943, "title": title, "state": "OPEN"}
    ]


def test_drift_issues_are_found_by_title_not_by_a_missing_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No `drift` label exists; filtering on it made every month read as no drift (#899)."""
    arguments: list[str] = []

    def answer(args: list[str]) -> str:
        arguments.extend(args)
        return json.dumps(
            [
                {
                    "number": 951,
                    "title": "[drift] datago.bus_arrival: x → y (Z)",
                    "state": "CLOSED",
                },
                {"number": 7, "title": "docs: explain drift detection", "state": "OPEN"},
            ]
        )

    monkeypatch.setattr(report, "_gh", answer)
    issues = report.collect_drift_issues("2026-10")

    assert [issue["number"] for issue in issues] == [951]
    assert "--label" not in arguments
    search = arguments[arguments.index("--search") + 1]
    assert "created:2026-10" in search and "in:title" in search


def test_missing_local_inputs_are_not_zero_measurements(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(report, "collect_drift_issues", lambda month: [])
    monkeypatch.setattr(report, "collect_spec_status", lambda: {})
    monkeypatch.setattr(report, "collect_pilot_stats", lambda month: {})
    text = report.build_report("2026-10", as_of="2026-10-11")
    assert "파일럿 로그 없음" in text
    assert "데이터셋 상태 스냅샷 없음" in text
    assert "catalogue: unknown" in text
    assert "기록 0건" not in text
    assert "표시용" in text
    assert "게이트 완화 검토" not in text
