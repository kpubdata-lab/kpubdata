# ADR 0005: 데이터셋 상태 어휘 — 정규 집합 하나, 나머지는 매핑

## 상태

채택됨(Accepted) — 2026-09-29

## 요약 (English summary)

> A dataset's state was named in six vocabularies with no mapping between them.
> This ADR fixes **one canonical set** (`DatasetStatus`), maps every other
> vocabulary onto it, and separates two things the old names mixed up: **what a
> dataset is** (a status) and **what one call observed** (a probe outcome or a
> drift signal — inputs that move a status, never a status themselves). The
> names live in `src/kpubdata/core/status.py`; a test fails when a design
> document uses a name the code does not define.

## 문제

2026-09-29 기준, "데이터셋 상태" 를 부르는 어휘가 여섯 곳에 따로 있었다 (#619).

| 위치 | 값 |
|---|---|
| `core/spec.py` `_STATUSES` | active, deprecated, broken, unstable |
| `_probe.py` `PROBE_STATUSES` | available, auth_unknown, application_required, params_invalid, rate_limited, temporarily_unavailable, network_error, insufficient_metadata, retired |
| `SUPPORTED_DATA.md` | 지원, 스키마만, 활용신청 대기, 진행 중, 예정 (+ 정의 없는 폐기) |
| `docs/DATASET_STATUS.md` | production, live-verified, fixture-verified, unstable, broken, application-required, retired |
| `docs/LIVE_PROBE.md` | healthy, degraded, unhealthy, retired, unknown |
| `docs/PRODUCTION_GRADE.md` | test-verified, production-grade |

서로의 매핑이 없어서 `스키마만`, `fixture-verified`, `test-verified` 가 같은 것인지
문서만 보고는 알 수 없었다. 설계 문서끼리도, 설계 문서와 코드도 어긋나 있었다.

- `DATASET_STATUS.md` 가 존재하지 않는 `core/status.py` 를 구현 위치로 지목했다.
- 같은 문서 안에서 다이어그램은 `PARAM_CHANGED`, 표는 `PARAMETER_CHANGED` 였다.
- 실패 임계가 `DATASET_STATUS.md` 는 3회, `LIVE_PROBE.md` 는 "2+" 였다.
- `LIVE_PROBE.md` 는 코드 32 를 `application_required` 로 분류했지만 `_probe.py` 는
  `auth_unknown` 으로 분류한다.
- `LIVE_PROBE.md` 예시의 `datago.air_forecast` 는 없는 키다 (`datago.airkorea_forecast`).
- `LIVE_PROBE.md` 는 neis·fds 가 datago 키를 공유한다고 썼지만 두 어댑터는 각자
  `neis`, `fds` 키를 fallback 없이 읽는다.

## 원인 — 상태와 관측을 한 이름으로 불렀다

여섯 어휘는 실은 **세 종류**다.

1. **데이터셋이 무엇인가** — SUPPORTED_DATA, DATASET_STATUS, PRODUCTION_GRADE.
2. **spec 이 무엇을 선언하나** — spec 의 `status:`. 수준이 아니라 관리자의 덮어쓰기다.
3. **한 번의 호출이 무엇을 봤나** — probe 결과, LIVE_PROBE 의 healthy/unhealthy.

3 은 상태를 **움직이는 입력**이지 상태가 아니다. rate limit 한 번은 데이터셋이
불안정하다는 뜻이 아니다. 그런데 `retired`, `application_required`, `broken` 같은
이름이 세 종류에 섞여 쓰이면서, 입력과 결과가 같은 표에 나란히 놓였다.

## 결정

### 1. 정규 상태 집합 — `DatasetStatus`

| 값 | 뜻 |
|---|---|
| `planned` | 후보. 이슈나 아이디어만 있다 |
| `in_progress` | 구현 중. 테스트가 아직 없다 |
| `fixture_verified` | fixture 기반 unit·contract 테스트 통과. 실API 검증 기록(`meta.json`)은 없다 |
| `live_verified` | 위 조건 + 실API 로 record 한 fixture 가 있다 |
| `production` | `docs/PRODUCTION_GRADE.md` 기준을 모두 충족 (사람이 승격) |
| `application_required` | 활용신청이 승인되지 않아 호출이 거부된다 |
| `unstable` | 일시 장애가 연속 `TRANSIENT_FAILURE_STREAK`(3)회 관측됐다 |
| `broken` | 스키마·파라미터·엔드포인트가 바뀌어 사용자 코드가 깨진다 |
| `retired` | 제공처에서 서비스가 사라졌다. 종착 상태, 사람만 옮긴다 |

이름은 코드 식별자와 같은 **snake_case** 다. 문서에서 `live-verified` 처럼 하이픈을
쓰던 곳은 모두 바꾼다 — 검색 한 번에 코드와 문서가 함께 나와야 한다.

### 2. 매핑

| 정규 상태 | SUPPORTED_DATA | PRODUCTION_GRADE | spec `status:` |
|---|---|---|---|
| `planned` | 예정 | | |
| `in_progress` | 진행 중 | | |
| `fixture_verified` | 스키마만 | test-verified | |
| `live_verified` | 지원 | | |
| `production` | | production-grade | |
| `application_required` | 활용신청 대기 | | |
| `unstable` | | | `unstable` |
| `broken` | | | `broken` |
| `retired` | 폐기 | | `deprecated` |

- spec 의 `active` 는 **덮어쓰기 없음**이다. 수준은 증거(fixture 의 `meta.json`)가
  정한다. spec 값의 이름은 바꾸지 않는다 — 스키마 계약(`specs/schema.json`)이고
  builder 가 읽는다. 대신 매핑을 코드(`SPEC_STATUS_OVERRIDE`)에 둔다.
- `dataset-prioritization.yaml` 의 `status`(spec / catalogue / planned)는 **구현
  형태**다. 상태가 아니므로 매핑하지 않는다. `planned` 만 이름이 겹치고 뜻도 같다.

### 3. 관측은 상태가 아니다 — `ProbeStatus` → `DriftClassification`

probe 결과는 `ProbeStatus` 그대로 기록하고, 상태 기계에는 `DriftClassification` 으로
바꿔 넣는다 (`PROBE_TO_DRIFT`).

| ProbeStatus | DriftClassification |
|---|---|
| `available` | `HEALTHY` |
| `application_required` | `APPLICATION_REQUIRED` |
| `auth_unknown` | `AUTH` |
| `rate_limited` | `RATE_LIMIT` |
| `temporarily_unavailable` | `SERVICE_DOWN` |
| `network_error` | `UNKNOWN` |
| `retired` | `RETIRED` |
| `params_invalid` | 없음 — probe 설정 문제 |
| `insufficient_metadata` | 없음 — 응답을 해석하지 못했다 |

LIVE_PROBE 의 healthy/degraded/unhealthy/unknown 은 **폐지**한다. probe 결과의
`status` 필드는 `ProbeStatus` 값을 그대로 쓴다. `degraded`(스키마 변경)는 probe 한
번으로 알 수 없고 drift 단계가 `schema_hash` 를 비교해 `SCHEMA_CHANGED` 로 낸다.

코드 32(`UNREGISTERED_IP`)는 코드가 맞다 — 키는 등록돼 있고 호출한 IP 가 아니다.
활용신청을 다시 해도 풀리지 않으므로 `application_required` 가 아니라 `auth_unknown`.

### 4. 임계값은 하나

일시 장애(`RATE_LIMIT`, `SERVICE_DOWN`, `UNKNOWN`)는 **연속 3회**에서 `unstable` 로
바뀌고 drift 이슈도 그때 연다. 상태가 바뀌지 않는 실패로 이슈를 열면 이슈와 상태가
어긋난다. 구조 변경과 `RETIRED` 는 1회에 즉시.

## 그래서 무엇을 만드는가

- `src/kpubdata/core/status.py` — `DatasetStatus`, `SpecStatus`, `ProbeStatus`,
  `DriftClassification`, 매핑 네 개, `TRANSIENT_FAILURE_STREAK`.
- `spec._STATUSES` 와 `_probe.PROBE_STATUSES` 는 이 enum 에서 만든다. 손으로 쓴
  목록이 두 벌이 되지 않게.
- `tests/unit/test_status_vocabulary.py` — 게이트. 다음이 어긋나면 실패한다.
  - enum ↔ `specs/schema.json` 의 status enum, `PROBE_STATUSES`
  - `SUPPORTED_DATA.md` 첫 열 ↔ `SUPPORTED_DATA_LEVELS`
  - `DATASET_STATUS.md` 전이표의 상태·분류 이름 ↔ enum
  - `LIVE_PROBE.md` 분류표의 코드 ↔ `_probe._CODE_STATUS`, 예시의 데이터셋 키 ↔ spec
  - 이 ADR 의 정규 상태 표 ↔ `DatasetStatus`
- 상태 전이 함수 `transition()` 은 이 ADR 범위가 아니다 (#625).

## 기각한 대안

- **spec `status:` 값을 정규 이름으로 바꾸기.** 스키마 계약이 바뀌고 builder 가
  같이 움직여야 한다. 얻는 것은 이름의 통일뿐인데, 매핑 한 줄로 같은 효과가 난다.
- **SUPPORTED_DATA 의 한국어 이름을 영어로 바꾸기.** 사용자 문서이고 한국어 도메인이다
  (ADR 0003). 매핑으로 충분하다.
- **probe 결과를 곧바로 상태로 쓰기.** rate limit 한 번이 `unstable` 이 되고, 사용자는
  기다리면 되는 것을 포기하게 된다 (#514 가 고친 것과 같은 실수).

## 관련

- #619 (이 ADR), #625 (전이 구현), #514 (probe 분류 확장)
- [`docs/DATASET_STATUS.md`](../DATASET_STATUS.md), [`docs/LIVE_PROBE.md`](../LIVE_PROBE.md),
  [`docs/PRODUCTION_GRADE.md`](../PRODUCTION_GRADE.md), [`SUPPORTED_DATA.md`](https://github.com/yeongseon/kpubdata/blob/main/SUPPORTED_DATA.md)
