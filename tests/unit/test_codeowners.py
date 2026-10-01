"""CODEOWNERS covers the R3 paths, and every path it names exists (#520, #629).

A rename silently drops coverage: GitHub ignores a pattern that matches nothing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
CODEOWNERS = REPO_ROOT / ".github" / "CODEOWNERS"

#: Paths that must require an owner's review. Extend it when a new R3 path appears.
REQUIRED = [
    "/.github/",
    "/src/kpubdata/config.py",
    "/src/kpubdata/transport/",
    "/src/kpubdata/specs/",
    "/docs/governance/",
    "/src/kpubdata/_hosts.py",
    "/scripts/record.py",
    "/scripts/verify_spec.py",
    "/scripts/check_fixture_authorship.py",
    "/scripts/legacy_evidence_baseline.txt",
    "/tests/fixtures/**/*.raw.json",
    "/tests/fixtures/**/*.meta.json",
    "/tests/fixtures/**/*.expected.json",
    "/scripts/release_notes.py",
    "/scripts/set_version.py",
    "/scripts/next_version.py",
    "/scripts/release_window.py",
    "/scripts/conventional_title.py",
    "/pyproject.toml",
    "/uv.lock",
]


def _patterns() -> list[str]:
    lines = CODEOWNERS.read_text(encoding="utf-8").splitlines()
    return [line.split()[0] for line in lines if line.strip() and not line.startswith("#")]


@pytest.mark.parametrize("path", REQUIRED)
def test_required_path_is_owned(path: str) -> None:
    assert path in _patterns()


@pytest.mark.parametrize("pattern", _patterns())
def test_every_pattern_names_something_that_exists(pattern: str) -> None:
    """A literal pattern must exist; a glob pattern must match at least one file.

    GitHub silently ignores a pattern that matches nothing, so a typo in a
    wildcard pattern is a silent coverage drop the same way a renamed path is.
    """
    relative = pattern.lstrip("/")
    if "*" in relative:
        assert list(REPO_ROOT.glob(relative)), pattern
    else:
        assert (REPO_ROOT / relative).exists(), pattern
