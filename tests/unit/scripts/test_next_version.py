"""Raising a version has to be testable, so it is not a heredoc in a workflow (#586).

The old bump lived inline in `publish-pypi.yml` and could only be exercised by
dispatching a real release. A mistake in it produced a tag before anyone could see it.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "next_version.py"


def _load_script():
    """Load the script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("next_version", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["next_version"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return _load_script()


@pytest.mark.parametrize(
    ("current", "bump", "expected"),
    [
        ("0.6.0", "patch", "0.6.1"),
        ("0.6.0", "minor", "0.7.0"),
        ("0.6.0", "pre", "0.6.1a0"),
        ("0.6.9", "patch", "0.6.10"),
        ("0.6.1a0", "pre", "0.6.1a1"),
        ("0.6.1a9", "pre", "0.6.1a10"),
        ("1.2.3", "minor", "1.3.0"),
    ],
)
def test_raising(script, current: str, bump: str, expected: str) -> None:
    assert script.next_version(current, bump) == expected


def test_finishing_a_prerelease_drops_the_suffix_rather_than_raising_the_patch(script) -> None:
    """0.6.1a1 -> 0.6.1, not 0.6.2.

    Raising it would skip the version that was announced as a pre-release and then
    never published under that number, which is the confusing outcome.
    """
    assert script.next_version("0.6.1a1", "patch") == "0.6.1"


def test_a_development_version_is_refused(script) -> None:
    """`0.4.0.dev0` says the version is not finished. It is not a starting point."""
    with pytest.raises(script.VersionError, match="dev"):
        script.next_version("0.4.0.dev0", "patch")


def test_an_unknown_bump_is_refused(script) -> None:
    with pytest.raises(script.VersionError, match="unknown bump"):
        script.next_version("0.6.0", "major")


def test_it_prints_github_output_lines(script, tmp_path: Path, capsys) -> None:
    """The workflow appends the output verbatim, so the shape is the contract."""
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\nversion = "0.6.0"\n', encoding="utf-8")

    exit_code = script.main(["minor", "--pyproject", str(pyproject)])

    assert exit_code == 0
    assert capsys.readouterr().out == "new_version=0.7.0\ntag=v0.7.0\n"


def test_a_pyproject_without_a_version_is_an_error(script, tmp_path: Path, capsys) -> None:
    pyproject = tmp_path / "pyproject.toml"
    pyproject.write_text('[project]\nname = "x"\n', encoding="utf-8")

    assert script.main(["patch", "--pyproject", str(pyproject)]) == 1
    assert "no [project] version" in capsys.readouterr().err
