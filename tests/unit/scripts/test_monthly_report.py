"""The monthly report quotes the status snapshot's per-family pass rate (#899)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load() -> Any:
    path = REPO_ROOT / "scripts" / "monthly_report.py"
    spec = importlib.util.spec_from_file_location("_monthly_report", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["_monthly_report"] = module
    spec.loader.exec_module(module)
    return module


report = _load()


def test_report_lists_every_family_and_the_as_of_date(monkeypatch: Any) -> None:
    monkeypatch.setattr(report, "collect_drift_issues", lambda month: [])
    families = report.collect_spec_status()["family_pass_rate"]
    text = report.build_report("2026-10", as_of="2026-10-11")
    assert "기준일: 2026-10-11" in text
    for name, f in families.items():
        assert f"| {name} | {f['total']} | {f['live_passing']} | {f['pass_rate']}% |" in text
