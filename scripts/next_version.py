#!/usr/bin/env python3
"""Work out the next version from the declared one (#586).

The bump used to be an inline shell heredoc inside the release workflow, where it
could not be run or tested without dispatching a release. Two things follow from
moving it out: it is testable, and a mistake in it shows up before a tag exists.

The declaring file is the source. `pyproject.toml` and `package.json` are both
understood, told apart by suffix, because Studio keeps its version in the second and
one shared tool beats two that drift. Output is the `key=value` lines a GitHub Actions
step writes to `$GITHUB_OUTPUT`, so the workflow does not have to parse anything:

    $ python3 scripts/next_version.py minor
    new_version=0.7.0
    tag=v0.7.0

`.github/actions/next-version` wraps this so the other two repositories call it
instead of copying it.

The `pre` bump follows PEP 440's `aN` spelling, matching what the ten releases before
this script used. Raising a pre-release raises the pre-release number; raising from a
finished version starts the next patch's `a0`. A release is never cut from a
pre-release version — check_version_consistency.py refuses that separately, because
tagging `0.7.0a1` as a release contradicts what the version says about itself.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_TOML_VERSION = re.compile(r'^version = "([^"]+)"', re.MULTILINE)
_JSON_VERSION = re.compile(r'"version"\s*:\s*"([^"]+)"')
# major.minor.patch, with an optional PEP 440 pre-release segment on the patch.
_PARTS = re.compile(r"^(\d+)\.(\d+)\.(\d+)(?:a(\d+))?$")


class VersionError(Exception):
    """The declared version is not one this script knows how to raise."""


def declared_version(path: Path) -> str:
    """The version declared in ``path``.

    A regular expression rather than a parser, in both formats. A TOML parser is 3.11+
    and this project supports 3.10, and a JSON round-trip would reformat the whole of
    `package.json` for a one-field change — a diff nobody can review.
    """
    text = path.read_text(encoding="utf-8")
    pattern = _JSON_VERSION if path.suffix == ".json" else _TOML_VERSION
    match = pattern.search(text)
    if match is None:
        raise VersionError(f"{path} declares no version")
    return match.group(1)


def next_version(current: str, bump: str) -> str:
    """The version after raising ``current`` by ``bump``.

    Raises:
        VersionError: The current version is not `major.minor.patch[aN]`, or the bump
            is not one of patch, minor, pre.
    """
    parts = _PARTS.match(current)
    if parts is None:
        raise VersionError(
            f"cannot raise {current!r}: expected major.minor.patch, optionally with aN. "
            "A .dev version is not a starting point for a release — set a real one first."
        )
    major, minor, patch = int(parts.group(1)), int(parts.group(2)), int(parts.group(3))
    pre = None if parts.group(4) is None else int(parts.group(4))

    if bump == "patch":
        # Finishing a pre-release means dropping the suffix, not adding to the patch:
        # 0.7.0a1 -> 0.7.0. Raising it to 0.7.1 would skip a version that was
        # announced and never published.
        return f"{major}.{minor}.{patch}" if pre is not None else f"{major}.{minor}.{patch + 1}"
    if bump == "minor":
        return f"{major}.{minor + 1}.0"
    if bump == "pre":
        if pre is not None:
            return f"{major}.{minor}.{patch}a{pre + 1}"
        return f"{major}.{minor}.{patch + 1}a0"
    raise VersionError(f"unknown bump {bump!r}: expected patch, minor or pre")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Print the next version as GITHUB_OUTPUT lines.")
    parser.add_argument("bump", choices=["patch", "minor", "pre"])
    parser.add_argument(
        "--file",
        dest="file",
        type=Path,
        default=REPO_ROOT / "pyproject.toml",
        help="Where the current version is declared (pyproject.toml or package.json).",
    )
    args = parser.parse_args(argv)

    try:
        version = next_version(declared_version(args.file), args.bump)
    except VersionError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    print(f"new_version={version}")
    print(f"tag=v{version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
