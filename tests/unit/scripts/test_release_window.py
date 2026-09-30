"""The release window is date arithmetic, so it is tested as date arithmetic (#685).

kpubdata shipped 0.7.0 and 0.8.0 two days apart while the rule said once a month. The
gate that now refuses that is only as good as its calendar, and a calendar is where an
off-by-one hides — the week that spills into the next month, the month with five
Thursdays, the seventh day.
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release_window.py"


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
    "issue", ["#123", "yeongseon/kpubdata#123", "https://github.com/yeongseon/kpubdata/issues/9"]
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
