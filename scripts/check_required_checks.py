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

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent

_MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}")
_PR_EVENTS = frozenset({"pull_request", "pull_request_target"})
_MATRIX_CONTROL = frozenset({"include", "exclude"})


def _text(value: object) -> str:
    """Spell a matrix value the way a job name shows it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _substitute(name: str, chosen: dict[str, str]) -> str:
    """Replace ``${{ matrix.axis }}`` in a job name with this combination's values."""
    return _MATRIX_REF.sub(lambda match: chosen.get(match.group(1), match.group(0)), name)


def _events(workflow: dict[object, object]) -> set[str]:
    """Event names in ``on:``. YAML 1.1 reads the bare key ``on`` as boolean True."""
    triggers = workflow.get("on", workflow.get(True))
    if isinstance(triggers, str):
        return {triggers}
    if isinstance(triggers, list):
        return {str(item) for item in triggers}
    if isinstance(triggers, dict):
        return {str(key) for key in triggers}
    return set()


def _combinations(matrix: dict[object, object]) -> list[dict[str, str]] | None:
    """Expand ``strategy.matrix`` the way GitHub does; None when it is not literal.

    Axes are every key but ``include``/``exclude``. ``exclude`` drops combinations that
    match all of its keys. An ``include`` entry that agrees with an existing
    combination on every original axis it names adds its extra keys to that
    combination; one that matches none becomes a combination of its own.
    """
    axes: dict[str, list[str]] = {}
    for key, values in matrix.items():
        if key in _MATRIX_CONTROL:
            continue
        if not isinstance(values, list):
            return None  # an expression such as fromJSON(...) cannot be expanded here
        axes[str(key)] = [_text(value) for value in values]
    combos = [dict(zip(axes, picked, strict=True)) for picked in itertools.product(*axes.values())]
    if not axes:
        combos = []

    def entries(key: str) -> list[dict[str, str]]:
        raw = matrix.get(key) or []
        if not isinstance(raw, list):
            return []
        return [
            {str(k): _text(v) for k, v in item.items()} for item in raw if isinstance(item, dict)
        ]

    for rule in entries("exclude"):
        combos = [c for c in combos if not all(c.get(k) == v for k, v in rule.items())]
    for extra in entries("include"):
        original = {k: v for k, v in extra.items() if k in axes}
        hits = [c for c in combos if all(c[k] == v for k, v in original.items())]
        if original and hits:
            for combo in hits:
                for k, v in extra.items():
                    combo.setdefault(k, v)
        else:
            combos.append(extra)
    return combos


def _job_contexts(job_id: str, job: dict[object, object]) -> set[str]:
    raw_name = job.get("name")
    base = str(raw_name) if raw_name is not None else job_id
    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if not isinstance(matrix, dict):
        return {base}
    combos = _combinations(matrix)
    if not combos:
        return {base}
    interpolated = bool(_MATRIX_REF.search(base))
    contexts: set[str] = set()
    for combo in combos:
        if interpolated:
            contexts.add(_substitute(base, combo))
        else:
            contexts.add(f"{base} ({', '.join(combo.values())})")
    return contexts


def produced_contexts(workflows: Path) -> set[str]:
    """The status-check contexts that pull requests can get from these workflow files.

    A job's context is its ``name``, or its id when it has none. A matrix job produces
    one context per combination, and how that is spelled depends on the name:

    * a name that interpolates the matrix — ``Tests (py${{ matrix.python-version }})``
      — becomes the substituted name, ``Tests (py3.10)``;
    * a name that does not gets the combination appended, ``Lint (3.10, ubuntu)``,
      which is what GitHub does.

    Only workflows triggered by ``pull_request`` or ``pull_request_target`` count: a job
    that runs on ``workflow_dispatch`` alone never reports on a pull request, so
    requiring it blocks every one for ever.

    The files are parsed as YAML (PyYAML is a runtime dependency). Regular expressions
    missed block-style matrices, which is the studio#416 outage again.
    """
    contexts: set[str] = set()
    for path in sorted(workflows.glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(workflow, dict) or not _events(workflow) & _PR_EVENTS:
            continue
        jobs = workflow.get("jobs")
        if not isinstance(jobs, dict):
            continue
        for job_id, job in jobs.items():
            if isinstance(job, dict):
                contexts |= _job_contexts(str(job_id), job)
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
