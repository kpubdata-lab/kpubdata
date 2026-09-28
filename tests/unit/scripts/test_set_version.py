"""Writing the version has to reach every file that declares it (#718).

kpubdata-builder#744 changed one line of `pyproject.toml` and nine checks failed:
`uv.lock` repeats the project's own version and `uv lock --check` noticed. A release
workflow that writes only the first file produces that failure on every release.

The dangerous failure is the quiet one — a pattern that stops matching writes the file
back unchanged and the release carries the old version under the new tag — so these
tests are mostly about what must *not* pass.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "set_version.py"

PYPROJECT = '[project]\nname = "kpubdata-builder"\nversion = "0.4.0.dev0"\n'
UV_LOCK = (
    "version = 1\n\n"
    '[[package]]\nname = "httpx"\nversion = "0.28.1"\nsource = { registry = "x" }\n\n'
    '[[package]]\nname = "kpubdata-builder"\nversion = "0.4.0.dev0"\n'
    'source = { editable = "." }\n'
)


def _load_script():
    spec = importlib.util.spec_from_file_location("set_version", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["set_version"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return _load_script()


@pytest.fixture
def python_repo(tmp_path: Path) -> Path:
    (tmp_path / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (tmp_path / "uv.lock").write_text(UV_LOCK, encoding="utf-8")
    return tmp_path


@pytest.fixture
def node_repo(tmp_path: Path) -> Path:
    (tmp_path / "package.json").write_text(
        json.dumps({"name": "kpubdata-studio", "version": "0.4.0"}, indent=2) + "\n",
        encoding="utf-8",
    )
    (tmp_path / "package-lock.json").write_text(
        '{\n  "name": "kpubdata-studio",\n  "version": "0.4.0",\n'
        '  "lockfileVersion": 3,\n  "packages": {\n'
        '    "": {\n      "name": "kpubdata-studio",\n      "version": "0.4.0",\n'
        '      "dependencies": { "react": "19.2.0" }\n    }\n  }\n}\n',
        encoding="utf-8",
    )
    return tmp_path


def test_it_reaches_the_lockfile_as_well_as_pyproject(script, python_repo: Path) -> None:
    written = script.set_version(python_repo, "0.4.0")

    assert written == {"pyproject.toml": 1, "uv.lock": 1}
    assert 'version = "0.4.0"\n' in (python_repo / "pyproject.toml").read_text()
    assert 'name = "kpubdata-builder"\nversion = "0.4.0"' in (python_repo / "uv.lock").read_text()


def test_a_dependency_in_the_lockfile_is_left_alone(script, python_repo: Path) -> None:
    """The project's entry is the one with `source = { editable = "." }`."""
    script.set_version(python_repo, "0.9.9")

    assert 'name = "httpx"\nversion = "0.28.1"' in (python_repo / "uv.lock").read_text()


def test_it_reaches_both_versions_in_package_lock(script, node_repo: Path) -> None:
    """npm writes the version twice and `npm ci` compares them. One is worse than none."""
    written = script.set_version(node_repo, "0.5.0")

    assert written == {"package.json": 1, "package-lock.json": 2}
    lock = json.loads((node_repo / "package-lock.json").read_text())
    assert lock["version"] == "0.5.0"
    assert lock["packages"][""]["version"] == "0.5.0"


def test_a_dependency_pin_is_not_mistaken_for_the_version(script, node_repo: Path) -> None:
    lock = json.loads((node_repo / "package-lock.json").read_text())
    script.set_version(node_repo, "0.5.0")

    assert (
        json.loads((node_repo / "package-lock.json").read_text())["packages"][""]["dependencies"]
        == lock["packages"][""]["dependencies"]
    )


def test_a_file_that_matches_nothing_is_an_error(script, python_repo: Path) -> None:
    (python_repo / "uv.lock").write_text("version = 1\n# no project entry\n", encoding="utf-8")

    with pytest.raises(script.VersionWriteError, match="uv.lock"):
        script.set_version(python_repo, "0.4.0")


def test_nothing_is_written_when_one_file_cannot_be(script, python_repo: Path) -> None:
    """The first draft wrote pyproject, then failed on uv.lock, leaving the repository
    half updated — the exact state this script exists to prevent."""
    (python_repo / "uv.lock").write_text("version = 1\n# no project entry\n", encoding="utf-8")

    with pytest.raises(script.VersionWriteError):
        script.set_version(python_repo, "0.4.0")

    assert 'version = "0.4.0.dev0"' in (python_repo / "pyproject.toml").read_text()


def test_the_project_name_comes_from_the_file_not_the_directory(script, tmp_path: Path) -> None:
    """A checkout can sit anywhere; a runner's path is not the package's identity.

    Deriving it from the directory made the first version fail against a copy of a
    repository, which is precisely how a release gets rehearsed.
    """
    elsewhere = tmp_path / "work" / "_temp" / "checkout-7f3a"
    elsewhere.mkdir(parents=True)
    (elsewhere / "pyproject.toml").write_text(PYPROJECT, encoding="utf-8")
    (elsewhere / "uv.lock").write_text(UV_LOCK, encoding="utf-8")

    assert script.set_version(elsewhere, "0.4.0") == {"pyproject.toml": 1, "uv.lock": 1}
    assert 'name = "kpubdata-builder"\nversion = "0.4.0"' in (elsewhere / "uv.lock").read_text()


def test_a_directory_declaring_nothing_is_an_error(script, tmp_path: Path) -> None:
    with pytest.raises(script.VersionWriteError, match="no name is declared"):
        script.set_version(tmp_path, "0.4.0")
