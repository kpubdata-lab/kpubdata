"""The required-check checker has to actually fail (kpubdata-studio#416).

A required status check that no workflow produces does not fail a pull request — it
leaves it BLOCKED for ever, because GitHub waits for an absent check rather than
reporting it. The only way past is ``--admin``, which bypasses every other check too.

So the script that notices this gets tests that break a fixture on purpose, including
the two spellings that made the first two drafts wrong.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_required_checks.py"


def _load_script():
    """Load the script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("check_required_checks", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_required_checks"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return _load_script()


def _write(directory: Path, name: str, body: str) -> None:
    (directory / name).write_text(body, encoding="utf-8")


def test_a_plain_job_produces_its_name(tmp_path: Path, script) -> None:
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n  quality:\n    name: Lint & Type Check\n    runs-on: ubuntu-latest\n",
    )

    assert script.produced_contexts(tmp_path) == {"Lint & Type Check"}


def test_a_job_without_a_name_produces_its_id(tmp_path: Path, script) -> None:
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n  build:\n    runs-on: ubuntu-latest\n",
    )

    assert script.produced_contexts(tmp_path) == {"build"}


def test_a_matrix_name_that_interpolates_is_substituted_not_suffixed(
    tmp_path: Path, script
) -> None:
    """`Tests (py${{ matrix.python-version }})` becomes `Tests (py3.10)`.

    The first draft appended the combination to every matrix job, so it reported all
    four of this repository's real `Test (Python 3.x)` contexts as missing. A check
    that cries wolf about the list it is meant to confirm is worse than no check.
    """
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n"
        "  test:\n"
        "    name: Test (Python ${{ matrix.python-version }})\n"
        "    strategy:\n"
        "      matrix:\n"
        '        python-version: ["3.10", "3.11"]\n',
    )

    assert script.produced_contexts(tmp_path) == {"Test (Python 3.10)", "Test (Python 3.11)"}


def test_a_matrix_name_that_does_not_interpolate_gets_the_combination_appended(
    tmp_path: Path, script
) -> None:
    """This is the spelling that caused the outage: `… build (20)`."""
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n"
        "  quality:\n"
        "    name: Lint, type check, test, build\n"
        "    strategy:\n"
        "      matrix:\n"
        '        node-version: ["22", "24"]\n',
    )

    assert script.produced_contexts(tmp_path) == {
        "Lint, type check, test, build (22)",
        "Lint, type check, test, build (24)",
    }


def test_a_required_check_no_job_produces_is_reported(tmp_path: Path, script) -> None:
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n"
        "  quality:\n"
        "    name: Lint, type check, test, build\n"
        "    strategy:\n"
        "      matrix:\n"
        '        node-version: ["22", "24"]\n',
    )

    exit_code = script.main(
        ["--workflows", str(tmp_path), "--required", "Lint, type check, test, build (20)"]
    )

    assert exit_code == 1


def test_the_set_that_is_produced_passes(tmp_path: Path, script) -> None:
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n  gate:\n    name: CI gate\n    runs-on: ubuntu-latest\n",
    )

    assert script.main(["--workflows", str(tmp_path), "--required", "CI gate"]) == 0


def test_a_context_containing_commas_stays_one_context(tmp_path: Path, script) -> None:
    """`--required` takes one argument per context, never a comma-separated list.

    The name that caused the outage contains three commas. Splitting on them would
    turn the one context this script exists to catch into four it invented, and each
    of those four would be reported as missing — a failure for the wrong reason, which
    is how a check stops being believed.
    """
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n"
        "  quality:\n"
        "    name: Lint, type check, test, build\n"
        "    strategy:\n"
        "      matrix:\n"
        '        node-version: ["22"]\n',
    )

    assert (
        script.main(
            ["--workflows", str(tmp_path), "--required", "Lint, type check, test, build (22)"]
        )
        == 0
    )


def test_an_empty_workflow_directory_is_an_error_not_a_pass(tmp_path: Path, script) -> None:
    """Otherwise a wrong path reports that every required check is fine."""
    assert script.main(["--workflows", str(tmp_path), "--required", "anything"]) == 1


def test_this_repository_requires_only_checks_its_workflows_produce(script) -> None:
    """The real thing, read off disk. No network: branch protection is not consulted."""
    produced = script.produced_contexts(REPO_ROOT / ".github" / "workflows")

    assert "CI gate" in produced


def test_a_block_style_matrix_is_expanded(tmp_path: Path, script) -> None:
    """studio#416 again: a block list matrix made `Lint` look like one plain job."""
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n"
        "  lint:\n"
        "    name: Lint\n"
        "    strategy:\n"
        "      matrix:\n"
        "        python-version:\n"
        '          - "3.11"\n'
        '          - "3.12"\n',
    )

    assert script.produced_contexts(tmp_path) == {"Lint (3.11)", "Lint (3.12)"}
    assert script.main(["--workflows", str(tmp_path), "--required", "Lint"]) == 1


def test_a_multi_axis_matrix_lists_values_in_key_order(tmp_path: Path, script) -> None:
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non: pull_request\njobs:\n"
        "  t:\n"
        "    name: T\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os: [linux, mac]\n"
        "        py:\n"
        "          - 3.11\n",
    )

    assert script.produced_contexts(tmp_path) == {"T (linux, 3.11)", "T (mac, 3.11)"}


def test_an_include_entry_adds_a_combination(tmp_path: Path, script) -> None:
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n"
        "  t:\n"
        "    name: T\n"
        "    strategy:\n"
        "      matrix:\n"
        "        py: ['3.11']\n"
        "        include:\n"
        "          - py: '3.13'\n"
        "          - py: '3.11'\n"
        "            experimental: true\n",
    )

    # The second entry matches an existing combination and extends it; the first
    # matches none and stands alone.
    assert script.produced_contexts(tmp_path) == {"T (3.11, true)", "T (3.13)"}


def test_an_exclude_entry_removes_a_combination(tmp_path: Path, script) -> None:
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n"
        "  t:\n"
        "    name: T\n"
        "    strategy:\n"
        "      matrix:\n"
        "        py: ['3.11', '3.12']\n"
        "        exclude:\n"
        "          - py: '3.12'\n",
    )

    assert script.produced_contexts(tmp_path) == {"T (3.11)"}


def test_a_dispatch_only_workflow_produces_nothing_for_pull_requests(
    tmp_path: Path, script
) -> None:
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n  gate:\n    name: CI gate\n",
    )
    _write(
        tmp_path,
        "build.yml",
        "name: Build\non:\n  workflow_dispatch:\njobs:\n  gate:\n    name: gate\n",
    )

    assert script.produced_contexts(tmp_path) == {"CI gate"}
    assert script.main(["--workflows", str(tmp_path), "--required", "CI gate", "gate"]) == 1


@pytest.mark.parametrize(
    "trigger",
    [
        "on: pull_request",
        "on: [push, pull_request]",
        "on:\n  push:\n  pull_request_target:\n    types: [opened]",
    ],
)
def test_pull_request_trigger_spellings_are_all_recognised(
    tmp_path: Path, script, trigger: str
) -> None:
    _write(tmp_path, "ci.yml", f"name: CI\n{trigger}\njobs:\n  a:\n    name: A\n")

    assert script.produced_contexts(tmp_path) == {"A"}


@pytest.mark.parametrize("trigger", ["on: push", "on: [push, schedule]", "on:\n  push:"])
def test_workflows_without_a_pull_request_trigger_are_ignored(
    tmp_path: Path, script, trigger: str
) -> None:
    _write(tmp_path, "ci.yml", f"name: CI\n{trigger}\njobs:\n  a:\n    name: A\n")

    assert script.produced_contexts(tmp_path) == set()


def _matrix_contexts(script, tmp_path: Path, matrix: str, name: str = "T") -> set[str]:
    """Contexts of one job whose ``strategy.matrix`` is the given block (already indented)."""
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\njobs:\n  t:\n"
        f"    name: {name}\n    strategy:\n      matrix:\n{matrix}",
    )
    return script.produced_contexts(tmp_path)


def test_githubs_documented_include_example(tmp_path: Path, script) -> None:
    """The fruit/animal/color/shape example from GitHub's matrix documentation."""
    contexts = _matrix_contexts(
        script,
        tmp_path,
        "        fruit: [apple, pear]\n"
        "        animal: [cat, dog]\n"
        "        include:\n"
        "          - color: green\n"
        "          - color: pink\n"
        "            animal: cat\n"
        "          - fruit: apple\n"
        "            shape: circle\n"
        "          - fruit: banana\n"
        "          - fruit: banana\n"
        "            animal: cat\n",
    )

    assert contexts == {
        "T (apple, cat, pink, circle)",
        "T (apple, dog, green, circle)",
        "T (pear, cat, pink)",
        "T (pear, dog, green)",
        "T (banana)",
        "T (banana, cat)",
    }


def test_include_naming_keys_no_combination_has_does_not_crash(tmp_path: Path, script) -> None:
    contexts = _matrix_contexts(
        script,
        tmp_path,
        "        fruit: [apple]\n"
        "        animal: [cat]\n"
        "        include:\n"
        "          - fruit: banana\n"
        "          - fruit: banana\n"
        "            animal: cat\n",
    )

    assert contexts == {"T (apple, cat)", "T (banana)", "T (banana, cat)"}


def test_an_include_without_axis_keys_extends_every_combination(tmp_path: Path, script) -> None:
    contexts = _matrix_contexts(
        script, tmp_path, "        py: ['3.11', '3.12']\n        include:\n          - flag: x\n"
    )

    assert contexts == {"T (3.11, x)", "T (3.12, x)"}


def test_a_later_include_overwrites_a_value_an_earlier_one_added(tmp_path: Path, script) -> None:
    contexts = _matrix_contexts(
        script,
        tmp_path,
        "        py: ['3.11']\n        include:\n          - color: green\n          - color: pink\n",
    )

    assert contexts == {"T (3.11, pink)"}


@pytest.mark.parametrize(
    "matrix",
    [
        "        include: ${{ fromJSON(needs.plan.outputs.matrix) }}\n",
        "        py: ${{ fromJSON(needs.plan.outputs.py) }}\n",
        "        py: ['3.11']\n        exclude:\n          - py: '3.11'\n",
    ],
    ids=["expression include", "expression axis", "exclude removes everything"],
)
def test_an_unexpandable_matrix_does_not_report_the_bare_name(
    tmp_path: Path, script, matrix: str
) -> None:
    assert _matrix_contexts(script, tmp_path, matrix) == set()
    assert script.main(["--workflows", str(tmp_path), "--required", "T"]) == 1


def test_an_expression_matrix_is_explained(
    tmp_path: Path, script, capsys: pytest.CaptureFixture[str]
) -> None:
    _matrix_contexts(script, tmp_path, "        include: ${{ fromJSON(x) }}\n")

    script.main(["--workflows", str(tmp_path), "--required", "T"])

    assert "cannot verify" in capsys.readouterr().err


def test_a_reusable_workflow_caller_is_not_its_own_context(tmp_path: Path, script) -> None:
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non: pull_request\njobs:\n  call:\n    name: Caller\n"
        "    uses: ./.github/workflows/inner.yml\n",
    )

    assert script.produced_contexts(tmp_path) == set()
    assert script.main(["--workflows", str(tmp_path), "--required", "Caller"]) == 1


@pytest.mark.parametrize(
    "trigger",
    [
        "on:\n  pull_request:\n    paths: ['src/**']",
        "on:\n  pull_request:\n    paths-ignore: ['docs/**']",
        "on:\n  pull_request:\n    branches: [release]",
        "on:\n  pull_request:\n    branches: [main, '!main']",
    ],
)
def test_a_filtered_pull_request_trigger_is_not_reliably_produced(
    tmp_path: Path, script, trigger: str, capsys: pytest.CaptureFixture[str]
) -> None:
    _write(tmp_path, "ci.yml", f"name: CI\n{trigger}\njobs:\n  a:\n    name: A\n")
    _write(tmp_path, "gate.yml", "name: G\non: pull_request\njobs:\n  g:\n    name: G\n")

    assert script.produced_contexts(tmp_path) == {"G"}
    assert script.main(["--workflows", str(tmp_path), "--required", "A"]) == 1
    assert "filtered" in capsys.readouterr().err


def test_a_context_is_reliable_when_any_workflow_produces_it_unfiltered(
    tmp_path: Path, script
) -> None:
    _write(
        tmp_path,
        "a.yml",
        "name: A\non:\n  pull_request:\n    paths: ['x']\n  pull_request_target:\njobs:\n  a:\n    name: A\n",
    )

    assert script.produced_contexts(tmp_path) == {"A"}


def test_yaml_one_one_booleans_keep_githubs_spelling(tmp_path: Path, script) -> None:
    """GitHub reads `yes`/`on` as strings and `010` as ten; PyYAML's defaults do not."""
    contexts = _matrix_contexts(
        script, tmp_path, "        flag: [yes, off]\n        n: [010]\n        t: [true]\n"
    )

    assert contexts == {"T (yes, 10, true)", "T (off, 10, true)"}


def test_the_real_required_set_comes_from_unfiltered_workflows(script) -> None:
    produced = script.produced_contexts(REPO_ROOT / ".github" / "workflows")

    assert {"CI gate", "PR title"} <= produced


def test_a_branches_filter_naming_the_protected_branch_is_fine(tmp_path: Path, script) -> None:
    """`branches: [main]` runs for every pull request into main, which is what is protected."""
    _write(
        tmp_path,
        "ci.yml",
        "name: CI\non:\n  pull_request:\n    branches: [main]\n    types: [opened]\n"
        "jobs:\n  a:\n    name: A\n",
    )

    assert script.produced_contexts(tmp_path) == {"A"}
