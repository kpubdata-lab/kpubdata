# Dataset Status State Machine (#464)

Mapping from Drift Classification (#382) to Dataset Status (#439).

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
    PARAM_CHANGED     SERVICE_DOWN /   APPLICATION_
    ENDPOINT_CHANGED  UNKNOWN (≥3)     REQUIRED (≥1)
    (≥1, immediate)   │               │
              │       │               │
              ▼       ▼               ▼
    ┌─────────────┐ ┌─────────┐ ┌──────────────────┐
    │   broken    │ │unstable │ │application-required│
    └──────┬──────┘ └────┬────┘ └──────────────────┘
           │             │
    HEALTHY (≥1)   HEALTHY (≥3)
    + fixture      │
    re-record      │ (restore previous)
           │       │
           ▼       ▼
    ┌─────────────┐ ┌─────────────────┐
    │   fixture-  │ │ previous status │
    │   verified  │ │ (or live-verif.)│
    └─────────────┘ └─────────────────┘
```

## Transition Rules

| Current Status | Drift Classification | Streak | Next Status |
|---|---|---|---|
| `production` | `RATE_LIMIT`, `SERVICE_DOWN`, `UNKNOWN` | 1–2 | _(no change, record only)_ |
| `production` | `RATE_LIMIT`, `SERVICE_DOWN`, `UNKNOWN` | ≥3 | `unstable` |
| `production` | `SCHEMA_CHANGED`, `PARAMETER_CHANGED`, `ENDPOINT_CHANGED` | ≥1 | `broken` _(immediate)_ |
| `production` | `AUTH`, `APPLICATION_REQUIRED` | ≥1 | `application-required` |
| `production` | `NO_DATA` | ≥3 | `unstable` |
| `live-verified` | _(same as production)_ | — | _(same as production)_ |
| `fixture-verified` | any failure | ≥1 | `fixture-verified` _(no auto downgrade)_ |
| `unstable` | `HEALTHY` | ≥3 | restore `previous_status` |
| `unstable` | any failure (cumulative) | ≥7 | `broken` |
| `broken` | `HEALTHY` | ≥1 | `fixture-verified` _(requires fixture re-record)_ |
| `retired` | all inputs | — | _(no transitions; manual only)_ |

## Core Principles

1. **Schema/Parameter/Endpoint changes break immediately** — user code breaks, no delay
2. **Transient failures (429, 5xx) use a 3-strike rule** — prevents false positives
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
  {"from": "live-verified", "to": "unstable", "reason": "SERVICE_DOWN", "streak": 3, "at": "2026-09-29"},
  {"from": "unstable", "to": "live-verified", "reason": "HEALTHY", "streak": 3, "at": "2026-09-30"}
]
```

### Drift Issue Title convention
```
[drift] <dataset_id>: <from_status> → <to_status> (<classification>)
```
Example: `[drift] datago.apt_trade: live-verified → broken (SCHEMA_CHANGED)`

Labels: `type:bug`, `epic:trust`, plus `severity:major` for `broken`, `severity:minor` for `unstable`.

## Pure Function

```python
def transition(
    current: str,
    classification: str,
    streak: int,
    cumulative_failures: int = 0,
    previous_status: str | None = None,
) -> str:
    """Compute the next dataset status from drift signal."""
```

See `src/kpubdata/core/status.py` for implementation.
