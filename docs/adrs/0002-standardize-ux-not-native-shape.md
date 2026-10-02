# ADR 0002: UX를 표준화하되, 네이티브 API 형태는 표준화하지 않는다

## 상태

승인됨

## 배경

공공데이터 API를 통합할 때 "어디까지 표준화할 것인가"가 핵심 설계 질문입니다.

- **과도한 표준화**: 모든 기관의 파라미터명, 응답 필드, 페이지네이션을 하나로 통일 → "가짜 보편성" 문제 발생
- **표준화 부재**: 기관마다 완전히 다른 사용법 → 사용자가 매번 새 API를 학습해야 함

실제 사례:
- BOK ECOS는 `start_date`/`end_date`를 URL 경로 세그먼트로 받고, datago는 쿼리 파라미터로 받음
- KOSIS는 `orgId`/`tblId`가 필수이지만, datago에는 해당 개념이 없음
- Seoul Open API는 인증키를 URL 경로에 넣고, 나머지는 쿼리 파라미터로 받음

이런 차이를 억지로 하나의 파라미터 스키마로 맞추면, 결국 `**kwargs`나 provider-specific 필드가 난무하게 되어 표준화의 의미가 사라집니다.

## 결정

**진입점과 결과 봉투만 표준화하고, 기관별 파라미터와 내부 데이터 구조는 그대로 둔다.**

### 표준화하는 것 (UX 계층)

| 항목 | 표준 |
|---|---|
| 클라이언트 생성 | `Client.from_env()` / `Client(provider_keys={...})` |
| 데이터셋 접근 | `client.dataset("provider.dataset_key")` |
| 데이터 조회 | `ds.list(**params)` → `RecordBatch` |
| 스키마 확인 | `ds.schema()` → 필드 목록 |
| 원본 호출 | `ds.call_raw(operation, **params)` → Provider 고유 객체 |
| 결과 봉투 | `RecordBatch(items, meta, next_page, next_cursor)` |
| 페이지네이션 UX | `page`, `page_size`, `cursor` — 표준 파라미터로 노출 |
| 에러 체계 | `AuthError`, `InvalidRequestError`, `ProviderResponseError` 등 |
| 기능 선언 | `adapter.capabilities` → 지원/미지원 명시 |

### 표준화하지 않는 것 (네이티브 계층)

| 항목 | 이유 |
|---|---|
| 기관별 필수 파라미터명 | 기관이 정의한 것이며, 임의 변환 시 디버깅 불가 |
| 날짜 형식 (`YYYYMM` vs `YYYYMMDD`) | 기관별 주기(frequency)에 따라 다름 |
| 응답 필드명 (`DATA_VALUE`, `DT`, `BPLC_NM` 등) | 원본 필드명 유지가 디버깅과 문서 대조에 유리 |
| 페이지네이션 내부 매핑 | adapter가 표준 `page`/`page_size`를 기관별 형식(`pageNo`/`numOfRows`, 인덱스 등)으로 변환 |

## 고려한 대안

### 대안 1: 완전 필드 매핑(전체 필드 정규화)

모든 기관의 응답 필드를 통일된 이름으로 변환(예: `DATA_VALUE` → `value`, `DT` → `value`).

- **장점**: 사용자가 기관 무관하게 동일 필드명 사용 가능
- **단점**: 원본 API 문서와 대조 불가, 기관별 추가 필드 손실, 디버깅 시 "이 `value`가 원래 뭐였지?" 문제
- **기각 이유**: 디버깅 용이성이 프레임워크의 핵심 가치

### 대안 2: 파라미터 이름 통일(통합 파라미터 이름)

모든 기관에 `start_date`, `end_date`, `region` 등 통일 파라미터 사용.

- **장점**: 사용자가 기관별 파라미터를 외울 필요 없음
- **단점**: 기관별 고유 파라미터(`sidoName`, `fyr`, `tblId` 등)를 매핑할 수 없음, 새 파라미터 추가 시 매번 매핑 규칙 정의 필요
- **기각 이유**: 매핑 비용 > 학습 비용. 각 기관 문서 2~3개 파라미터 외우는 게 더 현실적

## 영향

### 긍정적

- **정직한 추상화**: 사용자가 "이 라이브러리가 뭘 해주고 뭘 안 해주는지" 명확히 앎
- **디버깅 용이**: 원본 API 문서와 1:1 대응되어, 문제 발생 시 기관 문서를 바로 참조 가능
- **장기 호환성**: 기관 API가 변경되어도 adapter만 수정하면 되고, 표준 인터페이스는 유지됨
- **Raw 비상구**: `call_raw`를 통해 표준화 범위 밖의 모든 기능에 접근 가능

### 부정적

- **기관별 지식 필요**: 고급 사용 시 해당 기관의 파라미터명을 알아야 함
- **기관 간 집계 어려움**: 여러 기관 데이터를 통합 분석하려면 사용자가 필드 매핑을 직접 해야 함 → 향후 `kpubdata-builder`에서 해결 예정

## 관련 문서

- [CANONICAL_MODEL.md](https://github.com/kpubdata-lab/kpubdata/blob/main/CANONICAL_MODEL.md)
- [API_SPEC.md](https://github.com/kpubdata-lab/kpubdata/blob/main/API_SPEC.md)
- [ADR 0001: 방언 기반 아키텍처 채택](./0001-dialect-inspired-architecture.md)
