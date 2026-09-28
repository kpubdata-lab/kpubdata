#!/usr/bin/env python3
"""Every required status check must be one a workflow actually produces (studio#416).

`kpubdata-studio#413` removed Node 20 from the CI matrix. Branch protection still
required ``Lint, type check, test, build (20)``, and that context simply stopped
existing. GitHub does not treat an absent check as a failure — it waits. Every pull
request sat at BLOCKED with nothing to look at, and the only way past was ``--admin``,
which bypasses every *other* check as well. A rule that blocks everything protects
nothing, and it took a session of ``--admin`` merges before anyone asked why.

The aggregate ``CI gate`` job removes the coupling that caused it. This script is what
notices if the coupling comes back.

It runs locally, not in CI, and that is deliberate: reading branch protection needs an
admin token, and a workflow holding one is a larger risk than the drift it would catch.
``gh`` already has the right credential on a maintainer's machine.

Usage:
    python scripts/check_required_checks.py                          # this repository
    python scripts/check_required_checks.py --repo owner/name \\
        --workflows ../other-repo/.github/workflows                  # a sibling checkout
    python scripts/check_required_checks.py --required "A" "B"       # check a set by hand

The last form takes the required set as arguments instead of reading it from GitHub. It
is how this script is tested — asking it about a context that no longer exists has to
fail, and proving that must not mean editing live branch protection.

Each context is its own argument, never a comma-separated list. The context that caused
the outage is spelled ``Lint, type check, test, build (20)``: splitting on commas would
turn the one name this script exists to catch into four names it invented.
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

_JOB_ID = re.compile(r"^  ([A-Za-z_][\w-]*):", re.MULTILINE)
_JOB_NAME = re.compile(r"^    name:\s*(.+)$", re.MULTILINE)
_MATRIX_AXIS = re.compile(r"^        ([\w-]+):\s*\[([^\]]+)\]", re.MULTILINE)
_MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}")


def _unquote(value: str) -> str:
    return value.strip().strip("\"'")


def _substitute(name: str, chosen: dict[str, str]) -> str:
    """Replace ``${{ matrix.axis }}`` in a job name with this combination's values."""
    return _MATRIX_REF.sub(lambda match: chosen.get(match.group(1), match.group(0)), name)


def produced_contexts(workflows: Path) -> set[str]:
    """The status-check contexts these workflow files can produce.

    A job's context is its ``name``, or its id when it has none. A matrix job produces
    one context per combination, and how that is spelled depends on the name:

    * a name that interpolates the matrix — ``Tests (py${{ matrix.python-version }})``
      — becomes the substituted name, ``Tests (py3.10)``;
    * a name that does not gets the combination appended, ``Lint (3.10)``, which is
      what GitHub does.

    The first draft only knew the second rule, and reported all four of this
    repository's ``Tests (pyX.Y)`` contexts as missing — a check that cries wolf about
    the very list it is meant to confirm is worse than no check.

    The YAML is read with regular expressions on purpose. Requiring PyYAML would make
    this a script someone has to install something to run, and the thing it guards
    against is precisely the check nobody got around to running.
    """
    contexts: set[str] = set()
    for path in sorted(workflows.glob("*.y*ml")):
        text = path.read_text(encoding="utf-8")
        _, _, jobs = text.partition("\njobs:")
        if not jobs:
            continue
        starts = [m.start() for m in _JOB_ID.finditer(jobs)]
        for index, start in enumerate(starts):
            end = starts[index + 1] if index + 1 < len(starts) else len(jobs)
            block = jobs[start:end]
            job_id = _JOB_ID.match(block).group(1)  # type: ignore[union-attr]
            name_match = _JOB_NAME.search(block)
            base = _unquote(name_match.group(1)) if name_match else job_id
            axis_pairs = [
                (axis, [_unquote(v) for v in values.split(",")])
                for axis, values in _MATRIX_AXIS.findall(block)
            ]
            if not axis_pairs:
                contexts.add(base)
                continue
            interpolated = bool(_MATRIX_REF.search(base))
            axis_names = [axis for axis, _ in axis_pairs]
            for combo in itertools.product(*(values for _, values in axis_pairs)):
                chosen = {axis_names[index]: value for index, value in enumerate(combo)}
                if interpolated:
                    contexts.add(_substitute(base, chosen))
                else:
                    contexts.add(f"{base} ({', '.join(combo)})")
    return contexts


def required_contexts(repo: str) -> list[str]:
    """What branch protection currently requires on ``main``."""
    out = subprocess.run(
        ["gh", "api", f"repos/{repo}/branches/main/protection/required_status_checks"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return list(json.loads(out)["contexts"])


def report(required: list[str], produced: set[str], label: str) -> int:
    """Print the comparison and return the exit code."""
    missing = [c for c in required if c not in produced]
    if not missing:
        print(f"{label}: all {len(required)} required check(s) are produced")
        for context in required:
            print(f"  {context}")
        return 0
    print(f"{label}: {len(missing)} required check(s) no workflow produces\n", file=sys.stderr)
    for context in missing:
        print(f"  {context}", file=sys.stderr)
    print(
        "\nAn absent check is not a failure. GitHub waits for it, so every pull request"
        "\nstays BLOCKED with nothing to look at, and the only way past is --admin.",
        file=sys.stderr,
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", default=None, help="owner/name; default is this checkout's remote"
    )
    parser.add_argument(
        "--workflows",
        type=Path,
        default=REPO_ROOT / ".github" / "workflows",
        help="Workflow directory to read (default: this repository's).",
    )
    parser.add_argument(
        "--required",
        nargs="+",
        default=None,
        metavar="CONTEXT",
        help="Check these contexts instead of asking GitHub. One argument per context.",
    )
    args = parser.parse_args(argv)

    produced = produced_contexts(args.workflows)
    if not produced:
        print(f"error: no jobs found under {args.workflows}", file=sys.stderr)
        return 1

    if args.required is not None:
        return report(args.required, produced, str(args.workflows))

    repo = args.repo
    if repo is None:
        repo = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
    try:
        required = required_contexts(repo)
    except subprocess.CalledProcessError:
        print(f"{repo}: cannot read branch protection — an admin token is needed", file=sys.stderr)
        return 1
    return report(required, produced, repo)


if __name__ == "__main__":
    raise SystemExit(main())
