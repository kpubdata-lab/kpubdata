# Provider adapter contract — KPubData

## 1. Purpose

This document defines what it means to add a provider adapter to KPubData.

A provider adapter is the place where backend-specific behavior belongs.

## 2. Responsibilities

Every adapter must be responsible for:

- auth/key injection
- dataset discovery or dataset registration
- canonical-to-native parameter translation
- native-to-canonical result translation
- provider-specific error translation
- raw-call support
- honest operation and query-support declaration
- declaring whether the provider needs an API key (`requires_api_key`)

An adapter does not have to be hand-written. A dataset declared as a YAML spec under
`src/kpubdata/specs/<provider>/` is served by `SpecDatasetAdapter`
(`src/kpubdata/core/executor.py`), which implements this same contract on top of
`SpecExecutor`. That is the default way to add a dataset (see `AGENTS.md`, "Adding a
dataset"); the tutorial in §4 is for a provider whose conventions a spec cannot express.
When a provider has both a custom adapter and specs, `CompositeProviderAdapter`
(`src/kpubdata/core/bridge.py`) merges them and the spec wins for a shared `dataset_key`.

## 3. 어댑터란 무엇인가? (초보자용 설명)

어댑터(Adapter)는 일종의 **"변압기"나 "여행용 멀티 플러그"**와 같습니다.

한국에서 쓰던 220V 가전제품을 110V를 쓰는 일본에서 쓰려면 돼지코(어댑터)가 필요하죠? 가전제품(사용자 코드)은 그대로인데, 전기 콘센트(공공데이터 API) 모양이 다르기 때문입니다.

KPubData의 어댑터는 각 기관(공공데이터포털, 서울시 등)마다 제각각인 API의 "모양"을 우리 프레임워크가 약속한 "표준 모양"으로 맞춰주는 역할을 합니다.

```mermaid
sequenceDiagram
    participant U as 사용자 (User)
    participant D as 데이터셋 (Dataset)
    participant A as 어댑터 (Adapter)
    participant T as 전송 계층 (Transport)
    participant P as 공공 API (Public API)

    U->>D: 데이터 요청 (list/get)
    D->>A: 요청 전달
    A->>A: 표준 Query -> 기관용 파라미터 변환
    A->>T: HTTP 요청 실행
    T->>P: 실제 API 호출
    P-->>T: 원본 응답 (XML/JSON)
    T-->>A: 파이썬 객체로 변환된 데이터
    A->>A: 결과 파싱 및 표준화 (RecordBatch)
    A-->>U: RecordBatch 반환
```

## 4. 새 어댑터 개발 튜토리얼 (Step-by-Step)

새로운 공공데이터 기관을 연동하고 싶다면 다음 순서대로 진행하세요.

### 0단계: 연동할 API 결정
어떤 데이터를 가져올지 정하고, 해당 API의 문서를 준비합니다. (예: `data.go.kr`의 기상청 예보 서비스)

### 1단계: API 문서 분석
- 요청 주소(URL)는 무엇인가?
- 어떤 파라미터가 필수인가? (서비스키, 페이지 번호 등)
- 응답 형식이 무엇인가? (JSON, XML)
- 에러가 나면 어떤 코드가 돌아오는가?

### 2단계: 파일 생성
`src/kpubdata/providers/` 폴더 아래에 기관 이름을 따서 폴더를 만듭니다.
```text
src/kpubdata/providers/my_provider/
├── __init__.py
├── adapter.py      # 여기에 핵심 로직 작성
└── catalogue.json  # 지원하는 데이터셋 목록
```

`kpubdata scaffold provider my_provider` 명령이 이 골격(어댑터, `catalogue.json`, fixture, 계약 테스트)을 생성해 줍니다.

### 3단계: 기본 구조 작성 (adapter.py)
```python
class MyProviderAdapter:
    # 키가 필요 없는 기관이면 False로 선언합니다 (6.1절).
    requires_api_key: bool = True

    def __init__(self, *, config=None, transport=None):
        self._config = config or KPubDataConfig()
        self._transport = transport or HttpTransport()

    @property
    def name(self) -> str:
        return "my_provider"
```

내장 provider는 `adapter_cls(config=..., transport=...)` 형태의 키워드 인자로 생성됩니다(`src/kpubdata/bootstrap.py`). 외부 어댑터는 직접 만든 인스턴스를 `client.register_provider(adapter)`로 등록합니다.

### 4단계: `list_datasets` 구현
사용자가 `client.datasets.list()`를 했을 때 보여줄 목록을 반환합니다. 보통 `catalogue.json`에서 읽어옵니다.

### 5단계: `query_records` 구현
가장 중요한 부분입니다. 표준 `Query` 객체를 받아서 실제 API를 호출하고, 결과를 `RecordBatch`로 포장합니다.
```python
def query_records(self, dataset, query):
    # 1. 파라미터 변환 (KPubData -> 기관 API). 값은 모두 문자열입니다.
    api_key = self._config.require_provider_key("my_provider")
    params = {"ServiceKey": api_key, "pageNo": str(query.page or 1)}
    # 2. HTTP 요청 전송 (Transport 사용)
    response = self._transport.request("GET", url, params=params)
    # 3. 결과 파싱 및 표준화
    items = self._parse_items(response.content)
    # 4. RecordBatch로 반환
    return RecordBatch(items=items, dataset=dataset)
```

### 6단계: `call_raw` 구현 (비상구)
표준화되지 않은 기능을 쓰고 싶은 사용자를 위해 원본 데이터를 그대로 돌려주는 함수입니다.
```python
def call_raw(self, dataset, operation, params):
    # 어떠한 가공도 하지 않고 원본 응답을 반환합니다.
    return self._transport.request("GET", url, params=params).json()
```

### 7단계: 에러 처리
API가 주는 에러 코드를 보고 `AuthError`, `RateLimitError` 등 KPubData가 정의한 에러로 바꿔서 던져줍니다.

### 8단계: 테스트 작성
- `tests/fixtures/`에 실제 API 응답 샘플을 저장합니다.
- 유닛 테스트(`tests/unit/`)에서 이 샘플을 잘 파싱하는지 검증합니다.
- 계약 테스트(`tests/contract/`)에서 선언한 operation과 실제 동작이 일치하는지 검증합니다.

### 9단계: Operations와 QuerySupport 선언
이 어댑터가 어떤 정규 작업(`Operation.LIST`, `Operation.RAW` 등)을 지원하는지 `DatasetRef.operations`에 정직하게 선언합니다. 페이징, 검색, 정렬, 기간 조건 같은 질의 기능은 `QuerySupport`에 구조화해서 기록합니다.

```mermaid
flowchart TD
    S0[0단계: 연동할 API 결정] --> S1[1단계: API 문서 분석]
    S1 --> S2[2단계: 폴더 및 파일 생성]
    S2 --> S3[3단계: adapter.py 기본 구조 작성]
    S3 --> S4[4단계: list_datasets 구현]
    S4 --> S5[5단계: query_records 구현]
    S5 --> S6[6단계: call_raw 비상구 구현]
    S6 --> S7[7단계: 기관별 에러 처리]
    S7 --> S8[8단계: 피스처 및 테스트 작성]
    S8 --> S9[9단계: Operations와 QuerySupport 선언]
```

## 5. 기존 어댑터 분석: `datago`

가장 모범적인 사례인 `datago` 어댑터를 참고하세요.

- **`src/kpubdata/providers/datago/adapter.py`** (`DataGoAdapter`): 요청 조립(`_build_base_params`, `_build_request_url`)과 호출·디코딩(`_request_and_decode`)을 담당합니다.
- **`src/kpubdata/providers/datago/envelope.py`** (`DataGoEnvelopeParser`): 응답 해석을 담당합니다.
  - `parse` / `parse_odcloud`: 데이터셋의 envelope 종류에 맞는 검증 함수를 골라 응답이 깨졌는지, 에러가 들어있는지 체크합니다.
  - `normalize_items`: 아이템 목록을 뽑아내 `list[dict]`로 맞춥니다.
  - `_raise_for_result_code`: 기상청 등의 에러 코드(`01`, `02` 등)를 이해하기 쉬운 예외로 바꿉니다.
- **`src/kpubdata/providers/_datago_family.py`** (`DataGoFamilyAdapter`): 같은 data.go.kr 규약을 쓰는 `localdata`·`semas`가 상속하는 공통 구현입니다.

**이 파일을 복사해서 새로운 어댑터를 만들기 시작하는 것을 추천합니다!**

## 6. Minimal protocol

```python
from typing import Protocol


class ProviderAdapter(Protocol):
    requires_api_key: bool

    @property
    def name(self) -> str: ...

    def list_datasets(self) -> list[DatasetRef]: ...
    def search_datasets(self, text: str) -> list[DatasetRef]: ...
    def get_dataset(self, dataset_key: str) -> DatasetRef: ...
    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch: ...
    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None: ...
    def call_raw(
        self, dataset: DatasetRef, operation: str, params: dict[str, object]
    ) -> object: ...
```

```mermaid
classDiagram
    class ProviderAdapter {
        <<interface>>
        +bool requires_api_key
        +str name
        +list_datasets() list~DatasetRef~
        +search_datasets(text: str) list~DatasetRef~
        +get_dataset(dataset_key: str) DatasetRef
        +query_records(dataset: DatasetRef, query: Query) RecordBatch
        +get_schema(dataset: DatasetRef) SchemaDescriptor
        +call_raw(dataset: DatasetRef, op: str, params: dict) object
    }
```

The protocol is defined in `src/kpubdata/core/protocol.py`. `get_dataset` takes the
provider-local key (`apt_trade`), not the full id (`datago.apt_trade`). `get_schema`
returns `None` when the schema is unknown, never an empty one. The registry
(`src/kpubdata/registry.py`) refuses an adapter that lacks a non-empty `name` or any of
the six methods, and raises `CapabilityContractError` for a dataset whose `operations`
is empty.

### 6.1 `requires_api_key`

- `True` (what `Client` assumes when the attribute is missing): the provider needs a key.
  `Client.iter_authenticated_providers()` returns only these adapters.
- `False`: the provider is usable without a key. `krx` is the built-in example.
- The attribute is a declaration. Reading the key and injecting it into the request is
  still the adapter's job, through `KPubDataConfig.require_provider_key(...)`, which
  raises `ConfigError` when the key is missing.
- `SpecDatasetAdapter` derives it from its specs: `True` when any spec's `auth.type` is
  not `none`.

### 6.2 Optional: `query_records_all`

An adapter may also provide:

```python
def query_records_all(
    self, dataset: DatasetRef, query: Query, *, max_pages: int | None = None
) -> Iterator[RecordBatch]: ...

def supports_query_records_all(self, dataset_key: str) -> bool: ...
```

- It is not part of `ProviderAdapter` and the registry does not require it.
- When it exists, `Dataset.list_all()` calls it once instead of calling `query_records`
  page by page, and yields what it returns (`src/kpubdata/core/dataset.py`).
- Implement it only when the result must be decided across pages. `SpecDatasetAdapter`
  does, because column casting is all-or-nothing per column over the whole result: it
  requests every page first, then yields one `RecordBatch` per page, each with its own
  `raw`, `meta["provenance"]`, `next_page` and `validation`, plus
  `meta["validation_total"]` for the whole result. A page that fails raises and no
  batch is yielded.
- `max_pages` must be honoured: yield the pages fetched, then raise
  `InvalidRequestError` when more would be needed.
- `supports_query_records_all` is for an adapter that has the method but serves only
  some keys through it (`CompositeProviderAdapter`). When it is absent, the method is
  taken to serve every key.

## 7. 페이지네이션 반환 규약 (Pagination Return Contract)

어댑터는 `query_records` 결과로 반환되는 `RecordBatch`에 다음 페이지 정보를 포함해야 합니다.

- **`next_page` 또는 `next_cursor` 반환**: 어댑터는 반드시 둘 중 하나를 반환하거나, 마지막 페이지인 경우 둘 다 `None`을 반환해야 합니다.
- **우선순위**: `list_all()`은 `next_cursor`가 존재할 경우 이를 우선적으로 사용하며, 없을 경우 `next_page`를 사용합니다. 어댑터가 `query_records_all`(6.2절)을 제공하는 데이터셋은 이 순회 대신 그 메서드가 페이지를 넘깁니다.
- **권장 방식**: 가급적 `total_count` 기반의 정밀한 계산 방식을 선호합니다. 하지만 전체 개수 정보를 알 수 없는 경우 `len(items) == page_size` 휴리스틱을 사용하는 것도 허용됩니다.

## 8. Operation and query-support rules

- declare only operations the adapter truly supports in `DatasetRef.operations`
- describe pagination, filter, sort, time-range, and page-size support in `DatasetRef.query_support`
- if an operation is unavailable, raise `UnsupportedCapabilityError`
- do not silently emulate unsupported semantics unless documented

## 9. Raw rules

- every adapter must expose a raw path
- raw paths may be inconvenient; they must still be available
- raw payloads should not be lossy-normalized

## 10. Discovery rules

Adapters may support discovery via:

- static registrations
- provider metadata API
- cached generated manifests

At minimum, the adapter must surface enough metadata to populate `DatasetRef`.

## 11. Parse and normalization rules

Normalize only the common envelope and broadly reusable metadata.

Do not destroy provider-native fields. Prefer one of these approaches:

- preserve raw payload at `RecordBatch.raw`
- preserve unmapped fields in item-level metadata

## 12. Testing requirements

Every adapter must include:

- unit tests for mapping/parsing
- contract tests for declared operations and query-support behavior
- fixture-based tests for representative success/failure responses

```mermaid
graph LR
    UT[유닛 테스트 Unit Tests] --> MAP[매핑/파싱 로직 검증]
    CT[계약 테스트 Contract Tests] --> CAP[표준 기능 준수 확인]
    FT[피스처 테스트 Fixture Tests] --> RESP[실제 API 응답 처리 검증]
```

## 13. When to extend the core instead of the adapter

Only extend the core when:

- three or more adapters need the same concept
- it improves the public contract materially
- it reduces duplication without hiding semantics

Otherwise, keep the complexity local to the adapter.

## 14. Example adapter development checklist

1. define provider config and auth requirements
2. define dataset ids and metadata
3. implement discovery
4. implement `query_records`
5. implement `call_raw`
6. map provider errors
7. add fixtures and tests
8. document operations, query support, and caveats

---

## 관련 문서

### 이 저장소 내 문서
| 문서 | 설명 |
| :--- | :--- |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 시스템 아키텍처 설계 |
| [CANONICAL_MODEL.md](./CANONICAL_MODEL.md) | 표준 데이터 모델 정의 |
| [API_SPEC.md](./API_SPEC.md) | 파이썬 API 명세 |
| [VALIDATION.md](./VALIDATION.md) | 아키텍처 타당성 검증 |
| [AGENTS.md](./AGENTS.md) | 어댑터 개발 가이드 및 에이전트 규칙 |
