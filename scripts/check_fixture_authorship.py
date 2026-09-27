#!/usr/bin/env python3
"""Refuse fixture changes that did not come from the recorder (#523).

A recorded fixture is the evidence behind "this dataset is verified". If the
subject of that judgement can edit the evidence, the judgement means nothing --
and the path existed: ``scripts/record.py`` once rewrote a repository spec's
``last_verified`` regardless of ``fixtures_root`` (#497), and nobody noticed.

So a change under a recorded-fixture path is only accepted when the commit that
made it carries the recorder identity. A human or an agent editing a
``.raw.json`` or ``.meta.json`` by hand fails here.

This is not a security boundary on its own -- a commit author is self-asserted,
and anyone who can push can claim any name. What stops forgery is the trust
boundary in #521 (secrets only reachable from a protected environment) plus
branch protection in #520. This check is what makes an accidental or casual edit
visible instead of silent, and it is the piece that can exist before those land.

Usage::

    check_fixture_authorship.py --base origin/main
"""

from __future__ import annotations

import argparse
import subprocess
import sys

#: Files that hold recorded evidence. ``expected`` is derived from ``raw``, and
#: both plus ``meta`` decide whether a dataset counts as verified.
EVIDENCE_SUFFIXES = (".raw.json", ".expected.json", ".meta.json")

#: Paths under which the suffixes above are treated as evidence.
EVIDENCE_ROOT = "tests/fixtures/"

#: Commit author names allowed to change evidence. The recorder workflow sets
#: the first; the second is GitHub's own bot for workflow-made commits.
RECORDER_AUTHORS = frozenset({"kpubdata-agent", "github-actions[bot]"})


def _git(*args: str) -> str:
    return subprocess.run(
        ["git", *args], check=True, capture_output=True, text=True, encoding="utf-8"
    ).stdout


def _evidence_paths(base: str) -> list[str]:
    changed = _git("diff", "--name-only", f"{base}...HEAD").splitlines()
    return [
        path
        for path in changed
        if path.startswith(EVIDENCE_ROOT) and path.endswith(EVIDENCE_SUFFIXES)
    ]


def _authors_touching(base: str, path: str) -> set[str]:
    """Commit author names that changed ``path`` in this range."""
    log = _git("log", "--format=%an", f"{base}...HEAD", "--", path)
    return {line.strip() for line in log.splitlines() if line.strip()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args()

    try:
        paths = _evidence_paths(args.base)
    except subprocess.CalledProcessError as exc:
        print(f"error: cannot diff against {args.base}: {exc.stderr.strip()}", file=sys.stderr)
        return 2

    if not paths:
        print("no recorded evidence changed")
        return 0

    offenders: dict[str, set[str]] = {}
    for path in paths:
        authors = _authors_touching(args.base, path)
        unexpected = authors - RECORDER_AUTHORS
        if unexpected:
            offenders[path] = unexpected

    if not offenders:
        print(f"{len(paths)} evidence file(s) changed, all by the recorder")
        return 0

    print(
        "error: recorded evidence was changed outside the recorder. A fixture is "
        "the basis for calling a dataset verified, so editing it by hand makes "
        "that claim unfalsifiable (#497, #523). Re-record instead: make record "
        "DATASET=<id>.",
        file=sys.stderr,
    )
    for path, authors in sorted(offenders.items()):
        print(f"  {path}  (changed by {', '.join(sorted(authors))})", file=sys.stderr)
    print(
        "\nIf this change is legitimate -- moving a fixture, or a format "
        "migration that the recorder cannot express -- say so in the PR and have "
        "a human approve it. Do not widen RECORDER_AUTHORS to make the check "
        "pass.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
