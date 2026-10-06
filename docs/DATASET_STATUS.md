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

### 구현 (#625)

이 절의 결정은 `scripts/drift_detect.py` 가 구현하고, `live-probe` 워크플로의 **drift** 잡이
매일 밤 실행한다. 드리프트 상태(스트릭·`previous_status`·누적 실패)는 `drift-state.json`
아티팩트로 밤사이 이어지고, 전이가 일어나면 위 규약대로 이슈를 연다 — 같은 데이터셋에
열려 있는 `[drift]` 이슈가 있으면 다시 열지 않는다. `status_history.json` 기록은
`--write-history` 에서 담당하며, nightly 에는 끈다: 게이트가 저장소에 쓸 수는 없으므로
이슈 본문에 추가할 항목을 싣고, 사람(또는 에이전트)이 적용한다. `RETIRED` 는 상태를
움직이지 않지만 이슈는 연다 — 폐기는 사람의 판단이다.

## 두 개의 축 (#842)

`DatasetStatus` 는 데이터셋 하나에 이름 하나를 준다. 그래서 `application_required` 는 그 뒤의
데이터셋이 fixture 로 검증됐는지 전혀 검증되지 않았는지를 가렸다. 요약(`status`)은 그대로 두고,
서로를 움직이지 않는 두 축을 따로 읽을 수 있게 했다.

| 축 | 타입 | 값 | 원천 |
|---|---|---|---|
| 검증 수준 | `VerificationLevel` | `planned` · `in_progress` · `fixture_verified` · `live_verified` · `production` | `dataset_metadata.json` 의 `verification` |
| 활용신청 필요 여부 | `ApplicationRequirement` | `required` · `not_required` · `unknown` | spec/catalogue 의 `application.required`, 없으면 metadata 의 `level` |

- `DatasetRef.verification` 은 활용신청 대기 중에도 바뀌지 않는다. 폐기된 데이터셋과 표에 없는
  데이터셋은 `None` 이다.
- `DatasetRef.application_requirement` 는 **기록된 것만** 말한다. `application.required` 가 선언돼
  있으면 그 값, 없고 `level` 이 `application_required` 면 `required`, 그 밖은 `unknown` 이다.
  `unknown` 은 "신청 불필요" 가 아니다 — 대부분의 데이터셋은 이 질문이 적힌 적이 없다.
- 두 축 모두 라이선스·출처·재배포 조건을 말하지 않는다. 그것은 spec 의 `license` 이고(#609, #785),
  선언이 없으면 `None`(알 수 없음)으로 남는다. "실API 검증" 은 "재배포 가능" 이 아니다.
- 값은 SDK 의 어휘다. Builder 의 wire 어휘와 맞추지 않으며, Builder 가 필요하면 자기 쪽에서 매핑한다.

`src/kpubdata/dataset_metadata.json` 이 원천이다. `scripts/sync_supported_data.py` 가 fixture 의
`meta.json` 으로 그 파일을 다시 계산하고 `SUPPORTED_DATA.md` 의 상태·검증·검증일 열을 거기서 쓴다.
`scripts/gen_dataset_status.py` 가 같은 파일에서 `dataset_status.json`(`DatasetRef.status`)을 쓴다.
세 파일이 어긋나면 테스트가 실패한다.

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
