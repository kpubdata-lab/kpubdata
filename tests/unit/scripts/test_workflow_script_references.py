"""A workflow that calls a missing script fails only when someone dispatches it.

Written because the first draft of `release.yml` called
`scripts/check_version_consistency.py`, which lives in kpubdata-builder and not here.
Nothing would have said so until a release was attempted, and by then the person
attempting it is mid-release.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

_SCRIPT_REFERENCE = re.compile(r"scripts/[\w./-]+\.(?:py|sh|mjs|js)")


def test_every_script_a_workflow_calls_exists() -> None:
    missing: list[str] = []
    for workflow in sorted(WORKFLOWS.glob("*.y*ml")):
        text = workflow.read_text(encoding="utf-8")
        for reference in sorted(set(_SCRIPT_REFERENCE.findall(text))):
            if not (REPO_ROOT / reference).exists():
                missing.append(f"{workflow.name}: {reference}")

    assert not missing, "workflows call scripts that do not exist:\n  " + "\n  ".join(missing)


def test_the_sweep_actually_finds_references() -> None:
    """Otherwise a regex that matches nothing passes for ever."""
    found = {
        reference
        for workflow in WORKFLOWS.glob("*.y*ml")
        for reference in _SCRIPT_REFERENCE.findall(workflow.read_text(encoding="utf-8"))
    }

    assert len(found) >= 5, f"expected the workflows to call several scripts, found {found}"
