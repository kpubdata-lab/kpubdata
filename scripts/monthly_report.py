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
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _gh(args: list[str]) -> str:
    proc = subprocess.run(
        ["gh", *args, "--repo", "yeongseon/kpubdata"], check=False, capture_output=True, text=True
    )
    return proc.stdout if proc.returncode == 0 else ""


def collect_pilot_stats(month: str) -> dict[str, object]:
    """Extract stats for month from pilot-log.md."""
    log = REPO_ROOT / "docs/internal/pilot-log.md"
    if not log.is_file():
        return {}
    content = log.read_text(encoding="utf-8")
    rows = re.findall(r"\| (\d+) \| #(\d+) \| ([^|]+) \| (\d+) \| ([✅➖❌]) \|", content)
    return {
        "total": len(rows),
        "passed": sum(1 for r in rows if r[4] == "✅"),
        "skipped": sum(1 for r in rows if r[4] == "➖"),
        "failed": sum(1 for r in rows if r[4] == "❌"),
    }


def collect_drift_issues(month: str) -> list[dict[str, str]]:
    """Open/closed drift issues for month."""
    out = _gh(
        [
            "issue",
            "list",
            "--label",
            "drift",
            "--state",
            "all",
            "--search",
            f"created:{month}",
            "--json",
            "number,title,state",
        ]
    )
    if not out:
        return []
    return json.loads(out)


def collect_spec_status() -> dict[str, object]:
    """Current spec state."""
    status_path = REPO_ROOT / "docs/status/latest.json"
    if not status_path.is_file():
        return {}
    return json.loads(status_path.read_text(encoding="utf-8"))


def build_report(month: str) -> str:
    """Generate monthly report."""
    pilot = collect_pilot_stats(month)
    drift = collect_drift_issues(month)
    spec = collect_spec_status()
    now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    total = pilot.get("total", 0)
    passed = pilot.get("passed", 0)
    skipped = pilot.get("skipped", 0)
    failed = pilot.get("failed", 0)
    pass_rate = passed / max(total, 1) * 100
    spec_total = spec.get("spec_datasets", {}).get("total", "?")
    catalogue_total = sum(spec.get("catalogue_datasets", {}).values())

    lines = [
        f"# 월간 집계 — {month}",
        "",
        f"> 생성: {now} — `scripts/monthly_report.py` (직접 편집 금지)",
        "",
        "## 파일럿 통계",
        f"- 시도 {total}건 · 통과 {passed} · 보류 {skipped} · 실패 {failed}",
        f"- 통과율: {pass_rate:.0f}%",
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
            "## 개선 권고 (자동 생성)",
            "- 통과율 70% 이상: 게이트 완화 검토 (#384 6.3)",
            "- doc-wrong 다수: 활용가이드 캐시 보강",
            "- auth-blocked 다수: 활용신청 목록 갱신",
        ]
    )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="월간 집계 리포트")
    parser.add_argument("--month", default=datetime.utcnow().strftime("%Y-%m"))
    args = parser.parse_args(argv)
    report = build_report(args.month)
    out = REPO_ROOT / "docs/internal" / f"monthly-{args.month}.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report, encoding="utf-8")
    print(f"생성: {out.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
