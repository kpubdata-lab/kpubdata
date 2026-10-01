"""Recorded evidence may only be changed by the recorder (#523, #729).

A fixture is the basis for calling a dataset verified. If the subject of that
judgement can edit the evidence, the judgement is unfalsifiable -- and the path
existed: ``scripts/record.py`` once rewrote a repository spec's ``last_verified``
regardless of ``fixtures_root`` (#497).

The author check is not a security boundary by itself. A commit author is
self-asserted, so anyone who can push can claim the recorder's name -- and a
local tool did exactly that (#728). The run-reference layer closes it: a
changed meta must name a run of this repository's recording workflow, and the
run's head SHA must be the commit the meta claims. What stops forgery outright
is the secret boundary in #521 plus branch protection in #520; these checks
make the casual, accidental and self-asserted edit visible instead of silent,
which is the part that can exist before those land -- and these tests pin that
they actually fire.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_fixture_authorship.py"

_HUMAN = ("-c", "user.name=Some Developer", "-c", "user.email=dev@example.invalid")
_RECORDER = ("-c", "user.name=kpubdata-agent", "-c", "user.email=agent@kpubdata.local")
_BOT = ("-c", "user.name=github-actions[bot]", "-c", "user.email=bot@example.invalid")


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture()
def repo(tmp_path: Path) -> Iterator[Path]:
    """A repo with a recorded fixture on ``main``."""
    _git(tmp_path, "init", "-q", "-b", "main")
    fixture = tmp_path / "tests" / "fixtures" / "datago" / "air_quality"
    fixture.mkdir(parents=True)
    for suffix in ("raw", "expected", "meta"):
        (fixture / f"seoul.{suffix}.json").write_text('{"a": 1}\n', encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "thing.py").write_text("x = 1\n", encoding="utf-8")
    _git(tmp_path, *_RECORDER, "add", "-A")
    _git(tmp_path, *_RECORDER, "commit", "-qm", "initial")
    _git(tmp_path, "branch", "base")
    yield tmp_path


def _run(repo: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--base", "base"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )


def _edit(repo: Path, relative: str, value: object) -> None:
    path = repo / relative
    path.write_text(json.dumps({"a": value}) + "\n", encoding="utf-8")


class TestItRefuses:
    @pytest.mark.parametrize("suffix", ["raw", "expected", "meta"])
    def test_a_human_editing_evidence(self, repo: Path, suffix: str) -> None:
        relative = f"tests/fixtures/datago/air_quality/seoul.{suffix}.json"
        _edit(repo, relative, 2)
        _git(repo, *_HUMAN, "commit", "-qam", "tweak the fixture")
        result = _run(repo)
        assert result.returncode == 1
        assert relative in result.stderr
        assert "Some Developer" in result.stderr

    def test_it_names_the_re_record_route(self, repo: Path) -> None:
        """A check that only says no teaches nothing. The route is the
        recording workflow now - a local `make record` cannot bind a run."""
        _edit(repo, "tests/fixtures/datago/air_quality/seoul.meta.json", 2)
        _git(repo, *_HUMAN, "commit", "-qam", "tweak")
        assert "Build Dataset" in _run(repo).stderr

    def test_it_says_not_to_widen_the_allowlist(self, repo: Path) -> None:
        """Otherwise the obvious way to pass is to add yourself to it."""
        _edit(repo, "tests/fixtures/datago/air_quality/seoul.meta.json", 2)
        _git(repo, *_HUMAN, "commit", "-qam", "tweak")
        assert "Do not widen" in _run(repo).stderr

    def test_a_human_commit_anywhere_in_the_range_counts(self, repo: Path) -> None:
        """A recorder commit on top does not launder an earlier hand edit."""
        _edit(repo, "tests/fixtures/datago/air_quality/seoul.raw.json", 2)
        _git(repo, *_HUMAN, "commit", "-qam", "hand edit")
        _edit(repo, "tests/fixtures/datago/air_quality/seoul.raw.json", 3)
        _git(repo, *_RECORDER, "commit", "-qam", "chore(record): re-record")
        assert _run(repo).returncode == 1


class TestItAllows:
    def test_the_recorder_identity(self, repo: Path) -> None:
        """The author layer: the recorder's name passes on non-meta evidence.
        A meta change additionally needs the run reference - the test after
        next covers that path."""
        _edit(repo, "tests/fixtures/datago/air_quality/seoul.raw.json", 2)
        _git(repo, *_RECORDER, "commit", "-qam", "chore(record): re-record")
        result = _run(repo)
        assert result.returncode == 0, result.stderr

    def test_the_actions_bot(self, repo: Path) -> None:
        _edit(repo, "tests/fixtures/datago/air_quality/seoul.expected.json", 2)
        _git(repo, *_BOT, "commit", "-qam", "chore: re-record")
        assert _run(repo).returncode == 0

    def test_a_recorder_meta_bound_to_a_recording_run(
        self, repo: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The full pass path (#729): recorder name, meta bound to a run of
        the recording workflow whose head SHA is the recorded commit. ``gh``
        is stubbed on PATH - a subprocess cannot be monkeypatched."""
        sha = "1" * 40
        fixture = repo / "tests" / "fixtures" / "datago" / "air_quality"
        (fixture / "seoul.meta.json").write_text(
            json.dumps(
                {"dataset_id": "datago.air_quality", "record_commit": sha, "run_ref": "4242"}
            )
            + "\n",
            encoding="utf-8",
        )
        _edit(repo, "tests/fixtures/datago/air_quality/seoul.raw.json", 2)
        _git(repo, *_RECORDER, "commit", "-qam", "chore(record): re-record")

        stub = repo / "bin"
        stub.mkdir()
        (stub / "gh").write_text(
            "#!/bin/sh\n"
            'echo \'{"workflowName": "Build Dataset (agent)", "headSha": "' + sha + "\"}'\n",
            encoding="utf-8",
        )
        (stub / "gh").chmod(0o755)
        monkeypatch.setenv("PATH", f"{stub}:{os.environ['PATH']}")

        result = _run(repo)
        assert result.returncode == 0, result.stderr
        assert "bound to a recording-workflow run" in result.stdout

    def test_source_changes_by_a_human(self, repo: Path) -> None:
        """Writing code is the normal contribution. Only evidence is gated."""
        (repo / "src" / "thing.py").write_text("x = 2\n", encoding="utf-8")
        _git(repo, *_HUMAN, "commit", "-qam", "change the code")
        result = _run(repo)
        assert result.returncode == 0
        assert "no recorded evidence changed" in result.stdout

    def test_a_non_evidence_file_under_fixtures(self, repo: Path) -> None:
        """Spec fixtures and batch manifests are inputs, not evidence."""
        (repo / "tests" / "fixtures" / "batch-record.json").write_text("{}\n", encoding="utf-8")
        _git(repo, *_HUMAN, "add", "-A")
        _git(repo, *_HUMAN, "commit", "-qm", "add a batch manifest")
        assert _run(repo).returncode == 0


class TestItCannotBeSilentlyDisabled:
    def test_an_unknown_base_is_an_error_not_a_pass(self, repo: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(_SCRIPT), "--base", "no-such-ref"],
            cwd=repo,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert result.returncode == 2
        assert "cannot diff" in result.stderr
