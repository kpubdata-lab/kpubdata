#!/usr/bin/env python3
"""Write the dataset status map the package ships, from SUPPORTED_DATA.md (#783).

``DatasetRef.status`` has to answer at run time, and SUPPORTED_DATA.md is not in the
wheel. This derives ``src/kpubdata/dataset_status.json`` — dataset id → canonical
``DatasetStatus`` — from that document's level column, so the two cannot say different
things: the level is read with the row parser of ``sync_supported_data.py`` and mapped
with ``SUPPORTED_DATA_LEVELS`` (ADR 0005). A spec's ``status:`` override (``unstable``,
``broken``, ``deprecated``) replaces the level, as ``SPEC_STATUS_OVERRIDE`` says.

Usage:
    python scripts/gen_dataset_status.py           # rewrite the file
    python scripts/gen_dataset_status.py --check   # exit 1 if it would change
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sync_supported_data import DATASET_ROW, split_cells

from kpubdata.core.spec import discover_specs
from kpubdata.core.status import SPEC_STATUS_OVERRIDE, SUPPORTED_DATA_LEVELS, SpecStatus

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "SUPPORTED_DATA.md"
OUTPUT = ROOT / "src" / "kpubdata" / "dataset_status.json"


def document_levels(text: str) -> dict[str, str]:
    """Dataset id → the level written in the document's first column."""
    levels: dict[str, str] = {}
    for line in text.splitlines():
        match = DATASET_ROW.match(line.strip())
        if match:
            dataset_id = f"{match.group('provider')}.{match.group('dataset')}"
            levels[dataset_id] = split_cells(line)[0]
    return levels


def spec_overrides() -> dict[str, str]:
    """Dataset id → the status a spec's ``status:`` field overrides the level with."""
    overrides: dict[str, str] = {}
    for spec in discover_specs():
        override = SPEC_STATUS_OVERRIDE[SpecStatus(spec.status)]
        if override is not None:
            overrides[spec.id] = override.value
    return overrides


def build(text: str, overrides: dict[str, str]) -> dict[str, str]:
    """The status map; an unknown level is an error, not a missing entry."""
    statuses: dict[str, str] = {}
    for dataset_id, level in document_levels(text).items():
        if level not in SUPPORTED_DATA_LEVELS:
            raise ValueError(f"{dataset_id}: unknown SUPPORTED_DATA.md level {level!r}")
        statuses[dataset_id] = SUPPORTED_DATA_LEVELS[level].value
    statuses.update({key: value for key, value in overrides.items() if key in statuses})
    return dict(sorted(statuses.items()))


def render(statuses: dict[str, str]) -> str:
    return json.dumps(statuses, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="exit 1 instead of writing")
    args = parser.parse_args(argv)
    after = render(build(DOC.read_text(encoding="utf-8"), spec_overrides()))
    before = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
    if before == after:
        print("dataset_status.json matches SUPPORTED_DATA.md")
        return 0
    if args.check:
        print(
            "dataset_status.json differs from SUPPORTED_DATA.md — "
            "run scripts/gen_dataset_status.py",
            file=sys.stderr,
        )
        return 1
    OUTPUT.write_text(after, encoding="utf-8")
    print("dataset_status.json rewritten from SUPPORTED_DATA.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
