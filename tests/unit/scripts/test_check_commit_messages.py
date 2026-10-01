"""Commit messages merged into main forever — so the rules get a gate.

AGENTS.md says commits are English-only and carry the same conventional
shape as PR titles, but only the title was checked: the squash of PR #728
embedded a `record(fixtures):` header (not a type this project uses) and a
Korean word in a body. Main history is never rewritten, so the only fix is
before the merge. These tests pin the gate's verdicts against real git
history, hermetically - the same pattern as the authorship-gate tests.
"""

from __future__ import annotations

import importlib.util
import itertools
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_commit_messages.py"

_writes = itertools.count()

_GIT_ENV = {
    "PATH": os.environ["PATH"],
    "HOME": os.environ.get("HOME", ""),
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


def _load_script():
    """Load the script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("check_commit_messages", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_commit_messages"] = module
    spec.loader.exec_module(module)
    return module


ccm = _load_script()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
    )


def _commit(repo: Path, subject: str, body: str = "", *, author: str = "A Human") -> None:
    """Commit with fresh content, so every commit is a real change."""
    (repo / f"change-{next(_writes)}.txt").write_text("x\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        f"user.name={author}",
        "-c",
        "user.email=author@example.invalid",
        "commit",
        "-m",
        subject,
        "-m",
        body,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A work branch on a one-commit main, argv pointed at it."""
    _git(tmp_path, "init", "-b", "main")
    (tmp_path / "seed.txt").write_text("base\n", encoding="utf-8")
    _commit(tmp_path, "chore: seed", author="A Human")
    _git(tmp_path, "checkout", "-b", "the-change")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["check_commit_messages.py", "--base", "main"])
    return tmp_path


def test_conventional_english_commits_pass(repo: Path) -> None:
    _commit(repo, "feat(spec): add a dataset", "Two datasets recorded live.")
    _commit(repo, "fix(probe): classify 429 as rate_limited")

    assert ccm.main() == 0


def test_korean_in_a_body_fails(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The #728 case: the subject is fine, the body is not English-only."""
    _commit(repo, "feat(spec): migrate two datasets", "Removed per the 전환 rule.")

    assert ccm.main() == 1
    assert "English-only" in capsys.readouterr().out


def test_korean_in_a_subject_fails(repo: Path) -> None:
    _commit(repo, "feat(spec): 데이터셋 추가")

    assert ccm.main() == 1


def test_a_non_conventional_type_fails(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """The other #728 case: `record(fixtures):` is not a type this project uses."""
    _commit(repo, "record(fixtures): record live evidence")

    assert ccm.main() == 1
    assert "record" in capsys.readouterr().out


def test_a_single_bad_commit_fails_the_whole_pr(repo: Path) -> None:
    _commit(repo, "feat(spec): good commit")
    _commit(repo, "bad subject without type")

    assert ccm.main() == 1


def test_no_commits_in_range_passes(repo: Path) -> None:
    assert ccm.main() == 0


def test_a_merge_commit_in_range_is_ignored(repo: Path) -> None:
    """GitHub builds an ephemeral "Merge <sha> into <sha>" commit to test a
    pull request; a squash merge embeds only the non-merge commits, so the
    convention applies only to those."""
    _commit(repo, "feat(spec): the real change")
    _git(repo, "checkout", "-b", "side-branch")
    _commit(repo, "fix(core): side change")
    _git(repo, "checkout", "the-change")
    _git(
        repo,
        "-c",
        "user.name=A Human",
        "-c",
        "user.email=author@example.invalid",
        "merge",
        "--no-ff",
        "-m",
        "Merge side-branch into the-change",
        "side-branch",
    )

    subjects = [subject for _sha, subject, _body in ccm.commits_in_range("main")]

    assert "Merge side-branch into the-change" not in subjects
    assert sorted(subjects) == ["feat(spec): the real change", "fix(core): side change"]
    assert ccm.main() == 0


def test_a_base_that_cannot_be_resolved_is_an_error(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["check_commit_messages.py", "--base", "no-such-ref"])

    assert ccm.main() == 2
