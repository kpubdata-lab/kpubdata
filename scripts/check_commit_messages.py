#!/usr/bin/env python3
"""Check the commit messages a pull request will merge (#review of #728, #731).

AGENTS.md sets two rules for commit messages — "Always in English", and the
same `type(scope): description` shape the PR title carries. Nothing checked
either one: the PR title gate sees only the title, so a squash merge quietly
embedded whatever the intermediate commits carried. PR #728 merged a body
with a Korean word in it and a `record(fixtures):` header that is not a type
this project uses — visible in main's log forever, because main history is
never rewritten.

This gate reads every commit in ``base..HEAD``:

- the subject must parse with ``scripts/conventional_title.py`` — the one
  parser, loaded from its file so script and gate cannot diverge;
- no Hangul anywhere in the message — the English-only rule.

Usage::

    check_commit_messages.py --base origin/main
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

#: The same range check_english_comments.py reads — one definition of "Korean".
HANGUL = re.compile(r"[가-힣]")

_SCRIPTS_DIR = Path(__file__).resolve().parent


def _load_title_module() -> ModuleType:
    """Load scripts/conventional_title.py — scripts/ is not a package."""
    spec = importlib.util.spec_from_file_location(
        "conventional_title", _SCRIPTS_DIR / "conventional_title.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["conventional_title"] = module
    spec.loader.exec_module(module)
    return module


def commits_in_range(base: str) -> list[tuple[str, str, str]]:
    """Every commit in ``base..HEAD`` as ``(sha, subject, body)``.

    ``--no-merges``: the ephemeral merge commit GitHub builds to test a pull
    request ("Merge <sha> into <sha>") is not a commit anyone authored, and a
    squash merge embeds only the non-merge commits' messages - so those are
    the ones the convention applies to.
    """
    out = subprocess.run(
        ["git", "log", "--no-merges", "--format=%H%x1f%s%x1f%b%x1e", f"{base}..HEAD"],
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    ).stdout
    commits: list[tuple[str, str, str]] = []
    for chunk in out.split("\x1e"):
        if not chunk.strip():
            continue
        parts = chunk.strip("\n").split("\x1f")
        sha = parts[0]
        subject = parts[1] if len(parts) > 1 else ""
        body = parts[2] if len(parts) > 2 else ""
        commits.append((sha, subject, body))
    return commits


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", default="origin/main")
    args = parser.parse_args()

    try:
        commits = commits_in_range(args.base)
    except subprocess.CalledProcessError as exc:
        print(f"error: cannot log against {args.base}: {exc.stderr.strip()}", file=sys.stderr)
        return 2

    if not commits:
        print("no commits to check")
        return 0

    title_module = _load_title_module()
    failures = 0
    for sha, subject, body in commits:
        try:
            title_module.parse(subject)
        except title_module.TitleError as exc:
            failures += 1
            print(f"::error file={sha[:8]}::commit subject {subject!r}: {exc}")
        korean = next(
            (line.strip() for line in (subject + "\n" + body).splitlines() if HANGUL.search(line)),
            None,
        )
        if korean is not None:
            failures += 1
            print(
                f"::error file={sha[:8]}::commit messages are English-only "
                f"(AGENTS.md): {korean[:80]}"
            )

    if failures:
        print(
            f"error: {failures} commit-message violation(s). A squash merge carries "
            "them into main's history, which is never rewritten.",
            file=sys.stderr,
        )
        return 1
    print(f"{len(commits)} commit message(s) follow the convention")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
