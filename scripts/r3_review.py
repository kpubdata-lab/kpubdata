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

- Only a person counts. A bot account (``user.type == "Bot"``) is not a human review.
- Only someone who can write to the repository **now** counts (#860). On a public
  repository anyone can submit an APPROVED review. The review's ``author_association``
  (``OWNER``, ``MEMBER``, ``COLLABORATOR``) says how the account is related to the
  repository, not what it may do: an organisation member or a collaborator can hold
  read or triage access only. So the approver's permission is looked up — ``admin`` or
  ``write`` counts (GitHub reports ``maintain`` as ``write`` and ``triage`` as
  ``read``) — and an approver whose permission could not be read does not count. The
  association is still required as well; it costs nothing and narrows who is asked
  about.

  The permission is the one held when the check runs, not when the review was
  submitted: an approval from someone who has since lost write access stops counting
  the next time the check runs. Losing access is not an event the check runs on, so
  until a push, a label change or a review re-runs it, the earlier result stands.

The script reads the pull request, its reviews and the approvers' permissions as JSON
and makes no network call, so every branch of the rule is a unit test. The action
fetches them, in two steps: ``--candidates`` prints the accounts whose permission is
needed, and the decision is made once those are known.

    $ python3 scripts/r3_review.py --pull pr.json --reviews reviews.json --candidates
    alice
    $ python3 scripts/r3_review.py --pull pr.json --reviews reviews.json \
          --permissions permissions.json
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

# Associations an account with write access always has. Necessary, not sufficient: a
# member or a collaborator may hold read or triage access only (#860).
_TRUSTED_ASSOCIATIONS = frozenset({"OWNER", "MEMBER", "COLLABORATOR"})

# ``permission`` values of ``GET /repos/{owner}/{repo}/collaborators/{user}/permission``
# that let an account push. GitHub folds ``maintain`` into ``write`` and ``triage``
# into ``read`` in this field.
_WRITE_PERMISSIONS = frozenset({"admin", "write"})


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


def can_write(permissions: Mapping[str, Any], login: str) -> bool:
    """Whether ``permissions`` says ``login`` can push. Unknown, null or unread: no."""
    wanted = login.casefold()
    for name, permission in permissions.items():
        if isinstance(name, str) and name.casefold() == wanted:
            return isinstance(permission, str) and permission in _WRITE_PERMISSIONS
    return False


def approval_candidates(reviews: Iterable[Mapping[str, Any]], author: str) -> tuple[str, ...]:
    """The non-author humans, related to the repository, whose latest deciding review
    approves — the accounts whose permission decides whether the approval counts.

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


def current_approvers(
    reviews: Iterable[Mapping[str, Any]], author: str, permissions: Mapping[str, Any]
) -> tuple[str, ...]:
    """The candidates who can write to the repository now, by ``permissions``."""
    return tuple(
        login for login in approval_candidates(reviews, author) if can_write(permissions, login)
    )


def _is_labelled(pull: Mapping[str, Any], label: str) -> bool:
    labels = {item.get("name") for item in pull.get("labels") or [] if isinstance(item, Mapping)}
    return label in labels


def candidates_to_look_up(
    pull: Mapping[str, Any],
    reviews: Iterable[Mapping[str, Any]],
    label: str = R3_LABEL,
) -> tuple[str, ...]:
    """The accounts whose permission ``evaluate`` will need — none when the pull request
    does not carry the label or its author cannot be read, since nothing is then asked."""
    if not _is_labelled(pull, label):
        return ()
    author = _login(pull.get("user"))
    if author is None:
        return ()
    return approval_candidates(reviews, author)


def evaluate(
    pull: Mapping[str, Any],
    reviews: Iterable[Mapping[str, Any]],
    permissions: Mapping[str, Any],
    label: str = R3_LABEL,
) -> Decision:
    """Decide one pull request. ``pull`` is the REST ``pulls/{n}`` object and
    ``permissions`` maps each candidate's login to their repository permission."""
    number = pull.get("number")
    if not _is_labelled(pull, label):
        return Decision(True, f"#{number} is not {label}; no review is required by this check")

    author = _login(pull.get("user"))
    if author is None:
        return Decision(False, f"#{number} is {label} but its author could not be read")

    reviews = list(reviews)
    approvers = current_approvers(reviews, author, permissions)
    if approvers:
        return Decision(
            True, f"#{number} is {label} and approved by {', '.join(approvers)}", approvers
        )
    without_write = [
        login for login in approval_candidates(reviews, author) if not can_write(permissions, login)
    ]
    not_counted = (
        f" Approved by {', '.join(without_write)}, whose write access could not be "
        "confirmed — read or triage access, or a permission lookup that failed, does not count."
        if without_write
        else ""
    )
    return Decision(
        False,
        f"#{number} is {label} and needs an approval from a person other than its author "
        f"({author}) who has write access. A later request for changes or a dismissal "
        f"cancels an approval; bots do not count (POLICY 14.1).{not_counted}",
    )


def _load_permissions(text: str) -> dict[str, Any]:
    """``{login: permission}``. A permission that could not be read is ``null``."""
    loaded = json.loads(text) if text.strip() else {}
    if not isinstance(loaded, dict):
        raise ValueError("permissions must be a JSON object of login to permission")
    return loaded


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
    parser.add_argument(
        "--permissions",
        type=Path,
        help="JSON object of login to repository permission; without it nobody has write access",
    )
    parser.add_argument(
        "--candidates",
        action="store_true",
        help="Print the logins whose permission is needed, one per line, and decide nothing",
    )
    args = parser.parse_args(argv)

    try:
        pull = json.loads(args.pull.read_text(encoding="utf-8"))
        reviews = _load_reviews(args.reviews.read_text(encoding="utf-8"))
        permissions = (
            _load_permissions(args.permissions.read_text(encoding="utf-8"))
            if args.permissions is not None
            else {}
        )
    except (OSError, ValueError) as error:
        print(
            f"::error::cannot read the pull request, its reviews or the permissions: {error}",
            file=sys.stderr,
        )
        return 2
    if not isinstance(pull, dict):
        print("::error::the pull request JSON is not an object", file=sys.stderr)
        return 2

    if args.candidates:
        for login in candidates_to_look_up(pull, reviews, args.label):
            print(login)
        return 0

    decision = evaluate(pull, reviews, permissions, args.label)
    print(f"passed={'true' if decision.passed else 'false'}")
    print(f"reason={decision.reason}")
    print(f"approvers={','.join(decision.approvers)}")
    if not decision.passed:
        print(f"::error::{decision.reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
