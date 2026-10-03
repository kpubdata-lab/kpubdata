# ADR 0001: 방언(Dialect) 기반 아키텍처 채택

## 상태

승인됨

## 배경

한국 공공데이터 제공 기관(Provider)들은 API 설계 방식이 저마다 다릅니다:

- **인증**: 쿼리 파라미터, URL 경로 세그먼트, OAuth2 토큰 등 기관마다 상이
- **요청 형태**: REST query string(datago), URL 경로 기반(BOK ECOS), 고정 파라미터 집합(KOSIS) 등
- **응답 형식**: XML(datago 일부), JSON(대부분), CSV(일부 통계) 혼재
- **페이지네이션**: `pageNo`/`numOfRows`(datago), `start`/`end` 인덱스(BOK), 단일 응답(KOSIS) 등
- **에러 시그널링**: HTTP 상태 코드, 응답 본문 내 에러 코드, 혹은 둘 다

이러한 차이를 하나의 "범용 API"로 추상화하면, 기관별 특수성을 숨기게 되어 오히려 사용자에게 혼란을 줍니다. 반대로 기관별로 완전히 별개의 라이브러리를 만들면 중복이 과도해집니다.

## 결정

**작고 안정적인 정규 코어(Canonical Core) + 기관별 어댑터(Adapter, 방언)** 구조를 채택합니다.

- **코어**: `Client`, `Dataset`, `RecordBatch`, `Query`, 공통 예외 등 변하지 않는 진입점과 결과 봉투
- **어댑터**: 각 기관의 고유한 API 규칙(인증, URL 구성, 파싱, 에러 매핑)을 캡슐화하는 통역사

이는 SQL 데이터베이스의 "방언(Dialect)" 패턴에서 영감을 받았습니다. SQLAlchemy가 PostgreSQL/MySQL/SQLite의 차이를 dialect로 흡수하듯, KPubData는 datago/bok/kosis/seoul 등의 차이를 adapter로 흡수합니다.

## 고려한 대안

### 대안 1: 완전 범용 추상화(통합 질의 언어)

모든 기관을 하나의 통합 쿼리 언어로 감싸는 방식.

- **장점**: 사용자가 기관 차이를 전혀 몰라도 됨
- **단점**: 기관별 특수 파라미터를 표현할 수 없음, "가짜 보편성(fake universality)" 발생, 새 기관 추가 시 범용 스키마를 매번 확장해야 함
- **기각 이유**: 정직하지 않은 추상화. 사용자가 "왜 안 되지?" 하며 헤매게 됨

### 대안 2: 기관별 독립 라이브러리

각 기관마다 별도 패키지(예: `kpubdata-datago`, `kpubdata-bok`)를 만드는 방식.

- **장점**: 기관 간 의존성 완전 제거
- **단점**: 공통 로직(HTTP, 캐시, CLI, 에러 처리) 중복, 사용자가 여러 패키지를 조합해야 함
- **기각 이유**: 중복 비용이 너무 높고 사용자 경험이 분산됨

### 대안 3: 플러그인 기반 동적 로딩

코어는 인터페이스만 정의하고, 기관 어댑터를 런타임에 동적으로 로드하는 방식.

- **장점**: 확장성 극대화
- **단점**: v0.1 시점에서 과도한 엔지니어링, 디버깅 어려움, 타입 안전성 약화
- **기각 이유**: 현재 기관 수(~10개)에서는 정적 등록이 더 간단하고 안전함. 장기적으로 플러그인 확장을 검토할 수 있으나 현재 우선순위는 아님

## 영향

### 긍정적

- **점진적 확장**: 새 기관 추가 시 adapter 디렉토리 추가 + manifest 등록만으로 완료 (코어 로직 변경 불필요)
- **안정적인 공개 API**: 코어 인터페이스가 기관 추가와 무관하게 유지됨
- **명확한 책임 분리**: "이 버그는 어느 adapter 문제인가?"를 즉시 파악 가능
- **테스트 격리**: 기관별 fixture/unit/contract 테스트가 독립적으로 실행됨

### 부정적

- **수동 구현 필요**: 각 adapter는 수동으로 구현해야 함 (자동 생성 불가)
- **기관 내 중복 가능성**: 유사한 기관(예: datago 산하 여러 API)에서 일부 보일러플레이트 반복
- **학습 곡선**: 새 기여자가 adapter 계약(Contract)을 이해해야 함 → `PROVIDER_ADAPTER_CONTRACT.md`로 완화

## 관련 문서

- [ARCHITECTURE.md](https://github.com/kpubdata-lab/kpubdata/blob/main/ARCHITECTURE.md)
- [PROVIDER_ADAPTER_CONTRACT.md](https://github.com/kpubdata-lab/kpubdata/blob/main/PROVIDER_ADAPTER_CONTRACT.md)
- [ADR 0002: UX 표준화, 네이티브 형태 표준화 아님](./0002-standardize-ux-not-native-shape.md)
