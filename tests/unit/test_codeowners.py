"""CODEOWNERS covers the R3 paths, and every path it names exists (#520, #629).

A rename silently drops coverage: GitHub ignores a pattern that matches nothing.
"""

from __future__ import annotations

from fnmatch import fnmatch
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
    "/scripts/*_baseline.txt",
    "/tests/fixtures/**/*.raw.json",
    "/tests/fixtures/**/*.meta.json",
    "/tests/fixtures/**/*.expected.json",
    "/scripts/release_notes.py",
    "/scripts/set_version.py",
    "/scripts/next_version.py",
    "/scripts/release_window.py",
    "/scripts/conventional_title.py",
    "/scripts/r3_review.py",
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


def test_every_ratchet_baseline_is_owned() -> None:
    """Every scripts/*_baseline.txt file must fall under an owned pattern (#764).

    A count-only ratchet cannot stop one entry being swapped for another, which
    is why each baseline file sits behind an owner. The direction matters: the
    test above keeps CODEOWNERS honest about what it names, and this one keeps
    it honest about what exists — a baseline added without a pattern would be
    the silent hole the swap needs.
    """
    baselines = sorted((REPO_ROOT / "scripts").glob("*_baseline.txt"))
    assert baselines, "scripts/*_baseline.txt matched nothing — the glob moved?"
    patterns = [pattern.lstrip("/") for pattern in _patterns()]
    for baseline in baselines:
        relative = str(baseline.relative_to(REPO_ROOT))
        assert any(fnmatch(relative, pattern) for pattern in patterns), relative
