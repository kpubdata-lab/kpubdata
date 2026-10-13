"""A label alone does not reach the self-hosted runner (#521).

``build-dataset.yml`` ran an agent holding a provider key, a model key and a write token
on the owner's machine whenever the ``dataset-request`` label appeared, and the issue
template applies that label itself. The ``gate`` job now asks
``scripts/dataset_request_gate.py`` first, on a hosted runner with a read-only token.

The unit tests hold the decision; the workflow tests read the file and run the gate's
script under ``bash -eo pipefail`` against a fake ``gh``.
"""

from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dataset_request_gate as gate  # noqa: E402

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-dataset.yml"

_OPEN_REQUEST: dict[str, Any] = {"state": "open", "labels": [{"name": "dataset-request"}]}
_TEXT = "feat(datasets): air quality\n\n### 제안 데이터셋 id\n\ndatago.air_quality\n"


def _decide(**overrides: Any) -> gate.Decision:
    arguments: dict[str, Any] = {
        "permission": "write",
        "issue_number": "42",
        "issue": _OPEN_REQUEST,
        "text": _TEXT,
    }
    arguments.update(overrides)
    return gate.decide(**arguments)


# ---------------------------------------------------------------------- the decision


def test_a_maintainers_request_passes_with_its_dataset_and_agent() -> None:
    decision = _decide()

    assert decision.allowed
    assert decision.dataset == "datago.air_quality"
    assert decision.agent == "dataset-builder"


def test_a_drift_issue_goes_to_the_drift_fixer() -> None:
    decision = _decide(issue={"state": "open", "labels": [{"name": "drift"}]})

    assert decision.allowed and decision.agent == "drift-fixer"


@pytest.mark.parametrize("permission", ["read", "triage", "none", "", "maintain"])
def test_anyone_who_cannot_push_is_refused(permission: str) -> None:
    """``maintain`` never comes back from the permission field (GitHub folds it into
    ``write``); a value nobody expects is refused, not guessed at."""
    decision = _decide(permission=permission)

    assert not decision.allowed
    assert "write access" in decision.reason


@pytest.mark.parametrize("number", ["", "0", "-1", "42; rm -rf /", "4 2", "01", "1" * 11])
def test_an_issue_number_that_is_not_a_plain_integer_is_refused(number: str) -> None:
    assert not _decide(issue_number=number).allowed


@pytest.mark.parametrize(
    ("issue", "why"),
    [
        ({"state": "closed", "labels": [{"name": "dataset-request"}]}, "not open"),
        ({"state": "open", "labels": [{"name": "bug"}]}, "carries none"),
        ({**_OPEN_REQUEST, "pull_request": {"url": "x"}}, "pull request"),
        ({}, "not open"),
    ],
    ids=["closed", "unlabelled", "pull-request", "unreadable"],
)
def test_only_an_open_request_issue_is_processed(issue: dict[str, Any], why: str) -> None:
    decision = _decide(issue=issue)

    assert not decision.allowed
    assert why in decision.reason


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("datago.air_quality", "datago.air_quality"),
        ("see datago.apt_trade and datago.other", "datago.apt_trade"),
        ("no id here", None),
        ("datago.Air", None),  # uppercase
        ("datago.1abc", None),  # starts with a digit
        ("datago.a" + "b" * 64, None),  # too long
        ("xdatago.air", None),  # glued to a longer word
        ("evil.datago.air", None),
        ("datago.$(id)", None),
        # A malformed first mention is not skipped for a later, valid one.
        ("datago.Bad then datago.good", None),
    ],
)
def test_the_dataset_id_is_strict(text: str, expected: str | None) -> None:
    assert gate.extract_dataset(text) == expected


def test_a_request_without_a_dataset_id_is_refused() -> None:
    decision = _decide(text="please add the air quality data")

    assert not decision.allowed
    assert "dataset id" in decision.reason


def test_outputs_are_single_lines() -> None:
    decision = gate.Decision(False, "line one\nallowed=true")

    lines = decision.outputs()
    assert lines[0] == "allowed=false"
    assert "allowed=true" not in lines
    assert all("\n" not in line for line in lines)


def test_the_cli_reads_its_files_and_prints_outputs(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    issue = tmp_path / "issue.json"
    text = tmp_path / "issue.md"
    issue.write_text(json.dumps(_OPEN_REQUEST), encoding="utf-8")
    text.write_text(_TEXT, encoding="utf-8")

    code = gate.main(
        [
            "--permission",
            "admin",
            "--issue-number",
            "42",
            "--issue-json",
            str(issue),
            "--issue-text",
            str(text),
        ]
    )

    assert code == 0
    assert capsys.readouterr().out.splitlines()[0] == "allowed=true"


def test_the_cli_refuses_unreadable_files(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "issue.json").write_text("not json", encoding="utf-8")

    gate.main(
        [
            "--permission",
            "admin",
            "--issue-number",
            "42",
            "--issue-json",
            str(tmp_path / "issue.json"),
            "--issue-text",
            str(tmp_path / "missing.md"),
        ]
    )

    assert capsys.readouterr().out.splitlines()[0] == "allowed=false"


# ---------------------------------------------------------------------- the workflow


def _workflow() -> dict[str, Any]:
    loaded: dict[str, Any] = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return loaded


def _jobs() -> dict[str, dict[str, Any]]:
    jobs: dict[str, dict[str, Any]] = _workflow()["jobs"]
    return jobs


def test_stabilization_freeze_keeps_dataset_agent_manual_only() -> None:
    trigger = _workflow().get("on", _workflow().get(True))

    assert set(trigger) == {"workflow_dispatch"}
    assert "issue_number" in trigger["workflow_dispatch"]["inputs"]
    assert _jobs()["gate"]["if"] == "github.event_name == 'workflow_dispatch'"


def test_the_self_hosted_job_waits_for_the_hosted_gate() -> None:
    jobs = _jobs()

    assert jobs["gate"]["runs-on"] == "ubuntu-latest"
    assert jobs["build"]["needs"] == "gate"
    assert jobs["build"]["if"] == "needs.gate.outputs.allowed == 'true'"
    assert "secrets." not in yaml.safe_dump(jobs["gate"])


def test_every_job_names_its_own_least_permissions() -> None:
    assert _workflow()["permissions"] == {}
    jobs = _jobs()
    assert jobs["gate"]["permissions"] == {"contents": "read", "issues": "read"}
    assert set(jobs["build"]["permissions"]) == {"contents", "pull-requests", "issues"}


def test_no_checkout_keeps_its_credential() -> None:
    checkouts = [
        step
        for job in _jobs().values()
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/checkout@")
    ]

    assert len(checkouts) == 2
    assert all(step["with"]["persist-credentials"] is False for step in checkouts)


def test_no_run_script_interpolates_an_expression() -> None:
    """Values reach the shell as environment variables, never as text in the script."""
    offenders = [
        f"{name}: {step.get('name', step.get('uses'))}"
        for name, job in _jobs().items()
        for step in job["steps"]
        if "${{" in str(step.get("run", ""))
    ]

    assert not offenders


def test_the_build_job_never_reads_the_dataset_from_the_issue_text() -> None:
    build = yaml.safe_dump(_jobs()["build"])

    assert "datago\\\\." not in build and "datago\\." not in build
    assert _jobs()["build"]["env"]["DATASET"] == "${{ needs.gate.outputs.dataset }}"


def test_the_agent_cli_is_pinned_and_checked() -> None:
    version = str(_workflow()["env"]["OPENCODE_VERSION"])
    context = next(s for s in _jobs()["build"]["steps"] if s.get("name") == "Context")

    assert version.count(".") == 2 and "latest" not in version
    assert '"$OPENCODE_VERSION"' in context["run"]
    assert "@latest" not in WORKFLOW.read_text(encoding="utf-8")


def test_the_agents_run_without_a_github_token() -> None:
    runs = [str(step.get("run", "")) for step in _jobs()["build"]["steps"]]
    agent_lines = [line for run in runs for line in run.splitlines() if "opencode run" in line]
    joined = "\n".join(runs)

    assert len(agent_lines) == 2
    assert joined.count('env -u GH_TOKEN -u GITHUB_TOKEN GH_CONFIG_DIR="$(mktemp -d)"') == 2
    builder = next(
        s
        for s in _jobs()["build"]["steps"]
        if s.get("name") == "Run dataset-builder (or drift-fixer)"
    )
    assert "GH_TOKEN" not in builder.get("env", {})


@pytest.fixture
def fake_gh(tmp_path: Path) -> Path:
    """``gh`` answers from ``$FAKE_PERMISSION``, ``$FAKE_ISSUE`` and ``$FAKE_TEXT`` and
    logs its arguments to ``$GH_LOG``."""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    script = """#!/bin/sh
printf '%s\\n' "$*" >> "$GH_LOG"
case "$*" in
  *collaborators*) [ -n "$FAKE_PERMISSION" ] || exit 1; printf '%s\\n' "$FAKE_PERMISSION" ;;
  "api repos/"*"/issues/"*) printf '%s\\n' "$FAKE_ISSUE" ;;
  "issue view"*) printf '%s\\n' "$FAKE_TEXT" ;;
esac
"""
    path = bin_dir / "gh"
    path.write_text(script, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return bin_dir


def _run_gate(tmp_path: Path, fake_gh: Path, **env: str) -> tuple[dict[str, str], str]:
    step = next(s for s in _jobs()["gate"]["steps"] if s.get("id") == "decide")
    output = tmp_path / "output.txt"
    summary = tmp_path / "summary.md"
    gh_log = tmp_path / "gh.log"
    runner_temp = tmp_path / "runner"
    runner_temp.mkdir(exist_ok=True)
    for file in (output, summary, gh_log):
        file.write_text("", encoding="utf-8")
    environment = {
        **os.environ,
        "PATH": f"{fake_gh}{os.pathsep}{os.environ['PATH']}",
        "GITHUB_OUTPUT": str(output),
        "GITHUB_STEP_SUMMARY": str(summary),
        "GITHUB_REPOSITORY": "kpubdata-lab/kpubdata",
        "RUNNER_TEMP": str(runner_temp),
        "GH_LOG": str(gh_log),
        "FAKE_ISSUE": json.dumps(_OPEN_REQUEST),
        "FAKE_TEXT": _TEXT,
        "FAKE_PERMISSION": "write",
        "ACTOR": "maintainer",
        "ISSUE_NUMBER": "42",
        **env,
    }
    subprocess.run(
        ["bash", "-eo", "pipefail", "-c", step["run"]],
        env=environment,
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    outputs = dict(
        line.split("=", 1) for line in output.read_text(encoding="utf-8").splitlines() if line
    )
    return outputs, gh_log.read_text(encoding="utf-8")


def test_the_gate_step_passes_a_maintainers_request(tmp_path: Path, fake_gh: Path) -> None:
    outputs, _ = _run_gate(tmp_path, fake_gh)

    assert outputs["allowed"] == "true"
    assert outputs["dataset"] == "datago.air_quality"
    assert outputs["issue_number"] == "42"
    assert len(outputs["issue_sha256"]) == 64


@pytest.mark.parametrize(
    "env",
    [
        {"FAKE_PERMISSION": "read"},
        {"FAKE_PERMISSION": ""},  # not a collaborator: the lookup fails
        {"FAKE_PERMISSION": '{"message":"Not Found"}'},
    ],
    ids=["read", "lookup-failed", "unexpected"],
)
def test_the_gate_step_refuses_without_write_access(
    tmp_path: Path, fake_gh: Path, env: dict[str, str]
) -> None:
    outputs, _ = _run_gate(tmp_path, fake_gh, **env)

    assert outputs["allowed"] == "false"


def test_a_malformed_issue_number_never_reaches_gh(tmp_path: Path, fake_gh: Path) -> None:
    outputs, gh_calls = _run_gate(tmp_path, fake_gh, ISSUE_NUMBER="42 --repo evil/repo")

    assert outputs["allowed"] == "false"
    assert gh_calls == ""


def test_a_malformed_actor_is_not_looked_up(tmp_path: Path, fake_gh: Path) -> None:
    outputs, gh_calls = _run_gate(tmp_path, fake_gh, ACTOR="../../orgs/x")

    assert outputs["allowed"] == "false"
    assert "collaborators" not in gh_calls
