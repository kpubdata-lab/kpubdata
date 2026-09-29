# Canonical model — KPubData

## 1. Purpose

The canonical model defines the smallest stable set of objects needed to make heterogeneous public-data services usable through one Python framework.

The model should be:

- small
- explicit
- typed
- extensible by metadata
- honest about unsupported behavior

## 2. Design rule

Canonical objects standardize the **framework contract**, not every semantic detail of every provider.

```mermaid
classDiagram
    class DatasetRef {
        +str id
        +str provider
        +str dataset_key
        +str name
        +str description
        +tuple tags
        +str source_url
        +Representation representation
        +frozenset[Operation] operations
        +QuerySupport query_support
        +LicenseSpec license
    }
    class Query {
        +dict filters
        +int page
        +int page_size
        +str cursor
        +str start_date
        +str end_date
    }
    class RecordBatch {
        +list[dict] items
        +DatasetRef dataset
        +int total_count
        +int next_page
        +Any raw
    }
    class SchemaDescriptor {
        +DatasetRef dataset
        +list[FieldDescriptor] fields
    }
    class FieldDescriptor {
        +str name
        +str title
        +str type
        +str description
        +bool nullable
        +FieldConstraints constraints
    }
    class FieldConstraints {
        +int max_length
        +float min_value
        +float max_value
        +str pattern
        +tuple allowed_values
        +str format
    }

    DatasetRef "1" --o "1" RecordBatch
    DatasetRef "1" --o "1" SchemaDescriptor
    SchemaDescriptor "1" --* "many" FieldDescriptor
    FieldDescriptor "1" --o "0..1" FieldConstraints
    Query ..> RecordBatch : produces
```

## 3. 타입별 상세 설명 (이것은 무엇인가?)

KPubData에서 사용하는 핵심 타입들을 일상적인 도서관 비유로 설명합니다.

### 3.1 DatasetRef (도서 카드)
- **비유**: 도서관의 **"도서 목록 카드"**와 같습니다. 책이 어느 서가에 있는지, 대출이 가능한지(지원하는 기능), 어떤 내용인지 알려줍니다.
- **역할**: 이 데이터셋이 어디에 있고(Provider), 고유한 이름(ID)은 무엇인지, 어떤 형식(Representation)인지 정보를 담고 있습니다. 또한 데이터셋에 대한 설명(description), 분류 태그(tags), 원본 문서 링크(source_url)를 포함할 수 있습니다.

### 3.2 Query (검색 조건)
- **비유**: 도서관에서 책을 찾을 때 쓰는 **"검색 조건"**입니다. "2024년에 나온 소설 중 서울에서 발간된 것" 같은 조건이죠.
- **역할**: 사용자가 원하는 데이터를 필터링하기 위한 조건들(날짜, 지역, 페이지 번호 등)을 한데 모아둡니다.

### 3.3 RecordBatch (검색 결과 목록)
- **비유**: 검색 결과로 나온 **"책 목록 한 뭉치"**입니다. 실제 데이터(책 내용)뿐만 아니라 "총 몇 권이 나왔는지", "다음 페이지가 있는지" 같은 정보도 함께 들어있습니다.
- **역할**: 실제 데이터 행(rows)과 메타정보를 함께 전달하는 운반체입니다.

```mermaid
flowchart LR
    Ref[DatasetRef] --> Q[Query]
    Q --> List[dataset.list]
    List --> RB[RecordBatch]
    RB --> Items[items: list of dict]
    RB --> Meta[total_count, next_page]
```

### 3.4 SchemaDescriptor (데이터 설계도)
- **비유**: 데이터의 **"설계도" 또는 "명세서"**입니다. 이 데이터 목록의 첫 번째 칸은 '날짜'이고 숫자로 되어 있다는 것을 알려줍니다.
- **역할**: 각 칼럼(Field)의 이름, 타입, 설명 등을 정의하여 사용자가 데이터를 이해할 수 있게 돕습니다.

### 3.5 PublicDataError (에러 분류 체계)
- **비유**: 도서관에서 발생할 수 있는 **"사고 유형"**입니다. "카드가 없어요(AuthError)", "책이 없어요(DatasetNotFoundError)", "서가가 닫혔어요(ServiceUnavailableError)" 등으로 분류합니다.
- **역할**: 에러가 왜 발생했는지 구체적으로 알려주어 프로그래머가 적절히 대처할 수 있게 합니다.

## 4. 실제 사용 예시 (코드)

### 4.1 타입을 직접 만들어보는 예시
```python
from kpubdata.core.models import Query, DatasetRef
from kpubdata.core.capability import Operation
from kpubdata.core.representation import Representation

# 1. 데이터셋 정보를 직접 정의할 때 (DatasetRef)
ref = DatasetRef(
    id="datago.village_fcst",
    provider="datago",
    dataset_key="village_fcst",
    name="동네예보",
    representation=Representation.API_JSON,
    description="Korea Meteorological Administration short-range forecast",
    tags=("weather", "forecast"),
    source_url="https://www.data.go.kr",
    operations=frozenset([Operation.LIST])
)

# 2. 검색 조건을 만들 때 (Query)
query = Query(
    filters={"base_date": "20250401", "nx": "55"},
    page=1,
    page_size=10
)
```

### 4.2 타입을 사용하는 시나리오
```python
# 사용자가 데이터를 조회하면 RecordBatch가 돌아옵니다.
batch = ds.list(nx=55, ny=127)

print(f"총 {batch.total_count}개의 데이터가 있습니다.")
for item in batch.items:
    print(item["category"], item["fcstValue"])
```

## 5. 타입 관계도 (Relationship Diagram)

```text
[ Client ]
    |
    +-- (id) --> [ Catalog ] -- (resolve) --> [ DatasetRef ] (도서 카드)
                                                   |
                                                   v
[ Dataset (Bound Object) ] <-----------------------+
    |
    +-- (list) --+--> [ Query ] (검색 조건)
    |            |
    |            +--> [ ProviderAdapter ] -- (HTTP Request) --> [ Public Data API ]
    |                                                                   |
    |            <-- (RecordBatch) <------------------- (HTTP Response) +
    |                    |
    |                    +-- [ Items (list[dict]) ] (실제 데이터)
    |                    +-- [ Metadata ] (메타정보)
    |
    +-- (schema) ----> [ SchemaDescriptor ] (데이터 설계도)
                         |
                         +-- [ FieldDescriptor ] (칼럼 정보)
                              +-- [ FieldConstraints ] (제약 조건)
```

## 6. Core types

### 6.1 Operation and QuerySupport

```python
from enum import Enum

class Operation(str, Enum):
    LIST = "list"
    GET = "get"
    SCHEMA = "schema"
    RAW = "raw"
    DOWNLOAD = "download"

class PaginationMode(str, Enum):
    OFFSET = "offset"
    INDEX = "index"
    CURSOR = "cursor"
    NONE = "none"

@dataclass(slots=True, frozen=True)
class QuerySupport:
    pagination: PaginationMode = PaginationMode.NONE
    filterable_fields: frozenset[str] = frozenset()
    sortable_fields: frozenset[str] = frozenset()
    time_range: bool = False
    max_page_size: int | None = None
```

`Operation` describes the canonical actions a dataset supports. Query-shape features that used to be modeled as capability enum values are now structured in `QuerySupport`.

### 6.2 Representation

```python
from enum import Enum

class Representation(str, Enum):
    API_JSON = "api_json"
    API_XML = "api_xml"
    FILE_CSV = "file_csv"
    FILE_EXCEL = "file_excel"
    SHEET = "sheet"
    OTHER = "other"
```

```mermaid
graph TD
    subgraph Operations [Dataset Operations]
        LIST[LIST: Browse multiple records]
        GET[GET: Fetch single record by ID]
        SCHEMA[SCHEMA: Metadata about fields]
        RAW[RAW: Provider escape hatch]
        DOWNLOAD[DOWNLOAD: Download source artifact]
    end

    subgraph QuerySupport [Query Support]
        PAGINATION[pagination: offset/index/cursor/none]
        FILTERABLE[filterable_fields]
        SORTABLE[sortable_fields]
        TIME_RANGE[time_range]
    end

    subgraph Reps [Representations]
        API_JSON[API_JSON: JSON HTTP API]
        API_XML[API_XML: XML HTTP API]
        FILE_CSV[FILE_CSV: CSV file]
        FILE_EXCEL[FILE_EXCEL: Excel file]
        SHEET[SHEET: Google/Excel sheet]
    end
```

### 6.3 DatasetRef

```python
from dataclasses import dataclass, field
from types import MappingProxyType

@dataclass(slots=True, frozen=True)
class DatasetRef:
    id: str
    provider: str
    dataset_key: str
    name: str
    representation: Representation
    operations: frozenset[Operation] = frozenset()
    query_support: QuerySupport | None = None
    raw_metadata: MappingProxyType[str, object] = field(default_factory=_empty_proxy)
    description: str | None = None
    tags: tuple[str, ...] = ()
    source_url: str | None = None
    license: LicenseSpec | None = None
```

Notes:

- `id` is the stable bound identifier, e.g. `molit.apartment_trades`
- `representation` matters because the same logical dataset may be offered in more than one form
- `operations` is the honest set of supported canonical actions
- `query_support` describes pagination, filtering, sorting, time-range, and max page-size metadata when known
- `description` is a human-readable summary of what the dataset provides
- `tags` are categorization keywords for discovery (e.g. `("weather", "forecast")`)
- `source_url` links to the original API documentation or data portal page
- `raw_metadata` is immutable provider-native discovery metadata for debugging and adapter internals
- `license` is the spec's `license` section as parsed, or `None` when the dataset declares none — `None` means unknown, never "no restrictions" (#609)

### 6.4 Query

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class Query:
    filters: dict[str, Any] = field(default_factory=dict)
    page: int | None = None
    page_size: int | None = None
    cursor: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    fields: list[str] | None = None
    sort: list[str] | None = None
    extra: dict[str, Any] = field(default_factory=dict)
```

Notes:

- `filters` covers the normal case
- `extra` exists so adapters can carry provider-native hints without contaminating the core model

#### Validation

Query validates common input shape and types at construction time, raising `InvalidRequestError` for invalid values:

- `page`, `page_size`: must be positive integers (`>= 1`) or `None`; `bool`, zero, or negative values are rejected
- `cursor`: must be a non-empty string or `None`
- `start_date`, `end_date`: must be non-empty strings or `None`
- `fields`, `sort`: must be lists of strings or `None`; elements are type-checked
- `filters`, `extra`: must be dicts with string keys

#### Canonical vs Provider-Specific Rules

Canonical Query validates common input constraints. Provider-specific rules remain adapter responsibilities:

- **Date representation** (e.g., `YYYYMM` vs `YYYYMMDD`): provider-specific, validated by adapters
- **Required provider parameters** (e.g., specific datasets requiring `start_date`): validated by adapters
- **Provider-specific ranges and semantics**: validated by adapters

This separation ensures that invalid canonical inputs are rejected early (before provider invocation) while preserving provider flexibility for domain-specific constraints.

### 6.5 RecordBatch

```python
from dataclasses import dataclass, field
from typing import Any

@dataclass(slots=True)
class RecordBatch:
    items: list[dict[str, Any]]
    dataset: DatasetRef
    total_count: int | None = None
    next_page: int | None = None
    next_cursor: str | None = None
    raw: Any | None = None
    meta: dict[str, Any] = field(default_factory=dict)
```

### 6.6 SchemaDescriptor

```python
from dataclasses import dataclass, field
from types import MappingProxyType

@dataclass(slots=True)
class FieldConstraints:
    max_length: int | None = None
    min_value: float | None = None
    max_value: float | None = None
    pattern: str | None = None
    allowed_values: tuple[str, ...] | None = None
    format: str | None = None

@dataclass(slots=True)
class FieldDescriptor:
    name: str
    title: str | None = None
    type: str | None = None
    description: str | None = None
    nullable: bool | None = None
    constraints: FieldConstraints | None = None
    raw: MappingProxyType[str, object] = field(default_factory=_empty_object_proxy)

@dataclass(slots=True)
class SchemaDescriptor:
    dataset: DatasetRef
    fields: list[FieldDescriptor]
    raw: MappingProxyType[str, object] = field(default_factory=_empty_object_proxy)
```

## 4. Error model

```python
class PublicDataError(Exception): ...
class ConfigError(PublicDataError): ...
class AuthError(PublicDataError): ...
class TransportError(PublicDataError): ...
class TransportTimeoutError(TransportError): ...
class RateLimitError(TransportError): ...
class ServiceUnavailableError(TransportError): ...
class ParseError(PublicDataError): ...
class InvalidRequestError(PublicDataError): ...
class ProviderResponseError(PublicDataError): ...
class UnsupportedCapabilityError(PublicDataError): ...
class DatasetNotFoundError(PublicDataError): ...
class ProviderNotRegisteredError(PublicDataError): ...
class CapabilityContractError(PublicDataError): ...
```

## 5. Bound Dataset object

A bound dataset object wraps `DatasetRef` plus registry/config context.

Suggested shape:

```python
class Dataset:
    ref: DatasetRef

    def list(self, **filters) -> RecordBatch: ...
    def schema(self) -> SchemaDescriptor | None: ...
    def call_raw(self, operation: str, **params) -> object: ...
```

## 6. What the model deliberately does not do

It does not attempt to fully standardize:

- every domain field
- every geographic key
- every date format
- every pagination style
- every schema guarantee

Those belong in provider-specific metadata, mappers, and raw payloads.

## 7. Normalization rule

Normalize only what is broadly useful across providers:

- paging metadata
- canonical error type
- dataset identity
- representation
- item list envelope

Do not erase provider-native detail.

---

## 관련 문서

### 이 저장소 내 문서
| 문서 | 설명 |
| :--- | :--- |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 시스템 아키텍처 설계 |
| [PROVIDER_ADAPTER_CONTRACT.md](./PROVIDER_ADAPTER_CONTRACT.md) | 어댑터 구현 규약 |
| [API_SPEC.md](./API_SPEC.md) | 파이썬 API 명세 |
| [VALIDATION.md](./VALIDATION.md) | 아키텍처 타당성 검증 |
