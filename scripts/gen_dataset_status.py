#!/usr/bin/env python3
"""Write the dataset status map the package ships, from the dataset metadata (#783, #842).

``DatasetRef.status`` answers with one canonical ``DatasetStatus`` per dataset. This
derives ``src/kpubdata/dataset_status.json`` — dataset id → status — from the ``level``
of ``dataset_metadata.json``, the source SUPPORTED_DATA.md is written from too, so the
three cannot say different things. A spec's ``status:`` override (``unstable``,
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

from sync_supported_data import METADATA, load_metadata

from kpubdata.core.spec import discover_specs
from kpubdata.core.status import SPEC_STATUS_OVERRIDE, DatasetStatus, SpecStatus

ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "src" / "kpubdata" / "dataset_status.json"


def spec_overrides() -> dict[str, str]:
    """Dataset id → the status a spec's ``status:`` field overrides the level with."""
    overrides: dict[str, str] = {}
    for spec in discover_specs():
        override = SPEC_STATUS_OVERRIDE[SpecStatus(spec.status)]
        if override is not None:
            overrides[spec.id] = override.value
    return overrides


def build(metadata: dict[str, dict[str, str | None]], overrides: dict[str, str]) -> dict[str, str]:
    """The status map; a level outside the vocabulary is an error, not a missing entry."""
    statuses: dict[str, str] = {}
    for dataset_id, entry in metadata.items():
        try:
            statuses[dataset_id] = DatasetStatus(entry["level"]).value
        except ValueError:
            raise ValueError(
                f"{dataset_id}: unknown dataset_metadata level {entry['level']!r}"
            ) from None
    statuses.update({key: value for key, value in overrides.items() if key in statuses})
    return dict(sorted(statuses.items()))


def render(statuses: dict[str, str]) -> str:
    return json.dumps(statuses, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n", 1)[0])
    parser.add_argument("--check", action="store_true", help="exit 1 instead of writing")
    args = parser.parse_args(argv)
    after = render(build(load_metadata(METADATA), spec_overrides()))
    before = OUTPUT.read_text(encoding="utf-8") if OUTPUT.is_file() else ""
    if before == after:
        print("dataset_status.json matches dataset_metadata.json")
        return 0
    if args.check:
        print(
            "dataset_status.json differs from dataset_metadata.json — "
            "run scripts/gen_dataset_status.py",
            file=sys.stderr,
        )
        return 1
    OUTPUT.write_text(after, encoding="utf-8")
    print("dataset_status.json rewritten from dataset_metadata.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
