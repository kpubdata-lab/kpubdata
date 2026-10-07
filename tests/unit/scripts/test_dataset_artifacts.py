"""What adding a dataset produces is one list, and the documents and workflow follow it (#862).

``build-dataset.yml`` committed the spec and the fixtures only, while ``AGENTS.md``
also asked for an example script, a ``SUPPORTED_DATA.md`` row, a metadata entry and
regenerated files; the agent definition named yet other paths and told the agent to
commit, which the workflow refuses. ``scripts/dataset_artifacts.py`` is now the list;
these tests hold ``AGENTS.md``, the agent definition and the workflow to it, and run its
``check`` against a real git repository.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import dataset_artifacts  # noqa: E402

AGENTS = (REPO_ROOT / "AGENTS.md").read_text(encoding="utf-8")
AGENT_DEFINITION = (REPO_ROOT / ".opencode" / "agent" / "dataset-builder.md").read_text(
    encoding="utf-8"
)
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "build-dataset.yml"


def _section(text: str, heading: str) -> str:
    start = text.index(heading) + len(heading)
    end = text.find("\n#", start)
    return text[start : end if end != -1 else len(text)]


def _backticked(text: str) -> set[str]:
    return set(re.findall(r"`([^`\s]+)`", text))


def _roots(templates: list[str]) -> set[str]:
    """A template's fixed part: ``examples/{provider}/{key}.py`` → ``examples/``."""
    return {template.split("{", 1)[0] for template in templates}


ALLOWED_ROOTS = _roots([*dataset_artifacts.AGENT_WRITES, *dataset_artifacts.GENERATED])


def test_agents_md_lists_the_paths_the_module_does() -> None:
    section = _section(AGENTS, "### Paths you may change (dataset work)")
    named = _backticked(section.split("`scripts/dataset_artifacts.py`")[0])

    paths_only = {name for name in named if not name.startswith("scripts/")}
    assert paths_only == ALLOWED_ROOTS


def test_agents_md_forbids_the_paths_the_module_does() -> None:
    section = _section(AGENTS, "### Paths you may not change (dataset work)")

    assert _backticked(section) == set(dataset_artifacts.FORBIDDEN)


def test_the_agent_definition_lists_the_same_paths() -> None:
    allowed = _section(AGENT_DEFINITION, "## 수정 허용 경로")
    forbidden = _section(AGENT_DEFINITION, "## 수정 금지 경로")
    named = _backticked(allowed.split("이 목록의 기준은")[0])

    assert named == ALLOWED_ROOTS
    assert _backticked(forbidden) >= set(dataset_artifacts.FORBIDDEN)


def test_the_agent_definition_does_not_tell_the_agent_to_commit() -> None:
    done = _section(AGENT_DEFINITION, "## 완료 조건")

    assert "커밋하지 않고 PR 도 열지 않는다" in done
    assert "후 PR" not in done


def test_the_checklist_names_every_generator_the_module_names() -> None:
    checklist = _section(AGENTS, "### Checklist")
    for command in [*dataset_artifacts.GENERATED.values(), dataset_artifacts.SYNC_COMMAND]:
        script = command.split("{", 1)[0].removeprefix("uv run python ").strip()
        assert script in checklist, script
    assert "examples/{provider}/{dataset_key}.py" in checklist


def _pr_step() -> str:
    workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    steps = workflow["jobs"]["build"]["steps"]
    return str(next(step["run"] for step in steps if step.get("name") == "PR or needs-human"))


def test_the_workflow_commits_the_module_list_from_the_dispatch_commit() -> None:
    script = _pr_step()

    assert 'git show "$GITHUB_SHA:scripts/dataset_artifacts.py"' in script
    assert 'python3 /tmp/dataset_artifacts.py check "$DATASET" --base "$GITHUB_SHA"' in script
    assert 'python3 /tmp/dataset_artifacts.py paths "$DATASET"' in script
    # No path is named in the workflow any more: the list is the module's.
    assert 'git add -- "src/kpubdata/specs' not in script
    assert 'git add -- "tests/fixtures' not in script


def test_the_workflow_runs_the_generators_after_the_check() -> None:
    script = _pr_step()
    check = script.index("dataset_artifacts.py check")
    for command in [dataset_artifacts.SYNC_COMMAND, *dataset_artifacts.GENERATED.values()]:
        if command.startswith("make record"):
            continue  # the agent records against the live API; the workflow cannot
        assert command in script, command
        assert script.index(command) > check, f"{command} runs before the forbidden-path check"


# --------------------------------------------------------------------- the module itself


def test_paths_names_every_artifact_of_one_dataset() -> None:
    assert dataset_artifacts.paths("datago.apt_trade") == [
        "src/kpubdata/specs/datago/apt_trade.yaml",
        "examples/datago/apt_trade.py",
        "SUPPORTED_DATA.md",
        "src/kpubdata/dataset_metadata.json",
        "tests/fixtures/datago/apt_trade",
        "src/kpubdata/dataset_status.json",
        "docs/dataset-examples.md",
        "scripts/insecure_http_baseline.txt",
    ]


@pytest.mark.parametrize("dataset", ["datago", "datago.", ".apt_trade", "datago/x.y"])
def test_a_malformed_dataset_id_is_refused(dataset: str) -> None:
    with pytest.raises(ValueError):
        dataset_artifacts.paths(dataset)


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "insecure_http_baseline.txt").write_text("a\nb\n", encoding="utf-8")
    (tmp_path / "SUPPORTED_DATA.md").write_text("| x |\n", encoding="utf-8")
    _git(tmp_path, "add", "-A")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def _check(repo: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    code = dataset_artifacts.main(["check", "datago.x", "--root", str(repo), "--base", "HEAD"])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_dataset_artifacts_and_the_baseline_pass(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "examples" / "datago").mkdir(parents=True)
    (repo / "examples" / "datago" / "x.py").write_text("", encoding="utf-8")
    (repo / "SUPPORTED_DATA.md").write_text("| x |\n| y |\n", encoding="utf-8")
    (repo / "scripts" / "insecure_http_baseline.txt").write_text("a\n", encoding="utf-8")

    assert _check(repo, capsys) == (0, "", "")


def test_a_change_under_a_forbidden_path_fails(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "scripts" / "json.py").write_text("", encoding="utf-8")  # untracked counts too
    (repo / ".github").mkdir()
    (repo / ".github" / "x.yml").write_text("", encoding="utf-8")

    code, _, err = _check(repo, capsys)

    assert code == 1
    assert "may not change .github/x.yml" in err
    assert "may not change scripts/json.py" in err


def test_a_stray_file_elsewhere_is_named_and_left_out(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (repo / "notes.txt").write_text("", encoding="utf-8")
    (repo / "examples" / "datago").mkdir(parents=True)
    (repo / "examples" / "datago" / "other.py").write_text("", encoding="utf-8")

    code, out, _ = _check(repo, capsys)

    assert code == 0
    assert out.splitlines() == [
        "left out (not a datago.x artifact): examples/datago/other.py",
        "left out (not a datago.x artifact): notes.txt",
    ]
