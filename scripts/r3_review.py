#!/usr/bin/env python3
"""Say whether a pull request may merge under its review level (#722, builder#905).

POLICY defines R3 as the level that must have a human review, and section 14 forbids
an agent from giving the final approval on its own pull request. Nothing enforced
either: branch protection required no approvals, and kpubdata-builder#893, labelled
``review:R3``, merged with no review at all. A rule without a gate is a wish
(VERIFICATION 3), so this is the gate, and the four repositories call it through
``.github/actions/r3-review`` instead of keeping copies.

The rule, decided by the owner on 2026-10-01:

- A pull request without the ``review:R3`` label passes. The check runs on every pull
  request so that requiring it never leaves one waiting for a check that is not coming.
- A pull request with the label passes only when at least one reviewer other than its
  author currently approves it. "Currently" mirrors GitHub's own review state with
  "dismiss stale approvals" off, which is how branch protection is set:

  * each reviewer's latest APPROVED, CHANGES_REQUESTED or DISMISSED review decides
    their state — a COMMENTED review changes nothing, as on GitHub;
  * an approval given on an older head still counts, because GitHub keeps it too;
  * an approval followed by a request for changes, or dismissed, does not count.

- Only a person counts. A bot account (``user.type == "Bot"``) is not a human review,
  and neither is an account without write access to the repository: on a public
  repository anyone can submit an APPROVED review, so only ``OWNER``, ``MEMBER`` and
  ``COLLABORATOR`` associations count — the same people GitHub's required reviews count.

The script reads the pull request and its reviews as JSON and makes no network call,
so every branch of the rule is a unit test. The action fetches them.

    $ python3 scripts/r3_review.py --pull pr.json --reviews reviews.json
    passed=true
    reason=#12 is review:R3 and approved by alice

Exit status 0 means the pull request may merge, 1 that it may not, 2 bad input.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

R3_LABEL = "review:R3"

# Reviews that set a reviewer's state. COMMENTED and PENDING do not.
_DECIDING_STATES = frozenset({"APPROVED", "CHANGES_REQUESTED", "DISMISSED"})

# Accounts GitHub would count toward required reviews: people with write access.
_TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})


@dataclass(frozen=True)
class Decision:
    passed: bool
    reason: str
    approvers: tuple[str, ...] = ()


def _login(user: Any) -> str | None:
    if not isinstance(user, Mapping):
        return None  # a deleted account ("ghost") comes back as null
    login = user.get("login")
    return login if isinstance(login, str) and login else None


def current_approvers(reviews: Iterable[Mapping[str, Any]], author: str) -> tuple[str, ...]:
    """The non-author humans with write access whose latest deciding review approves.

    Reviews are ordered by ``submitted_at`` and then by ``id``; GitHub returns them in
    that order already, but the rule should not depend on it.
    """
    ordered = sorted(
        reviews,
        key=lambda review: (str(review.get("submitted_at") or ""), int(review.get("id") or 0)),
    )
    latest: dict[str, Mapping[str, Any]] = {}
    for review in ordered:
        if review.get("state") not in _DECIDING_STATES:
            continue
        login = _login(review.get("user"))
        if login is None:
            continue
        latest[login] = review

    approvers = []
    for login, review in latest.items():
        if review.get("state") != "APPROVED":
            continue
        if login.casefold() == author.casefold():
            continue  # GitHub refuses this, but the rule must not rely on that
        if review["user"].get("type") == "Bot":
            continue
        if review.get("author_association") not in _TRUSTED_ASSOCIATIONS:
            continue
        approvers.append(login)
    return tuple(sorted(approvers, key=str.casefold))


def evaluate(
    pull: Mapping[str, Any],
    reviews: Iterable[Mapping[str, Any]],
    label: str = R3_LABEL,
) -> Decision:
    """Decide one pull request. ``pull`` is the REST ``pulls/{n}`` object."""
    number = pull.get("number")
    labels = {item.get("name") for item in pull.get("labels") or [] if isinstance(item, Mapping)}
    if label not in labels:
        return Decision(True, f"#{number} is not {label}; no review is required by this check")

    author = _login(pull.get("user"))
    if author is None:
        return Decision(False, f"#{number} is {label} but its author could not be read")

    approvers = current_approvers(reviews, author)
    if approvers:
        return Decision(
            True, f"#{number} is {label} and approved by {', '.join(approvers)}", approvers
        )
    return Decision(
        False,
        f"#{number} is {label} and needs an approval from a person other than its author "
        f"({author}) who has write access. A later request for changes or a dismissal "
        "cancels an approval; bots do not count (POLICY 14.1).",
    )


def _load_reviews(text: str) -> list[dict[str, Any]]:
    """Accept a JSON array, or one review per line as ``gh api --paginate --jq '.[]'`` writes.

    ``gh api --paginate`` without ``--jq`` concatenates one array per page, which is not
    valid JSON; the action uses the line form, and both are accepted here.
    """
    stripped = text.strip()
    if not stripped:
        return []
    if stripped.startswith("["):
        loaded = json.loads(stripped)
        if not isinstance(loaded, list):
            raise ValueError("reviews must be a JSON array")
        return loaded
    return [json.loads(line) for line in stripped.splitlines() if line.strip()]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--pull", type=Path, required=True, help="REST pulls/{n} JSON")
    parser.add_argument("--reviews", type=Path, required=True, help="REST pulls/{n}/reviews")
    parser.add_argument(
        "--label", default=R3_LABEL, help=f"Label that requires review ({R3_LABEL})"
    )
    args = parser.parse_args(argv)

    try:
        pull = json.loads(args.pull.read_text(encoding="utf-8"))
        reviews = _load_reviews(args.reviews.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"::error::cannot read the pull request or its reviews: {error}", file=sys.stderr)
        return 2
    if not isinstance(pull, dict):
        print("::error::the pull request JSON is not an object", file=sys.stderr)
        return 2

    decision = evaluate(pull, reviews, args.label)
    print(f"passed={'true' if decision.passed else 'false'}")
    print(f"reason={decision.reason}")
    print(f"approvers={','.join(decision.approvers)}")
    if not decision.passed:
        print(f"::error::{decision.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
