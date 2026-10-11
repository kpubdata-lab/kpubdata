"""README.en.md dataset counts are generated and checked like README.md's (#903)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import gen_readme_datasets  # noqa: E402


def test_repository_readmes_are_current() -> None:
    assert gen_readme_datasets.main(["--check"]) == 0


def test_check_fails_when_english_count_is_wrong(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ko = tmp_path / "README.md"
    en = tmp_path / "README.en.md"
    ko.write_text(gen_readme_datasets.build_section("ko") + "\n", encoding="utf-8")
    stale = gen_readme_datasets.build_section("en").replace("datasets**: ", "datasets**: 9")
    en.write_text(stale + "\n", encoding="utf-8")
    monkeypatch.setattr(gen_readme_datasets, "README", ko)
    monkeypatch.setattr(gen_readme_datasets, "README_EN", en)

    assert gen_readme_datasets.main(["--check"]) == 1
    assert gen_readme_datasets.main([]) == 0
    assert gen_readme_datasets.main(["--check"]) == 0
