#!/usr/bin/env python3
"""Release notes come from the CHANGELOG, and a release without them does not happen.

The first releases of all three repositories used `gh release create --generate-notes`
alone. That lists every merged pull request title in merge order: kpubdata 0.7.0 buried
four credential and TLS fixes among seventeen translation pull requests, and Studio 0.4.0
had no earlier tag, so its notes were the repository's entire history. Meanwhile the
CHANGELOG, which is where the curated account lives, was not read by anything — and
kpubdata 0.7.0 shipped with its entries still under `[Unreleased]`.

Two commands, both used by `.github/actions/release-notes`:

    promote VERSION   rename the `[Unreleased]` section to VERSION, dated, and open a
                      fresh empty `[Unreleased]` above it. Run by the prepare job, so
                      the release pull request carries its own CHANGELOG change.
    extract VERSION   print VERSION's section as a release body. Run by the release
                      job before any gate, so a missing or empty section stops the
                      release before a tag exists.

Both fail rather than guess. A section already written for VERSION is left alone.

Heading style follows the file: `## [0.7.0] — 2026-09-28` where headings are bracketed
(Keep a Changelog, kpubdata), `## v0.4.1 — 2026-10-01` otherwise (builder, studio —
whose `check_version_consistency.py` reads `## vX.Y`).
"""

from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

_HEADING = re.compile(r"^## ", re.MULTILINE)
_UNRELEASED = re.compile(r"^## \[?unreleased\]?[^\n]*$", re.MULTILINE | re.IGNORECASE)
_BRACKETED = re.compile(r"^## \[\d", re.MULTILINE)


class ChangelogError(Exception):
    """The CHANGELOG cannot give a release its notes."""


def _version_heading(version: str) -> re.Pattern[str]:
    """Match a heading for exactly this version, bracketed or `v`-prefixed.

    `## v0.4` does not match 0.4.0 and `## v0.4.1` does not match 0.4.10: the version
    must be followed by the end of the line, whitespace or a closing bracket.
    """
    return re.compile(
        rf"^## \[?v?{re.escape(version)}(?=[\]\s]|$)[^\n]*$",
        re.MULTILINE,
    )


def _section(text: str, heading: re.Match[str]) -> str:
    """The body under a heading, up to the next `## ` heading."""
    following = _HEADING.search(text, heading.end())
    end = following.start() if following else len(text)
    return text[heading.end() : end].strip()


def _has_content(body: str) -> bool:
    """Whether a section says anything beyond sub-headings."""
    return any(line.strip() and not line.startswith("#") for line in body.splitlines())


def extract(text: str, version: str) -> str:
    """Return VERSION's section body.

    Raises:
        ChangelogError: There is no section for VERSION, or it is empty.
    """
    heading = _version_heading(version).search(text)
    if heading is None:
        raise ChangelogError(
            f"CHANGELOG.md has no section for {version}. Write the release's entries "
            "under `## [Unreleased]` — the prepare job renames it — or add the section "
            "by hand."
        )
    body = _section(text, heading)
    if not _has_content(body):
        raise ChangelogError(f"CHANGELOG.md's section for {version} is empty.")
    return body


def promote(text: str, version: str, date: dt.date) -> str:
    """Rename `[Unreleased]` to VERSION and open a new empty one above it.

    Returns the text unchanged when VERSION already has a section.

    Raises:
        ChangelogError: No section for VERSION, and `[Unreleased]` is missing or empty.
    """
    if _version_heading(version).search(text):
        return text
    unreleased = _UNRELEASED.search(text)
    if unreleased is None or not _has_content(_section(text, unreleased)):
        raise ChangelogError(
            f"nothing to release as {version}: CHANGELOG.md has no section for it and "
            "`## [Unreleased]` is missing or empty. Record what changed first."
        )
    name = f"[{version}]" if _BRACKETED.search(text) else f"v{version}"
    heading = f"## [Unreleased]\n\n## {name} — {date.isoformat()}"
    return text[: unreleased.start()] + heading + text[unreleased.end() :]


def main(argv: list[str] | None = None) -> int:
    """Run a command. Returns 0 on success, 1 when the CHANGELOG cannot serve."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("command", choices=["promote", "extract"])
    parser.add_argument("version", help="the version being released, with or without v")
    parser.add_argument("--changelog", type=Path, default=Path("CHANGELOG.md"))
    parser.add_argument("--compare-url", help="appended to the extracted notes")
    parser.add_argument("--output", type=Path, help="write extracted notes here")
    args = parser.parse_args(argv)
    version = args.version.removeprefix("v")

    try:
        text = args.changelog.read_text(encoding="utf-8")
        if args.command == "promote":
            today = dt.datetime.now(ZoneInfo("Asia/Seoul")).date()
            args.changelog.write_text(promote(text, version, today), encoding="utf-8")
            print(f"CHANGELOG.md: section for {version} is in place")
            return 0
        notes = extract(text, version)
    except (ChangelogError, OSError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1

    if args.compare_url:
        notes += f"\n\n**Full changelog**: {args.compare_url}"
    if args.output:
        args.output.write_text(notes + "\n", encoding="utf-8")
    else:
        print(notes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
