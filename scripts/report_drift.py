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

The run ends with one verdict, printed as ``verdict=<name>``, and an exit status (#859):

==================== ====== ======================================================
verdict              status meaning
==================== ====== ======================================================
ok                   0      the last runs were read and no dataset failed twice
drift                0      datasets failed twice in a row, and each was reported
insufficient_history 0      fewer completed runs exist than a streak needs
undetermined         2      the runs or their results could not be read
report_failed        1      drift was found and an issue could not be filed
==================== ====== ======================================================

A failed ``gh`` call used to be read as an empty answer: a 403 on the run list ended as
"not enough history", and a failed ``gh issue create`` printed that the issue was
filed. Nothing is read as empty now — a call that fails, an answer that cannot be
parsed, and a failed run whose results cannot be found all end ``undetermined``, and a
dataset is never called healthy on the strength of a run nobody could read.

Requires: gh CLI + a token with ``actions: read`` and ``issues: write``
(GH_TOKEN/GITHUB_TOKEN).
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


class UndeterminedError(Exception):
    """The runs or their results could not be read, so no verdict can be given."""


class ReportFailedError(Exception):
    """Drift was found and telling anyone about it failed."""


@dataclass
class DriftReport:
    """Drift determination result."""

    consecutive_failures: list[str] = field(default_factory=list)
    recent_runs: list[dict[str, object]] = field(default_factory=list)
    #: Completed runs found. Fewer than a streak needs is "not enough history", which
    #: is not the same as a list that could not be read.
    completed_runs: int = 0


def _gh(args: list[str]) -> str:
    """Run gh CLI and return stdout.

    Raises:
        UndeterminedError: ``gh`` exited non-zero. Its message is cut short and carries
            no token: ``gh`` does not print one.
    """
    proc = subprocess.run(
        ["gh", *args, "--repo", REPO],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise UndeterminedError(f"gh {args[0]} {args[1]} 실패: {proc.stderr.strip()[:200]}")
    return proc.stdout


def _json(text: str, what: str) -> object:
    try:
        return json.loads(text)
    except ValueError as error:
        raise UndeterminedError(f"{what} 응답을 해석할 수 없음: {error}") from error


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
    if listing.returncode != 0:
        raise UndeterminedError(
            f"실행 {run_id} 의 아티팩트 목록 조회 실패: {listing.stderr.strip()[:200]}"
        )
    artifact_ids = listing.stdout.split()
    if not artifact_ids:
        # The run failed and left no results: which datasets failed is not known. That
        # is not the same as "none did".
        raise UndeterminedError(f"실패한 실행 {run_id} 에 결과 아티팩트가 없음")
    found: set[str] = set()
    read_any = False
    for artifact_id in artifact_ids:
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
            raise UndeterminedError(f"실행 {run_id} 의 아티팩트 {artifact_id} 를 내려받지 못함")
        try:
            with zipfile.ZipFile(io.BytesIO(proc.stdout)) as archive:
                for name in archive.namelist():
                    if not name.endswith(".xml"):
                        continue
                    root = ET.fromstring(archive.read(name))
                    read_any = True
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
        except (zipfile.BadZipFile, ET.ParseError) as error:
            raise UndeterminedError(
                f"실행 {run_id} 의 아티팩트 {artifact_id} 를 해석할 수 없음: {type(error).__name__}"
            ) from error
    if not read_any:
        raise UndeterminedError(f"실패한 실행 {run_id} 의 아티팩트에 테스트 결과(xml)가 없음")
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
    loaded = _json(listing, "실행 목록")
    if not isinstance(loaded, list):
        raise UndeterminedError("실행 목록 응답이 배열이 아님")
    runs = [run for run in loaded if isinstance(run, dict) and run.get("conclusion")]
    if len(runs) < consecutive_required:
        # Really too few completed runs — the list itself was read.
        return DriftReport(completed_runs=len(runs))
    failures_per_run: list[tuple[str, set[str]]] = []
    # Only the runs a streak is counted over are read: a run outside that window that
    # cannot be read must not stop a verdict it has no part in.
    for run in runs[:consecutive_required]:
        run_id = str(run["databaseId"])
        conclusion = str(run.get("conclusion"))
        if conclusion == "success":
            failures_per_run.append((run_id, set()))
        else:
            failures_per_run.append((run_id, _failed_datasets_from_run(run_id)))

    report = DriftReport(
        recent_runs=[{"id": rid, "failures": sorted(f)} for rid, f in failures_per_run],
        completed_runs=len(runs),
    )

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
    issues = _json(out, "이슈 검색")
    if not isinstance(issues, list):
        raise UndeterminedError("이슈 검색 응답이 배열이 아님")
    for issue in issues:
        if isinstance(issue, dict) and dataset in str(issue.get("title", "")):
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

    # A search that fails must not be read as "no issue yet": that is how a second
    # issue for the same dataset gets filed. Nothing is created unless the search
    # answered.
    try:
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
    except UndeterminedError as error:
        raise ReportFailedError(f"{dataset}: {error}") from error
    print(f"발행: {out.strip()} {dataset}")


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="스모크 드리프트 리포트")
    parser.add_argument("--dry-run", action="store_true", help="이슈 발행 없이 판정만")
    args = parser.parse_args(argv)

    try:
        report = collect()
    except UndeterminedError as error:
        print(f"판정할 수 없음: {error}")
        print("verdict=undetermined")
        return 2
    if not report.recent_runs:
        print(
            f"완료된 스모크 실행이 {report.completed_runs}회뿐이라 "
            "연속 실패를 셀 수 없음 (최소 2회)"
        )
        print("verdict=insufficient_history")
        return 0
    streak_text = report.consecutive_failures or "없음"
    print(f"최근 실행 {len(report.recent_runs)}회 분석 — 연속 실패: {streak_text}")
    not_reported: list[str] = []
    for dataset in report.consecutive_failures:
        try:
            file_or_update(dataset, report, args.dry_run)
        except ReportFailedError as error:
            # Go on to the other datasets; one failed report must not hide the rest.
            print(f"보고 실패: {error}")
            not_reported.append(dataset)
    if not_reported:
        print(f"드리프트가 있으나 보고하지 못함: {', '.join(not_reported)}")
        print("verdict=report_failed")
        return 1
    print(f"verdict={'drift' if report.consecutive_failures else 'ok'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
