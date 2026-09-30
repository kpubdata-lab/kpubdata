"""The release freeze is date arithmetic plus pull-request facts (#701).

The freeze — only release pull requests merge into Builder and Studio `main` during
the release week — held on paper while the release window gained its gate (#685).
These tests pin the calendar half (the week spilling into the next month, the Monday
start, the Sunday end) and the pull-request half (the three ways to be a release
pull request, and the refusal when none applies).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release_freeze.py"


def _load_script():
    """Load the script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("release_freeze", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_freeze"] = module
    spec.loader.exec_module(module)
    return module


rf = _load_script()

# The 2026-10 window: its last Thursday is 10-29, so the week runs 10-26 to 11-01 —
# the Sunday spills into November. The September window (09-21 to 09-27) is over
# before it starts.
MONDAY = date(2026, 10, 26)
TUESDAY = date(2026, 10, 27)
SUNDAY = date(2026, 11, 1)
AFTER = date(2026, 11, 2)
BEFORE = date(2026, 10, 20)


def _decide(
    today: date,
    *,
    head_branch: str = "feat/issue-1-something",
    body: str = "",
    files: list[str] | None = None,
    studio_release_times: list[str] | None = None,
) -> tuple[bool, bool]:
    decision = rf.freeze_decision(
        today,
        head_branch=head_branch,
        body=body,
        files=files if files is not None else ["src/thing.py"],
        studio_release_times=studio_release_times or [],
    )
    return decision.frozen, decision.allowed


def test_a_normal_pull_request_outside_the_week_is_not_frozen() -> None:
    assert _decide(BEFORE) == (False, True)
    assert _decide(AFTER) == (False, True)


@pytest.mark.parametrize("today", [MONDAY, TUESDAY, SUNDAY])
def test_a_normal_pull_request_is_refused_every_day_of_the_week(today: date) -> None:
    """Monday opens the freeze, the November Sunday still is it, and a feature pull
    request changing code fails every one of those days — the refusal this gate
    exists for."""
    assert _decide(today) == (True, False)


def test_the_refusal_names_the_waiting_alternatives() -> None:
    decision = rf.freeze_decision(
        TUESDAY,
        head_branch="feat/issue-1-something",
        body="",
        files=["src/thing.py", "src/other.py"],
        studio_release_times=[],
    )
    assert "src/thing.py" in decision.reason
    assert "Critical-Patch" in decision.reason


def test_a_release_branch_passes_whatever_it_changes() -> None:
    assert _decide(TUESDAY, head_branch="release/v0.4.0") == (True, True)


def test_a_pull_request_touching_only_release_files_passes() -> None:
    assert _decide(
        TUESDAY,
        files=["CHANGELOG.md", "pyproject.toml", "uv.lock", "compatibility.json"],
    ) == (True, True)


@pytest.mark.parametrize(
    "path",
    [
        "CHANGELOG.md",
        "pyproject.toml",
        "uv.lock",
        "requirements.txt",
        "package.json",
        "package-lock.json",
        "compatibility.json",
        "docs/compatibility.md",
    ],
)
def test_release_files(path: str) -> None:
    assert rf.is_release_file(path)


@pytest.mark.parametrize("path", ["src/thing.py", "docs/index.md", "tests/test_a.py"])
def test_not_release_files(path: str) -> None:
    assert not rf.is_release_file(path)


def test_one_code_file_among_release_files_refuses() -> None:
    assert _decide(TUESDAY, files=["CHANGELOG.md", "src/thing.py"]) == (True, False)


def test_a_critical_patch_line_passes() -> None:
    assert _decide(TUESDAY, head_branch="fix/hotfix", body="Critical-Patch: #123") == (True, True)


def test_a_critical_patch_line_accepts_the_long_issue_forms() -> None:
    assert _decide(TUESDAY, body="Critical-Patch: owner/repo#123") == (True, True)


def test_a_critical_patch_line_without_an_issue_is_refused() -> None:
    assert _decide(TUESDAY, body="Critical-Patch:") == (True, False)


def test_studio_shipping_ends_the_freeze_not_thursday() -> None:
    """§5.1: the freeze ends when Studio ships — a Tuesday publish opens `main`
    again for every pull request, not the passing of Thursday."""
    assert _decide(TUESDAY, studio_release_times=["2026-10-27T09:00:00Z"]) == (False, True)


def test_a_studio_release_outside_this_window_does_not_end_it() -> None:
    assert _decide(TUESDAY, studio_release_times=["2026-09-29T09:00:00Z"]) == (True, False)


def test_the_freeze_ends_even_for_a_pull_request_that_would_be_refused() -> None:
    assert _decide(SUNDAY, studio_release_times=["2026-10-26T09:00:00Z"]) == (False, True)


def test_main_prints_the_decision(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    body = tmp_path / "body"
    body.write_text("", encoding="utf-8")
    files = tmp_path / "files"
    files.write_text("src/thing.py\n", encoding="utf-8")
    assert (
        rf.main(
            [
                "--today",
                str(TUESDAY),
                "--head-branch",
                "feat/issue-1-something",
                "--body-file",
                str(body),
                "--files-from",
                str(files),
                "--studio-release-times",
                "",
            ]
        )
        == 1
    )
    out = capsys.readouterr().out.splitlines()
    assert out[0] == "frozen=true"
    assert out[1] == "allowed=false"
    assert out[2].startswith("reason=")


def test_main_report_only_warns_instead_of_failing(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    files = tmp_path / "files"
    files.write_text("src/thing.py\n", encoding="utf-8")
    assert (
        rf.main(
            [
                "--today",
                str(TUESDAY),
                "--head-branch",
                "feat/issue-1-something",
                "--files-from",
                str(files),
                "--report-only",
            ]
        )
        == 0
    )
    assert "::warning::" in capsys.readouterr().err


def test_main_rejects_a_bad_date() -> None:
    assert rf.main(["--today", "not-a-date"]) == 2
