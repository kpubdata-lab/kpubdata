"""The verify guard must blame the tool, not the developer (#513).

The table below is the contract. The row that matters most is the second one:
the old guard failed there, and a guard that fails during ordinary work gets
skipped -- which is how the mutation it exists to catch (#497) gets through.

| Before                  | During                   | Expected |
|-------------------------|--------------------------|----------|
| clean                   | no change                | PASS     |
| dirty                   | no additional change     | PASS     |
| dirty                   | additional mutation      | FAIL     |
| clean                   | new protected file       | FAIL     |
| clean                   | deleted protected file   | FAIL     |
| clean                   | content mutated in place | FAIL     |
| untracked new spec      | no additional change     | PASS     |
"""

from __future__ import annotations

import json
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

_GUARD = Path(__file__).resolve().parents[2] / "scripts" / "verify_guard.py"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Iterator[Path]:
    """A throwaway git repo shaped like this one: a tracked ``src/`` tree."""
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "guard@test.invalid")
    _git(tmp_path, "config", "user.name", "guard")
    src = tmp_path / "src" / "kpubdata" / "specs"
    src.mkdir(parents=True)
    (src / "one.yaml").write_text("id: one\n", encoding="utf-8")
    (src / "two.yaml").write_text("id: two\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "initial")
    yield tmp_path


def _run(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_GUARD), *args],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _guarded(repo: Path, during: Callable[[], None]) -> subprocess.CompletedProcess[str]:
    """Snapshot, run ``during``, compare -- what the Makefile recipe does."""
    snap = _run(repo, "snapshot")
    assert snap.returncode == 0, snap.stderr
    baseline = repo / "baseline.json"
    baseline.write_text(snap.stdout, encoding="utf-8")
    during()
    return _run(repo, "compare", str(baseline))


def _nothing() -> None:
    return None


class TestPasses:
    def test_clean_tree_untouched(self, repo: Path) -> None:
        assert _guarded(repo, _nothing).returncode == 0

    def test_already_dirty_file_is_not_blamed_on_the_tool(self, repo: Path) -> None:
        """The row the old guard got wrong: editing a spec then running verify."""
        (repo / "src/kpubdata/specs/one.yaml").write_text(
            "id: one\nedited: yes\n", encoding="utf-8"
        )
        result = _guarded(repo, _nothing)
        assert result.returncode == 0, result.stderr

    def test_untracked_new_spec_is_not_blamed_on_the_tool(self, repo: Path) -> None:
        """Adding a dataset means an untracked file exists before verify runs."""
        (repo / "src/kpubdata/specs/three.yaml").write_text("id: three\n", encoding="utf-8")
        result = _guarded(repo, _nothing)
        assert result.returncode == 0, result.stderr

    def test_changes_outside_the_watched_tree_are_ignored(self, repo: Path) -> None:
        def during() -> None:
            (repo / "notes.txt").write_text("scratch\n", encoding="utf-8")

        assert _guarded(repo, during).returncode == 0


class TestFails:
    def test_mutation_on_top_of_an_already_dirty_file(self, repo: Path) -> None:
        """Dirty before *and* touched during. The old guard could not see this --
        git's status letters stay ` M` either way, so only content shows it."""
        target = repo / "src/kpubdata/specs/one.yaml"
        target.write_text("id: one\nedited: yes\n", encoding="utf-8")

        def during() -> None:
            target.write_text("id: one\nedited: yes\nlast_verified: 2026-09-27\n", encoding="utf-8")

        result = _guarded(repo, during)
        assert result.returncode == 1
        assert "modified src/kpubdata/specs/one.yaml" in result.stderr

    def test_a_file_created_during_the_run(self, repo: Path) -> None:
        def during() -> None:
            (repo / "src/kpubdata/specs/generated.yaml").write_text("id: gen\n", encoding="utf-8")

        result = _guarded(repo, during)
        assert result.returncode == 1
        assert "created  src/kpubdata/specs/generated.yaml" in result.stderr

    def test_a_file_deleted_during_the_run(self, repo: Path) -> None:
        def during() -> None:
            (repo / "src/kpubdata/specs/two.yaml").unlink()

        result = _guarded(repo, during)
        assert result.returncode == 1
        assert "deleted  src/kpubdata/specs/two.yaml" in result.stderr

    def test_a_chmod_during_the_run(self, repo: Path) -> None:
        """Content is identical, only the executable bit changed. The digest
        alone cannot see it, and the old ``git status`` guard could -- ignoring
        it would be a regression, not a simplification."""
        target = repo / "src/kpubdata/specs/one.yaml"

        def during() -> None:
            target.chmod(0o755)

        result = _guarded(repo, during)
        assert result.returncode == 1
        assert "chmod    src/kpubdata/specs/one.yaml" in result.stderr

    def test_content_rewritten_in_place(self, repo: Path) -> None:
        """What #497 actually did: overwrite ``last_verified`` in a clean tree."""

        def during() -> None:
            (repo / "src/kpubdata/specs/one.yaml").write_text(
                "id: one\nlast_verified: 2026-09-27\n", encoding="utf-8"
            )

        result = _guarded(repo, during)
        assert result.returncode == 1
        assert "#497" in result.stderr


class TestTheGuardCannotBeSilentlyDisabled:
    def test_a_missing_baseline_is_an_error_not_a_pass(self, repo: Path) -> None:
        result = _run(repo, "compare", str(repo / "does-not-exist.json"))
        assert result.returncode == 2
        assert "cannot read the snapshot" in result.stderr

    def test_a_corrupt_baseline_is_an_error_not_a_pass(self, repo: Path) -> None:
        bad = repo / "bad.json"
        bad.write_text("not json", encoding="utf-8")
        assert _run(repo, "compare", str(bad)).returncode == 2

    def test_snapshot_covers_untracked_files(self, repo: Path) -> None:
        """A tracked-only walk would miss a spec created during the run."""
        (repo / "src/kpubdata/specs/extra.yaml").write_text("id: extra\n", encoding="utf-8")
        data = json.loads(_run(repo, "snapshot").stdout)
        assert "src/kpubdata/specs/extra.yaml" in data

    def test_a_non_mapping_baseline_is_a_clean_error(self, repo: Path) -> None:
        """``[]`` used to reach ``compare`` and die with an AttributeError
        traceback. Non-zero either way, but a traceback cannot be told apart
        from a real finding."""
        bad = repo / "list.json"
        bad.write_text("[]", encoding="utf-8")
        result = _run(repo, "compare", str(bad))
        assert result.returncode == 2
        assert "not a snapshot object" in result.stderr
        assert "Traceback" not in result.stderr

    def test_a_baseline_with_non_string_entries_is_rejected(self, repo: Path) -> None:
        bad = repo / "nulls.json"
        bad.write_text('{"src/kpubdata/specs/one.yaml": null}', encoding="utf-8")
        result = _run(repo, "compare", str(bad))
        assert result.returncode == 2
        assert "Traceback" not in result.stderr

    def test_an_unreadable_file_aborts_instead_of_reporting_clean(self, repo: Path) -> None:
        """Unreadable before *and* after would compare equal, so the guard would
        report success over a state it never observed."""
        target = repo / "src/kpubdata/specs/one.yaml"
        target.chmod(0o000)
        try:
            snap = _run(repo, "snapshot")
            assert snap.returncode == 2
            assert "cannot snapshot" in snap.stderr
        finally:
            target.chmod(0o644)

    def test_snapshot_ignores_gitignored_files(self, repo: Path) -> None:
        (repo / ".gitignore").write_text("src/**/*.tmp\n", encoding="utf-8")
        (repo / "src/kpubdata/specs/scratch.tmp").write_text("x", encoding="utf-8")
        data = json.loads(_run(repo, "snapshot").stdout)
        assert "src/kpubdata/specs/scratch.tmp" not in data
