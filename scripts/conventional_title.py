#!/usr/bin/env python3
"""Issue and pull request titles carry the change type; the `type:*` label follows.

ADR 0003 asked for Conventional Commits pull request titles, and the last forty
merged titles in kpubdata all complied — but nothing checked, so the rule held only
while everyone remembered it. Issues went the other way: the type lived in a
hand-set `type:*` label while the title said nothing, and the three repositories'
issue templates disagreed on the label name (`type:bug` here, `bug` in the other
two).

POLICY 2.1.3 settles it. The title is the source; the label is derived from it by a
workflow, never set by hand, so the two cannot drift. This script is the one parser
both the pull request check and the issue labeller use, in all three repositories.

    $ python3 scripts/conventional_title.py "fix(localdata): empty wrapper becomes a row"
    type=fix
    scope=localdata
    breaking=false
    label=type:bug

The output is `key=value` lines for `$GITHUB_OUTPUT`. An invalid title exits 1 with
an `::error::` line that says what a valid one looks like.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass

# The eleven types POLICY 2.1.3 allows, the same in all three repositories. `i18n` was
# dropped on 2026-09-29: translation work is `docs` or `chore(i18n)`, so it needs no
# type of its own. Titles merged before then are history and are not rewritten.
TYPES = (
    "feat",
    "fix",
    "docs",
    "chore",
    "test",
    "ci",
    "refactor",
    "style",
    "perf",
    "build",
    "revert",
)

# POLICY 2.1 names four kinds: bug, feature, docs, chore. Everything that is neither a
# defect, a capability nor documentation is upkeep.
LABELS = {
    "fix": "type:bug",
    "feat": "type:feature",
    "docs": "type:docs",
}
DEFAULT_LABEL = "type:chore"
ALL_LABELS = ("type:bug", "type:feature", "type:docs", "type:chore")

# One line only: a line break in the scope or description would let a title add its own
# `key=value` lines to $GITHUB_OUTPUT (#628). `fullmatch` and the excluded \r\n keep a
# title to exactly one line.
_TITLE = re.compile(
    r"(?P<type>[a-z0-9]+)"
    r"(?:\((?P<scope>[^()\s][^()\r\n]*)\))?"
    r"(?P<breaking>!)?"
    r": (?P<description>\S[^\r\n]*)"
)

_GITHUB_REVERT = re.compile(r'^Revert ".+"$')

# POLICY 2.1.3: PR titles do not carry issue numbers (#699). Squash merge appends
# the PR number, so "(#123)" in a title becomes "... (#123) (#456)" in the commit.
_ISSUE_NUMBER = re.compile(r"\(#[0-9]+\)\s*$")

_EXAMPLE = "fix(localdata): empty wrapper becomes a phantom row"

# Pull request titles only (POLICY 2.1.3, #742). A pull request title becomes the commit
# title on main, which is English and carries no issue reference; an issue title may be
# Korean when English would block the report (AGENTS.md), so these do not apply to it.
MAX_PR_TITLE_LENGTH = 100
_HANGUL = re.compile(r"[\u1100-\u11ff\u3130-\u318f\ua960-\ua97f\uac00-\ud7af\ud7b0-\ud7ff]")
# `#123`, `(#123)`, `repo#123`, `owner/repo#123`, and issue or pull request URLs. A `#`
# not followed by a digit (`C#`, a `#` in a code span) is not a reference.
_ISSUE_REFERENCE = re.compile(
    r"(?:^|[^\w&])(?:[\w.-]+/)?(?:[\w.-]+)?#[0-9]+\b"
    r"|github\.com/[^\s/]+/[^\s/]+/(?:issues|pull)/[0-9]+"
)


class TitleError(Exception):
    """The title does not follow `type(scope): description`."""


@dataclass(frozen=True)
class Title:
    """A parsed title."""

    type: str
    scope: str | None
    breaking: bool
    description: str

    @property
    def label(self) -> str:
        """The `type:*` label this title implies."""
        return LABELS.get(self.type, DEFAULT_LABEL)


def parse(title: str, *, pull_request: bool = False) -> Title:
    """Parse a title.

    ``pull_request`` adds the rules for a title that becomes a commit on main: no
    Hangul, no issue reference anywhere, at most MAX_PR_TITLE_LENGTH characters.
    GitHub's own `Revert "..."` title quotes the reverted commit as it was and is
    exempt.

    Raises:
        TitleError: The shape is wrong, the type is not one of TYPES, or a pull
            request title breaks a pull-request-only rule.
    """
    title = title.strip()
    if "\n" in title or "\r" in title:
        raise TitleError("title must be a single line")
    # POLICY 2.1.3: no issue numbers in PR titles (#699). Squash merge appends the PR
    # number, so a trailing "(#123)" becomes "... (#123) (#456)" in the commit title.
    # Link issues from the body with `Closes #123` instead.
    if _ISSUE_NUMBER.search(title):
        raise TitleError(
            "PR titles do not carry issue numbers — squash merge appends the PR number "
            "and the final commit would read `... (#123) (#456)`. Link the issue from "
            "the body with `Closes #123`."
        )
    # GitHub's own "Revert" button writes `Revert "fix: ..."`. It is a revert whatever
    # it reverts, and refusing it would make undoing a merge fail a check.
    if _GITHUB_REVERT.match(title):
        return Title(type="revert", scope=None, breaking=False, description=title)
    if pull_request:
        _check_pull_request_title(title)
    match = _TITLE.fullmatch(title)
    if match is None:
        raise TitleError(
            f"title must look like `type(scope): description`, for example `{_EXAMPLE}`. "
            "The scope is optional."
        )
    kind = match.group("type")
    if kind not in TYPES:
        allowed = ", ".join(TYPES)
        raise TitleError(f"`{kind}` is not a type this project uses. Use one of: {allowed}.")
    return Title(
        type=kind,
        scope=match.group("scope"),
        breaking=match.group("breaking") is not None,
        description=match.group("description").strip(),
    )


def _check_pull_request_title(title: str) -> None:
    """Refuse what a commit title on main may not carry (POLICY 2.1.3, #742)."""
    if _HANGUL.search(title):
        raise TitleError(
            "PR titles are English — the title becomes the commit title on main "
            "(ADR 0003). Korean belongs in the PR body."
        )
    if _ISSUE_REFERENCE.search(title):
        raise TitleError(
            "PR titles carry no issue reference (`#123`, `repo#123`, an issue URL). "
            "Link it from the body with `Closes #123` or `Refs owner/repo#123`."
        )
    if len(title) > MAX_PR_TITLE_LENGTH:
        raise TitleError(
            f"PR titles are at most {MAX_PR_TITLE_LENGTH} characters (this one is "
            f"{len(title)}). Say the rest in the body."
        )


def main(argv: list[str] | None = None) -> int:
    """Check one title. Returns 0 when it parses, 1 otherwise."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("title")
    parser.add_argument(
        "--pull-request",
        action="store_true",
        help="also apply the rules for a title that becomes a commit on main",
    )
    args = parser.parse_args(argv)
    try:
        title = parse(args.title, pull_request=args.pull_request)
    except TitleError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1
    print(f"type={title.type}")
    print(f"scope={title.scope or ''}")
    print(f"breaking={'true' if title.breaking else 'false'}")
    print(f"label={title.label}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
