#!/usr/bin/env python3
"""Detect drift between two nightly probe runs (#625, #382, docs/DATASET_STATUS.md).

``kpubdata probe`` says whether a dataset was reachable last night, but nothing
compared that verdict with the night before — a schema change or a dead service
stayed invisible until a user's query broke. This script is the drift step of the
live-probe design: it reads the current and the previous ``probe-result.json``,
applies the dataset status machine (``kpubdata.core.status.transition``) per
dataset, records transitions in ``status_history.json``, and files one GitHub
issue per transition that needs a person.

Two decisions live here, both from the design:

- A schema change is **not** a probe outcome. This step compares ``schema_hash``
  between the two runs and emits ``SCHEMA_CHANGED`` itself — which moves a
  watched dataset to ``broken`` immediately (user code breaks, no delay).
- Transient failures (rate limit, outage, network) need
  ``TRANSIENT_FAILURE_STREAK`` consecutive nights before they move anything, so
  one bad night moves nothing. ``RETIRED`` moves nothing either — a person
  retires the dataset — but it still files an issue.

Restores (HEALTHY after ``unstable``/``application_required``) restore
``previous_status`` and file nothing: good news is not a bug.

The exit status is always 0. An upstream API failure is a drift event, not a CI
failure — a red nightly would train people to ignore it.

    $ python3 scripts/drift_detect.py \
          --current docs/status/probe-result.json \
          --previous previous/probe-result.json \
          --state docs/status/drift-state.json
    transitions=1 issues=1
    [drift] datago.apt_trade: live_verified → broken (SCHEMA_CHANGED)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from kpubdata.core.status import (
    DatasetStatus,
    DriftClassification,
    transition,
)

KST = timezone(timedelta(hours=9), name="KST")

#: Statuses a drift signal moves a dataset into; entering one remembers the
#: status it came from, leaving one forgets it again.
_FAULTS = frozenset(
    {DatasetStatus.UNSTABLE, DatasetStatus.BROKEN, DatasetStatus.APPLICATION_REQUIRED}
)


@dataclass
class DatasetState:
    """What the drift step remembers between two runs, for one dataset."""

    status: DatasetStatus = DatasetStatus.LIVE_VERIFIED
    previous_status: DatasetStatus | None = None
    streak: int = 0
    streak_classification: DriftClassification | None = None
    cumulative_failures: int = 0


@dataclass(frozen=True)
class DriftEvent:
    """One transition the drift step observed, with the evidence behind it.

    ``from_status == to_status`` only for ``RETIRED``: the status moves nothing
    (a person retires the dataset), but the issue is still filed.
    """

    dataset_id: str
    from_status: DatasetStatus
    to_status: DatasetStatus
    classification: DriftClassification
    streak: int
    at: str
    evidence: str


@dataclass(frozen=True)
class DriftIssue:
    """The GitHub issue one DriftEvent files (docs/DATASET_STATUS.md)."""

    dataset_id: str
    title: str
    body: str
    labels: tuple[str, ...]


def _row_str(row: dict[str, object], key: str) -> str | None:
    value = row.get(key)
    return value if isinstance(value, str) and value else None


def _rows_by_dataset(payload: object) -> list[dict[str, object]]:
    """The ``results`` rows of a probe report, tolerating anything else."""
    if not isinstance(payload, dict):
        return []
    rows = payload.get("results")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _evidence(row: dict[str, object]) -> str:
    """One human line of what the probe saw, for the issue body."""
    parts: list[str] = []
    http_status = row.get("http_status")
    if isinstance(http_status, int) and not isinstance(http_status, bool):
        parts.append(f"http={http_status}")
    if (code := _row_str(row, "result_code")) is not None:
        parts.append(f"code={code}")
    latency = row.get("latency_ms")
    if isinstance(latency, int) and not isinstance(latency, bool):
        parts.append(f"latency_ms={latency}")
    if (schema_hash := _row_str(row, "schema_hash")) is not None:
        parts.append(f"schema_hash={schema_hash}")
    if (probed_at := _row_str(row, "probed_at")) is not None:
        parts.append(f"probed_at={probed_at}")
    return " ".join(parts)


def _classification(
    row: dict[str, object], previous_row: dict[str, object] | None
) -> DriftClassification | None:
    """The signal this row feeds the state machine, or None when there is none.

    A schema change is not a probe outcome (#606): when both runs fingerprinted
    the returned field names and the fingerprints differ, this step emits
    ``SCHEMA_CHANGED`` itself — including on an otherwise healthy row, because
    user code breaks on the new shape however reachable the endpoint is.
    """
    if previous_row is not None:
        current_hash = _row_str(row, "schema_hash")
        previous_hash = _row_str(previous_row, "schema_hash")
        if current_hash is not None and previous_hash is not None and current_hash != previous_hash:
            return DriftClassification.SCHEMA_CHANGED
    name = row.get("classification")
    if not isinstance(name, str) or not name:
        return None
    try:
        return DriftClassification(name)
    except ValueError:
        return None


def detect_drift(
    current_rows: list[dict[str, object]],
    previous_rows: list[dict[str, object]],
    state: dict[str, DatasetState],
    *,
    today: str,
) -> tuple[list[DriftEvent], dict[str, DatasetState]]:
    """Run the state machine over one report; returns (events, next state).

    Datasets absent from ``current_rows`` leave the state — the next report is
    the whole picture, and keeping rows for removed specs would go on naming a
    dataset that no longer exists.
    """
    previous_by_id = {
        str(row.get("dataset_id")): row
        for row in previous_rows
        if isinstance(row.get("dataset_id"), str)
    }
    events: list[DriftEvent] = []
    next_state: dict[str, DatasetState] = {}

    for row in current_rows:
        dataset_id = row.get("dataset_id")
        if not isinstance(dataset_id, str) or not dataset_id:
            continue
        dataset_state = state.get(dataset_id, DatasetState())
        classification = _classification(row, previous_by_id.get(dataset_id))

        if classification is None:
            # No signal (probe config issue, unparseable body, a row from before
            # the evidence fields): carry the state forward unchanged.
            next_state[dataset_id] = dataset_state
            continue

        if dataset_state.streak_classification is classification and dataset_state.streak > 0:
            dataset_state.streak += 1
        else:
            dataset_state.streak = 1
        dataset_state.streak_classification = classification
        if classification is DriftClassification.HEALTHY:
            dataset_state.cumulative_failures = 0
        else:
            dataset_state.cumulative_failures += 1

        next_status = transition(
            dataset_state.status,
            classification,
            dataset_state.streak,
            cumulative_failures=dataset_state.cumulative_failures,
            previous_status=dataset_state.previous_status,
        )

        if classification is DriftClassification.RETIRED:
            # The table files the issue and moves nothing — a person retires it.
            events.append(
                DriftEvent(
                    dataset_id=dataset_id,
                    from_status=dataset_state.status,
                    to_status=dataset_state.status,
                    classification=classification,
                    streak=dataset_state.streak,
                    at=today,
                    evidence=_evidence(row),
                )
            )
        elif next_status is not dataset_state.status:
            events.append(
                DriftEvent(
                    dataset_id=dataset_id,
                    from_status=dataset_state.status,
                    to_status=next_status,
                    classification=classification,
                    streak=dataset_state.streak,
                    at=today,
                    evidence=_evidence(row),
                )
            )
            if next_status in _FAULTS and dataset_state.status not in _FAULTS:
                dataset_state.previous_status = dataset_state.status
            elif next_status not in _FAULTS:
                dataset_state.previous_status = None
            dataset_state.status = next_status

        next_state[dataset_id] = dataset_state

    return events, next_state


def issue_worthy(event: DriftEvent) -> bool:
    """Whether an event files an issue: entering a fault, or a retirement.

    Restores file nothing — good news is not a bug — but they do land in
    status_history, which is the record of what the dataset went through.
    """
    return event.to_status in _FAULTS or event.classification is DriftClassification.RETIRED


def issue_for(event: DriftEvent) -> DriftIssue:
    """The issue one event files: title and labels are DATASET_STATUS.md's."""
    if event.to_status is DatasetStatus.BROKEN or (
        event.classification is DriftClassification.RETIRED
    ):
        severity = "severity:major"
    else:
        severity = "severity:minor"
    title = (
        f"[drift] {event.dataset_id}: "
        f"{event.from_status.value} → {event.to_status.value} "
        f"({event.classification.value})"
    )
    lines = [
        f"상태 전이: `{event.from_status.value}` → `{event.to_status.value}` "
        f"(`{event.classification.value}`, streak {event.streak}).",
        "",
        f"관측 증거: {event.evidence or '(없음)'}",
        "",
        "status_history 에 추가할 항목:",
        "",
        "```json",
        json.dumps(
            {
                "from": event.from_status.value,
                "to": event.to_status.value,
                "reason": event.classification.value,
                "streak": event.streak,
                "at": event.at,
            },
            ensure_ascii=False,
        ),
        "```",
        "",
        "규칙과 복구 절차: [docs/DATASET_STATUS.md](../blob/main/docs/DATASET_STATUS.md) "
        "— `broken` 은 사람이 fixture 를 다시 기록하기 전까지 돌아가지 않는다.",
    ]
    return DriftIssue(
        dataset_id=event.dataset_id,
        title=title,
        body="\n".join(lines),
        labels=("type:bug", "epic:trust", severity),
    )


def history_entry(event: DriftEvent) -> dict[str, object] | None:
    """The status_history.json row for an event; None when nothing moved."""
    if event.from_status is event.to_status:
        return None
    return {
        "from": event.from_status.value,
        "to": event.to_status.value,
        "reason": event.classification.value,
        "streak": event.streak,
        "at": event.at,
    }


def write_history(events: list[DriftEvent], fixtures_root: Path, *, today: str) -> list[Path]:
    """Append each transition to ``<fixtures_root>/<provider>/<key>/status_history.json``.

    The live-probe workflow cannot write to the repository, so it leaves this
    off and carries the entry in the issue body; a person (or an agent) applies
    it here. That keeps ``broken`` recovery human-reviewed by construction.
    """
    written: list[Path] = []
    for event in events:
        entry = history_entry(event)
        if entry is None:
            continue
        provider, _, key = event.dataset_id.partition(".")
        if not provider or not key:
            continue
        path = fixtures_root / provider / key / "status_history.json"
        rows: list[dict[str, object]] = []
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, list):
                rows = [row for row in loaded if isinstance(row, dict)]
        except OSError:
            rows = []
        rows.append(entry)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    return written


def load_state(path: Path) -> dict[str, DatasetState]:
    """Read drift-state.json, tolerating absence and anything unexpected."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(payload, dict):
        return {}
    datasets = payload.get("datasets")
    if not isinstance(datasets, dict):
        return {}
    state: dict[str, DatasetState] = {}
    for dataset_id, raw in datasets.items():
        if not isinstance(dataset_id, str) or not isinstance(raw, dict):
            continue
        try:
            status = DatasetStatus(str(raw.get("status", DatasetStatus.LIVE_VERIFIED.value)))
        except ValueError:
            continue
        previous = raw.get("previous_status")
        streak_classification = raw.get("streak_classification")
        state[dataset_id] = DatasetState(
            status=status,
            previous_status=(
                DatasetStatus(str(previous))
                if isinstance(previous, str) and previous and _is_status(previous)
                else None
            ),
            streak=raw.get("streak", 0) if isinstance(raw.get("streak", 0), int) else 0,
            streak_classification=(
                DriftClassification(str(streak_classification))
                if isinstance(streak_classification, str)
                and streak_classification
                and _is_classification(streak_classification)
                else None
            ),
            cumulative_failures=(
                raw.get("cumulative_failures", 0)
                if isinstance(raw.get("cumulative_failures", 0), int)
                else 0
            ),
        )
    return state


def _is_status(name: str) -> bool:
    try:
        DatasetStatus(name)
    except ValueError:
        return False
    return True


def _is_classification(name: str) -> bool:
    try:
        DriftClassification(name)
    except ValueError:
        return False
    return True


def save_state(state: dict[str, DatasetState], path: Path) -> None:
    """Write drift-state.json atomically; a torn file would read as no memory."""
    payload = {
        "updated_at": datetime.now(tz=KST).isoformat(timespec="seconds"),
        "datasets": {
            dataset_id: {
                "status": dataset_state.status.value,
                "previous_status": (
                    dataset_state.previous_status.value if dataset_state.previous_status else None
                ),
                "streak": dataset_state.streak,
                "streak_classification": (
                    dataset_state.streak_classification.value
                    if dataset_state.streak_classification
                    else None
                ),
                "cumulative_failures": dataset_state.cumulative_failures,
            }
            for dataset_id, dataset_state in sorted(state.items())
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(dir=path.parent, prefix=path.name)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def _open_drift_datasets(repo: str) -> set[str]:
    """Dataset ids that already have an open [drift] issue.

    Retired datasets stay retired: without this check the nightly would file
    the same issue every night until a person closes it.
    """
    completed = subprocess.run(
        [
            "gh",
            "issue",
            "list",
            "--repo",
            repo,
            "--state",
            "open",
            "--search",
            "in:title [drift]",
            "--json",
            "title",
            "--limit",
            "100",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    titles = json.loads(completed.stdout)
    datasets: set[str] = set()
    for row in titles if isinstance(titles, list) else []:
        title = row.get("title") if isinstance(row, dict) else None
        if not isinstance(title, str) or not title.startswith("[drift] "):
            continue
        rest = title[len("[drift] ") :]
        dataset_id, separator, _ = rest.partition(":")
        if separator:
            datasets.add(dataset_id)
    return datasets


def create_issues(issues: list[DriftIssue], *, repo: str) -> list[str]:
    """File the issues with gh, skipping datasets that already have an open one."""
    already_open = _open_drift_datasets(repo)
    created: list[str] = []
    for issue in issues:
        if issue.dataset_id in already_open:
            print(f"open drift issue exists, skipping: {issue.dataset_id}")
            continue
        completed = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--repo",
                repo,
                "--title",
                issue.title,
                "--body",
                issue.body,
                *[_part for label in issue.labels for _part in ("--label", label)],
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0:
            print(f"::warning::could not file: {issue.title}", file=sys.stderr)
            print(completed.stderr.strip(), file=sys.stderr)
            continue
        created.append(completed.stdout.strip())
    return created


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--current", required=True, help="this run's probe-result.json")
    parser.add_argument("--previous", default="", help="the previous run's probe-result.json")
    parser.add_argument("--state", required=True, help="drift-state.json to read and write")
    parser.add_argument(
        "--fixtures-root",
        default="",
        help="write status_history.json under this root (tests/fixtures)",
    )
    parser.add_argument(
        "--today", default="", help="YYYY-MM-DD in KST for history entries (default: now)"
    )
    parser.add_argument(
        "--create-issues", default="false", help="file GitHub issues (true or false)"
    )
    parser.add_argument("--repo", default="kpubdata-lab/kpubdata")
    args = parser.parse_args(argv)

    def _load(path: str) -> object:
        return json.loads(Path(path).read_text(encoding="utf-8")) if path else None

    try:
        current = _load(args.current)
        previous = _load(args.previous)
        today = args.today or datetime.now(tz=KST).date().isoformat()
        state = load_state(Path(args.state))
    except (OSError, ValueError) as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 2

    events, next_state = detect_drift(
        _rows_by_dataset(current), _rows_by_dataset(previous), state, today=today
    )
    save_state(next_state, Path(args.state))

    if args.fixtures_root:
        for path in write_history(events, Path(args.fixtures_root), today=today):
            print(f"history: {path}")

    issues = [issue_for(event) for event in events if issue_worthy(event)]
    for issue in issues:
        print(issue.title)

    if args.create_issues.strip().lower() in {"true", "1", "yes"}:
        create_issues(issues, repo=args.repo)

    print(f"transitions={len(events)} issues={len(issues)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
