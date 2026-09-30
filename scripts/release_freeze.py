#!/usr/bin/env python3
"""Say whether a pull request may merge into Builder or Studio `main` today (#701).

The release freeze — during the release week, only release pull requests merge into
`kpubdata-builder` and `kpubdata-studio` `main` (docs/compatibility.md §5.1) — used to
live only on paper. The release itself was refused outside the window
(`release_window.py`, #685), but a normal feature pull request could merge into a
frozen `main` and change what the release ships after the version was decided. A rule
without a gate is a wish (VERIFICATION 3).

The freeze starts on the release week's Monday and ends when **Studio** ships — not on
Thursday — so the calendar alone cannot answer; whether Studio has published inside
this window decides too. A pull request passes the freeze when it is a release pull
request, which §5.1 defines three ways:

- its head branch is ``release/*`` (the release workflow's prepare step creates it), or
- it changes only release files — the version, the CHANGELOG, dependency pins, the
  compatibility documents; Builder's kpubdata pin bump lives here too ("a pin is not a
  release"), or
- its body carries a ``Critical-Patch: #N`` line naming the issue it fixes. A line
  without an issue is refused, the same way `release_window.py` refuses it.

kpubdata `main` never freezes (§5.1), so this gate is only wired into Builder and
Studio pull requests, through `.github/actions/release-freeze`.

    $ python3 scripts/release_freeze.py --today 2026-10-27 \
          --head-branch feat/issue-123-something \
          --studio-release-times 2026-09-28T10:10:43Z
    frozen=true
    allowed=false
    reason=2026-10-27 is inside the 2026-10 release week (2026-10-26 to 2026-11-01) and
    Studio has not shipped in it; feat/issue-123-something is not a release pull request

Exit status 0 means allowed (or not applicable), 1 refused, 2 bad arguments. With
``--report-only`` a refusal is printed as a warning and the exit status is 0.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import ModuleType

_scripts_dir = Path(__file__).resolve().parent


def _load_release_window() -> ModuleType:
    """Load the sibling `release_window.py` — scripts/ is not a package."""
    spec = importlib.util.spec_from_file_location(
        "release_window", _scripts_dir / "release_window.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_window"] = module
    spec.loader.exec_module(module)
    return module


rw = _load_release_window()

# §5.1: the line looks like `Critical-Patch: #123`, written by the release prepare
# step or by hand for a defect fix that must merge during the freeze. The issue token
# is validated with release_window's `_ISSUE`, so `owner/repo#123` and the full URL
# work too.
_CRITICAL_PATCH = re.compile(r"^Critical-Patch:[ \t]*(\S+)[ \t]*$", re.MULTILINE)

# Files a release pull request may touch (§5.1: 버전·CHANGELOG·의존 핀·호환성 문서).
# Builder keeps its version in `pyproject.toml`; Studio is a Node application whose
# version sits in `package.json`. Lock files are the dependency pins. Matched against
# the basename, so the list stays the same wherever a repo keeps its files.
_RELEASE_FILE_PATTERNS = (
    "CHANGELOG*",
    "pyproject.toml",
    "uv.lock",
    "requirements*.txt",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "yarn.lock",
    "compatibility.json",
)
_COMPAT_DOCS = ("docs/compatibility.md", "compatibility.md")


@dataclass(frozen=True)
class FreezeDecision:
    frozen: bool
    allowed: bool
    reason: str


def _window_for(today: date) -> tuple[int, int, date, date] | None:
    """The release week containing ``today``, as (year, month, monday, sunday).

    Mirrors `release_window.monthly`: this month's week, then last month's spilling
    over (October's week ends on November 1st).
    """
    for year, month in ((today.year, today.month), rw._previous_month(today.year, today.month)):
        monday, sunday = rw.release_week(year, month)
        if monday <= today <= sunday:
            return year, month, monday, sunday
    return None


def is_release_file(path: str) -> bool:
    """Whether one changed file is a release file."""
    from fnmatch import fnmatch

    name = path.strip()
    if not name:
        return False
    if name.lower() in _COMPAT_DOCS:
        return True
    basename = name.rsplit("/", 1)[-1]
    return any(fnmatch(basename, pattern) for pattern in _RELEASE_FILE_PATTERNS)


def _critical_patch_issue(body: str) -> str | None:
    """The issue a `Critical-Patch:` line names, or None when the body has none.

    A line that is present but names nothing (or names something that is not an
    issue) returns the empty string, which the caller refuses — an unnamed critical
    patch is not a critical patch (§5.1).
    """
    matches = _CRITICAL_PATCH.findall(body)
    if not matches:
        return None
    token = matches[-1]
    return token if rw._ISSUE.match(token) else ""


def freeze_decision(
    today: date,
    *,
    head_branch: str,
    body: str,
    files: list[str],
    studio_release_times: list[str],
) -> FreezeDecision:
    """Whether `main` is frozen for this pull request today, and whether it may merge.

    ``studio_release_times`` are GitHub ISO publish timestamps of Studio's final
    releases; a publish inside the window ends the freeze.
    """
    window = _window_for(today)
    if window is None:
        return FreezeDecision(False, True, f"{today} is outside every release week")
    year, month, monday, sunday = window
    window_name = f"{year}-{month:02d}"

    shipped = [
        rw.to_kst_date(t) for t in studio_release_times if monday <= rw.to_kst_date(t) <= sunday
    ]
    if shipped:
        latest = max(shipped)
        return FreezeDecision(
            False,
            True,
            f"the {window_name} freeze ended: Studio shipped on {latest}",
        )

    frozen_context = (
        f"{today} is inside the {window_name} release week ({monday} to {sunday}) "
        "and Studio has not shipped in it"
    )

    branch = head_branch.strip()
    if branch.startswith("release/"):
        return FreezeDecision(True, True, f"{frozen_context}; {branch} is a release branch")

    critical = _critical_patch_issue(body)
    if critical == "":
        return FreezeDecision(
            True,
            False,
            f"{frozen_context}; the Critical-Patch line names no issue — "
            "write `Critical-Patch: #123` pointing at the issue it fixes",
        )
    if critical is not None:
        return FreezeDecision(True, True, f"{frozen_context}; critical patch for {critical}")

    non_release = [f for f in files if not is_release_file(f)]
    if not non_release:
        return FreezeDecision(
            True,
            True,
            f"{frozen_context}; every changed file is a release file "
            "(version, CHANGELOG, dependency pin, compatibility document)",
        )
    preview = ", ".join(non_release[:3])
    more = "" if len(non_release) <= 3 else f" (+{len(non_release) - 3} more)"
    return FreezeDecision(
        True,
        False,
        f"{frozen_context}; {branch} changes {preview}{more}, which is not release-only. "
        "Non-release pull requests wait on their branch until the freeze ends; a fix for "
        "a release-blocking defect carries `Critical-Patch: #N` in its body.",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--today", help="YYYY-MM-DD in KST (default: now)")
    parser.add_argument("--head-branch", default="", help="the pull request's head branch")
    parser.add_argument(
        "--body-file",
        default="",
        help="a file with the pull request body (empty means no body)",
    )
    parser.add_argument(
        "--files-from",
        default="",
        help="a file with one changed path per line (empty means no files)",
    )
    parser.add_argument(
        "--studio-release-times",
        default="",
        help="Studio's final-release publish timestamps, space separated",
    )
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)

    def _read(path: str) -> str:
        return Path(path).read_text(encoding="utf-8") if path else ""

    try:
        today = date.fromisoformat(args.today) if args.today else rw.today_kst()
        decision = freeze_decision(
            today,
            head_branch=args.head_branch,
            body=_read(args.body_file),
            files=[line for line in _read(args.files_from).splitlines() if line.strip()],
            studio_release_times=args.studio_release_times.split(),
        )
    except ValueError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    print(f"frozen={'true' if decision.frozen else 'false'}")
    print(f"allowed={'true' if decision.allowed else 'false'}")
    print(f"reason={decision.reason}")
    if decision.allowed:
        return 0
    if args.report_only:
        print(
            f"::warning::a real check would refuse this pull request: {decision.reason}",
            file=sys.stderr,
        )
        return 0
    print(f"::error::release freeze: {decision.reason}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
