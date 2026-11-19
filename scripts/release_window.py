#!/usr/bin/env python3
"""Say whether a release may happen today (#685).

The release rule used to live only in `docs/compatibility.md` §5.1, and nothing
stopped a release outside it: kpubdata shipped 0.7.0 and 0.8.0 two days apart, while
the document said once a month. A rule without a gate is a wish (VERIFICATION 3), so
this is the gate, and the three repositories call it through
`.github/actions/release-window` instead of keeping copies.

Two policies, one per kind of repository:

- ``on-demand`` (kpubdata, a standalone SDK — ADR 0007): at most one final release
  every ``--min-interval-days`` days (7), counted from the last final release.
- ``monthly`` (kpubdata-builder and kpubdata-studio, one application — ADR 0004): only
  in the Monday-to-Sunday week that holds the month's last Thursday.

Either can be overridden by a critical patch — a security fix or a defect that blocks
a release — which must name its issue. The issue is printed so the release notes can
carry it.

Dates are Korean Standard Time (UTC+9, no daylight saving): the week a person in Seoul
calls "the last week" is the one that counts, not the runner's UTC calendar.

    $ python3 scripts/release_window.py --policy monthly --today 2026-10-28
    allowed=true
    reason=2026-10-28 is inside the 2026-10 release week (2026-10-26 to 2026-11-01)

Exit status 0 means allowed, 1 refused, 2 bad arguments. With ``--report-only`` a
refusal is printed as a warning and the exit status is 0, so a dry run can show what a
real run would decide without stopping.
"""

from __future__ import annotations

import argparse
import calendar
import json
import os
import re
import subprocess
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, timezone

KST = timezone(timedelta(hours=9), name="KST")
THURSDAY = 3
_ISSUE = re.compile(
    r"^(?:(?P<slug>[\w.-]+/[\w.-]+))?#(?P<n>\d+)$"
    r"|^https://github\.com/(?P<url_slug>[\w.-]+/[\w.-]+)/issues/(?P<url_n>\d+)$"
)
#: Either label marks an issue as one a critical patch may name.
CRITICAL_LABELS = frozenset({"severity:critical", "priority:critical"})


class LookupFailed(Exception):
    """The issue could not be read; the critical-patch bypass stays closed."""


#: ``(repository, number)`` to the issue's REST payload; raises ``LookupFailed``.
IssueLookup = Callable[[str, int], Mapping[str, object]]


def gh_issue(repo: str, number: int) -> Mapping[str, object]:
    """The issue ``number`` of ``repo`` from the REST API, or ``LookupFailed``."""
    try:
        completed = subprocess.run(
            ["gh", "api", f"repos/{repo}/issues/{number}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as exc:
        raise LookupFailed(f"gh could not be run ({exc})") from exc
    if completed.returncode != 0:
        reason = completed.stderr.strip().splitlines()
        raise LookupFailed(reason[-1] if reason else f"gh exited {completed.returncode}")
    try:
        payload = json.loads(completed.stdout)
    except ValueError as exc:
        raise LookupFailed("the API did not return JSON") from exc
    if not isinstance(payload, dict):
        raise LookupFailed("the API did not return an issue")
    return payload


def _critical_problem(issue: str, repo: str, lookup: IssueLookup | None) -> str | None:
    """Why ``issue`` cannot authorise a critical patch, or ``None`` when it can."""
    match = _ISSUE.match(issue)
    if match is None:
        return None
    slug = match.group("slug") or match.group("url_slug") or repo
    number = int(match.group("n") or match.group("url_n"))
    if not repo:
        return "the repository is unknown, so the issue cannot be verified"
    if slug.lower() != repo.lower():
        return f"{issue} is not an issue of {repo}"
    if lookup is None:
        return "no issue lookup is available, so the issue cannot be verified"
    try:
        payload = lookup(slug, number)
    except LookupFailed as exc:
        return f"{issue} could not be verified: {exc}"
    if "pull_request" in payload:
        return f"{issue} is a pull request, not an issue"
    labels = payload.get("labels")
    rows = labels if isinstance(labels, list) else []
    names = {row.get("name") for row in rows if isinstance(row, dict)}
    if not names & CRITICAL_LABELS:
        return f"{issue} carries neither severity:critical nor priority:critical"
    return None


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    critical_issue: str | None = None


def today_kst(now: datetime | None = None) -> date:
    """The calendar date in Seoul at ``now`` (default: the current instant)."""
    moment = now if now is not None else datetime.now(UTC)
    return moment.astimezone(KST).date()


def to_kst_date(timestamp: str) -> date:
    """A GitHub ISO timestamp (``2026-09-30T10:10:43Z``) as a Seoul calendar date."""
    moment = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    if moment.tzinfo is None:
        raise ValueError(f"timestamp has no time zone: {timestamp}")
    return moment.astimezone(KST).date()


def last_thursday(year: int, month: int) -> date:
    """The last Thursday of the month."""
    last_day = calendar.monthrange(year, month)[1]
    end = date(year, month, last_day)
    return end - timedelta(days=(end.weekday() - THURSDAY) % 7)


def release_week(year: int, month: int) -> tuple[date, date]:
    """Monday and Sunday of the week holding the month's last Thursday.

    The Sunday can fall in the next month (October 2026: 10-26 to 11-01); the Monday
    never falls in the previous one, because a last Thursday is on the 22nd or later.
    """
    thursday = last_thursday(year, month)
    monday = thursday - timedelta(days=THURSDAY)
    return monday, monday + timedelta(days=6)


def _previous_month(year: int, month: int) -> tuple[int, int]:
    return (year - 1, 12) if month == 1 else (year, month - 1)


def monthly(today: date) -> Decision:
    """Allowed only inside a release week — this month's, or last month's spilling over."""
    for year, month in ((today.year, today.month), _previous_month(today.year, today.month)):
        monday, sunday = release_week(year, month)
        if monday <= today <= sunday:
            return Decision(
                True,
                f"{today} is inside the {year}-{month:02d} release week ({monday} to {sunday})",
            )
    monday, sunday = release_week(today.year, today.month)
    if today > sunday:
        next_year, next_month = (
            (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
        )
        monday, sunday = release_week(next_year, next_month)
    return Decision(
        False,
        f"{today} is outside the monthly release week; the next one is {monday} to {sunday}",
    )


def on_demand(today: date, last_release: date | None, min_interval_days: int) -> Decision:
    """Allowed when the last final release is at least ``min_interval_days`` old."""
    if last_release is None:
        return Decision(True, "no earlier final release")
    elapsed = (today - last_release).days
    if elapsed >= min_interval_days:
        return Decision(
            True,
            f"last final release was {last_release}, {elapsed} days ago "
            f"(minimum {min_interval_days})",
        )
    earliest = last_release + timedelta(days=min_interval_days)
    return Decision(
        False,
        f"last final release was {last_release}, {elapsed} days ago; "
        f"the next may go out on {earliest} (minimum {min_interval_days} days)",
    )


def decide(
    policy: str,
    today: date,
    *,
    last_release: date | None = None,
    min_interval_days: int = 7,
    critical_patch: bool = False,
    critical_issue: str = "",
    repo: str = "",
    lookup: IssueLookup | None = None,
) -> Decision:
    """The decision for one release attempt."""
    if critical_patch:
        issue = critical_issue.strip()
        if not _ISSUE.match(issue):
            return Decision(
                False,
                "a critical patch must name its issue (e.g. #123 or owner/repo#123); "
                f"got {issue or 'nothing'}",
            )
        problem = _critical_problem(issue, repo, lookup)
        if problem:
            return Decision(False, f"critical patch refused: {problem}")
        return Decision(True, f"critical patch for {issue}, outside the {policy} rule", issue)
    if policy == "monthly":
        return monthly(today)
    if policy == "on-demand":
        return on_demand(today, last_release, min_interval_days)
    raise ValueError(f"unknown policy: {policy}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--policy", required=True, choices=["on-demand", "monthly"])
    parser.add_argument("--today", help="YYYY-MM-DD in KST (default: now)")
    parser.add_argument(
        "--last-release", default="", help="the last final release's timestamp or date"
    )
    parser.add_argument("--min-interval-days", type=int, default=7)
    parser.add_argument("--critical-patch", default="false", help="true or false")
    parser.add_argument("--critical-issue", default="")
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_REPOSITORY", ""),
        help="owner/name the critical issue must belong to (default: GITHUB_REPOSITORY)",
    )
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)

    try:
        today = date.fromisoformat(args.today) if args.today else today_kst()
        last = args.last_release.strip()
        last_release = (
            (to_kst_date(last) if "T" in last else date.fromisoformat(last)) if last else None
        )
        critical = args.critical_patch.strip().lower() in {"true", "1", "yes"}
        decision = decide(
            args.policy,
            today,
            last_release=last_release,
            min_interval_days=args.min_interval_days,
            critical_patch=critical,
            critical_issue=args.critical_issue,
            repo=args.repo.strip(),
            lookup=gh_issue,
        )
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    print(f"allowed={'true' if decision.allowed else 'false'}")
    print(f"reason={decision.reason}")
    print(f"critical_issue={decision.critical_issue or ''}")
    if decision.allowed:
        print(f"::notice::release allowed: {decision.reason}", file=sys.stderr)
        return 0
    if args.report_only:
        print(f"::warning::a real release would be refused: {decision.reason}", file=sys.stderr)
        return 0
    print(f"::error::release refused: {decision.reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
