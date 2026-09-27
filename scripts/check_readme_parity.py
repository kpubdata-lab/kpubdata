#!/usr/bin/env python3
"""Keep README.md and README.en.md structurally in step (#546).

ADR 0003 originally refused a separate `README.en.md`, and the reason it gave was
right: a translation in its own file stops being maintained and becomes a lie a few
months later. The decision changed, so the reason needs a counterweight rather than a
promise.

This compares **section structure only** — the `##` headings, their number and their
order. It does not compare content, which is neither possible nor wanted: a Korean
sentence and its English counterpart are not the same string, and the English file
says things the Korean one does not need to.

What actually drifts is a section added to one file and not the other. That is what
this catches.

Usage:
    python scripts/check_readme_parity.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
KOREAN = REPO_ROOT / "README.md"
ENGLISH = REPO_ROOT / "README.en.md"

# A README this long has stopped being a README. 150 is the budget #546 set; the
# number is a decision, not a discovery, and it is enforced so that it survives.
MAX_LINES = 150

_HEADING = re.compile(r"^## +(.+?)\s*$", re.MULTILINE)


def headings(path: Path) -> list[str]:
    """The `##` headings of a file, in order."""
    return _HEADING.findall(path.read_text(encoding="utf-8"))


def main() -> int:
    """Compare the two READMEs. Returns 0 when they agree, 1 otherwise."""
    problems: list[str] = []

    for path in (KOREAN, ENGLISH):
        if not path.exists():
            problems.append(f"{path.name} 가 없다")
    if problems:
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        return 1

    for path in (KOREAN, ENGLISH):
        count = len(path.read_text(encoding="utf-8").splitlines())
        if count > MAX_LINES:
            problems.append(
                f"{path.name} 가 {count}줄이다 (상한 {MAX_LINES}). 참조 내용은 docs/ 로 "
                "옮긴다 — README 는 프로젝트를 평가하는 문서다"
            )

    ko, en = headings(KOREAN), headings(ENGLISH)
    if ko != en:
        only_ko = [h for h in ko if h not in en]
        only_en = [h for h in en if h not in ko]
        if only_ko:
            problems.append(f"README.md 에만 있는 절: {only_ko}")
        if only_en:
            problems.append(f"README.en.md 에만 있는 절: {only_en}")
        if not only_ko and not only_en:
            problems.append(f"절 순서가 다르다\n      ko: {ko}\n      en: {en}")

    if problems:
        print("README 두 파일이 어긋난다.\n", file=sys.stderr)
        for line in problems:
            print(f"  {line}", file=sys.stderr)
        print(
            "\n한쪽에만 절을 더하면 같은 프로젝트가 두 가지로 설명된다. ADR 0003 이 별도"
            "\n파일을 한 번 기각한 이유가 그것이고, 이 검사가 그 이유를 무력화한다.",
            file=sys.stderr,
        )
        return 1

    print(f"README 두 파일이 같은 {len(ko)}개 절을 같은 순서로 가진다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
