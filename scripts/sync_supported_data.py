#!/usr/bin/env python3
"""Keep the dataset metadata equal to the evidence, and write the documents from it (#621, #842).

``src/kpubdata/dataset_metadata.json`` is the source for a dataset's level: what the
package answers at run time, and what SUPPORTED_DATA.md's three level columns say.
Before #842 the document was the source and the package read a file derived from it.

This recomputes the metadata from ``tests/fixtures`` and then the document from the
metadata:

- a ``meta.json`` exists for the dataset — a response recorded from the live API —
  → level and verification ``live_verified``, ``checked_on`` its latest ``recorded_at``
- none exists but the entry claims ``live_verified`` → ``fixture_verified``, no date
- any other level (awaiting an application, retired, in progress …) is a human
  judgement written in the metadata, and is kept

A dataset row with no metadata entry, or an entry with no row, is an error.

It also normalises the row shape: every row has exactly as many cells as the header
and ends with ``|``. Text written after the closing pipe (which GitHub drops from the
rendered table) is moved into the last cell.

Usage:
    python scripts/sync_supported_data.py           # rewrite the files
    python scripts/sync_supported_data.py --check   # exit 1 if they would change
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
METADATA = ROOT / "src" / "kpubdata" / "dataset_metadata.json"

#: Canonical level → the document's first column (``SUPPORTED_DATA_LEVELS``, reversed).
LEVEL_LABELS = {
    "planned": "예정",
    "in_progress": "진행 중",
    "fixture_verified": "스키마만",
    "live_verified": "지원",
    "application_required": "활용신청 대기",
    "retired": "폐기",
}
#: Verification → the document's second column. A retired dataset has none: the
#: column then says its retirement was confirmed, and the date is when.
RETIREMENT_CONFIRMED = "폐기 확인"
VERIFICATION_LABELS = {
    "planned": "-",
    "in_progress": "-",
    "fixture_verified": "테스트 검증",
    "live_verified": "실API 검증",
    "production": "실API 검증",
}

Entry = dict[str, str | None]

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


def refresh(metadata: dict[str, Entry], dates: dict[tuple[str, str], str]) -> dict[str, Entry]:
    """The metadata with its evidence-derived fields recomputed from the recordings."""
    refreshed: dict[str, Entry] = {}
    for dataset_id, entry in sorted(metadata.items()):
        provider, _, dataset = dataset_id.partition(".")
        recorded = dates.get((provider, dataset))
        if recorded is not None:
            entry = {"level": "live_verified", "verification": "live_verified"}
            entry["checked_on"] = None if recorded == "-" else recorded
        elif entry["level"] == "live_verified" or entry["verification"] == "live_verified":
            level = "fixture_verified" if entry["level"] == "live_verified" else entry["level"]
            entry = {"level": level, "verification": "fixture_verified", "checked_on": None}
        refreshed[dataset_id] = {key: entry[key] for key in ("level", "verification", "checked_on")}
    return refreshed


def sync_row(line: str, metadata: dict[str, Entry]) -> str:
    match = DATASET_ROW.match(line.strip())
    if not match:
        return line
    cells = split_cells(line)
    if len(cells) != COLUMNS:
        return line  # left for the lint to report
    dataset_id = f"{match.group('provider')}.{match.group('dataset')}"
    entry = metadata.get(dataset_id)
    if entry is None:
        raise ValueError(f"{dataset_id}: a row in SUPPORTED_DATA.md with no dataset_metadata entry")
    cells[0:3] = [
        LEVEL_LABELS[str(entry["level"])],
        RETIREMENT_CONFIRMED
        if entry["verification"] is None
        else VERIFICATION_LABELS[entry["verification"]],
        entry["checked_on"] or "-",
    ]
    return "| " + " | ".join(cells) + " |"


def document_ids(text: str) -> set[str]:
    """Dataset ids of every dataset row in the document."""
    matches = (DATASET_ROW.match(line.strip()) for line in text.split("\n"))
    return {f"{m.group('provider')}.{m.group('dataset')}" for m in matches if m}


def sync(text: str, metadata: dict[str, Entry]) -> str:
    unlisted = sorted(set(metadata) - document_ids(text))
    if unlisted:
        raise ValueError(f"dataset_metadata entries with no SUPPORTED_DATA.md row: {unlisted}")
    return "\n".join(sync_row(line, metadata) for line in text.split("\n"))


def load_metadata(path: Path | None = None) -> dict[str, Entry]:
    return dict(json.loads((path or METADATA).read_text(encoding="utf-8")))


def render_metadata(metadata: dict[str, Entry]) -> str:
    return json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="exit 1 instead of writing")
    args = parser.parse_args()
    metadata = refresh(load_metadata(), recorded_dates(FIXTURES))
    wanted = {
        METADATA: render_metadata(metadata),
        DOC: sync(DOC.read_text(encoding="utf-8"), metadata),
    }
    stale = [path for path, text in wanted.items() if path.read_text(encoding="utf-8") != text]
    if not stale:
        print("dataset_metadata.json and SUPPORTED_DATA.md match the evidence")
        return 0
    names = ", ".join(path.name for path in stale)
    if args.check:
        print(
            f"{names} differ from the evidence — run scripts/sync_supported_data.py",
            file=sys.stderr,
        )
        return 1
    for path in stale:
        path.write_text(wanted[path], encoding="utf-8")
    print(f"{names} rewritten from the evidence")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
