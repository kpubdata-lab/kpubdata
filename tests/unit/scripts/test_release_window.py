"""The release window is date arithmetic, so it is tested as date arithmetic (#685).

kpubdata shipped 0.7.0 and 0.8.0 two days apart while the rule said once a month. The
gate that now refuses that is only as good as its calendar, and a calendar is where an
off-by-one hides — the week that spills into the next month, the month with five
Thursdays, the seventh day.
"""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release_window.py"
RELEASE = REPO_ROOT / ".github" / "workflows" / "release.yml"


def _load_script():
    spec = importlib.util.spec_from_file_location("release_window", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_window"] = module
    spec.loader.exec_module(module)
    return module


rw = _load_script()


@pytest.mark.parametrize(
    ("year", "month", "expected"),
    [
        (2026, 2, date(2026, 2, 26)),  # four Thursdays: 5, 12, 19, 26
        (2026, 10, date(2026, 10, 29)),  # five Thursdays: 1, 8, 15, 22, 29
        (2026, 9, date(2026, 9, 24)),
        (2026, 12, date(2026, 12, 31)),  # the month's last day is the Thursday
        (2027, 1, date(2027, 1, 28)),
    ],
)
def test_last_thursday(year: int, month: int, expected: date) -> None:
    assert rw.last_thursday(year, month) == expected


def test_the_release_week_can_end_in_the_next_month() -> None:
    assert rw.release_week(2026, 10) == (date(2026, 10, 26), date(2026, 11, 1))


@pytest.mark.parametrize(
    "today",
    [
        date(2026, 10, 26),  # Monday, first day
        date(2026, 10, 28),  # Wednesday, Builder's day
        date(2026, 10, 29),  # Thursday, Studio's day
        date(2026, 11, 1),  # Sunday in November, still October's week
        date(2026, 12, 31),  # the week holding Thursday 12-31
        date(2027, 1, 3),  # its Sunday, in the next year
    ],
)
def test_monthly_allows_the_release_week(today: date) -> None:
    decision = rw.decide("monthly", today)
    assert decision.allowed, decision.reason


@pytest.mark.parametrize(
    "today",
    [
        date(2026, 9, 30),  # September's last Thursday was 9-24: its week ended 9-27
        date(2026, 10, 25),  # the Sunday before
        date(2026, 11, 2),  # the Monday after
        date(2026, 10, 1),
    ],
)
def test_monthly_refuses_outside_the_release_week(today: date) -> None:
    decision = rw.decide("monthly", today)
    assert not decision.allowed
    assert "2026-10-26 to 2026-11-01" in decision.reason or "2026-11-23" in decision.reason


def test_monthly_names_the_next_window() -> None:
    assert "2026-10-26 to 2026-11-01" in rw.decide("monthly", date(2026, 9, 30)).reason
    assert "2026-11-23 to 2026-11-29" in rw.decide("monthly", date(2026, 11, 2)).reason


@pytest.mark.parametrize(
    ("elapsed", "allowed"),
    [(0, False), (2, False), (6, False), (7, True), (30, True)],
)
def test_on_demand_waits_seven_days(elapsed: int, allowed: bool) -> None:
    last = date(2026, 9, 30)
    today = date.fromordinal(last.toordinal() + elapsed)
    assert rw.decide("on-demand", today, last_release=last).allowed is allowed


def test_on_demand_0_8_0_would_have_been_refused() -> None:
    decision = rw.decide("on-demand", date(2026, 9, 30), last_release=date(2026, 9, 28))
    assert not decision.allowed
    assert "2026-10-05" in decision.reason


def test_on_demand_with_no_earlier_release_is_allowed() -> None:
    assert rw.decide("on-demand", date(2026, 9, 30), last_release=None).allowed


def test_the_interval_is_configurable() -> None:
    decision = rw.decide(
        "on-demand", date(2026, 10, 2), last_release=date(2026, 9, 30), min_interval_days=2
    )
    assert decision.allowed


@pytest.mark.parametrize(
    "issue",
    ["#123", "kpubdata-lab/kpubdata#123", "https://github.com/kpubdata-lab/kpubdata/issues/9"],
)
def test_a_critical_patch_with_an_issue_passes_either_policy(issue: str) -> None:
    for policy in ("monthly", "on-demand"):
        decision = rw.decide(
            policy,
            date(2026, 9, 30),
            last_release=date(2026, 9, 29),
            critical_patch=True,
            critical_issue=issue,
        )
        assert decision.allowed
        assert decision.critical_issue == issue


@pytest.mark.parametrize("issue", ["", "   ", "123", "security fix", "#", "#12a"])
def test_a_critical_patch_without_an_issue_is_refused(issue: str) -> None:
    decision = rw.decide("monthly", date(2026, 10, 28), critical_patch=True, critical_issue=issue)
    assert not decision.allowed
    assert "must name its issue" in decision.reason


def test_dates_are_korean_standard_time() -> None:
    # 2026-10-25 16:00 UTC is 2026-10-26 01:00 in Seoul: already Monday of the window.
    assert rw.today_kst(datetime(2026, 10, 25, 16, 0, tzinfo=timezone.utc)) == date(2026, 10, 26)
    # 0.8.0 was published at 10:10 UTC on 9-30, which is still 9-30 in Seoul.
    assert rw.to_kst_date("2026-09-30T10:10:43Z") == date(2026, 9, 30)
    assert rw.to_kst_date("2026-09-30T20:00:00Z") == date(2026, 10, 1)


def test_cli_refuses_with_status_1_and_reports_only_on_request(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert rw.main(["--policy", "monthly", "--today", "2026-09-30"]) == 1
    out = capsys.readouterr()
    assert "allowed=false" in out.out
    assert "::error::release refused" in out.err

    assert rw.main(["--policy", "monthly", "--today", "2026-09-30", "--report-only"]) == 0
    out = capsys.readouterr()
    assert "allowed=false" in out.out
    assert "::warning::" in out.err


def test_cli_reads_a_github_timestamp(capsys: pytest.CaptureFixture[str]) -> None:
    code = rw.main(
        ["--policy", "on-demand", "--today", "2026-10-07", "--last-release", "2026-09-30T10:10:43Z"]
    )
    assert code == 0
    assert "allowed=true" in capsys.readouterr().out


def test_cli_prints_the_critical_issue(capsys: pytest.CaptureFixture[str]) -> None:
    code = rw.main(
        [
            "--policy",
            "monthly",
            "--today",
            "2026-09-30",
            "--critical-patch",
            "true",
            "--critical-issue",
            "#9",
        ]
    )
    assert code == 0
    assert "critical_issue=#9" in capsys.readouterr().out


def test_cli_rejects_a_bad_date() -> None:
    assert rw.main(["--policy", "monthly", "--today", "30/09/2026"]) == 2


# ------------------------------------------------- the real 0.9.0 -> 0.10.0 gap (#895)
#
# v0.9.0 was published at 2026-10-06T02:43:55Z and v0.10.0 at 2026-10-09T01:44:46Z,
# three days apart. The gate did not miss it: the release pull request (#830) carried a
# `Critical-Patch: #821` line, and the run logged "release allowed: critical patch for
# #821, outside the on-demand rule". These tests hold both halves of that.

V0_9_0_PUBLISHED = "2026-10-06T02:43:55Z"
PR_830_TAIL = (
    "This PR was generated with [Release Please](https://github.com/googleapis/release-please)."
    "\r\n\r\nCritical-Patch: #821\r\n"
)


@pytest.mark.parametrize(
    ("today", "allowed"),
    [
        (date(2026, 10, 9), False),  # the day v0.10.0 went out
        (date(2026, 10, 12), False),  # six days
        (date(2026, 10, 13), True),  # seven days
    ],
)
def test_without_a_critical_patch_0_10_0_would_have_waited_for_the_seventh_day(
    today: date, allowed: bool
) -> None:
    last = rw.to_kst_date(V0_9_0_PUBLISHED)
    decision = rw.decide("on-demand", today, last_release=last)
    assert decision.allowed is allowed, decision.reason
    if not allowed:
        assert "2026-10-13" in decision.reason


def test_the_seventh_day_starts_at_midnight_in_seoul_not_in_utc() -> None:
    last = rw.to_kst_date(V0_9_0_PUBLISHED)
    # 2026-10-12 15:00 UTC is 2026-10-13 00:00 KST: six days on the UTC calendar, seven
    # on Seoul's, and Seoul's is the one that counts.
    today = rw.today_kst(datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc))
    assert rw.decide("on-demand", today, last_release=last).allowed
    today = rw.today_kst(datetime(2026, 10, 12, 14, 59, tzinfo=timezone.utc))
    assert not rw.decide("on-demand", today, last_release=last).allowed


def _release_steps(job: str) -> list[dict[str, object]]:
    workflow = yaml.safe_load(RELEASE.read_text(encoding="utf-8"))
    steps: list[dict[str, object]] = workflow["jobs"][job]["steps"]
    return steps


def _step_index(steps: list[dict[str, object]], name: str) -> int:
    names = [step.get("name") for step in steps]
    assert name in names, f"no step named {name!r}"
    return names.index(name)


@pytest.mark.parametrize(
    ("job", "first_write"),
    [("prepare", "Work out the new version"), ("release", "Tag and release")],
)
def test_both_release_paths_run_the_on_demand_window_before_they_write(
    job: str, first_write: str
) -> None:
    steps = _release_steps(job)
    window = steps[_step_index(steps, "Release window")]
    assert window["uses"] == "./.github/actions/release-window"
    assert isinstance(window["with"], dict)
    assert window["with"]["policy"] == "on-demand"
    assert window["with"].get("min_interval_days", "7") == "7"
    assert _step_index(steps, "Release window") < _step_index(steps, first_write)


def _read_critical_declaration(tmp_path: Path, body: str) -> dict[str, str]:
    """Run release.yml's own `Read a critical-patch declaration` script on a merge event."""
    steps = _release_steps("release")
    script = steps[_step_index(steps, "Read a critical-patch declaration")]["run"]
    assert isinstance(script, str)
    output = tmp_path / "output"
    output.write_text("", encoding="utf-8")
    subprocess.run(
        ["bash", "-eo", "pipefail", "-c", script],
        env={
            **os.environ,
            "EVENT": "pull_request",
            "PR_BODY": body,
            "INPUT_PATCH": "",
            "INPUT_ISSUE": "",
            "GITHUB_OUTPUT": str(output),
        },
        check=True,
    )
    pairs = (line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines())
    return dict(pairs)


def test_the_0_10_0_pull_request_passed_as_a_declared_critical_patch(tmp_path: Path) -> None:
    declared = _read_critical_declaration(tmp_path, PR_830_TAIL)
    assert declared == {"patch": "true", "issue": "#821"}

    decision = rw.decide(
        "on-demand",
        date(2026, 10, 9),
        last_release=rw.to_kst_date(V0_9_0_PUBLISHED),
        critical_patch=declared["patch"] == "true",
        critical_issue=declared["issue"],
    )
    assert decision.allowed
    assert decision.critical_issue == "#821"


def test_a_release_pull_request_without_the_line_is_refused_inside_the_gap(
    tmp_path: Path,
) -> None:
    body = PR_830_TAIL.replace("Critical-Patch: #821", "")
    declared = _read_critical_declaration(tmp_path, body)
    assert declared == {"patch": "false", "issue": ""}

    decision = rw.decide(
        "on-demand",
        date(2026, 10, 9),
        last_release=rw.to_kst_date(V0_9_0_PUBLISHED),
        critical_patch=False,
        critical_issue=declared["issue"],
    )
    assert not decision.allowed
