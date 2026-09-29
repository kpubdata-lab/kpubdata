"""The status state machine does what docs/DATASET_STATUS.md says (#625).

The design shipped as a table with no code behind it (#607). The table-driven test
below reads that table and runs every row against ``transition()``, so editing one
without the other fails here.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from kpubdata.core.status import (
    TRANSIENT_FAILURE_STREAK,
    UNSTABLE_TO_BROKEN_FAILURES,
    DatasetStatus,
    DriftClassification,
    transition,
)

DOC = Path(__file__).resolve().parents[3] / "docs" / "DATASET_STATUS.md"
BACKTICKED = re.compile(r"`([A-Za-z_]+)`")
FAILURES = [c for c in DriftClassification if c is not DriftClassification.HEALTHY]
PREVIOUS = DatasetStatus.PRODUCTION


def _rows() -> list[tuple[str, str, str, str]]:
    text = DOC.read_text(encoding="utf-8")
    section = text[text.index("## Transition Rules") : text.index("## Core Principles")]
    rows = []
    for line in section.splitlines()[4:]:
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            rows.append((cells[0], cells[1], cells[2], cells[3]))
    return rows


def _streaks(cell: str) -> list[int]:
    if cell in {"—", ""}:
        return [1, TRANSIENT_FAILURE_STREAK]
    if match := re.fullmatch(r"(\d)–(\d)", cell):
        return list(range(int(match[1]), int(match[2]) + 1))
    if match := re.fullmatch(r"≥(\d)", cell):
        return [int(match[1])]
    raise AssertionError(f"unreadable streak {cell!r}")


def _cases() -> list[tuple[str, str, int, int, str]]:
    """(current, classification, streak, cumulative_failures, expected) per table row."""
    rows = _rows()
    by_current: dict[str, list[tuple[str, str, str, str]]] = {}
    for row in rows:
        by_current.setdefault(row[0], []).append(row)
    cases = []
    for current_cell, signal_cell, streak_cell, next_cell in rows:
        current = BACKTICKED.findall(current_cell)[0]
        if "same as production" in signal_cell:
            # Replay production's rows with this status as the current one.
            for _, sig, stk, nxt in by_current["`production`"]:
                for case in _expand(current, sig, stk, nxt):
                    cases.append(case)
            continue
        cases.extend(_expand(current, signal_cell, streak_cell, next_cell))
    return cases


def _expand(current: str, signal_cell: str, streak_cell: str, next_cell: str):
    signals = (
        [s.value for s in FAILURES]
        if signal_cell.startswith("any failure") or signal_cell == "all inputs"
        else BACKTICKED.findall(signal_cell)
    )
    if signal_cell == "all inputs":
        signals = [s.value for s in DriftClassification]
    cumulative = "cumulative" in signal_cell
    for signal in signals:
        for streak in _streaks(streak_cell):
            if next_cell.startswith("restore"):
                expected = PREVIOUS.value
            elif named := BACKTICKED.findall(next_cell):
                expected = named[0]
            else:
                expected = current  # "no change" / "no transitions"
            yield (
                current,
                signal,
                1 if cumulative else streak,
                streak if cumulative else 0,
                expected,
            )


CASES = _cases()


def test_the_table_is_read() -> None:
    assert len(CASES) > 30


@pytest.mark.parametrize(("current", "signal", "streak", "cumulative", "expected"), CASES)
def test_every_table_row(
    current: str, signal: str, streak: int, cumulative: int, expected: str
) -> None:
    got = transition(current, signal, streak, cumulative, previous_status=PREVIOUS)
    assert got == DatasetStatus(expected)


def test_transient_streak_boundary() -> None:
    below = transition("live_verified", "SERVICE_DOWN", TRANSIENT_FAILURE_STREAK - 1)
    assert below is DatasetStatus.LIVE_VERIFIED
    at = transition("live_verified", "SERVICE_DOWN", TRANSIENT_FAILURE_STREAK)
    assert at is DatasetStatus.UNSTABLE


def test_unstable_breaks_on_the_seventh_failure_not_the_sixth() -> None:
    six = transition("unstable", "RATE_LIMIT", 1, UNSTABLE_TO_BROKEN_FAILURES - 1)
    assert six is DatasetStatus.UNSTABLE
    assert (
        transition("unstable", "RATE_LIMIT", 1, UNSTABLE_TO_BROKEN_FAILURES) is DatasetStatus.BROKEN
    )


def test_restore_without_previous_falls_back_to_live_verified() -> None:
    assert transition("unstable", "HEALTHY", 3) is DatasetStatus.LIVE_VERIFIED
    # A fault is never restored into, or the machine would loop.
    assert (
        transition("unstable", "HEALTHY", 3, previous_status="broken")
        is DatasetStatus.LIVE_VERIFIED
    )


def test_unstable_needs_three_healthy_runs_to_recover() -> None:
    assert (
        transition("unstable", "HEALTHY", 2, previous_status="production") is DatasetStatus.UNSTABLE
    )


def test_broken_never_restores_production_directly() -> None:
    assert (
        transition("broken", "HEALTHY", 10, previous_status="production")
        is DatasetStatus.FIXTURE_VERIFIED
    )


@pytest.mark.parametrize("status", ["planned", "in_progress", "fixture_verified", "retired"])
@pytest.mark.parametrize("signal", [c.value for c in DriftClassification])
def test_unwatched_statuses_do_not_move(status: str, signal: str) -> None:
    assert transition(status, signal, 5, 10) is DatasetStatus(status)


def test_unknown_names_and_bad_streaks_are_refused() -> None:
    with pytest.raises(ValueError):
        transition("live-verified", "HEALTHY", 1)
    with pytest.raises(ValueError):
        transition("live_verified", "PARAM_CHANGED", 1)
    with pytest.raises(ValueError, match="at least 1"):
        transition("live_verified", "HEALTHY", 0)
