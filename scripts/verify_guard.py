#!/usr/bin/env python3
"""Detect changes made *by* a verification run, not changes that predate it (#513).

``make verify`` used to fail whenever ``git status --porcelain -- src/`` was not
empty afterwards. That cannot tell two situations apart:

- the tool mutated the tree, which is the bug this guard exists to catch
  (``scripts/record.py`` once rewrote a spec's ``last_verified`` regardless of
  ``fixtures_root``, and nobody noticed -- #497)
- the developer already had edits in progress, which is what adding a dataset
  looks like

So the guard refused normal work, and a tool that refuses normal work gets
skipped -- which is how the mutation it was meant to catch gets through.

This takes a content snapshot before the run and compares afterwards. Only a
difference between the two is a failure. Files that were already dirty stay
dirty without complaint; a file the run touched is reported even if it was
already dirty, because the comparison is over content, not over git's status
letters.

Usage::

    verify_guard.py snapshot > before.json
    <run the verification>
    verify_guard.py compare before.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

#: Trees a verification run must not write to.
WATCHED = ("src",)

_DELETED = "<deleted>"

#: Mode bits worth recording. Only the executable bits matter here: a verify run
#: that chmods a spec has mutated the tree, and the content digest alone cannot
#: see it -- the old ``git status`` guard could, so ignoring it would be a
#: regression rather than a simplification.
_MODE_MASK = 0o111


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def _watched_paths() -> set[Path]:
    """Every file under the watched trees: tracked, plus untracked-not-ignored.

    Untracked files matter. A run that *creates* a spec is mutating the tree just
    as much as one that edits an existing spec, and a tracked-only walk would
    miss it.
    """
    paths: set[Path] = set()
    for tree in WATCHED:
        if not Path(tree).is_dir():
            continue
        tracked = _git("ls-files", "-z", "--", tree)
        untracked = _git("ls-files", "-z", "--others", "--exclude-standard", "--", tree)
        for blob in (tracked, untracked):
            paths.update(Path(entry) for entry in blob.split("\0") if entry)
    return paths


class UnreadablePath(Exception):
    """A watched file could not be read, so no snapshot can be taken.

    This is not the same as "unchanged". If the same path is unreadable before
    and after, a marker recorded in both snapshots would compare equal and the
    guard would report success over a state it never actually observed.
    """


def snapshot() -> dict[str, str]:
    """Map each watched path to a digest of its content and relevant mode bits.

    A path that git knows about but that is missing from the working tree is
    recorded as deleted rather than skipped, so that deleting a file during the
    run is a detectable difference instead of a silently shorter dictionary.

    Raises:
        UnreadablePath: A watched file exists but cannot be read.
    """
    result: dict[str, str] = {}
    for path in sorted(_watched_paths()):
        try:
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            mode = path.stat().st_mode & _MODE_MASK
        except (FileNotFoundError, IsADirectoryError, NotADirectoryError):
            result[str(path)] = _DELETED
            continue
        except OSError as exc:
            raise UnreadablePath(f"{path}: {exc.strerror or exc.errno}") from exc
        result[str(path)] = f"{digest}:{mode:o}"
    return result


def compare(before: dict[str, str], after: dict[str, str]) -> list[str]:
    """Human-readable lines describing what the run changed. Empty means clean."""
    problems: list[str] = []
    for path in sorted(set(before) | set(after)):
        old = before.get(path)
        new = after.get(path)
        if old == new:
            continue
        if old is None or old == _DELETED:
            problems.append(f"created  {path}")
        elif new is None or new == _DELETED:
            problems.append(f"deleted  {path}")
        elif _digest_of(old) == _digest_of(new):
            # Same bytes, different mode bits.
            problems.append(f"chmod    {path}")
        else:
            problems.append(f"modified {path}")
    return problems


def _digest_of(entry: str) -> str:
    """The content digest out of a ``"<digest>:<mode>"`` snapshot entry."""
    return entry.split(":", 1)[0]


def _validate_baseline(value: object) -> dict[str, str]:
    """Reject anything that is not a path-to-entry mapping.

    A baseline of ``[]`` used to reach ``compare`` and die with an
    ``AttributeError`` traceback. That is not a silent pass -- the exit status
    was still non-zero -- but a traceback is the wrong way to say "this file is
    not a snapshot", and a reader cannot tell it apart from a real finding.
    """
    if not isinstance(value, dict):
        msg = f"not a snapshot object (found {type(value).__name__})"
        raise ValueError(msg)
    for key, entry in value.items():
        if not isinstance(key, str) or not isinstance(entry, str):
            msg = "snapshot entries must map a path string to a digest string"
            raise ValueError(msg)
    return dict(value)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("snapshot", help="write a content snapshot to stdout as JSON")
    compare_parser = sub.add_parser("compare", help="compare a snapshot against the tree now")
    compare_parser.add_argument("baseline", type=Path)
    args = parser.parse_args()

    if args.command == "snapshot":
        try:
            taken = snapshot()
        except UnreadablePath as exc:
            print(f"error: cannot snapshot the working tree: {exc}", file=sys.stderr)
            return 2
        json.dump(taken, sys.stdout)
        return 0

    try:
        before = _validate_baseline(json.loads(args.baseline.read_text(encoding="utf-8")))
    except (OSError, ValueError) as exc:
        # No usable baseline means the guard cannot answer the question. Saying
        # "clean" here would quietly disable it.
        print(f"error: cannot read the snapshot at {args.baseline}: {exc}", file=sys.stderr)
        return 2

    try:
        after = snapshot()
    except UnreadablePath as exc:
        # The guard cannot answer the question, and answering "clean" would
        # switch it off for exactly the run that needs it.
        print(f"error: cannot verify the working tree: {exc}", file=sys.stderr)
        return 2

    problems = compare(before, after)
    if not problems:
        return 0

    print(
        "error: the verification run modified the working tree. "
        "verify must only read -- this is a defect in the tooling (#497, #513).",
        file=sys.stderr,
    )
    for line in problems:
        print(f"  {line}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
