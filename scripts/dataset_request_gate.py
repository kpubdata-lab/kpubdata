#!/usr/bin/env python3
"""Decide whether a dataset request may reach the self-hosted runner (#521).

``build-dataset.yml`` runs an agent with a provider key, a model key and repository
write permission on the owner's machine. It used to start on the label name alone, and
the dataset request template applies that label itself, so filing a request was enough.

The workflow's ``gate`` job runs on a GitHub-hosted runner, holds no secret and a
read-only token, and asks this script before the self-hosted job is assigned. A request
passes only when:

* the account that started the run (who applied the label, or who dispatched or re-ran
  the workflow) can push to the repository now — ``admin`` or ``write`` from
  ``GET /repos/{owner}/{repo}/collaborators/{user}/permission``;
* the issue number is a plain positive integer, and the issue is an open issue, not a
  pull request, carrying ``dataset-request`` or ``drift``;
* the issue text names one well-formed ``datago.<key>`` dataset id.

The dataset id and the agent are decided here and handed to the self-hosted job as job
outputs, so its shell never has to read them out of the issue text again.

This is containment, not a trust boundary: the issue text still reaches the agent.

Usage (prints ``key=value`` lines for ``$GITHUB_OUTPUT``; exits 0 either way):
    python scripts/dataset_request_gate.py --permission write \\
        --issue-number 42 --issue-json issue.json --issue-text issue.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

#: Labels that ask for the automation, and the agent each one starts.
REQUEST_LABELS = ("dataset-request", "drift")
_WRITE_PERMISSIONS = frozenset({"admin", "write"})

_ISSUE_NUMBER = re.compile(r"[1-9][0-9]{0,9}")
# The same search the workflow's later steps used to run on the issue text, now made
# strict: a key starts with a letter, holds only lowercase letters, digits and
# underscores, and is not glued to a longer word on either side.
_DATASET_SEARCH = re.compile(r"(?<![A-Za-z0-9_.])datago\.[A-Za-z0-9_]+(?![A-Za-z0-9_])")
_DATASET_ID = re.compile(r"datago\.[a-z][a-z0-9_]{0,63}")


@dataclass(frozen=True)
class Decision:
    allowed: bool
    reason: str
    dataset: str = ""
    agent: str = ""

    def outputs(self) -> list[str]:
        """``key=value`` lines for ``$GITHUB_OUTPUT``. No value holds a newline."""
        reason = " ".join(self.reason.split())
        return [
            f"allowed={'true' if self.allowed else 'false'}",
            f"reason={reason}",
            f"dataset={self.dataset}",
            f"agent={self.agent}",
        ]


def valid_issue_number(value: str) -> bool:
    return _ISSUE_NUMBER.fullmatch(value) is not None


def extract_dataset(text: str) -> str | None:
    """The first ``datago.<key>`` id in ``text`` when it is well formed, else ``None``.

    Only the first mention counts, as before; a malformed first mention is refused
    rather than skipped, so a later one cannot be smuggled past it."""
    match = _DATASET_SEARCH.search(text)
    if match is None:
        return None
    candidate = match.group(0)
    return candidate if _DATASET_ID.fullmatch(candidate) else None


def _label_names(issue: Mapping[str, Any]) -> set[str]:
    labels = issue.get("labels")
    if not isinstance(labels, list):
        return set()
    names: set[str] = set()
    for label in labels:
        name = label.get("name") if isinstance(label, Mapping) else label
        if isinstance(name, str):
            names.add(name)
    return names


def decide(*, permission: str, issue_number: str, issue: Mapping[str, Any], text: str) -> Decision:
    if permission not in _WRITE_PERMISSIONS:
        return Decision(
            False,
            f"the account that started this run has '{permission or 'no'}' permission;"
            " a maintainer with write access must apply the label or dispatch the workflow",
        )
    if not valid_issue_number(issue_number):
        return Decision(False, "the issue number is not a plain positive integer")
    if issue.get("pull_request") is not None:
        return Decision(False, f"#{issue_number} is a pull request, not an issue")
    if issue.get("state") != "open":
        return Decision(False, f"issue #{issue_number} is not open")
    labels = _label_names(issue)
    if not labels & set(REQUEST_LABELS):
        return Decision(False, f"issue #{issue_number} carries none of {', '.join(REQUEST_LABELS)}")
    dataset = extract_dataset(text)
    if dataset is None:
        return Decision(
            False,
            "the issue names no well-formed dataset id"
            " (datago.<key>: lowercase letters, digits and underscores)",
        )
    agent = "drift-fixer" if "drift" in labels else "dataset-builder"
    return Decision(True, f"{dataset} by {agent}", dataset=dataset, agent=agent)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--permission", required=True, help="the starter's repository permission")
    parser.add_argument("--issue-number", required=True)
    parser.add_argument("--issue-json", type=Path, required=True, help="GET /issues/{n} as JSON")
    parser.add_argument("--issue-text", type=Path, required=True, help="title and body as text")
    args = parser.parse_args(argv)

    try:
        loaded = json.loads(args.issue_json.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        loaded = None
    issue: Mapping[str, Any] = loaded if isinstance(loaded, Mapping) else {}
    try:
        text = args.issue_text.read_text(encoding="utf-8")
    except OSError:
        text = ""

    decision = decide(
        permission=args.permission.strip(),
        issue_number=args.issue_number.strip(),
        issue=issue,
        text=text,
    )
    print("\n".join(decision.outputs()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
