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
