#!/usr/bin/env python3
"""Fail when a workflow pins an action by tag or branch instead of a SHA (#875).

A tag or branch ref can be moved to a different commit by anyone with push
access to the action's repository; a 40-hex SHA cannot. kpubdata-builder and
kpubdata-studio already gate on this — the check brings this repository level
with them, publish-pypi.yml included. Local actions (``./...``) and container
images (``docker://``) are out of scope.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_SHA = re.compile(r"[0-9a-f]{40}")
_USES = re.compile(r"^\s*(?:-\s+)?uses:\s*(\S+)")


def _offenders(text: str) -> list[tuple[int, str]]:
    offenders: list[tuple[int, str]] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = _USES.match(line)
        if match is None:
            continue
        reference = match.group(1)
        if reference.startswith(("./", "docker://")):
            continue
        if "@" not in reference:
            offenders.append((number, f"{reference} has no ref"))
            continue
        ref = reference.rsplit("@", 1)[1]
        if _SHA.fullmatch(ref) is None:
            offenders.append((number, f"{reference} is not pinned by SHA"))
    return offenders


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(".github/workflows")
    failed = False
    for path in sorted(root.glob("*.yml")):
        for number, message in _offenders(path.read_text(encoding="utf-8")):
            print(f"{path.relative_to(root.parent.parent)}:{number}: {message}")
            failed = True
    if failed:
        print("pin every action by its 40-character commit SHA (comment keeps the tag)")
        return 1
    print(f"action pin gate: every uses ref under {root} is a SHA")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
