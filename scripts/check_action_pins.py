#!/usr/bin/env python3
"""Refuse workflow steps that run another repository's code by a movable ref.

Ported from kpubdata-builder (kpubdata-builder#1003), without its ``--bump-kpubdata``:
this repository uses its own actions by local path.

A ``uses:`` reference to another repository runs whatever that ref points at when the
job starts. A branch (``@main``) or a tag (``@v7``) can move without a change in this
repository, so the release, title and review gates would run code nobody here reviewed.
Every such reference must name a full 40-character commit SHA.

What is swept: every ``*.yml``/``*.yaml`` under ``.github/workflows`` and
``.github/actions``. A local reference (``./.github/workflows/x.yml``) runs this
repository's own code at the same commit and passes. A ``docker://`` image must be
pinned by ``@sha256:`` digest.

A file is read twice. Line by line, which gives the line number, and as parsed YAML,
which finds the forms a line pattern misses: a flow mapping (``- {uses: a/b@v1}``) and
a quoted key (``"uses": a/b@v1``). A reference found either way is checked, and a file
that is not valid YAML is refused, since its references cannot be listed.

Third-party actions carry a ``# vX.Y.Z`` comment, and Dependabot (``github-actions``)
raises the SHA and the comment together.

Usage:
    python scripts/check_action_pins.py
    python scripts/check_action_pins.py FILE...
"""

from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import NamedTuple

import yaml

ROOT = Path(__file__).resolve().parents[1]
SWEPT_DIRS = (".github/workflows", ".github/actions")

_USES = re.compile(
    r"""^(?P<head>\s*(?:-\s+)?uses:\s*)(?P<quote>["']?)(?P<ref>[^\s"'#]+)(?P=quote)(?P<tail>.*)$"""
)
_SHA = re.compile(r"[0-9a-f]{40}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")


class Violation(NamedTuple):
    path: Path
    line: int
    ref: str
    reason: str

    def __str__(self) -> str:
        return f"{self.path}:{self.line}: {self.ref} — {self.reason}"


def _reason(ref: str) -> str | None:
    """Return why ``ref`` is not pinned, or ``None`` when it is."""
    if ref.startswith("./"):
        return None
    if ref.startswith("docker://"):
        image = ref.removeprefix("docker://")
        _, _, digest = image.partition("@")
        if _DIGEST.fullmatch(digest):
            return None
        return "pin the image by @sha256: digest"
    _, sep, version = ref.rpartition("@")
    if not sep:
        return "no ref; pin a full commit SHA"
    if _SHA.fullmatch(version):
        return None
    return f"'{version}' can move; pin a full 40-character commit SHA"


def _step_refs(container: dict[object, object]) -> list[str]:
    steps = container.get("steps")
    if not isinstance(steps, list):
        return []
    return [
        step["uses"]
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("uses"), str)
    ]


def _parsed_refs(document: object) -> list[str]:
    """Every ``uses`` a runner would act on: a job's, a job's steps', a composite action's."""
    if not isinstance(document, dict):
        return []
    refs: list[str] = []
    jobs = document.get("jobs")
    if isinstance(jobs, dict):
        for job in jobs.values():
            if not isinstance(job, dict):
                continue
            if isinstance(job.get("uses"), str):
                refs.append(job["uses"])
            refs.extend(_step_refs(job))
    runs = document.get("runs")
    if isinstance(runs, dict):
        refs.extend(_step_refs(runs))
    return refs


def _line_of(lines: Sequence[str], ref: str) -> int:
    return next((number for number, line in enumerate(lines, 1) if ref in line), 1)


def _check_file(path: Path) -> list[Violation]:
    lines = path.read_text(encoding="utf-8").splitlines()
    violations: list[Violation] = []
    for number, line in enumerate(lines, 1):
        match = _USES.match(line)
        if match is None:
            continue
        ref = match["ref"]
        reason = _reason(ref)
        if reason is not None:
            violations.append(Violation(path, number, ref, reason))

    try:
        document = yaml.safe_load("\n".join(lines))
    except yaml.YAMLError as error:
        problem = str(error).splitlines()[0]
        violations.append(Violation(path, 1, "-", f"not valid YAML, so not checked: {problem}"))
        return violations

    # What the line pattern already reported is not reported again.
    reported = Counter(violation.ref for violation in violations)
    for ref in _parsed_refs(document):
        reason = _reason(ref)
        if reason is None:
            continue
        if reported[ref] > 0:
            reported[ref] -= 1
            continue
        violations.append(Violation(path, _line_of(lines, ref), ref, reason))
    return sorted(violations, key=lambda violation: violation.line)


def check(paths: Iterable[Path]) -> list[Violation]:
    violations: list[Violation] = []
    for path in paths:
        violations.extend(_check_file(path))
    return violations


def default_paths(root: Path = ROOT) -> list[Path]:
    paths: list[Path] = []
    for directory in SWEPT_DIRS:
        base = root / directory
        if base.is_dir():
            paths.extend(sorted(p for p in base.rglob("*") if p.suffix in {".yml", ".yaml"}))
    return paths


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("files", nargs="*", type=Path, help="files to check (default: all)")
    args = parser.parse_args(argv)
    paths = list(args.files) or default_paths()

    violations = check(paths)
    for violation in violations:
        print(violation, file=sys.stderr)
    if violations:
        print(
            f"\n{len(violations)} reference(s) can change without a change here. "
            "Pin each to a full commit SHA (see scripts/check_action_pins.py).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
