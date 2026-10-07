"""The dataset verifier checks the pull request its own run opened, and says so (#858).

``build-dataset.yml`` used to find the pull request again by branch name in the verifier
step, from a ``DATASET`` that only the previous step's shell had set — so it looked for
``agent/issue-N`` while the branch was ``agent/datago.x`` — and both that lookup and the
verifier ended in ``|| true``. A run whose verifier never ran, or rejected the pull
request, finished green.

The structural tests read the workflow; the behavioural ones run the verifier and record
steps' scripts under ``bash -eo pipefail`` (the shell GitHub runs ``run:`` with) against
a fake ``opencode`` and ``gh``.
"""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-dataset.yml"


def _steps() -> dict[str, dict[str, Any]]:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return {step["name"]: step for step in workflow["jobs"]["build"]["steps"] if "name" in step}


def test_the_pull_request_step_hands_its_number_to_the_verifier() -> None:
    steps = _steps()
    create = steps["PR or needs-human"]
    verifier = steps["Verifier review"]

    assert create["id"] == "pr"
    for name in ("dataset", "branch", "pr_number"):
        assert f"{name}=" in create["run"] and '"$GITHUB_OUTPUT"' in create["run"]
    assert verifier["env"]["PR_NUMBER"] == "${{ steps.pr.outputs.pr_number }}"
    assert "steps.pr.outputs.pr_number != ''" in verifier["if"]


def test_no_step_finds_the_pull_request_again_by_branch() -> None:
    assert "gh pr list" not in WORKFLOW.read_text(encoding="utf-8")


def test_a_failed_pull_request_creation_fails_the_step() -> None:
    """The number is read from what ``gh pr create`` printed, and nothing after it is
    allowed to fail quietly."""
    block = _steps()["PR or needs-human"]["run"]
    assert "PR_URL=$(gh pr create" in block
    assert "|| true" not in block[block.index("PR_URL=$(gh pr create") :]


def test_the_verifier_and_its_record_hide_no_failure() -> None:
    steps = _steps()
    for name in ("Verifier review", "Record verifier outcome"):
        assert "|| true" not in steps[name]["run"], name
    assert steps["Record verifier outcome"]["if"] == "always()"
    assert steps["Record verifier outcome"]["env"]["OUTCOME"] == "${{ steps.verifier.outcome }}"


# ----------------------------------------------------------------- running the scripts


@pytest.fixture
def fake_bin(tmp_path: Path) -> Path:
    """``opencode`` prints ``$VERIFIER_OUTPUT`` and exits ``$VERIFIER_EXIT``; ``gh``
    records its arguments in ``$GH_LOG``."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    scripts = {
        "opencode": '#!/bin/sh\nprintf "%s\\n" "$VERIFIER_OUTPUT"\nexit "${VERIFIER_EXIT:-0}"\n',
        "gh": '#!/bin/sh\nprintf "%s\\n" "$*" >> "$GH_LOG"\n',
    }
    for name, body in scripts.items():
        path = bin_dir / name
        path.write_text(body, encoding="utf-8")
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def _run(step: str, tmp_path: Path, fake_bin: Path, **env: str) -> tuple[int, str, str]:
    """Run one step's script; return its exit code, the run summary and the gh calls."""
    summary = tmp_path / "summary.md"
    gh_log = tmp_path / "gh.log"
    summary.write_text("", encoding="utf-8")
    gh_log.write_text("", encoding="utf-8")
    environment = {
        **os.environ,
        "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_STEP_SUMMARY": str(summary),
        "GH_LOG": str(gh_log),
        "GITHUB_SERVER_URL": "https://github.com",
        "GITHUB_REPOSITORY": "kpubdata-lab/kpubdata",
        "GITHUB_RUN_ID": "1",
        **env,
    }
    result = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", _steps()[step]["run"]],
        env=environment,
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    return (
        result.returncode,
        summary.read_text(encoding="utf-8"),
        gh_log.read_text(encoding="utf-8"),
    )


def test_an_approval_passes_and_is_posted_on_that_pull_request(
    tmp_path: Path, fake_bin: Path
) -> None:
    code, _, gh_calls = _run(
        "Verifier review",
        tmp_path,
        fake_bin,
        PR_NUMBER="42",
        VERIFIER_OUTPUT="판정: 승인\n사유: -\n확인된 증거: make verify exit 0",
    )

    assert code == 0
    assert gh_calls == "pr comment 42 --body-file /tmp/verifier.md\n"


@pytest.mark.parametrize(
    ("output", "exit_code"),
    [
        ("판정: 반려\n사유: 4. assert True", "0"),  # a rejection
        ("**판정:** 반려", "0"),  # in bold
        ("체크리스트를 다 돌리지 못했다", "0"),  # no verdict to read
        ("판정: 승인", "1"),  # the agent itself failed, whatever it printed
    ],
    ids=["rejected", "rejected-bold", "no-verdict", "agent-failed"],
)
def test_anything_but_an_approval_fails_the_step(
    tmp_path: Path, fake_bin: Path, output: str, exit_code: str
) -> None:
    code, _, _ = _run(
        "Verifier review",
        tmp_path,
        fake_bin,
        PR_NUMBER="42",
        VERIFIER_OUTPUT=output,
        VERIFIER_EXIT=exit_code,
    )

    assert code != 0


def test_a_bold_approval_passes(tmp_path: Path, fake_bin: Path) -> None:
    code, _, _ = _run(
        "Verifier review", tmp_path, fake_bin, PR_NUMBER="42", VERIFIER_OUTPUT="**판정: 승인**"
    )

    assert code == 0


@pytest.mark.parametrize(
    ("outcome", "pr_number", "summary", "comments"),
    [
        ("success", "42", "verifier: PR #42 를 검사해 승인했다\n", False),
        ("failure", "42", "verifier: PR #42 를 반려했거나, 실행이나 판정 읽기에 실패했다\n", True),
        (
            "skipped",
            "",
            "verifier: 실행되지 않았다 — 풀 리퀘스트가 없거나 앞 단계가 실패했다\n",
            False,
        ),
        (
            "skipped",
            "42",
            "verifier: 실행되지 않았다 — 풀 리퀘스트가 없거나 앞 단계가 실패했다\n",
            True,
        ),
    ],
    ids=["approved", "failed", "never-ran", "pr-but-not-run"],
)
def test_the_run_summary_tells_a_verifier_that_never_ran_from_one_that_passed(
    tmp_path: Path, fake_bin: Path, outcome: str, pr_number: str, summary: str, comments: bool
) -> None:
    code, written, gh_calls = _run(
        "Record verifier outcome", tmp_path, fake_bin, OUTCOME=outcome, PR_NUMBER=pr_number
    )

    assert code == 0
    assert written == summary
    assert gh_calls.startswith(f"pr comment {pr_number} --body ") is comments
