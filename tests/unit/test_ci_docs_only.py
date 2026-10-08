"""Documentation-only pull requests skip the heavy jobs, on purpose (#873).

A ``changes`` job diffs the pull request; when nothing but documentation moved,
test, build and base-install are skipped and the gate accepts a deliberate
skip. A failing upstream job still fails the gate — its own result is a
failure, not a skip, and these jobs carry no other ``needs``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[2]


def _load() -> dict[str, Any]:
    path = _ROOT / ".github/workflows/ci.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_the_changes_job_gates_the_heavy_jobs() -> None:
    doc = _load()
    assert doc["jobs"]["changes"]["outputs"]["code"] == "${{ steps.filter.outputs.code }}"
    for job in ("test", "build", "base-install"):
        spec = doc["jobs"][job]
        assert spec["needs"] == ["changes"], job
        assert spec["if"] == "needs.changes.outputs.code == 'true'", job


def test_the_gate_accepts_a_deliberate_skip() -> None:
    doc = _load()
    assert "changes" in doc["jobs"]["gate"]["needs"]
    run = doc["jobs"]["gate"]["steps"][0]["run"]
    assert "success|skipped)" in run
    assert '!= "success"' not in run


def test_build_and_base_install_wait_on_nothing_else() -> None:
    doc = _load()
    for job in ("build", "base-install"):
        assert doc["jobs"][job]["needs"] == ["changes"], job
