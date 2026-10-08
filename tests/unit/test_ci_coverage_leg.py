"""Coverage rides one matrix leg instead of a separate full run (#872).

A dedicated Coverage Gate job ran the whole suite a second time only to add
``--cov``. The 3.12 leg now carries the instrumentation, the floor stays in
pyproject's ``[tool.coverage.report] fail_under``, and the gate waits on the
test legs alone.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[2]


def _load() -> dict[str, Any]:
    path = _ROOT / ".github/workflows/ci.yml"
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def test_no_separate_coverage_job() -> None:
    assert "coverage" not in _load()["jobs"]


def test_the_312_leg_carries_the_instrumentation() -> None:
    doc = _load()
    matrix = doc["jobs"]["test"]["strategy"]["matrix"]
    assert {"python-version": "3.12", "coverage": "--cov --cov-report=term-missing"} in matrix["include"]
    text = (_ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    assert "COVERAGE_ARGS: ${{ matrix.coverage }}" in text


def test_the_gate_waits_on_the_test_legs() -> None:
    needs = _load()["jobs"]["gate"]["needs"]
    assert "test" in needs
    assert "coverage" not in needs
