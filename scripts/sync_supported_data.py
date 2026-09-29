#!/usr/bin/env python3
"""Derive SUPPORTED_DATA.md's level columns from the evidence; keep the table well-formed (#621).

The document defines the "supported" level as a record with a ``meta.json`` — a
response recorded from the live API. The level was typed by hand and drifted from
that definition in both directions. This recomputes the three level columns of every
dataset row from ``tests/fixtures``:

- a ``meta.json`` exists for the dataset → supported, live-verified, ``<latest recorded_at date>``
- none exists but the row claims supported → schema-only, test-verified, ``-``
- any other level (awaiting activation, retired, in progress …) is a human judgement
  and is kept

It also normalises the row shape: every row has exactly as many cells as the header
and ends with ``|``. Text written after the closing pipe (which GitHub drops from the
rendered table) is moved into the last cell.

Usage:
    python scripts/sync_supported_data.py           # rewrite the file
    python scripts/sync_supported_data.py --check   # exit 1 if it would change
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "SUPPORTED_DATA.md"
FIXTURES = ROOT / "tests" / "fixtures"

COLUMNS = 9
CELL_SPLIT = re.compile(r"(?<!\\)\|")
# A dataset row: the provider is the fourth cell (third when a pipe is missing) and the
# dataset id follows it. Other tables in the document (planned work, escape hatches)
# have a different shape.
DATASET_ROW = re.compile(
    r"^\|(?:[^|]*\|){2,3}[^|]*\(`(?P<provider>\w+)`\)\s*\|\s*`(?P<dataset>[\w.]+)`"
)
DATE_GLUED_TO_PROVIDER = re.compile(r"^(\d{4}-\d{2}-\d{2})\s+(.+\(`\w+`\))$")


def recorded_dates(fixtures: Path) -> dict[tuple[str, str], str]:
    """(provider, dataset) → the latest ``recorded_at`` date among its meta files."""
    dates: dict[tuple[str, str], str] = {}
    for meta in fixtures.glob("*/*/*.meta.json"):
        provider, dataset = meta.parts[-3], meta.parts[-2]
        recorded = str(json.loads(meta.read_text(encoding="utf-8")).get("recorded_at", ""))[:10]
        key = (provider, dataset)
        if recorded and recorded > dates.get(key, ""):
            dates[key] = recorded
        dates.setdefault(key, recorded or "-")
    return dates


def split_cells(line: str) -> list[str]:
    """Cells of a table row; text after the closing pipe becomes part of the last cell."""
    body = line.strip()
    trailing = ""
    if not body.endswith("|"):
        head, _, trailing = body.rpartition("|")
        body = head + "|"
    cells = [cell.strip() for cell in CELL_SPLIT.split(body)[1:-1]]
    note = trailing.strip().lstrip("—").strip()
    if note:
        cells.append(note)
    # A date and a provider written into one cell (a missing pipe).
    if len(cells) == COLUMNS - 1 and (glued := DATE_GLUED_TO_PROVIDER.match(cells[2])):
        cells[2:3] = [glued.group(1), glued.group(2)]
    # Anything beyond the last column belongs to the note.
    if len(cells) > COLUMNS:
        cells = cells[: COLUMNS - 1] + [" — ".join(cells[COLUMNS - 1 :])]
    return cells


def sync_row(line: str, dates: dict[tuple[str, str], str]) -> str:
    match = DATASET_ROW.match(line.strip())
    if not match:
        return line
    cells = split_cells(line)
    if len(cells) != COLUMNS:
        return line  # left for the lint to report
    key = (match.group("provider"), match.group("dataset"))
    if key in dates:
        cells[0:3] = ["지원", "실API 검증", dates[key]]
    elif cells[0] == "지원":
        cells[0:3] = ["스키마만", "테스트 검증", "-"]
    return "| " + " | ".join(cells) + " |"


def sync(text: str, dates: dict[tuple[str, str], str]) -> str:
    return "\n".join(sync_row(line, dates) for line in text.split("\n"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="exit 1 instead of writing")
    args = parser.parse_args()
    before = DOC.read_text(encoding="utf-8")
    after = sync(before, recorded_dates(FIXTURES))
    if before == after:
        print("SUPPORTED_DATA.md matches the evidence")
        return 0
    if args.check:
        print(
            "SUPPORTED_DATA.md differs from the evidence — run scripts/sync_supported_data.py",
            file=sys.stderr,
        )
        return 1
    DOC.write_text(after, encoding="utf-8")
    print("SUPPORTED_DATA.md rewritten from the evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
