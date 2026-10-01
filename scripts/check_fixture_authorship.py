#!/usr/bin/env python3
"""Refuse fixture changes that did not come from the recorder (#523, #729).

A recorded fixture is the evidence behind "this dataset is verified". If the
subject of that judgement can edit the evidence, the judgement means nothing --
and the path existed: ``scripts/record.py`` once rewrote a repository spec's
``last_verified`` regardless of ``fixtures_root`` (#497), and nobody noticed.

Two layers, one per lie an evidence change can tell:

1. **Author (#523):** a change under a recorded-fixture path is only accepted
   when the commits that made it carry a recorder name. A human or an agent
   editing a ``.raw.json`` by hand fails here.
2. **Run reference (#729):** the author name is self-asserted -- a local tool
   can commit as ``kpubdata-agent``, and PR #728 did exactly that. So a
   changed ``.meta.json`` must also carry ``record_commit`` and ``run_ref``,
   and ``run_ref`` must resolve to a run of this repository's recording
   workflow whose head SHA is that commit. A name without a run proves
   nothing; a run from another workflow or repository is not this recorder.

Not a security boundary on its own -- what stops forgery is the trust
boundary in #521 (secrets only reachable from a protected environment) plus
branch protection in #520. This check makes the casual and the accidental
edit visible instead of silent, and fails closed when a run cannot be
verified.

Usage::

    check_fixture_authorship.py --base origin/main   # GH_TOKEN for run lookups
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

#: Files that hold recorded evidence. ``expected`` is derived from ``raw``, and
#: both plus ``meta`` decide whether a dataset counts as verified.
EVIDENCE_SUFFIXES = (".raw.json", ".expected.json", ".meta.json")

#: Paths under which the suffixes above are treated as evidence.
EVIDENCE_ROOT = "tests/fixtures/"

#: Commit author names allowed to change evidence. The recorder workflow sets
#: the first; the second is GitHub's own bot for workflow-made commits.
RECORDER_AUTHORS = frozenset({"kpubdata-agent", "github-actions[bot]"})

#: The only workflow permitted to record evidence (#729): build-dataset.yml's
#: ``name:`` field. It runs on the kr runner with the provider keys, and its
#: runs are what a meta's ``run_ref`` must point at.
RECORDING_WORKFLOW_NAME = "Build Dataset (agent)"


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


def _run_details(run_ref: str) -> tuple[str, str] | None:
    """(workflow name, head SHA) of a run in this repository, or None.

    ``None`` covers every way a run reference can fail to be *this* recorder:
    no such run here (a run id from another repository resolves to nothing),
    a network or permission failure, or a payload without the fields. The
    gate fails closed on all of them -- an unverifiable run is not evidence.
    """
    completed = subprocess.run(
        ["gh", "run", "view", run_ref, "--json", "workflowName,headSha"],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return None
    try:
        payload = json.loads(completed.stdout)
    except ValueError:
        return None
    name = payload.get("workflowName")
    head = payload.get("headSha")
    if not isinstance(name, str) or not isinstance(head, str):
        return None
    return name, head


def _binding_failures(metas: list[str]) -> list[str]:
    """Every changed meta that does not name a recording-workflow run (#729)."""
    failures: list[str] = []
    runs: dict[str, tuple[str, str] | None] = {}
    for meta_path in metas:
        try:
            meta = json.loads(Path(meta_path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            failures.append(f"{meta_path}: cannot read the meta file")
            continue
        if not isinstance(meta, dict):
            failures.append(f"{meta_path}: meta is not a JSON object")
            continue
        commit = meta.get("record_commit")
        run_ref = meta.get("run_ref")
        if not isinstance(commit, str) or not commit:
            failures.append(f"{meta_path}: no record_commit - not recorded in a CI run")
            continue
        if not isinstance(run_ref, str) or not run_ref:
            failures.append(
                f"{meta_path}: no run_ref - a recorder name alone proves nothing "
                "(a local tool can claim it, #728)"
            )
            continue
        if run_ref not in runs:
            runs[run_ref] = _run_details(run_ref)
        details = runs[run_ref]
        if details is None:
            failures.append(
                f"{meta_path}: run {run_ref} is not verifiable in this repository "
                "(missing, from another repository, or the lookup failed)"
            )
            continue
        workflow_name, head_sha = details
        if workflow_name != RECORDING_WORKFLOW_NAME:
            failures.append(
                f"{meta_path}: run {run_ref} is '{workflow_name}', not the "
                f"recording workflow ({RECORDING_WORKFLOW_NAME})"
            )
            continue
        if commit != head_sha:
            failures.append(
                f"{meta_path}: record_commit {commit[:8]} does not match run "
                f"{run_ref} head {head_sha[:8]}"
            )
    return failures


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

    binding = _binding_failures([path for path in paths if path.endswith(".meta.json")])

    if not offenders and not binding:
        print(
            f"{len(paths)} evidence file(s) changed, all by the recorder, "
            "each meta bound to a recording-workflow run"
        )
        return 0

    print(
        "error: recorded evidence was changed outside the recorder. A fixture is "
        "the basis for calling a dataset verified, so editing it by hand makes "
        "that claim unfalsifiable (#497, #523, #729). Re-record instead - on a "
        "dataset-request issue, the Build Dataset workflow does it and binds "
        "the run.",
        file=sys.stderr,
    )
    for path, authors in sorted(offenders.items()):
        print(f"  {path}  (changed by {', '.join(sorted(authors))})", file=sys.stderr)
    for line in binding:
        print(f"  {line}", file=sys.stderr)
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
