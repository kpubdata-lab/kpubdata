#!/usr/bin/env python3
"""Catalogue-only datasets may only shrink, and no dataset is declared twice (#898).

A dataset is declared either by a provider catalogue (``providers/*/catalogue.json``,
served by that provider's adapter) or by a spec (``specs/<provider>/*.yaml``, served by
the spec executor). Where both declare the same key, ``core/bridge.py`` serves the spec
and the catalogue copy is dead text that still reads as the definition. #898 removed
those copies; this gate keeps them from coming back and keeps the catalogue-only list
from growing while datasets move to specs.

Three things fail:

- a catalogue entry that ``scripts/catalogue_only_baseline.txt`` does not list -- a new
  dataset is written as a spec, not added to a catalogue;
- a baseline line whose catalogue entry is gone -- the list only shrinks, so remove the
  line in the same change;
- a key declared by both a catalogue and a spec.

The spec id is read with a regex, as ``check_baseline_shrink.py`` does, so the gate
needs nothing beyond Python itself.

Usage:
    python scripts/check_catalogue_baseline.py [--root PATH]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BASELINE = Path("scripts") / "catalogue_only_baseline.txt"
PROVIDERS = Path("src") / "kpubdata" / "providers"
SPECS = Path("src") / "kpubdata" / "specs"

_SPEC_ID = re.compile(r"^id:\s*['\"]?([\w.]+)['\"]?\s*$", re.MULTILINE)


def catalogue_ids(root: Path) -> set[str]:
    """Every ``provider.dataset_key`` a provider catalogue declares."""
    ids: set[str] = set()
    for path in sorted((root / PROVIDERS).glob("*/catalogue.json")):
        provider = path.parent.name
        for entry in json.loads(path.read_text(encoding="utf-8")):
            ids.add(f"{provider}.{entry['dataset_key']}")
    return ids


def spec_ids(root: Path) -> set[str]:
    """Every dataset id a bundled spec declares."""
    ids: set[str] = set()
    for path in sorted((root / SPECS).rglob("*.y*ml")):
        match = _SPEC_ID.search(path.read_text(encoding="utf-8"))
        if match:
            ids.add(match.group(1))
    return ids


def baseline_ids(root: Path) -> set[str]:
    """The baseline's entries, without comments and blank lines."""
    lines = (root / BASELINE).read_text(encoding="utf-8").splitlines()
    return {line.strip() for line in lines if line.strip() and not line.startswith("#")}


def evaluate(
    catalogue: set[str],
    specs: set[str],
    baseline: set[str],
) -> list[str]:
    """Problems with the current catalogues; an empty list means the gate passes."""
    problems: list[str] = []
    duplicates = catalogue & specs
    for dataset_id in sorted(duplicates):
        problems.append(
            f"{dataset_id} is declared by both a catalogue and a spec; the spec serves it, "
            "so remove the catalogue entry"
        )
    catalogue_only = catalogue - specs
    for dataset_id in sorted(catalogue_only - baseline):
        problems.append(
            f"{dataset_id} is a new catalogue-only entry; write it as a spec instead "
            f"({BASELINE} may only shrink)"
        )
    for dataset_id in sorted(baseline - catalogue_only):
        problems.append(
            f"{dataset_id} is no longer catalogue-only; remove its line from {BASELINE}"
        )
    return problems


def main(argv: list[str] | None = None) -> int:
    """Check the catalogues once. Returns 0 when they match the baseline."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", default=str(REPO_ROOT))
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    problems = evaluate(catalogue_ids(root), spec_ids(root), baseline_ids(root))
    if not problems:
        print(f"catalogue baseline holds: {len(baseline_ids(root))} catalogue-only entries")
        return 0
    for problem in problems:
        print(f"::error::{problem}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
