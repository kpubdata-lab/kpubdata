"""The evidence authorship gate keeps a fixture edit from passing unnoticed (#523).

A recorded fixture is the evidence behind "this dataset is verified"; if the
subject of that judgement can edit the evidence quietly, the claim becomes
unfalsifiable (#497). scripts/check_fixture_authorship.py is the gate CI runs
on every pull request — these tests pin its verdicts against real git
history: the recorder passes, a hand edit or a self-asserted agent name
fails, and files the recorder legitimately rewrites outside the evidence
suffixes do not block.

The script is not a security boundary on its own — a commit author is
self-asserted. What it does is make the edit visible; the trust boundary is
#521's protected environment.
"""

from __future__ import annotations

import importlib.util
import itertools
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_fixture_authorship.py"

FIXTURE = "tests/fixtures/datago/x/default.raw.json"

#: A hermetic git environment: no global or system config leaks in, so the
#: author names come only from each commit's own -c flags.
_GIT_ENV = {
    "PATH": os.environ["PATH"],
    "HOME": os.environ.get("HOME", ""),
    "GIT_CONFIG_GLOBAL": "/dev/null",
    "GIT_CONFIG_SYSTEM": "/dev/null",
}


def _load_script():
    """Load the script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("check_fixture_authorship", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_fixture_authorship"] = module
    spec.loader.exec_module(module)
    return module


cfa = _load_script()


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
        env=_GIT_ENV,
    )


def _commit(repo: Path, message: str, *, author: str) -> None:
    _git(repo, "add", "-A")
    _git(
        repo,
        "-c",
        f"user.name={author}",
        "-c",
        "user.email=author@example.invalid",
        "commit",
        "-m",
        message,
    )


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A work branch on top of a main that holds one recorded fixture.

    The gate reads git history (``diff`` and ``log`` against ``--base``), so
    the fixture builds real history: main records the evidence as the
    recorder, and the test commits on a branch off it as whichever author it
    names — the way a pull request would.
    """
    _git(tmp_path, "init", "-b", "main")
    _write(FIXTURE, tmp_path)
    _commit(tmp_path, "record the fixture", author="kpubdata-agent")
    _git(tmp_path, "checkout", "-b", "the-change")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["check_fixture_authorship.py", "--base", "main"])
    return tmp_path


def _write(path: str, repo: Path, content: str | None = None) -> None:
    """Write a file, fresh content by default so every write is a real change.

    A rewrite with identical content leaves nothing to commit, and the
    author-verdict tests need an actual diff against the base.
    """
    if content is None:
        content = f'{{"write": {next(_writes)}}}\n'
    (repo / path).parent.mkdir(parents=True, exist_ok=True)
    (repo / path).write_text(content, encoding="utf-8")


_writes = itertools.count()


def test_the_recorders_own_change_passes(repo: Path) -> None:
    _write(FIXTURE, repo)
    _commit(repo, "re-record", author="kpubdata-agent")

    assert cfa.main() == 0


def test_the_github_bot_also_counts_as_the_recorder(repo: Path) -> None:
    _write(FIXTURE, repo)
    _commit(repo, "workflow re-record", author="github-actions[bot]")

    assert cfa.main() == 0


def test_a_hand_edit_of_evidence_fails(repo: Path) -> None:
    _write(FIXTURE, repo)
    _commit(repo, "tweak the numbers", author="A Human")

    assert cfa.main() == 1


def test_an_agent_name_is_not_the_recorder(repo: Path) -> None:
    """The negative test the issue asks for: an agent forging raw/meta to
    produce a verified dataset cannot do it under its own name — and the
    check treats every name outside RECORDER_AUTHORS alike."""
    _write(FIXTURE, repo)
    _commit(repo, "agent improves the evidence", author="coding-agent")

    assert cfa.main() == 1


def test_a_human_touching_the_same_file_as_the_recorder_fails(repo: Path) -> None:
    _write(FIXTURE, repo)
    _commit(repo, "re-record", author="kpubdata-agent")
    _write(FIXTURE, repo, content='{"edited": true}\n')
    _commit(repo, "polish", author="A Human")

    assert cfa.main() == 1


def test_files_the_recorder_writes_outside_the_evidence_do_not_block(
    repo: Path,
) -> None:
    """status_history.json lands under tests/fixtures/ when the drift step
    applies a transition — it is bookkeeping, not evidence, and the gate
    must not block it."""
    _write("tests/fixtures/datago/x/status_history.json", repo)
    _commit(repo, "apply the drift transition", author="A Human")

    assert cfa.main() == 0


def test_changes_outside_the_fixture_tree_do_not_block(repo: Path) -> None:
    _write("src/kpubdata/thing.py", repo)
    _commit(repo, "code change", author="A Human")

    assert cfa.main() == 0


_HEAD_SHA = "1" * 40


def _record_evidence(repo: Path, *, run_ref: str | None, commit: str | None) -> None:
    """Write raw+meta as the recorder would, carrying whatever binding it has."""
    meta: dict[str, object] = {"dataset_id": "datago.x", "recorded_by": "kpubdata-agent"}
    if commit is not None:
        meta["record_commit"] = commit
    if run_ref is not None:
        meta["run_ref"] = run_ref
    _write("tests/fixtures/datago/x/default.meta.json", repo, json.dumps(meta) + "\n")
    _write(FIXTURE, repo)


def test_a_recording_without_a_run_reference_fails(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The #728 case: the name is the recorder's, the proof is missing."""

    def _no_lookup(run_ref: str) -> tuple[str, str] | None:
        raise AssertionError("a meta without run_ref must not trigger a lookup")

    monkeypatch.setattr(cfa, "_run_details", _no_lookup)
    _record_evidence(repo, run_ref=None, commit=_HEAD_SHA)
    _commit(repo, "record the fixture", author="kpubdata-agent")

    assert cfa.main() == 1


def test_a_run_from_a_foreign_workflow_fails(
    repo: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(cfa, "_run_details", lambda run_ref: ("Release kpubdata", _HEAD_SHA))
    _record_evidence(repo, run_ref="42", commit=_HEAD_SHA)
    _commit(repo, "record the fixture", author="kpubdata-agent")

    assert cfa.main() == 1
    assert "not the recording workflow" in capsys.readouterr().err


def test_a_run_from_another_repository_is_not_verifiable(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(cfa, "_run_details", lambda run_ref: None)
    _record_evidence(repo, run_ref="999999", commit=_HEAD_SHA)
    _commit(repo, "record the fixture", author="kpubdata-agent")

    assert cfa.main() == 1


def test_a_head_sha_mismatch_fails(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cfa, "_run_details", lambda run_ref: (cfa.RECORDING_WORKFLOW_NAME, "2" * 40)
    )
    _record_evidence(repo, run_ref="7", commit=_HEAD_SHA)
    _commit(repo, "record the fixture", author="kpubdata-agent")

    assert cfa.main() == 1


def test_a_recording_workflow_run_passes(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cfa, "_run_details", lambda run_ref: (cfa.RECORDING_WORKFLOW_NAME, _HEAD_SHA)
    )
    _record_evidence(repo, run_ref="7", commit=_HEAD_SHA)
    _commit(repo, "record the fixture", author="kpubdata-agent")

    assert cfa.main() == 0


def test_a_base_that_cannot_be_resolved_is_an_error(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["check_fixture_authorship.py", "--base", "no-such-ref"])

    assert cfa.main() == 2
