"""The status page is a function of the repository, not of the calendar (#620).

It counted "verified in the last 90 days" against today, so on 2026-12-09 the rendered
page would change with no content change and ``--check`` would fail every pull
request. It also counted only three of the six SUPPORTED_DATA levels.
"""

from __future__ import annotations

import datetime as dt
import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from kpubdata.core.status import SUPPORTED_DATA_LEVELS

REPO_ROOT = Path(__file__).resolve().parents[3]


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gen = _load("_gen_status_page", REPO_ROOT / "scripts" / "gen_status_page.py")
sync = _load("_sync_supported_data_for_status", REPO_ROOT / "scripts" / "sync_supported_data.py")


def _frozen(day: dt.date) -> tuple[type[dt.date], type[dt.datetime]]:
    class FrozenDate(dt.date):
        @classmethod
        def today(cls) -> dt.date:  # type: ignore[override]
            return day

    class FrozenDateTime(dt.datetime):
        @classmethod
        def now(cls, tz: dt.tzinfo | None = None) -> dt.datetime:  # type: ignore[override]
            return dt.datetime.combine(day, dt.time(), tzinfo=tz)

    return FrozenDate, FrozenDateTime


@pytest.mark.parametrize("day", [dt.date(2026, 12, 9), dt.date(2030, 1, 1)])
def test_the_page_does_not_change_with_the_date(monkeypatch, day: dt.date) -> None:
    frozen_date, frozen_datetime = _frozen(day)
    monkeypatch.setattr(gen, "date", frozen_date, raising=False)
    monkeypatch.setattr(gen, "datetime", frozen_datetime)
    rendered = gen._without_timestamp(gen.render_md(gen.build_status()))
    committed = gen._without_timestamp(gen.STATUS_MD.read_text(encoding="utf-8"))
    assert rendered == committed


def test_every_supported_data_row_is_counted() -> None:
    lines = gen.SUPPORTED.read_text(encoding="utf-8").splitlines()
    # Any table row led by a level — the planned section uses a shorter table.
    level_rows = [
        line
        for line in lines
        if line.startswith("| ") and line.split("|")[1].strip() in SUPPORTED_DATA_LEVELS
    ]
    dataset_rows = [line for line in lines if sync.DATASET_ROW.match(line.strip())]
    assert dataset_rows
    # A dataset row with a level the page does not know would silently drop out.
    assert set(dataset_rows) <= set(level_rows)
    assert sum(gen._supported_summary().values()) == len(level_rows)


def test_family_pass_rate_is_computed_from_metadata() -> None:
    """Each family's counts and rates come from dataset_metadata.json (#899)."""
    import json

    metadata = json.loads(
        (REPO_ROOT / "src" / "kpubdata" / "dataset_metadata.json").read_text(encoding="utf-8")
    )
    families = gen.build_status()["family_pass_rate"]
    assert sum(f["total"] for f in families.values()) == len(metadata)
    for name, f in families.items():
        ids = [k for k in metadata if k.split(".", 1)[0] == name]
        live = [k for k in ids if metadata[k]["level"] in ("live_verified", "production")]
        assert f["total"] == len(ids)
        assert f["live_passing"] == len(live)
        assert f["pass_rate"] == round(len(live) / len(ids) * 100, 1)
        assert 0 <= f["pass_rate"] <= f["fixture_pass_rate"] <= 100


def test_family_pass_rate_reaches_the_rendered_page() -> None:
    """The page carries a row per family, so ``--check`` gates the numbers."""
    status = gen.build_status()
    text = gen.render_md(status)
    assert "## 계열별 통과율" in text
    for name in status["family_pass_rate"]:
        assert f"| {name} |" in text
