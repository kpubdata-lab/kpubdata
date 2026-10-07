#!/usr/bin/env python3
"""The files adding one dataset produces, in one list (#862).

``AGENTS.md`` ("Adding a dataset"), the agent definition
(``.opencode/agent/dataset-builder.md``) and ``build-dataset.yml`` each named what a
dataset adds, and they disagreed: the workflow committed the spec and the fixtures and
left out the example, the ``SUPPORTED_DATA.md`` row, the metadata entry and the
generated files, so ``make verify`` failed on the pull request it opened. This module is
the list they follow; ``tests/unit/scripts/test_dataset_artifacts.py`` holds the two
documents to it.

The paths are in three groups:

- ``AGENT_WRITES``: what the agent (or a person) writes by hand.
- ``GENERATED``: what a generator writes, with the command that writes it. Nobody edits
  these by hand; the workflow runs the generators itself before it commits.
- ``BASELINE``: the insecure-http baseline, which may only lose this dataset's line
  (``scripts/check_baseline_shrink.py`` guards it).

Usage::

    python scripts/dataset_artifacts.py paths datago.apt_trade   # one path per line
    python scripts/dataset_artifacts.py check datago.apt_trade   # exit 1 on a forbidden change

The workflow runs a copy taken from the commit it checked out, so an agent cannot widen
the list for its own run.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

#: Written by hand. ``{provider}`` and ``{key}`` are the dataset id's two halves.
AGENT_WRITES: tuple[str, ...] = (
    "src/kpubdata/specs/{provider}/{key}.yaml",
    "examples/{provider}/{key}.py",
    "SUPPORTED_DATA.md",
    "src/kpubdata/dataset_metadata.json",
)

#: Written by a generator: path → the command that writes it.
GENERATED: dict[str, str] = {
    "tests/fixtures/{provider}/{key}": "make record DATASET={provider}.{key}",
    "src/kpubdata/dataset_status.json": "uv run python scripts/gen_dataset_status.py",
    "docs/dataset-examples.md": "uv run python scripts/gen_docs_examples.py",
}

#: ``scripts/sync_supported_data.py`` also rewrites the status, verification and
#: verified-on cells of ``SUPPORTED_DATA.md`` and refreshes ``dataset_metadata.json``;
#: the row and the entry themselves are written by hand.
SYNC_COMMAND = "uv run python scripts/sync_supported_data.py"

#: May only lose this dataset's line.
BASELINE = "scripts/insecure_http_baseline.txt"

#: Dataset work never changes these (``AGENTS.md``, "Paths you may not change").
FORBIDDEN: tuple[str, ...] = (
    "src/kpubdata/core/",
    "tests/contract/",
    "scripts/",
    "Makefile",
    ".github/",
)


def split_dataset(dataset: str) -> tuple[str, str]:
    """``provider.key`` → ``(provider, key)``; a malformed id is refused."""
    provider, dot, key = dataset.partition(".")
    if not dot or not provider or not key or "/" in dataset:
        raise ValueError(f"not a dataset id: {dataset!r}")
    return provider, key


def paths(dataset: str) -> list[str]:
    """Every path one dataset may add or change, in commit order."""
    provider, key = split_dataset(dataset)
    templates = [*AGENT_WRITES, *GENERATED, BASELINE]
    return [template.format(provider=provider, key=key) for template in templates]


def is_forbidden(path: str) -> bool:
    """A path dataset work must not touch. The baseline is the one exception under
    ``scripts/``: its shrink is checked on its own."""
    if path == BASELINE:
        return False
    return any(path == prefix or path.startswith(prefix) for prefix in FORBIDDEN)


def _git_paths(root: Path, *args: str) -> set[str]:
    """The paths a git command lists, read NUL-separated (``-z``): a name with a space or
    a non-ASCII character comes back as it is, not quoted or split (#867 review)."""
    output = subprocess.run(
        ["git", *args], cwd=root, capture_output=True, check=True
    ).stdout.decode("utf-8", errors="surrogateescape")
    return {path for path in output.split("\0") if path}


def changed_paths(root: Path, base: str) -> list[str]:
    """Every path changed since ``base``, for the forbidden-path check and the report.

    - Tracked changes are listed without rename detection, so a file moved out of a
      forbidden path shows up as deleted there.
    - Untracked files under a forbidden path are listed whatever the ignore rules say.
      An agent can add a rule (``.gitignore``, ``.git/info/exclude``) before it writes
      ``scripts/json.py``, which the generators run next would import. Python's bytecode
      cache (``__pycache__/``) is left out: running ``make verify`` writes it there, and
      Python never imports a cached file whose source is missing.
    - Untracked files elsewhere are listed as the ignore rules say, for the report.
    """
    tracked = _git_paths(root, "diff", "-z", "--name-only", "--no-renames", base, "--")
    hidden = _git_paths(root, "ls-files", "-z", "--others", "--", *FORBIDDEN)
    untracked = _git_paths(root, "ls-files", "-z", "--others", "--exclude-standard")
    hidden = {path for path in hidden if "__pycache__" not in path.split("/")}
    return sorted(tracked | hidden | untracked)


def _covered(path: str, allowed: list[str]) -> bool:
    return any(path == entry or path.startswith(entry + "/") for entry in allowed)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("paths", "check"):
        command = sub.add_parser(name)
        command.add_argument("dataset")
        command.add_argument("--root", type=Path, default=Path.cwd())
        command.add_argument("--base", default="HEAD")
    args = parser.parse_args(argv)
    try:
        allowed = paths(args.dataset)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if args.command == "paths":
        print("\n".join(allowed))
        return 0
    changed = changed_paths(args.root, args.base)
    forbidden = [path for path in changed if is_forbidden(path)]
    stray = [path for path in changed if not is_forbidden(path) and not _covered(path, allowed)]
    for path in stray:
        print(f"left out (not a {args.dataset} artifact): {path}")
    if forbidden:
        for path in forbidden:
            print(f"error: dataset work may not change {path}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
