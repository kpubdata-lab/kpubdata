"""Public GitHub Releases show curated summaries, not full change logs (#982)."""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "release_notes.py"

FULL_CHANGELOG = """# Changelog

## [Unreleased]

### Highlights

- Clearer record fields (#1).
- An existing provider now reports credential errors consistently (#2).

### Upgrade notes

- Catch `AuthError` rather than `TransportError` for provider refusals (#2).

### Known limitations

- Live checks require a configured runner (#3).

### Added

- An internal implementation paragraph that should stay in the full changelog (#99).

## [0.10.0] — 2026-10-09

### Fixed

- Old maintenance detail.
"""


@pytest.fixture
def script():
    module_spec = importlib.util.spec_from_file_location("release_notes", SCRIPT)
    assert module_spec is not None and module_spec.loader is not None
    module = importlib.util.module_from_spec(module_spec)
    sys.modules["release_notes"] = module
    module_spec.loader.exec_module(module)
    return module


def test_public_release_notes_include_only_curated_content(script) -> None:
    text = script.promote(FULL_CHANGELOG, "0.11.0", dt.date(2026, 11, 15))
    summary = script.render_public_notes(text, "0.11.0")
    assert "## KPubData SDK v0.11.0" in summary
    assert "Clearer record fields (#1)" in summary
    assert "Catch `AuthError`" in summary
    assert "Live checks require a configured runner" in summary
    assert 'pip install -U "kpubdata==0.11.0"' in summary
    assert "blob/v0.11.0/CHANGELOG.md" in summary
    assert "internal implementation paragraph" not in summary
    assert "Old maintenance detail" not in summary
    assert script.render_public_notes(text, "0.11.0") == summary


@pytest.mark.parametrize("missing", ["Highlights", "Upgrade notes", "Known limitations"])
def test_public_release_refuses_missing_curated_section(script, missing: str) -> None:
    text = script.promote(FULL_CHANGELOG, "0.11.0", dt.date(2026, 11, 15))
    text = text.replace(f"### {missing}", f"### Wrong {missing}")
    with pytest.raises(script.ChangelogError, match="require CHANGELOG headings"):
        script.render_public_notes(text, "0.11.0")


def test_public_release_refuses_too_many_highlights(script) -> None:
    text = script.promote(FULL_CHANGELOG, "0.11.0", dt.date(2026, 11, 15))
    text = text.replace(
        "### Upgrade notes",
        "- Extra #3\n- Extra #4\n- Extra #5\n- Extra #6\n\n### Upgrade notes",
    )
    with pytest.raises(script.ChangelogError, match="1 to 5"):
        script.render_public_notes(text, "0.11.0")


def test_public_release_refuses_non_bullet_summary(script) -> None:
    text = script.promote(FULL_CHANGELOG, "0.11.0", dt.date(2026, 11, 15))
    text = text.replace(
        "- Live checks require a configured runner (#3).",
        "Live checks are not available.",
    )
    with pytest.raises(script.ChangelogError, match="one-line Markdown bullets"):
        script.render_public_notes(text, "0.11.0")


def test_extract_still_returns_complete_history(script) -> None:
    text = script.promote(FULL_CHANGELOG, "0.11.0", dt.date(2026, 11, 15))
    assert "internal implementation paragraph" in script.extract(text, "0.11.0")


def test_public_cli_writes_summary_and_compare_link(script, tmp_path: Path) -> None:
    text = script.promote(FULL_CHANGELOG, "0.11.0", dt.date(2026, 11, 15))
    changelog = tmp_path / "CHANGELOG.md"
    output = tmp_path / "release.md"
    changelog.write_text(text, encoding="utf-8")
    result = script.main(
        [
            "extract",
            "0.11.0",
            "--public",
            "--changelog",
            str(changelog),
            "--compare-url",
            "https://github.com/kpubdata-lab/kpubdata/compare/v0.10.0...v0.11.0",
            "--output",
            str(output),
        ]
    )
    assert result == 0
    rendered = output.read_text(encoding="utf-8")
    assert rendered.count("### Highlights") == 1
    assert rendered.count("**Full changelog**") == 1
    assert "compare/v0.10.0...v0.11.0" in rendered
    assert "internal implementation paragraph" not in rendered


def test_upcoming_sdk_changelog_has_a_verified_summary(script) -> None:
    """The active release branch can be promoted without an empty public summary."""
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    promoted = script.promote(text, "0.11.0", dt.date(2026, 11, 15))
    summary = script.render_public_notes(promoted, "0.11.0")
    assert "### Upgrade notes" in summary
    assert "### Known limitations" in summary
    assert "### Added" not in summary
