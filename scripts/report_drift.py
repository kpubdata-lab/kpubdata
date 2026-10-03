"""Drift report — extracts "2 consecutive failures" datasets from smoke results.

Usage (the report job of GitHub Actions smoke.yml, or locally):
    gh run list --workflow=smoke.yml --limit 3   # prerequisite: smoke history
    GH_TOKEN=... uv run python scripts/report_drift.py [--dry-run]

Behavior:
1. Extracts the failing integration tests (datasets) from recent smoke runs
2. Selects only datasets that failed the last 2 consecutive runs
   (distinguishing transient outages from persistent drift)
3. For each dataset: updates the comment on an existing open drift issue,
   or files a new one
4. ``--dry-run`` prints the verdict without filing issues

Requires: gh CLI + a write-capable token (GH_TOKEN/GITHUB_TOKEN).
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field

REPO = "kpubdata-lab/kpubdata"
WORKFLOW = "smoke.yml"
# Integration test function name pattern: test_datago_village_fcst → datago.village_fcst
_TEST_RE = re.compile(r"FAILED\s+\S*test_(?P<provider>[a-z]+)_(?P<key>[a-z0-9_]+)\b")


@dataclass
class DriftReport:
    """Drift determination result."""

    consecutive_failures: list[str] = field(default_factory=list)
    recent_runs: list[dict[str, object]] = field(default_factory=list)


def _gh(args: list[str]) -> str:
    """Run gh CLI and return stdout."""
    proc = subprocess.run(
        ["gh", *args, "--repo", REPO],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        print(f"gh 오류: {proc.stderr.strip()[:200]}")
        return ""
    return proc.stdout


def _failed_datasets_from_run(run_id: str) -> set[str]:
    """Extract set of failed dataset ids from run's junit artifact.

    Logs are not reliably retained, so the (smoke-*) artifacts are the
    primary source.
    """
    import io
    import xml.etree.ElementTree as ET
    import zipfile

    listing = subprocess.run(
        ["gh", "api", f"repos/{REPO}/actions/runs/{run_id}/artifacts", "-q", ".artifacts[].id"],
        check=False,
        capture_output=True,
        text=True,
    )
    found: set[str] = set()
    for artifact_id in listing.stdout.split():
        proc = subprocess.run(
            [
                "gh",
                "api",
                f"repos/{REPO}/actions/artifacts/{artifact_id}/zip",
                "-H",
                "Accept: application/vnd.github+json",
            ],
            check=False,
            capture_output=True,
        )
        if proc.returncode != 0 or not proc.stdout:
            continue
        try:
            with zipfile.ZipFile(io.BytesIO(proc.stdout)) as archive:
                for name in archive.namelist():
                    if not name.endswith(".xml"):
                        continue
                    root = ET.fromstring(archive.read(name))
                    for case in root.iter("testcase"):
                        has_failure = any(child.tag in ("failure", "error") for child in case)
                        if not has_failure:
                            continue
                        match = _TEST_RE.search(
                            f"FAILED {case.get('classname', '')}.{case.get('name', '')}"
                        )
                        if match is None:
                            match = _TEST_RE.search(f"test_{case.get('name', '')}")
                        if match:
                            found.add(f"{match.group('provider')}.{match.group('key')}")
        except (zipfile.BadZipFile, ET.ParseError):
            continue
    return found


def collect(consecutive_required: int = 2, limit: int = 6) -> DriftReport:
    """Analyze recent smoke runs to determine N consecutive failure datasets."""
    listing = _gh(
        [
            "run",
            "list",
            "--workflow",
            WORKFLOW,
            "--limit",
            str(limit),
            "--json",
            "databaseId,status,conclusion,createdAt",
        ]
    )
    if not listing:
        return DriftReport()
    runs = [run for run in json.loads(listing) if run.get("conclusion")]
    failures_per_run: list[tuple[str, set[str]]] = []
    for run in runs:
        run_id = str(run["databaseId"])
        conclusion = str(run.get("conclusion"))
        if conclusion == "success":
            failures_per_run.append((run_id, set()))
        else:
            failures_per_run.append((run_id, _failed_datasets_from_run(run_id)))

    report = DriftReport(
        recent_runs=[{"id": rid, "failures": sorted(f)} for rid, f in failures_per_run]
    )
    if len(failures_per_run) < consecutive_required:
        return report

    _latest_id, latest = failures_per_run[0]
    for dataset in sorted(latest):
        streak = 0
        for _rid, failures in failures_per_run[:consecutive_required]:
            if dataset in failures:
                streak += 1
        if streak >= consecutive_required:
            report.consecutive_failures.append(dataset)
    return report


def _existing_drift_issue(dataset: str) -> int | None:
    """Find open drift issue number for dataset (one per dataset principle)."""
    out = _gh(
        ["issue", "list", "--search", f'"{dataset}" is:open label:drift', "--json", "number,title"]
    )
    if not out:
        return None
    issues = json.loads(out)
    for issue in issues:
        if dataset in str(issue.get("title", "")):
            return int(issue["number"])
    return None


def file_or_update(dataset: str, report: DriftReport, dry_run: bool) -> None:
    """Publish 2 consecutive failure datasets as issue or update existing issue."""
    title = f"[drift] {dataset} 실API 스모크 연속 실패"
    body_lines = [
        f"## 대상\n{dataset}",
        "",
        "## 증상",
        f"최근 {len(report.recent_runs)}회 스모크 중 직전 실행부터 연속 실패.",
    ]
    for run in report.recent_runs:
        failures = run.get("failures", [])
        mark = "실패" if failures else "성공"
        body_lines.append(f"- 실행 {run['id']}: {mark} {sorted(failures) if failures else ''}")
    dataset_key = dataset.split(".", 1)[1]
    reproduce = (
        "KPUBDATA_DATAGO_API_KEY=... uv run pytest -m integration "
        f"-k '{dataset_key}' tests/integration/test_datago_live.py"
    )
    body_lines += [
        "",
        "## 재현",
        f"`{reproduce}`",
        "",
        "## 수리 절차",
        "drift-fixer 에이전트 절차를 따른다 (fixture는 반드시 make record로 재기록).",
    ]
    body = "\n".join(body_lines)

    if dry_run:
        print(f"[dry-run] {title}")
        return

    existing = _existing_drift_issue(dataset)
    if existing is not None:
        _gh(
            [
                "issue",
                "comment",
                str(existing),
                "--body",
                "스모크 연속 실패 지속 (자동 갱신):\n" + body,
            ]
        )
        print(f"갱신: #{existing} {dataset}")
        return
    out = _gh(["issue", "create", "--title", title, "--body", body, "--label", "drift"])
    print(f"발행: {out.strip()} {dataset}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="스모크 드리프트 리포트")
    parser.add_argument("--dry-run", action="store_true", help="이슈 발행 없이 판정만")
    args = parser.parse_args(argv)

    report = collect()
    if not report.recent_runs:
        print("스모크 실행 기록이 부족하여 판정 불가 (최소 2회 필요)")
        return 0
    streak_text = report.consecutive_failures or "없음"
    print(f"최근 실행 {len(report.recent_runs)}회 분석 — 연속 실패: {streak_text}")
    for dataset in report.consecutive_failures:
        file_or_update(dataset, report, args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
