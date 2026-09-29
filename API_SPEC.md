# Public API specification — KPubData

## 1. Top-level API

```python
from kpubdata import Client
```

## 2. Client construction

### Explicit construction

```python
client = Client(
    provider_keys={
        "datago": "...",
        "seoul": "...",
    },
    timeout=10.0,
    cache=True,
    cache_ttl_seconds=3600,
)
```

`Client(...)` supports these transport/cache options:

- `timeout: float = 30.0`
- `max_retries: int = 3`
- `cache: bool | ResponseCache = False`
  - `False`: disable cache (default)
  - `True`: use default disk cache directory
  - `ResponseCache(...)`: use a caller-supplied cache instance
- `cache_ttl_seconds: int = 86400`

### Environment construction

```python
client = Client.from_env()
```

`Client.from_env()` additionally honors:

- `KPUBDATA_CACHE=1`
- `KPUBDATA_CACHE_DIR=/custom/cache/path`
- `KPUBDATA_CACHE_TTL=3600`

## 3. Discovery API

```python
client.datasets.list()
client.datasets.list(provider="datago")
client.datasets.search("예보")
client.datasets.search("forecast", provider="datago")
client.datasets.search("weathr", threshold=0.5)  # fuzzy match
client.dataset("datago.apt_trade")
```

### Search behavior

`search(text, *, provider=None, threshold=0.5)` scores each dataset against
*text* using substring, token-overlap, and fuzzy matching across **name**,
**description**, **tags**, **id**, **dataset_key**, and **provider**. Results are
returned in descending relevance order.

- **Exact substring** match in any field → score 1.0 (always included).
- **Fuzzy match** via `difflib.SequenceMatcher` → included if score ≥ *threshold*.
- **threshold** default is `0.5`.  Raise it (e.g. `0.8`) for stricter results,
  lower it (e.g. `0.2`) for broader recall.

Each `DatasetRef` returned by discovery exposes:
- `id`, `provider`, `dataset_key`, `name`, `representation`, `operations`
- `description`: human-readable summary (may be ``None``)
- `tags`: categorization keywords as a tuple (e.g. ``("weather", "forecast")``)
- `source_url`: link to original API documentation (may be ``None``)

## 4. Bound dataset operations

### List/query

```python
dataset = client.dataset("datago.apt_trade")
result = dataset.list(lawd_code="11680", deal_ym="202503")
```

`list()` returns exactly one page of results. When another page is available,
the returned `RecordBatch.next_page` is set.

### List all pages

```python
dataset = client.dataset("datago.apt_trade")
for batch in dataset.list_all(lawd_code="11680", deal_ym="202503"):
    for item in batch.items:
        print(item)
```

`list_all()` yields one `RecordBatch` per page and follows `next_page`
automatically until pagination is exhausted.

Dataset metadata may expose provider-specific pagination styles through
`DatasetRef.query_support.pagination`, including `offset`, `cursor`, and
index-window based `index` pagination.

#### Query validation

`list()` validates canonical query parameters and raises `InvalidRequestError` for invalid values before provider invocation:

| Parameter | Accepted values |
|---|---|
| `page` | `None` or positive integer (`>= 1`) |
| `page_size` | `None` or positive integer (`>= 1`) |
| `cursor` | `None` or non-empty string |
| `start_date`, `end_date` | `None` or non-empty string (provider-specific format) |
| `fields`, `sort` | `None` or `list[str]` |

Other kwargs are passed as provider-specific filters to the adapter. For example, `dataset.list(region="11", custom_param="value")` passes `{"region": "11", "custom_param": "value"}` as provider-specific filters.

**Provider-specific rules** (enforced by adapters):
- Required provider parameters (e.g., some datasets require `start_date`/`end_date`)
- Provider-specific date formats (e.g., `YYYYMM` vs `YYYYMMDD`)
- Provider-specific maximum page size

### Schema

```python
schema = dataset.schema()
```

### Raw

```python
raw = dataset.call_raw(operation="list", lawd_code="11680", deal_ym="202503")
```

## 5. Convenience aliases

Optional convenience aliases may be added for common datasets, but only if they do not obscure the canonical dataset id.

Example:

```python
client.apartment_trades.list(lawd_code="11680", deal_ym="202503")
```

Rules:

- convenience aliases are secondary
- docs should always show the canonical `client.dataset(...)` path

## 6. Return values

### `list()`

Returns `RecordBatch`.

`RecordBatch.validation` is a `ValidationReport | None` (`None` when the adapter did
not run field-level validation). A report holds `issues: tuple[FieldIssue, ...]` and
exposes:

| Member | Description |
|---|---|
| `ok` | `True` when there are no issues |
| `issues_of(kind)` | Issues of one `IssueKind` (`"uncastable"`, `"missing"`, `"undeclared"`); raises `ValueError` for an unknown kind |
| `to_dict()` | JSON-serialisable `{"ok": bool, "issues": [...]}` |

Counts are taken on the value the cast sees, so numeric null markers (`""`, `"-"`)
count as nulls. A page with no records produces an empty (ok) report.

### `list_all()`

Returns a generator of `RecordBatch` values, one per page.

### `schema()`

Returns `SchemaDescriptor | None`.

`SchemaDescriptor.fields` contains `FieldDescriptor` objects. Each `FieldDescriptor` may carry a `constraints: FieldConstraints | None` with structured metadata:

| Attribute | Type | Description |
|---|---|---|
| `max_length` | `int \| None` | Maximum character length |
| `min_value` | `float \| None` | Minimum numeric value |
| `max_value` | `float \| None` | Maximum numeric value |
| `pattern` | `str \| None` | Regex pattern |
| `allowed_values` | `tuple[str, ...] \| None` | Permitted values |
| `format` | `str \| None` | Semantic format hint (e.g. `"YYYYMM"`) |

### `call_raw()`

Returns provider-native payload / response object.

## 7. Public API promises

KPubData promises stability for:

- `Client`
- `Client.from_env()`
- dataset discovery methods
- `Dataset.list/list_all/schema/call_raw`
- canonical model classes
- canonical error types

KPubData does **not** promise stability for:

- internal adapter helper functions
- internal transport implementation details
- provider-specific metadata layout beyond documented keys

## 8. Anti-goals for the API surface

Avoid turning the public API into:

- copied endpoint names from providers
- a giant generic `query()` with dozens of weakly-defined arguments
- a mandatory dataframe API
- a fake SQL-like language

## 9. Suggested usage style

Preferred:

```python
client.dataset("seoul.subway_realtime_arrival").list(station_name="강남")
```

Acceptable advanced usage:

```python
client.dataset("seoul.subway_realtime_arrival").call_raw(operation="list", stationNm="강남")
```

Discouraged as the main public entry point:

```python
client.call_provider_endpoint("seoul", "SearchSTNTimeTableByIDService", ...)
```

## 10. CLI

설치 후에는 콘솔 스크립트 `kpubdata`를 사용할 수 있습니다.

- 데이터셋 목록: `kpubdata datasets list`
- 메타데이터 확인: `kpubdata datasets show <dataset_id>`
- 정규화 조회: `kpubdata fetch <dataset_id> ...`
- Raw 호출: `kpubdata raw <dataset_id> <operation> ...`

상세 사용법, 출력 형식, 종료 코드, 환경 변수 연동은 [docs/cli.md](./docs/cli.md)를 참고하세요.

---

## 관련 문서

### 이 저장소 내 문서
| 문서 | 설명 |
| :--- | :--- |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 시스템 아키텍처 설계 |
| [CANONICAL_MODEL.md](./CANONICAL_MODEL.md) | 표준 데이터 모델 정의 |
| [PROVIDER_ADAPTER_CONTRACT.md](./PROVIDER_ADAPTER_CONTRACT.md) | 어댑터 구현 규약 |
| [VALIDATION.md](./VALIDATION.md) | 아키텍처 타당성 검증 |

### KPubData Product Family
| 저장소 | 문서 | 설명 |
| :--- | :--- | :--- |
| [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder) | [API_CONTRACT.md](https://github.com/yeongseon/kpubdata-builder/blob/main/API_CONTRACT.md) | Builder API 규약 |
| [kpubdata-studio](https://github.com/yeongseon/kpubdata-studio) | [API_CONTRACT.md](https://github.com/yeongseon/kpubdata-studio/blob/main/API_CONTRACT.md) | Studio API 규약 |
