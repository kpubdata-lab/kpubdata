"""The catalogue baseline gate has to actually fail (#898).

Catalogue-only datasets may only shrink, and a key may not be declared by both a
catalogue and a spec. Most of these tests copy the repository's catalogues, specs and
baseline into a temporary root, plant one violation, and expect exit code 1.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = REPO_ROOT / "scripts" / "check_catalogue_baseline.py"


def _module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("check_catalogue_baseline", _SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_SCRIPT), "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    """A copy of what the gate reads: catalogues, specs and the baseline."""
    providers = REPO_ROOT / "src" / "kpubdata" / "providers"
    for catalogue in providers.glob("*/catalogue.json"):
        target = tmp_path / catalogue.relative_to(REPO_ROOT)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(catalogue, target)
    shutil.copytree(
        REPO_ROOT / "src" / "kpubdata" / "specs", tmp_path / "src" / "kpubdata" / "specs"
    )
    (tmp_path / "scripts").mkdir()
    shutil.copy(
        REPO_ROOT / "scripts" / "catalogue_only_baseline.txt",
        tmp_path / "scripts" / "catalogue_only_baseline.txt",
    )
    return tmp_path


def _add_catalogue_entry(root: Path, provider: str, dataset_key: str) -> None:
    path = root / "src" / "kpubdata" / "providers" / provider / "catalogue.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    entries.append({"dataset_key": dataset_key})
    path.write_text(json.dumps(entries), encoding="utf-8")


def test_the_repository_passes() -> None:
    result = _run(REPO_ROOT)

    assert result.returncode == 0, result.stderr


def test_the_copy_passes_before_anything_is_planted(repo: Path) -> None:
    """Otherwise every failure below could come from the copy, not the plant."""
    result = _run(repo)

    assert result.returncode == 0, result.stderr


def test_a_new_catalogue_only_entry_fails(repo: Path) -> None:
    _add_catalogue_entry(repo, "datago", "brand_new_dataset")

    result = _run(repo)

    assert result.returncode == 1
    assert "datago.brand_new_dataset is a new catalogue-only entry" in result.stderr


def test_a_catalogue_entry_a_spec_already_declares_fails(repo: Path) -> None:
    _add_catalogue_entry(repo, "datago", "apt_trade")

    result = _run(repo)

    assert result.returncode == 1
    assert "datago.apt_trade is declared by both a catalogue and a spec" in result.stderr


def test_a_baseline_line_without_its_catalogue_entry_fails(repo: Path) -> None:
    """Removing a catalogue entry without its baseline line is caught: the list shrinks."""
    path = repo / "src" / "kpubdata" / "providers" / "datago" / "catalogue.json"
    entries = json.loads(path.read_text(encoding="utf-8"))
    path.write_text(
        json.dumps([entry for entry in entries if entry["dataset_key"] != "asos_daily"]),
        encoding="utf-8",
    )

    result = _run(repo)

    assert result.returncode == 1
    assert "datago.asos_daily is no longer catalogue-only" in result.stderr


def test_a_former_localdata_duplicate_is_rejected() -> None:
    module = _module()

    problems = module.evaluate(
        catalogue={"localdata.bakery", "localdata.other"},
        specs={"localdata.bakery"},
        baseline={"localdata.other"},
    )

    assert problems == [
        "localdata.bakery is declared by both a catalogue and a spec; "
        "the spec serves it, so remove the catalogue entry"
    ]


def test_a_spec_only_localdata_dataset_passes() -> None:
    module = _module()

    problems = module.evaluate(
        catalogue={"localdata.other"},
        specs={"localdata.bakery"},
        baseline={"localdata.other"},
    )

    assert problems == []
