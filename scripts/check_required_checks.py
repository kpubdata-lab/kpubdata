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
import fnmatch
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
_TRIGGER_FILTERS = frozenset({"paths", "paths-ignore", "branches", "branches-ignore"})
# Branch protection is read from, and applies to, pull requests into this branch.
_PROTECTED_BRANCH = "main"
_BOOL_TAG = "tag:yaml.org,2002:bool"
_INT_TAG = "tag:yaml.org,2002:int"


class _GitHubLoader(yaml.SafeLoader):
    """A loader that keeps scalars the way GitHub's YAML 1.2 reader spells them.

    PyYAML follows YAML 1.1, where ``on``, ``off``, ``yes`` and ``no`` are booleans and
    ``010`` is octal. GitHub reads ``on`` as a plain string and ``010`` as ten, so a
    matrix value ``[yes, no]`` posts ``Job (yes, no)``, not ``Job (true, false)``.
    """


_GitHubLoader.yaml_implicit_resolvers = {
    first: [item for item in resolvers if item[0] not in (_BOOL_TAG, _INT_TAG)]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_GitHubLoader.add_implicit_resolver(
    _BOOL_TAG, re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)
_GitHubLoader.add_implicit_resolver(_INT_TAG, re.compile(r"^[-+]?[0-9]+$"), list("-+0123456789"))
_GitHubLoader.add_constructor(
    _BOOL_TAG, lambda loader, node: str(loader.construct_scalar(node)).lower() == "true"
)
_GitHubLoader.add_constructor(
    _INT_TAG, lambda loader, node: int(str(loader.construct_scalar(node)))
)


def _text(value: object) -> str | None:
    """Spell a matrix value the way a job name shows it; None when it is not a scalar."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (str, int, float)):
        return str(value)
    return None


def _substitute(name: str, chosen: dict[str, str]) -> str:
    """Replace ``${{ matrix.axis }}`` in a job name with this combination's values."""
    return _MATRIX_REF.sub(lambda match: chosen.get(match.group(1), match.group(0)), name)


def _filters_out_protected_branch(config: dict[object, object]) -> bool:
    """True when a pull request into the protected branch may skip this trigger.

    A ``branches`` list that names the protected branch with no negated pattern lets
    every pull request into it through, so it is not a filter that matters here. Any
    ``paths``, ``paths-ignore`` or ``branches-ignore`` can skip some pull request.
    """
    used = _TRIGGER_FILTERS & {str(key) for key in config}
    if not used:
        return False
    if used != {"branches"}:
        return True
    patterns = config["branches"]
    if not isinstance(patterns, list) or any(str(p).startswith("!") for p in patterns):
        return True
    return not any(fnmatch.fnmatchcase(_PROTECTED_BRANCH, str(p)) for p in patterns)


def _pull_request_trigger(workflow: dict[object, object]) -> str | None:
    """ "always" or "filtered" when pull requests trigger the workflow, else None."""
    triggers = workflow.get("on")
    if isinstance(triggers, str):
        return "always" if triggers in _PR_EVENTS else None
    if isinstance(triggers, list):
        return "always" if _PR_EVENTS & {str(item) for item in triggers} else None
    if not isinstance(triggers, dict):
        return None
    found: str | None = None
    for event in _PR_EVENTS:
        if event not in triggers:
            continue
        config = triggers[event]
        if isinstance(config, dict) and _filters_out_protected_branch(config):
            found = found or "filtered"
        else:
            return "always"
    return found


def _combinations(matrix: dict[object, object]) -> tuple[list[dict[str, str]], str]:
    """Expand ``strategy.matrix`` the way GitHub does.

    Returns the combinations and, when they cannot be known, an empty list and why.

    Axes are every key but ``include``/``exclude``. ``exclude`` drops combinations that
    match all of its keys. An ``include`` entry is added to each *original* combination
    whose axis values it does not overwrite (later entries may overwrite what earlier
    ones added); an entry that cannot be added to any becomes a combination of its own.
    """
    axes: dict[str, list[str]] = {}
    for key, values in matrix.items():
        if key in _MATRIX_CONTROL:
            continue
        spelled = [_text(v) for v in values] if isinstance(values, list) else None
        if spelled is None or None in spelled:
            return [], f"matrix axis {key!r} is not a literal list of scalars"
        axes[str(key)] = [v for v in spelled if v is not None]

    def entries(key: str) -> list[dict[str, str]] | None:
        raw = matrix.get(key) or []
        if not isinstance(raw, list):
            return None
        out: list[dict[str, str]] = []
        for item in raw:
            if not isinstance(item, dict):
                return None
            spelled = {str(k): _text(v) for k, v in item.items()}
            if None in spelled.values():
                return None
            out.append({k: v for k, v in spelled.items() if v is not None})
        return out

    excludes, includes = entries("exclude"), entries("include")
    if excludes is None or includes is None:
        return [], "matrix include/exclude is not a literal list of mappings"

    originals = (
        [dict(zip(axes, picked, strict=True)) for picked in itertools.product(*axes.values())]
        if axes
        else []
    )
    for rule in excludes:
        originals = [c for c in originals if not all(c.get(k) == v for k, v in rule.items())]
    combos = [dict(c) for c in originals]
    extra_combos: list[dict[str, str]] = []
    for entry in includes:
        fitting = [
            index
            for index, original in enumerate(originals)
            if all(original[k] == v for k, v in entry.items() if k in axes)
        ]
        for index in fitting:
            for k, v in entry.items():
                if k not in axes:
                    combos[index][k] = v
        if not fitting:
            extra_combos.append(dict(entry))
    combos += extra_combos
    if not combos:
        return [], "the matrix expands to no combinations"
    return combos, ""


def _job_contexts(job_id: str, job: dict[object, object]) -> tuple[set[str], str]:
    """The contexts a job posts, or an empty set and why they cannot be known."""
    if "uses" in job:
        return set(), f"job {job_id!r} calls a reusable workflow (contexts are 'caller / job')"
    raw_name = job.get("name")
    base = str(raw_name) if raw_name is not None else job_id
    strategy = job.get("strategy")
    matrix = strategy.get("matrix") if isinstance(strategy, dict) else None
    if matrix is None:
        names = [base]
    elif not isinstance(matrix, dict):
        return set(), f"job {job_id!r} has a matrix that is an expression"
    else:
        combos, why = _combinations(matrix)
        if not combos:
            return set(), f"job {job_id!r}: {why}"
        if _MATRIX_REF.search(base):
            names = [_substitute(base, combo) for combo in combos]
        else:
            names = [f"{base} ({', '.join(combo.values())})" for combo in combos]
    if any("${{" in name for name in names):
        return set(), f"job {job_id!r} has a name that is computed at run time"
    return set(names), ""


def scan(workflows: Path) -> tuple[set[str], set[str], list[str]]:
    """Return ``(reliable, filtered, notes)`` for these workflow files.

    ``reliable`` holds the contexts every pull request gets. ``filtered`` holds those
    that come only from a workflow whose ``pull_request`` trigger has ``paths`` or
    ``branches`` filters: a pull request that misses the filter never gets them, which
    is the BLOCKED-for-ever case. ``notes`` says which jobs could not be expanded; their
    contexts are never reported as produced, because a false "present" is the failure
    this script exists to prevent and a false alarm is only an annoyance.
    """
    reliable: set[str] = set()
    filtered: set[str] = set()
    notes: list[str] = []
    for path in sorted(workflows.glob("*.y*ml")):
        workflow = yaml.load(path.read_text(encoding="utf-8"), Loader=_GitHubLoader)  # noqa: S506
        if not isinstance(workflow, dict):
            continue
        trigger = _pull_request_trigger(workflow)
        jobs = workflow.get("jobs")
        if trigger is None or not isinstance(jobs, dict):
            continue
        for job_id, job in jobs.items():
            if not isinstance(job, dict):
                continue
            contexts, why = _job_contexts(str(job_id), job)
            if why:
                notes.append(f"{path.name}: {why}")
            (reliable if trigger == "always" else filtered).update(contexts)
    return reliable, filtered - reliable, notes


def produced_contexts(workflows: Path) -> set[str]:
    """The status-check contexts that every pull request gets from these workflow files.

    A job's context is its ``name``, or its id when it has none. A matrix job produces
    one context per combination, and how that is spelled depends on the name:

    * a name that interpolates the matrix — ``Tests (py${{ matrix.python-version }})``
      — becomes the substituted name, ``Tests (py3.10)``;
    * a name that does not gets the combination appended, ``Lint (3.10, ubuntu)``,
      which is what GitHub does.

    Only workflows triggered by ``pull_request`` or ``pull_request_target`` count, and
    only without ``paths``/``branches`` filters; see :func:`scan` for the rest.

    The files are parsed as YAML (PyYAML is a runtime dependency). Regular expressions
    missed block-style matrices, which is the studio#416 outage again.
    """
    return scan(workflows)[0]


def required_contexts(repo: str) -> list[str]:
    """What branch protection currently requires on ``main``."""
    out = subprocess.run(
        ["gh", "api", f"repos/{repo}/branches/main/protection/required_status_checks"],
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return list(json.loads(out)["contexts"])


def report(
    required: list[str],
    produced: set[str],
    label: str,
    filtered: set[str] | None = None,
    notes: list[str] | None = None,
) -> int:
    """Print the comparison and return the exit code."""
    missing = [c for c in required if c not in produced]
    if not missing:
        print(f"{label}: all {len(required)} required check(s) are produced")
        for context in required:
            print(f"  {context}")
        return 0
    print(f"{label}: {len(missing)} required check(s) no workflow produces\n", file=sys.stderr)
    for context in missing:
        why = "  (only from a workflow whose pull_request trigger is filtered)"
        print(f"  {context}{why if context in (filtered or set()) else ''}", file=sys.stderr)
    for note in notes or []:
        print(f"  cannot verify: {note}", file=sys.stderr)
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

    produced, filtered, notes = scan(args.workflows)
    if not (produced or filtered or notes):
        print(f"error: no jobs found under {args.workflows}", file=sys.stderr)
        return 1

    if args.required is not None:
        return report(args.required, produced, str(args.workflows), filtered, notes)

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
    return report(required, produced, repo, filtered, notes)


if __name__ == "__main__":
    raise SystemExit(main())
