"""The independence gate has to actually fail (#668).

ADR 0007 Rules 1 and 2: KPubData never depends on KPubData Builder or KPubData
Studio. A gate nobody has watched fail is not a gate, so most of these tests plant
a violation in a temporary repository and expect exit code 1.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = REPO_ROOT / "scripts" / "check_independence.py"

_CLEAN_PYPROJECT = """\
[project]
name = "kpubdata"
dependencies = [
  "httpx>=0.27,<1",
]

[project.optional-dependencies]
dev = ["pytest>=8"]
"""


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


def _repo(
    tmp_path: Path, source: str = "import httpx\n", pyproject: str = _CLEAN_PYPROJECT
) -> Path:
    package = tmp_path / "src" / "kpubdata"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(source, encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text(pyproject, encoding="utf-8")
    return tmp_path


def test_this_repository_passes() -> None:
    """The case the gate must not break: KPubData as it is today."""
    result = _run(REPO_ROOT)
    assert result.returncode == 0, result.stderr


def test_a_clean_repository_passes(tmp_path: Path) -> None:
    result = _run(_repo(tmp_path))
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "source",
    [
        "import kpubdata_builder\n",
        "import kpubdata_builder.service as svc\n",
        "from kpubdata_builder import BuildSpec\n",
        "from kpubdata_builder.spec import BuildSpec\n",
        "def f():\n    import kpubdata_studio\n",
        "import importlib\nimportlib.import_module('kpubdata_builder')\n",
        "__import__('kpubdata_builder.spec')\n",
        "import kpubdata_watch\n",
        "from kpubdata_watch.status import Verdict\n",
    ],
)
def test_importing_builder_or_studio_fails(tmp_path: Path, source: str) -> None:
    result = _run(_repo(tmp_path, source=source))
    assert result.returncode == 1
    assert "src/kpubdata/__init__.py" in result.stderr


def test_a_violation_deep_in_the_tree_is_found(tmp_path: Path) -> None:
    root = _repo(tmp_path)
    nested = root / "src" / "kpubdata" / "providers" / "x"
    nested.mkdir(parents=True)
    (nested / "adapter.py").write_text("from kpubdata_builder import x\n", encoding="utf-8")

    result = _run(root)

    assert result.returncode == 1
    assert "providers/x/adapter.py:1" in result.stderr


@pytest.mark.parametrize(
    "requirement",
    [
        '"kpubdata-builder>=0.5"',
        '"kpubdata_builder"',
        "\"KPubData.Studio ; python_version >= '3.11'\"",
        '"kpubdata-studio[extra]==1.0"',
        '"kpubdata-watch>=0.1"',
    ],
)
def test_declaring_builder_or_studio_as_a_dependency_fails(
    tmp_path: Path, requirement: str
) -> None:
    pyproject = _CLEAN_PYPROJECT.replace(
        '"httpx>=0.27,<1",', f'"httpx>=0.27,<1",\n  {requirement},'
    )
    result = _run(_repo(tmp_path, pyproject=pyproject))
    assert result.returncode == 1
    assert "pyproject.toml" in result.stderr


def test_a_uv_source_key_fails(tmp_path: Path) -> None:
    pyproject = _CLEAN_PYPROJECT + '\n[tool.uv.sources]\nkpubdata-builder = { path = "../b" }\n'
    result = _run(_repo(tmp_path, pyproject=pyproject))
    assert result.returncode == 1
    assert "key" in result.stderr


@pytest.mark.parametrize(
    "harmless",
    [
        "import kpubdata\n",
        "import kpubdata_builderish\n",
        "import kpubdata_watchdog\n",
        "from . import builder\n",
        "NAME = 'kpubdata_builder'\n",
    ],
)
def test_names_that_only_look_alike_pass(tmp_path: Path, harmless: str) -> None:
    result = _run(_repo(tmp_path, source=harmless))
    assert result.returncode == 0, result.stderr


def test_a_missing_src_fails_rather_than_passing_empty(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(_CLEAN_PYPROJECT, encoding="utf-8")
    result = _run(tmp_path)
    assert result.returncode == 1
