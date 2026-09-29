# Dataset Status State Machine (#464)

Mapping from Drift Classification (#382) to Dataset Status (#439).

Status names are the canonical set from
[ADR 0005](adrs/0005-dataset-status-vocabulary.md) and
`kpubdata.core.status.DatasetStatus`; classifications are
`kpubdata.core.status.DriftClassification`. `tests/unit/test_status_vocabulary.py`
fails when this page uses a name the code does not define.

## State Diagram

```
                    ┌─────────────────────────────────┐
                    │         retired (terminal)       │
                    │   (manual transitions only)      │
                    └─────────────────────────────────┘

    ┌──────────────────────────────────────────────────────────┐
    │                     production                           │
    │              (manual promotion only)                    │
    └─────────┬────────────────┬───────────────┬──────────────┘
              │                │               │
    SCHEMA_CHANGED    RATE_LIMIT /     AUTH /
    PARAMETER_CHANGED SERVICE_DOWN /   APPLICATION_
    ENDPOINT_CHANGED  UNKNOWN (≥3)     REQUIRED (≥1)
    (≥1, immediate)   │               │
              │       │               │
              ▼       ▼               ▼
    ┌─────────────┐ ┌─────────┐ ┌──────────────────┐
    │   broken    │ │unstable │ │application_required│
    └──────┬──────┘ └────┬────┘ └──────────────────┘
           │             │
    HEALTHY (≥1)   HEALTHY (≥3)
    + fixture      │
    re-record      │ (restore previous)
           │       │
           ▼       ▼
    ┌─────────────┐ ┌─────────────────┐
    │   fixture_  │ │ previous status │
    │   verified  │ │ (or live_verif.)│
    └─────────────┘ └─────────────────┘
```

## Transition Rules

| Current Status | Drift Classification | Streak | Next Status |
|---|---|---|---|
| `production` | `RATE_LIMIT`, `SERVICE_DOWN`, `UNKNOWN` | 1–2 | _(no change, record only)_ |
| `production` | `RATE_LIMIT`, `SERVICE_DOWN`, `UNKNOWN` | ≥3 | `unstable` |
| `production` | `SCHEMA_CHANGED`, `PARAMETER_CHANGED`, `ENDPOINT_CHANGED` | ≥1 | `broken` _(immediate)_ |
| `production` | `AUTH`, `APPLICATION_REQUIRED` | ≥1 | `application_required` |
| `production` | `NO_DATA` | ≥3 | `unstable` |
| `production` | `RETIRED` | ≥1 | _(no change; drift issue filed — a person retires it)_ |
| `live_verified` | _(same as production)_ | — | _(same as production)_ |
| `fixture_verified` | any failure | ≥1 | `fixture_verified` _(no auto downgrade)_ |
| `unstable` | `HEALTHY` | ≥3 | restore `previous_status` |
| `unstable` | `SCHEMA_CHANGED`, `PARAMETER_CHANGED`, `ENDPOINT_CHANGED` | ≥1 | `broken` _(immediate)_ |
| `unstable` | any failure (cumulative) | ≥7 | `broken` |
| `broken` | `HEALTHY` | ≥1 | `fixture_verified` _(requires fixture re-record)_ |
| `application_required` | `HEALTHY` | ≥1 | restore `previous_status` _(application approved)_ |
| `retired` | all inputs | — | _(no transitions; manual only)_ |

## Core Principles

1. **Schema/Parameter/Endpoint changes break immediately** — user code breaks, no delay
2. **Transient failures (429, 5xx) use a 3-strike rule** — prevents false positives.
   The number is `TRANSIENT_FAILURE_STREAK`; LIVE_PROBE.md files its drift issue on the same count
3. **`broken` never auto-restores to `production`** — a human must re-record fixtures and pass contract tests
4. **`retired` is terminal** — only manual transitions

## Decisions

### previous_status storage
**Yes** — stored in `fixtures/<dataset>/status_history.json` alongside the existing meta.
Simple, co-located with the data it describes, and inspectable without GitHub API calls.

### Transition history location
`fixtures/<dataset>/status_history.json`:
```json
[
  {"from": "live_verified", "to": "unstable", "reason": "SERVICE_DOWN", "streak": 3, "at": "2026-09-29"},
  {"from": "unstable", "to": "live_verified", "reason": "HEALTHY", "streak": 3, "at": "2026-09-30"}
]
```

### Drift Issue Title convention
```
[drift] <dataset_id>: <from_status> → <to_status> (<classification>)
```
Example: `[drift] datago.apt_trade: live_verified → broken (SCHEMA_CHANGED)`

Labels: `type:bug`, `epic:trust`, plus `severity:major` for `broken`, `severity:minor` for `unstable`.

## Pure Function

```python
def transition(
    current: DatasetStatus | str,
    classification: DriftClassification | str,
    streak: int,
    cumulative_failures: int = 0,
    previous_status: DatasetStatus | str | None = None,
) -> DatasetStatus:
    """Compute the next dataset status from drift signal."""
```

Implemented as `kpubdata.core.status.transition()` (#625), with the vocabulary
(`DatasetStatus`, `DriftClassification`, `TRANSIENT_FAILURE_STREAK`). `restore
previous_status` falls back to `live_verified` when there is none, or when it names a
fault. `tests/unit/core/test_status_transition.py` runs every row of the table above
against the function, so the table and the code cannot drift apart.
