# ADR 0007: 독립성 규칙 — KPubData 는 Builder·Studio 없이 성립한다

## 상태

채택됨(Accepted) — 2026-09-30

## 요약 (English summary)

> KPubData is a standalone Python SDK. KPubData Builder and KPubData Studio are
> related projects built on top of it, and dependencies flow one way only:
> **Studio → Builder → KPubData**. This ADR records twelve Independence Rules as
> architecture invariants, defines what counts as KPubData's public API (the names
> in `kpubdata.__all__`, as specified in `API_SPEC.md`) and what does not
> (underscore modules, internal helpers, fixtures, repository layout). It does not
> change ADR 0004; whether Studio keeps sharing Builder's version number is left
> to the owner.

## 배경

2026-09-30 소유자 결정 「KPubData 명칭·제품 구조·의존성 경계 최종 정리」가 공식 이름을
**KPubData**, **KPubData Builder**, **KPubData Studio** 로 정했다. `Core` 는 제품명이
아니라 아키텍처 역할명이다 (#666).

이름만 정리하면 경계는 그대로 흐려진 채 남는다. 지금까지 세 저장소는 "함께 쓰는 파이프라인"
으로 소개됐고, 그래서 다음 같은 일이 생길 여지가 있었다.

- Studio 화면의 편의를 위해 KPubData 의 용어나 공개 API 를 바꾸는 일.
- Builder 가 `kpubdata._probe` 같은 비공개 모듈을 직접 import 하는 일.
- Studio 가 KPubData 의 상수, fixture, 저장소 구조를 직접 읽는 일.
- "세 저장소의 main 이 지금 함께 돌아간다" 를 호환성의 근거로 삼는 일.

이 ADR 은 경계를 불변식으로 적는다.

## 결정

### 1. 의존 방향

```text
KPubData Studio  →  KPubData Builder  →  KPubData
```

의존은 이 한 방향으로만 흐른다. 역방향(KPubData → Builder, KPubData → Studio,
Builder → Studio)은 금지다. Studio 는 KPubData 에 직접 의존하지 않고 Builder 가 소유한
계약만 쓴다.

### 2. 독립성 규칙 (Independence Rules)

| # | 규칙 |
|---|---|
| 1 | KPubData 는 KPubData Builder(`kpubdata-builder`)에 의존하지 않는다. |
| 2 | KPubData 는 KPubData Studio(`kpubdata-studio`)에 의존하지 않는다. |
| 3 | KPubData 의 공개 API 는 Builder·Studio 없이 그 자체로 의미가 성립한다. |
| 4 | KPubData 의 용어를 Builder·Studio 의 UX 만을 이유로 바꾸지 않는다. |
| 5 | Builder 는 KPubData 의 **문서화된 공개 API** 에 의존할 수 있다. |
| 6 | Builder 는 KPubData 의 비공개 구현 세부에 의존하지 않는다. |
| 7 | Builder 는 KPubData 개념을 **Builder 소유 계약**으로 번역한 뒤에 HTTP/OpenAPI 로 노출한다. |
| 8 | Studio 는 Builder 소유 계약을 소비한다. |
| 9 | Studio 는 KPubData 의 상수, 비공개 모듈, fixture, 저장소 구조에 의존하지 않는다. |
| 10 | 각 저장소는 독립적으로 설치·테스트·버전 관리·릴리스할 수 **있다**. |
| 11 | 저장소 간 호환성은 명시적이고 버전화되어 있다. |
| 12 | 각 저장소의 main 브랜치끼리 맞는다는 사실은 암묵적 호환성 계약이 아니다. |

규칙 1·2 는 이 저장소의 CI 게이트로 확인한다 (#668). 규칙 5–9 는 Builder·Studio
저장소 쪽에서 지키는 규칙이며, 각 저장소가 자기 게이트를 둔다.

### 3. 공개 API 의 경계

규칙 5·6 이 뜻을 가지려면 "공개" 가 무엇인지 정해져 있어야 한다.
[`docs/compatibility.md` §3](../compatibility.md) 과 [`API_SPEC.md`](https://github.com/yeongseon/kpubdata/blob/main/API_SPEC.md) 를
기준으로 다음과 같이 적는다.

**공개 (Builder 가 의존할 수 있음)**

- `kpubdata` 최상위 패키지의 `__all__` 에 있는 이름 — `Client`, `DatasetRef`, `Query`,
  `RecordBatch`, `SchemaDescriptor`, `FieldDescriptor`, `Operation`, `PaginationMode`,
  `QuerySupport`, `Representation`, 정규 예외 계층 등. 목록의 정본은 코드
  (`src/kpubdata/__init__.py`)와 `API_SPEC.md` 다.
- 그 객체들의 문서화된 메서드 (`Client.from_env()`, `Dataset.list/list_all/schema/call_raw`
  등, `API_SPEC.md` §7).
- 정규 데이터 모델 ([`CANONICAL_MODEL.md`](https://github.com/yeongseon/kpubdata/blob/main/CANONICAL_MODEL.md)).
- 외부에 노출된 dataset id (`datago.apt_trade` 등) — 약속 범위는 compatibility.md §3 을 따른다.

**비공개 (의존 금지)**

- 밑줄로 시작하는 모듈과 이름 — `kpubdata._probe`, `kpubdata._hosts`, `kpubdata._typing`,
  그리고 모든 `_` 접두 함수·상수.
- 어댑터 내부 헬퍼와 transport 구현 세부 (`API_SPEC.md` §7 "does not promise").
- 테스트 fixture, 저장소 디렉터리 구조, 스크립트, 생성 파일의 파일 경로.

공개 API 에 없는 것이 Builder 에 필요하면, Builder 가 비공개 모듈을 import 하는 대신 이
저장소에 공개 API 추가를 제안한다. 추가는 규칙 3·4 를 지켜야 한다 — Builder·Studio 없이도
뜻이 통하는 이름과 모양이어야 한다.

### 4. ADR 0004 와의 관계 — 결정하지 않은 것

소유자 정리 문서는 Studio 를 "independent lifecycle" 로 적었다. 이는
[ADR 0004](0004-versioning-and-release.md) — Builder 와 Studio 는 한 애플리케이션이므로
**버전을 공유한다** — 및 compatibility.md §5.1 의 월말 순차 릴리스와 겹친다.

이 ADR 은 **ADR 0004 를 바꾸지 않는다.** 규칙 10 은 "독립적으로 릴리스 **가능**하다" —
다른 저장소를 함께 고치지 않고도 설치·테스트·릴리스할 수 있다 — 로 읽는다. Studio 가
Builder 와 같은 버전 번호를 계속 쓸지는 소유자가 정할 열린 결정으로 남긴다.

## 결과

- KPubData 의 README 와 문서는 KPubData 를 독립 SDK 로 소개하고, Builder·Studio 를
  파이프라인의 다음 단계가 아니라 관련 프로젝트로 소개한다 (#666).
- 공개 API 를 바꿀 때 "Builder 나 Studio 가 이렇게 쓰니까" 는 근거가 되지 않는다.
  근거는 KPubData 사용자에게 그 변경이 뜻이 통하는가다.
- 규칙 1·2 를 어기는 변경은 CI 에서 실패한다 (#668).

## 검토한 대안

- **규칙을 AGENTS.md 에만 적는다.** 에이전트 안내문은 설계 근거를 담는 곳이 아니고, 사람이
  읽는 아키텍처 문서에서 경계가 보이지 않는다. ADR 에 근거를 두고 AGENTS.md 에는 요약만 둔다.
- **공개 API 를 "import 할 수 있는 모든 것" 으로 둔다.** 파이썬에서는 거의 모든 것이 import
  가능하므로 경계가 없는 것과 같다. `__all__` 과 `API_SPEC.md` 를 기준으로 좁힌다.
- **ADR 0004 를 이번에 함께 고친다.** 버전 공유는 배포 단위에 대한 별개 결정이고, 이 ADR 의
  범위(의존 경계)가 아니다. 소유자 결정으로 남긴다.

## 참조

- #666 (명칭 정리), #667 (이 ADR), #668 (규칙 1·2 의 CI 게이트)
- [ADR 0004](0004-versioning-and-release.md), [`docs/compatibility.md`](../compatibility.md)
- [`docs/product-family-architecture.md`](../product-family-architecture.md)
