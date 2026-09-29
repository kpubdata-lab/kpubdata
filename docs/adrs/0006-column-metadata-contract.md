# ADR 0006: 컬럼 메타 계약 — 저장 타입, 의미, 표시를 나눈다

## 상태

채택됨(Accepted) — 2026-09-29

## 요약 (English summary)

> A column's metadata carried three different things under overlapping names: the
> type a value is cast to, what the value *means*, and how it should be shown. This
> ADR separates them in Core. **Storage type** stays `type` (the cast result).
> **Meaning** is a new `semantic_kind` (code, measure, date, period, text, flag), and
> `code` requires the source string to be kept. **Display** reuses the fields Core
> already has — `FieldDescriptor.title` and `FieldConstraints.format` — instead of
> adding `label` or a second `format`. A `semantic_kind` that contradicts the storage
> type is a spec validation error. Core owns only the declared layer; the precedence
> between user notes, Core, catalogue and Engine estimates is Engine's contract
> (kpubdata-builder#813).

## 문제

2026-09-29 기준, 컬럼 하나의 메타가 세 군데에 흩어져 있고 경계가 없다 (#644).

| 위치 | 필드 |
|---|---|
| spec `FieldSpec` (`core/spec.py`) | `name`, `type`, `source_name`, `unit`, `transform`, `description` |
| 공개 `FieldDescriptor` (`core/models.py`) | `name`, `title`, `type`, `description`, `nullable`, `raw`, `constraints` |
| 공개 `FieldConstraints` | `max_length`, `min_value`, `max_value`, `pattern`, `allowed_values`, `format` |

`type` 하나가 "무엇으로 캐스팅하나" 와 "이 값이 무엇인가" 를 함께 떠맡았다. 그래서

- 우편번호·지번 같은 **코드**가 숫자처럼 생겼다는 이유로 `integer` 로 선언돼 앞자리
  0 을 잃었다 (#613 — 번들 spec 에서 16개 필드).
- Engine 이 컬럼이 식별자인지 판정할 근거가 없다 (kpubdata-builder#702).
- 표시명·형식을 새로 넣으려 하면 기존 `title`·`format` 과 같은 의미가 두 곳에서
  운영된다.

## 결정

### 1. 세 층

| 층 | 질문 | Core 의 자리 |
|---|---|---|
| **저장 타입** | 값을 무엇으로 캐스팅하나 | `FieldSpec.type` → `FieldDescriptor.type` (그대로) |
| **의미** | 이 값은 무엇인가 | `FieldSpec.semantic_kind` → `FieldDescriptor.semantic_kind` (신규) |
| **표시** | 사람에게 어떻게 보이나 | `FieldSpec.title` → `FieldDescriptor.title`, `FieldSpec.format` → `FieldConstraints.format`, `unit` |

저장 타입은 바꾸지 않는다: `string`, `integer`, `number`, `boolean` — 캐스팅 결과다.

### 2. 의미 — `semantic_kind`

| 값 | 뜻 | 허용 저장 타입 |
|---|---|---|
| `code` | 식별자·분류 코드. 산술의 대상이 아니다 (우편번호, 지번, 역코드, 시각코드) | `string` 만 |
| `measure` | 양. 더하거나 평균낼 수 있다 (금액, 면적, 인원) | `integer`, `number` |
| `date` | 날짜 | `string` (ISO `YYYY-MM-DD`, `date_yyyymmdd` 변환 후) |
| `period` | 기간 단위 (연, 연월) | `string` (`YYYY`, `YYYY-MM`) |
| `text` | 자유 텍스트, 이름 | `string` |
| `flag` | 참·거짓 | `boolean` |

- **`code` 는 원천 문자열 보존을 요구한다.** 숫자로 캐스팅하지 않고, 숫자 변환 `transform`
  (`to_int`, `to_float`, `strip_comma`)도 허용하지 않는다. #613 의 해법(코드 컬럼을
  `string` 으로)이 이 규칙의 첫 적용이다.
- 선언이 없으면 **모른다**. Core 는 추정하지 않는다. 추정은 Engine 층의 일이고, 추정임을
  표시해야 한다.
- 목록에 없는 값은 spec 검증 오류다. 소비자(Engine·Studio)는 모르는 값을 만나면 원문 그대로
  표시한다 — 새 값이 추가돼도 깨지지 않게.

### 3. 표시 — 기존 필드를 재사용한다

- 표시명은 `FieldDescriptor.title`. `label` 을 따로 만들지 않는다.
- 표시 형식은 `FieldConstraints.format` (예: `"YYYY-MM"`, `"url"`). 두 번째 `format` 을
  만들지 않는다.
- `description` 은 지금처럼 설명문.

### 4. 단위

- `unit` 은 **원천 문서로 확인된 값만** 적는다. 모르면 비운다.
- `unit` 은 `measure` 에만 붙는다. 다른 의미에 붙으면 검증 오류.
- 배율·통화(`천원` = 1,000 × 원)를 구조로 나누는 일은 이 ADR 범위가 아니다. 지금은 원문
  단위 문자열 그대로 둔다. 나눌 때 별도 결정.

### 5. 충돌은 검증 오류

spec 로딩(`core/spec.py`)과 `scripts/validate_spec.py` 가 다음을 거부한다.

1. `semantic_kind` 가 위 표의 허용 저장 타입과 맞지 않는다 (`code` + `integer` 등).
2. `code` 에 숫자 변환 `transform` 이 있다.
3. `unit` 이 `measure` 가 아닌 필드에 있다.
4. `semantic_kind` 가 목록에 없는 값이다.

선언이 없는 필드는 검사하지 않는다 — 기존 spec 이 그대로 통과한다. 선언이 없는 코드
컬럼의 안전망은 #613 의 캐스팅 거부(0으로 시작하는 값은 숫자로 캐스팅하지 않음)다.

### 6. 우선순위는 Engine 의 계약

표시 메타가 여러 곳에서 올 때의 우선순위 — 사용자 주석 > Core 명세 > 카탈로그 > Engine
추정 — 는 Engine 계약(kpubdata-builder#813)에 둔다. Core 는 **명세 층만** 책임진다.
어느 층도 저장 타입·라이선스·PII 판정을 덮어쓰지 않는다.

## 그래서 무엇을 만드는가

이 ADR 은 계약이다. 구현은 #651 로 나눈다.

- `FieldSpec` 에 `semantic_kind`, `title`, `format` 추가, `specs/schema.json` enum 추가
- `FieldDescriptor.semantic_kind` 추가, `get_schema`(#643)가 세 층을 채운다
- 5절의 검증 규칙과, 각 규칙이 실패하는 것을 보이는 테스트
- 번들 spec 의 코드 컬럼(#613 의 16개)에 `semantic_kind: code` 선언

규칙은 구현 이슈에서 게이트(검증 오류 + 실패 시연 테스트)와 함께 들어온다. 이 문서만으로
강제되는 것은 없다.

## 기각한 대안

- **`code` 저장 타입 신설.** 저장 타입과 의미를 다시 한 축에 섞는다. `string` 으로 저장하고
  의미를 따로 적으면 같은 효과에 builder 타입 매핑 변경이 없다.
- **`label`·`display_format` 신설.** `title`·`format` 이 이미 공개 모델에 있다. 같은 의미가
  두 곳에 살면 어느 쪽이 맞는지 소비자가 매번 골라야 한다.
- **Core 가 의미를 추정.** 값 모양(숫자, 0으로 시작)으로 추정하면 틀릴 때 조용히 틀린다.
  추정은 추정임을 표시할 수 있는 Engine 층에 둔다.

## 관련

- #644 (이 ADR), #613 (코드 컬럼 앞자리 0), #643 (`get_schema`)
- kpubdata-builder#813 (Engine 컬럼 메타 계약), kpubdata-builder#702 (식별자 판정)
