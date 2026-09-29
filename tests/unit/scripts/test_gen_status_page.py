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
