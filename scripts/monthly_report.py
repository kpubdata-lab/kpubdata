"""Monthly aggregation report (#384 6.5) — synthesizes pilot-log + drift issues + status page.

Usage:
    uv run python scripts/monthly_report.py [--month 2026-09]

Output: docs/internal/monthly-{month}.md — failure-cause distribution,
pass rate, improvement advice.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

REPO_ROOT = Path(__file__).resolve().parents[1]
_DRIFT_ISSUE_LIMIT = 1000


class DriftIssue(TypedDict):
    """The issue fields used as report evidence."""

    number: int
    title: str
    state: str


def _gh(args: list[str]) -> str:
    try:
        proc = subprocess.run(
            ["gh", *args, "--repo", "kpubdata-lab/kpubdata"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as error:
        raise RuntimeError("Drift issue evidence is unavailable") from error
    if proc.returncode != 0:
        raise RuntimeError("Drift issue evidence is unavailable")
    return proc.stdout


def collect_pilot_stats(month: str) -> dict[str, object]:
    """Count cumulative undated pilot entries, which cannot be assigned to a month."""
    log = REPO_ROOT / "docs/internal/pilot-log.md"
    if not log.is_file():
        return {}
    content = log.read_text(encoding="utf-8")
    rows = re.findall(r"\| (\d+) \| #(\d+) \| ([^|]+) \| (\d+|-) \| ([✅➖❌]) \|", content)
    return {
        "total": len(rows),
        "passed": sum(1 for r in rows if r[4] == "✅"),
        "skipped": sum(1 for r in rows if r[4] == "➖"),
        "failed": sum(1 for r in rows if r[4] == "❌"),
    }


def collect_drift_issues(month: str) -> list[DriftIssue]:
    """Open/closed drift issues for month."""
    out = _gh(
        [
            "issue",
            "list",
            "--label",
            "drift",
            "--state",
            "all",
            "--limit",
            str(_DRIFT_ISSUE_LIMIT),
            "--search",
            f"created:{month}",
            "--json",
            "number,title,state",
        ]
    )
    try:
        data: object = json.loads(out)
    except json.JSONDecodeError as error:
        raise RuntimeError("Drift issue evidence is invalid") from error
    if not isinstance(data, list):
        raise RuntimeError("Drift issue evidence is invalid")
    if len(data) >= _DRIFT_ISSUE_LIMIT:
        raise RuntimeError("Drift issue evidence may be truncated")
    issues: list[DriftIssue] = []
    for item in data:
        if not isinstance(item, dict):
            raise RuntimeError("Drift issue evidence is invalid")
        number, title, state = item.get("number"), item.get("title"), item.get("state")
        if (
            not isinstance(number, int)
            or isinstance(number, bool)
            or not isinstance(title, str)
            or not isinstance(state, str)
            or state.lower() not in {"open", "closed"}
        ):
            raise RuntimeError("Drift issue evidence is invalid")
        issues.append({"number": number, "title": title, "state": state})
    return issues


def collect_spec_status() -> dict[str, object]:
    """Current spec state."""
    status_path = REPO_ROOT / "docs/status/latest.json"
    if not status_path.is_file():
        return {}
    return json.loads(status_path.read_text(encoding="utf-8"))


def _family_lines(families: dict[str, dict[str, object]]) -> list[str]:
    """Per-family pass-rate rows, copied from the status snapshot."""
    return [
        f"| {name} | {f['total']} | {f['live_passing']} | {f['pass_rate']}% | "
        f"{f['fixture_passing']} | {f['fixture_pass_rate']}% |"
        for name, f in families.items()
    ]


def build_report(month: str, as_of: str | None = None) -> str:
    """Generate monthly report."""
    pilot = collect_pilot_stats(month)
    drift = collect_drift_issues(month)
    spec = collect_spec_status()
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    families = spec.get("family_pass_rate", {})

    total = pilot.get("total", 0)
    passed = pilot.get("passed", 0)
    skipped = pilot.get("skipped", 0)
    failed = pilot.get("failed", 0)
    pass_rate = passed / max(total, 1) * 100
    spec_total = spec.get("spec_datasets", {}).get("total", "?")
    catalogue_total = sum(spec.get("catalogue_datasets", {}).values()) if spec else "unknown"

    lines = [
        f"# 월간 집계 — {month}",
        "",
        f"> 생성: {now} — `scripts/monthly_report.py` (직접 편집 금지)",
        *(
            [f"> 기준일: {as_of} (표시용 — 원천 증거를 이 날짜의 상태로 복원하지 않습니다)"]
            if as_of
            else []
        ),
        "",
        "## 증거 범위",
        "- 월별 집계는 생성일로 조회한 드리프트 이슈에만 적용합니다. "
        "이슈 상태는 조회 시점의 값입니다.",
        "- 파일럿 로그는 날짜 없는 누적 기록으로, 해당 월의 실행 실적이 아닙니다.",
        f"- 데이터셋 상태 스냅샷 생성 시각: {spec.get('generated_at', 'unknown')}. "
        "월말 상태나 현재 API 가용성을 입증하지 않습니다.",
        *([] if spec else ["- 데이터셋 상태 스냅샷 없음: 상태 집계 불가."]),
        "- 월별 fixture/probe/live API 실행과 키·runner 부재를 구분할 실행 증거가 없어 "
        "월간 실행 통과율은 계산하지 않습니다.",
        "",
        "## 파일럿 누적 통계",
        *(
            [
                f"- 기록 {total}건 · 통과 {passed} · 보류 {skipped} · 실패 {failed}",
                f"- 누적 기록 중 통과 비율 (보류 포함): {pass_rate:.0f}%",
            ]
            if pilot
            else ["- 파일럿 로그 없음: 누적 집계 불가."]
        ),
        "",
        "## 드리프트 이슈",
    ]
    if drift:
        for issue in drift:
            state = "종료" if issue["state"].lower() == "closed" else "열림"
            title = issue["title"][:60]
            lines.append(f"- #{issue['number']} [{state}] {title}")
    else:
        lines.append("- 해당 월 없음")

    lines.extend(
        [
            "",
            "## 데이터셋 상태",
            f"- spec: {spec_total}종",
            f"- catalogue: {catalogue_total}종",
            "",
            "## 계열별 통과율",
            "- 원천: `docs/status/latest.json` 의 `family_pass_rate` "
            "(`scripts/gen_status_page.py` 가 `dataset_metadata.json` 에서 계산)",
            "- 분모는 스냅샷에 등록된 계열별 데이터셋 수입니다. "
            "실행 횟수 기준의 월간 통과율이 아닙니다.",
            "",
            "| 계열 | 전체 | 실API 검증 기록 | 기록 비율 | 테스트 검증 기록 | 기록 비율 |",
            "|---|---|---|---|---|---|",
            *_family_lines(families),
            "",
            "## 개선 권고 (자동 생성)",
            "- 자동 집계만으로 검증 게이트를 바꾸지 않고 필요한 실행 증거를 먼저 확인합니다.",
            "- doc-wrong 다수: 활용가이드 캐시 보강",
            "- auth-blocked 다수: 활용신청 목록 갱신",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="월간 집계 리포트")
    parser.add_argument("--month", default=datetime.now(UTC).strftime("%Y-%m"))
    parser.add_argument(
        "--as-of", help="reference date label only, not historical evidence (YYYY-MM-DD)"
    )
    args = parser.parse_args(argv)
    try:
        report = build_report(args.month, args.as_of)
    except RuntimeError:
        print(
            "Report not written: drift issue evidence is unavailable or invalid.", file=sys.stderr
        )
        return 1
    out = REPO_ROOT / "docs/internal" / f"monthly-{args.month}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"생성: {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
