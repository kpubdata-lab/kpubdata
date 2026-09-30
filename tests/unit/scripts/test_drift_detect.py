"""The drift step is the status machine plus two files (#625, docs/DATASET_STATUS.md).

``kpubdata probe`` records one night's verdict; nothing compared consecutive
nights, so a schema change or a dead service stayed invisible until a user's
query broke. These tests pin the decisions the drift step makes: a schema
change breaks immediately, transient failures move nothing before the third
night, restores file nothing, and retirement moves nothing but files.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "drift_detect.py"


def _load_script():
    """Load the script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("drift_detect", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["drift_detect"] = module
    spec.loader.exec_module(module)
    return module


dd = _load_script()

State = dict[str, "dd.DatasetState"]


def _row(
    dataset_id: str = "datago.x",
    classification: str | None = "HEALTHY",
    schema_hash: str | None = None,
) -> dict[str, object]:
    row: dict[str, object] = {"dataset_id": dataset_id}
    if classification is not None:
        row["classification"] = classification
    if schema_hash is not None:
        row["schema_hash"] = schema_hash
    return row


def _nights(rows: list[dict[str, object]]) -> tuple[list[object], State]:
    """Run one row per night, feeding the state forward."""
    state: State = {}
    events: list[object] = []
    for night, row in enumerate(rows, start=1):
        night_events, state = dd.detect_drift([row], [], state, today=f"2026-10-{night:02d}")
        events.extend(night_events)
    return events, state


def test_a_healthy_first_run_files_nothing() -> None:
    events, state = _nights([_row()])

    assert events == []
    assert state["datago.x"].status is dd.DatasetStatus.LIVE_VERIFIED


def test_a_schema_change_breaks_immediately() -> None:
    previous = [_row(schema_hash="bbb")]
    events, _state = dd.detect_drift([_row(schema_hash="aaa")], previous, {}, today="2026-10-01")

    event = events[0]
    assert event.to_status is dd.DatasetStatus.BROKEN
    assert event.classification is dd.DriftClassification.SCHEMA_CHANGED
    assert dd.issue_worthy(event)
    assert dd.issue_for(event).labels == ("type:bug", "epic:trust", "severity:major")


def test_the_same_hash_is_not_a_change() -> None:
    previous = [_row(schema_hash="aaa")]
    events, _state = dd.detect_drift([_row(schema_hash="aaa")], previous, {}, today="2026-10-01")

    assert events == []


def test_transient_failures_need_three_nights() -> None:
    events, state = _nights([_row(classification="SERVICE_DOWN")] * 3)

    assert len(events) == 1
    assert events[0].to_status is dd.DatasetStatus.UNSTABLE
    assert events[0].streak == 3
    assert dd.issue_for(events[0]).labels == ("type:bug", "epic:trust", "severity:minor")
    assert state["datago.x"].previous_status is dd.DatasetStatus.LIVE_VERIFIED


def test_two_bad_nights_move_nothing() -> None:
    events, state = _nights([_row(classification="SERVICE_DOWN")] * 2)

    assert events == []
    assert state["datago.x"].status is dd.DatasetStatus.LIVE_VERIFIED


def test_auth_once_needs_an_application() -> None:
    events, state = _nights([_row(classification="AUTH")])

    assert events[0].to_status is dd.DatasetStatus.APPLICATION_REQUIRED
    assert dd.issue_worthy(events[0])
    assert state["datago.x"].previous_status is dd.DatasetStatus.LIVE_VERIFIED


def test_recovery_restores_previous_status_without_an_issue() -> None:
    events, state = _nights([_row(classification="AUTH"), _row()])

    assert len(events) == 2
    restore = events[1]
    assert restore.from_status is dd.DatasetStatus.APPLICATION_REQUIRED
    assert restore.to_status is dd.DatasetStatus.LIVE_VERIFIED
    assert not dd.issue_worthy(restore)
    assert dd.history_entry(restore) is not None
    assert state["datago.x"].previous_status is None


def test_unstable_recovers_on_the_third_healthy_night() -> None:
    events, _state = _nights([_row(classification="SERVICE_DOWN")] * 3 + [_row()] * 3)

    assert [event.to_status for event in events] == [
        dd.DatasetStatus.UNSTABLE,
        dd.DatasetStatus.LIVE_VERIFIED,
    ]
    assert events[1].streak == 3


def test_retired_files_an_issue_and_moves_nothing() -> None:
    events, state = _nights([_row(classification="RETIRED")])

    event = events[0]
    assert event.from_status is dd.DatasetStatus.LIVE_VERIFIED
    assert event.to_status is dd.DatasetStatus.LIVE_VERIFIED
    assert dd.issue_worthy(event)
    assert dd.issue_for(event).labels == ("type:bug", "epic:trust", "severity:major")
    assert dd.history_entry(event) is None
    assert state["datago.x"].status is dd.DatasetStatus.LIVE_VERIFIED


def test_no_signal_carries_the_state() -> None:
    _events, state = _nights([_row(classification="SERVICE_DOWN")] * 2)
    events, state = _nights_with_state([_row(classification=None)], state)

    assert events == []
    assert state["datago.x"].streak == 2
    assert state["datago.x"].status is dd.DatasetStatus.LIVE_VERIFIED


def _nights_with_state(rows: list[dict[str, object]], state: State) -> tuple[list[object], State]:
    """Run rows against an existing state without resetting it."""
    events: list[object] = []
    for night, row in enumerate(rows, start=1):
        night_events, state = dd.detect_drift([row], [], state, today=f"2026-10-{night:02d}")
        events.extend(night_events)
    return events, state


def test_a_bogus_classification_is_no_signal() -> None:
    events, state = dd.detect_drift(
        [_row(classification="NOT-A-SIGNAL")], [], {}, today="2026-10-01"
    )

    assert events == []
    assert state["datago.x"].status is dd.DatasetStatus.LIVE_VERIFIED


def test_state_survives_a_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "drift-state.json"
    state: State = {
        "datago.x": dd.DatasetState(
            status=dd.DatasetStatus.UNSTABLE,
            previous_status=dd.DatasetStatus.LIVE_VERIFIED,
            streak=2,
            streak_classification=dd.DriftClassification.SERVICE_DOWN,
            cumulative_failures=5,
        )
    }

    dd.save_state(state, path)
    loaded = dd.load_state(path)

    assert loaded["datago.x"] == state["datago.x"]


def test_state_reading_tolerates_a_bogus_file(tmp_path: Path) -> None:
    path = tmp_path / "drift-state.json"
    path.write_text(
        json.dumps({"datasets": {"datago.x": {"status": "NOT-A-STATUS"}}}), encoding="utf-8"
    )

    assert dd.load_state(path) == {}
    assert dd.load_state(tmp_path / "absent.json") == {}


def test_history_is_appended_under_the_fixture_layout(tmp_path: Path) -> None:
    _events, _state = dd.detect_drift([_row()], [], {}, today="2026-10-01")
    events, _state2 = dd.detect_drift(
        [_row(schema_hash="aaa")], [_row(schema_hash="bbb")], {}, today="2026-10-01"
    )

    written = dd.write_history(list(events), tmp_path, today="2026-10-01")

    path = tmp_path / "datago" / "x" / "status_history.json"
    assert written == [path]
    rows = json.loads(path.read_text(encoding="utf-8"))
    assert rows == [
        {
            "from": "live_verified",
            "to": "broken",
            "reason": "SCHEMA_CHANGED",
            "streak": 1,
            "at": "2026-10-01",
        }
    ]


def test_history_appends_to_an_existing_file(tmp_path: Path) -> None:
    path = tmp_path / "datago" / "x" / "status_history.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([{"from": "a", "to": "b"}]), encoding="utf-8")
    events, _state = dd.detect_drift(
        [_row(schema_hash="aaa")], [_row(schema_hash="bbb")], {}, today="2026-10-02"
    )

    dd.write_history(list(events), tmp_path, today="2026-10-02")

    rows = json.loads(path.read_text(encoding="utf-8"))
    assert len(rows) == 2
    assert rows[0] == {"from": "a", "to": "b"}


def test_datasets_missing_from_the_report_leave_the_state() -> None:
    state: State = {"datago.gone": dd.DatasetState(status=dd.DatasetStatus.UNSTABLE)}

    _events, next_state = dd.detect_drift([_row()], [], state, today="2026-10-01")

    assert "datago.gone" not in next_state
    assert "datago.x" in next_state


def test_issue_title_and_body_match_the_documented_convention() -> None:
    events, _state = dd.detect_drift(
        [_row(schema_hash="aaa")],
        [_row(schema_hash="bbb")],
        {},
        today="2026-10-01",
    )

    issue = dd.issue_for(events[0])

    assert issue.title == "[drift] datago.x: live_verified → broken (SCHEMA_CHANGED)"
    assert "status_history" in issue.body
    assert "SCHEMA_CHANGED" in issue.body


def test_main_writes_state_and_prints_the_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    current = tmp_path / "current.json"
    previous = tmp_path / "previous.json"
    state = tmp_path / "drift-state.json"
    current.write_text(json.dumps({"results": [_row(schema_hash="aaa")]}), encoding="utf-8")
    previous.write_text(json.dumps({"results": [_row(schema_hash="bbb")]}), encoding="utf-8")

    code = dd.main(
        [
            "--current",
            str(current),
            "--previous",
            str(previous),
            "--state",
            str(state),
            "--today",
            "2026-10-01",
        ]
    )

    assert code == 0
    out = capsys.readouterr().out
    assert "[drift] datago.x: live_verified → broken (SCHEMA_CHANGED)" in out
    assert "transitions=1 issues=1" in out
    saved = json.loads(state.read_text(encoding="utf-8"))
    assert saved["datasets"]["datago.x"]["status"] == "broken"
