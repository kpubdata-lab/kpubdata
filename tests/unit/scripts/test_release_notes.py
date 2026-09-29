"""Release notes come from the CHANGELOG, and a release without them stops.

kpubdata 0.7.0 was published with its entries still under `[Unreleased]` and a body
of 110 pull request titles. These tests pin the two commands that prevent both.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "release_notes.py"
DAY = dt.date(2026, 10, 29)

BRACKETED = """# Changelog

## [Unreleased]

### Fixed

- a fix (#1)

## [0.7.0] — 2026-09-28

### Added

- a feature (#2)
"""

V_STYLE = """# 변경 이력

## [Unreleased]

### Fixed
- pin kpubdata 0.7 (#746)

## v0.4.0 — 2026-09-28

### Added
- everything
"""


def _load_script():
    """Load the script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("release_notes", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["release_notes"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def script():
    return _load_script()


def test_extract_returns_the_section_only(script) -> None:
    notes = script.extract(BRACKETED, "0.7.0")
    assert notes == "### Added\n\n- a feature (#2)"


def test_extract_accepts_v_prefixed_headings(script) -> None:
    assert "everything" in script.extract(V_STYLE, "0.4.0")


def test_extract_refuses_a_missing_version(script) -> None:
    with pytest.raises(script.ChangelogError, match="no section for 0.8.0"):
        script.extract(BRACKETED, "0.8.0")


def test_extract_refuses_an_empty_section(script) -> None:
    text = "## [0.7.1] — 2026-10-01\n\n### Fixed\n\n## [0.7.0]\n\n- x\n"
    with pytest.raises(script.ChangelogError, match="empty"):
        script.extract(text, "0.7.1")


@pytest.mark.parametrize(
    ("heading", "version"),
    [("## v0.4", "0.4.0"), ("## v0.4.10", "0.4.1"), ("## [0.4.0rc1]", "0.4.0")],
)
def test_a_near_miss_is_not_the_version(script, heading: str, version: str) -> None:
    """`## v0.4` is a line, not 0.4.0 — the old builder heading must not pass."""
    with pytest.raises(script.ChangelogError):
        script.extract(f"{heading}\n\n- x\n", version)


def test_promote_renames_unreleased_in_the_file_style(script) -> None:
    promoted = script.promote(BRACKETED, "0.7.1", DAY)
    assert "## [Unreleased]\n\n## [0.7.1] — 2026-10-29\n\n### Fixed" in promoted
    assert script.extract(promoted, "0.7.1") == "### Fixed\n\n- a fix (#1)"

    promoted = script.promote(V_STYLE, "0.4.1", DAY)
    assert "## v0.4.1 — 2026-10-29" in promoted
    assert promoted.index("## [Unreleased]") < promoted.index("## v0.4.1")


def test_promote_leaves_a_written_section_alone(script) -> None:
    assert script.promote(BRACKETED, "0.7.0", DAY) == BRACKETED


def test_promote_refuses_when_there_is_nothing_to_release(script) -> None:
    empty = "## [Unreleased]\n\n## [0.7.0]\n\n- x\n"
    with pytest.raises(script.ChangelogError, match="nothing to release"):
        script.promote(empty, "0.7.1", DAY)


def test_main_writes_notes_with_the_compare_link(script, tmp_path: Path) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(BRACKETED, encoding="utf-8")
    output = tmp_path / "notes.md"
    code = script.main(
        [
            "extract",
            "v0.7.0",
            "--changelog",
            str(changelog),
            "--compare-url",
            "https://example.test/compare",
            "--output",
            str(output),
        ]
    )
    assert code == 0
    assert output.read_text(encoding="utf-8").endswith(
        "**Full changelog**: https://example.test/compare\n"
    )


def test_main_fails_without_a_section(script, tmp_path: Path, capsys) -> None:
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text(BRACKETED, encoding="utf-8")
    assert script.main(["extract", "0.9.0", "--changelog", str(changelog)]) == 1
    assert "::error::" in capsys.readouterr().err


def test_this_repositorys_changelog_serves_the_released_version(script) -> None:
    """0.7.0 shipped with no section; the file must now answer for it."""
    text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert "Security" in script.extract(text, "0.7.0")


AFTER_PRERELEASES = """# Changelog

## [Unreleased]

### Fixed

- after a1 (#5)

## [0.7.1a1] — 2026-10-20

### Added

- second pre-release (#4)

## [0.7.1a0] — 2026-10-15

### Fixed

- first pre-release (#3)

## [0.7.0] — 2026-09-28

### Added

- a feature (#2)
"""


def test_promote_final_folds_its_prereleases(script) -> None:
    """#622: `promote 0.7.1` after `promote 0.7.1a0` used to find nothing to release."""
    promoted = script.promote(AFTER_PRERELEASES, "0.7.1", DAY)
    assert "0.7.1a" not in promoted
    assert script.extract(promoted, "0.7.1") == (
        "### Fixed\n\n- after a1 (#5)\n- first pre-release (#3)\n\n"
        "### Added\n\n- second pre-release (#4)"
    )
    assert "## [Unreleased]\n\n## [0.7.1] — 2026-10-29" in promoted
    assert promoted.endswith("## [0.7.0] — 2026-09-28\n\n### Added\n\n- a feature (#2)\n")


def test_promote_final_works_with_an_empty_unreleased(script) -> None:
    text = AFTER_PRERELEASES.replace("### Fixed\n\n- after a1 (#5)\n\n", "", 1)
    promoted = script.promote(text, "0.7.1", DAY)
    assert "second pre-release" in script.extract(promoted, "0.7.1")
    assert "first pre-release" in script.extract(promoted, "0.7.1")


def test_promote_prerelease_does_not_fold_siblings(script) -> None:
    promoted = script.promote(AFTER_PRERELEASES, "0.7.1a2", DAY)
    assert script.extract(promoted, "0.7.1a2") == "### Fixed\n\n- after a1 (#5)"
    assert "## [0.7.1a1]" in promoted


def test_promote_does_not_fold_another_versions_prereleases(script) -> None:
    text = AFTER_PRERELEASES.replace("0.7.1a", "0.7.10a")
    promoted = script.promote(text, "0.7.1", DAY)
    assert "## [0.7.10a1]" in promoted
    assert script.extract(promoted, "0.7.1") == "### Fixed\n\n- after a1 (#5)"


@pytest.mark.parametrize(
    ("version", "expected"),
    [("0.7.1a0", True), ("v0.7.1rc1", True), ("0.7.1b2", True), ("0.7.1", False)],
)
def test_prerelease_command(script, capsys, version: str, expected: bool) -> None:
    assert script.main(["prerelease", version]) == 0
    assert capsys.readouterr().out.strip() == str(expected).lower()
