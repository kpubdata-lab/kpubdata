# PRD — KPubData

## 1. Document information

- Product name: `KPubData`
- Product type: Python data access framework / SDK
- Target runtime: Python 3.10+
- Primary users: Python developers, backend developers, data engineers, agent/MCP developers
- Product stage: active development — current release `v0.9.0` (see §2-current status)

## 2-current. 현재 제품 상태 (Current status — v0.9.0)

> 이 절은 현재 실제로 출시된 제품 계약을 요약한다. 원래 초기 계획(§13 릴리스 계획의 v0.1)은 역사적 기록으로 보존하되, 아래 내용이 현재 기준이다.

- **현재 버전**: `v0.9.0` (`pyproject.toml` 기준). PRD 초안이 가정한 "architecture and bootstrap" 단계를 이미 넘어섰다.
  - 이것은 **SDK 자신의 버전**이다. Builder·Studio 와 함께 검증된 **지원 조합**은 별개이며 [docs/compatibility.md](./docs/compatibility.md) 1절과 `compatibility.json` 이 단일 출처다. 지원 조합은 Builder·Studio 릴리스 때에만 바뀌므로 SDK 버전이 그보다 앞서 있는 것이 정상이다.
- **지원 provider**: 내장 provider는 `bok`, `datago`, `fds`, `kipris`, `korean`, `kosis`, `krx`, `law`, `localdata`, `lofin`, `neis`, `semas`, `seoul`, `sgis` 14개이며(`src/kpubdata/providers/manifest.py`), 하나의 공개 인터페이스 아래 통합되어 있다. 정확한 데이터셋 수와 검증 수준은 [SUPPORTED_DATA.md](./SUPPORTED_DATA.md)를 단일 출처로 참조한다.
- **핵심 API**: `Client` / `Client.from_env()`, `client.datasets.list()/search()`, `client.dataset(...)`, `dataset.list()/list_all()/schema()/call_raw()`, `client.probe()/probe_all()`, `DatasetRef`(+`status`, `to_dict()`), `RecordBatch`(+`validation`, `to_pandas()`).
- **CLI**: `kpubdata` 명령이 함께 설치되며 `datasets list/show`, `fetch`, `raw`, `probe`, `scaffold provider` 서브커맨드를 제공한다.
- **부가 기능**: 디스크 기반 응답 캐시(TTL), pandas 변환(`kpubdata[pandas]`), 전체 페이지 자동 순회(`list_all()`).
- **여전히 유효한 비목표**: async 지원 없음, MCP/HTTP 서비스 레이어는 코어에 미포함(별도 레포로 분리 예정).

> 향후 계획은 [ROADMAP.md](./ROADMAP.md), 버전별 변경 이력은 CHANGELOG를 단일 출처로 참조한다.
## 2. Problem statement

Korean public-data APIs are difficult to use consistently because they vary by provider and service family in:

- authentication conventions
- parameter naming and validation
- response envelopes and error signaling
- representation format (JSON, XML, file, sheet, mixed)
- pagination semantics
- schema stability and metadata quality

As a result, developers repeatedly rebuild the same glue code:

- auth/key injection
- request construction
- XML/JSON parsing
- result normalization
- provider-specific error handling
- schema probing
- debugging around raw payloads

## 3. Product vision

KPubData will provide a **Pythonic, dataset-oriented, provider-aware** framework for accessing Korean public-data services through a small canonical core, while preserving the ability to drop down to provider-specific/raw behavior when needed.

## 4. Product definition

KPubData is **not** a single fake standard API.
It is a **dialect-inspired integration layer**:

- a stable core defines canonical contracts
- adapters absorb provider differences
- users interact through a consistent dataset-oriented Python API

## 5. Target users

### 5.1 Application developers

Need to integrate Korean public data into product features without learning every provider from scratch.

### 5.2 Data engineers / analysts

Need repeatable access, metadata visibility, and raw/debug paths for pipelines.

### 5.3 Agent / MCP developers

Need a stable core library so that the future MCP layer can remain thin.

### 5.4 Contributors

Need a predictable adapter contract and a clear definition of done when adding a provider.

## 6. Jobs to be done

1. Discover datasets/services without manually browsing each portal.
2. Query datasets through a consistent Python entry point.
3. Know which operations each dataset supports.
4. Access raw payloads when normalization is insufficient.
5. Add a new provider adapter without changing the whole framework.

## 7. Product principles

1. **Dataset-oriented, provider-aware**
2. **Small stable core, provider complexity pushed outward**
3. **Capability-first honesty**
4. **Canonical + raw together**
5. **Modern Python packaging and typing discipline**
6. **Agentic-development friendly repository structure**

## 8. Goals

### 8.1 Product goals

- provide a canonical query/result/error/capability model
- support multiple heterogeneous provider families under one public interface
- preserve provider identity and raw access
- keep the public API small and learnable
- make adapter authoring systematic

### 8.2 Success criteria for the first meaningful release

- three materially different provider/service families integrated
- each provider passes contract tests for its declared capabilities
- first successful query possible within 10 minutes for a developer with keys
- public API docs cover common discovery and query workflows
- raw access remains available in every provider adapter

## 9. Non-goals for v0.1

- complete coverage of all Korean public-data APIs
- universal query language across all providers
- async support
- built-in scheduling/caching/warehouse loading
- full MCP server in the initial release
- full field-level semantic standardization across every provider

## 10. Functional requirements

### FR-1. Client initialization

The framework must support explicit config and environment-based config.

Acceptance:

- `Client(...)`
- `Client.from_env()`
- provider key lookup order documented

### FR-2. Provider registry

The framework must register and retrieve provider adapters by identifier.

Acceptance:

- duplicate registration blocked
- lazy loading allowed
- adapter metadata available

### FR-3. Dataset discovery

Users must be able to list and search dataset descriptors.

Acceptance:

- `client.datasets.list()`
- `client.datasets.search(text)`
- each descriptor exposes `id`, `provider`, `name`, `representation`, `operations`
- each descriptor exposes its recorded verification `status` and a JSON-serialisable `to_dict()`

### FR-4. Dataset binding

Users must be able to bind a dataset reference into an object with operations.

Acceptance:

- `client.dataset("provider.dataset")`
- unknown dataset raises a clear exception

### FR-5. Record listing/query

A list/query operation must return a canonical result envelope.

Acceptance:

- `dataset.list(...)`
- returns `RecordBatch`
- includes `items`
- includes `raw`
- includes metadata about pagination and provider
- includes a field-level `validation` report when the adapter ran one

### FR-6. Schema/metadata access

Datasets may expose schema or field metadata.

Acceptance:

- `dataset.schema()`
- returns `SchemaDescriptor | None`

### FR-7. Raw access

Every provider adapter must expose a raw-call path.

Acceptance:

- `dataset.call_raw(...)` or provider raw call equivalent
- raw payload preserved without normalization loss

### FR-8. 대량 페이지네이션 (Bulk pagination)

사용자는 여러 페이지를 수동으로 순회하지 않고 전체 결과를 받을 수 있어야 한다.

Acceptance:

- `dataset.list_all(...)`가 페이지를 자동 순회하며 `RecordBatch`를 생성(yield)한다
- 각 provider의 페이지네이션 규칙 차이를 호출자가 알 필요 없다
- spec 기반 데이터셋은 컬럼 타입을 전체 결과에 대해 한 번에 결정하므로, 모든 페이지를 가져온 뒤에 첫 `RecordBatch`를 내보낸다 (어댑터의 `query_records_all`)

### FR-9. Error normalization

Provider-specific failures must map to canonical error types.

Acceptance:

- transport, auth, parse, unsupported capability, and provider-response failures mapped explicitly
- original status/message retained in exception metadata

### FR-10. Representation handling

The framework must support multiple content and representation types through adapters.

Acceptance:

- XML and JSON in core scope
- representation metadata attached to dataset descriptors
- file/sheet/download capability represented even if not normalized in v0.1

### FR-11. CLI

프레임워크는 설치 시 `kpubdata` 명령을 함께 등록해 간단한 탐색·조회를 스크립트 없이 지원해야 한다.

Acceptance:

- `kpubdata datasets list` / `datasets show`
- `kpubdata fetch <dataset> -p key=value ... --format ...`
- `kpubdata raw` (원본 호출 비상구)
- `kpubdata scaffold provider` (provider 어댑터 스캐폴딩)

### FR-12. Tabular 변환

결과 envelope는 선택적으로 pandas DataFrame으로 변환될 수 있어야 한다.

Acceptance:

- `RecordBatch.to_pandas()`
- pandas는 선택 의존성(`kpubdata[pandas]` extra)으로 분리

### FR-13. 응답 캐싱

반복 호출 비용을 줄이기 위해 선택적 디스크 캐시를 지원해야 한다.

Acceptance:

- 디스크 기반 응답 캐시 활성화/비활성화
- TTL 및 캐시 정리 지원 (자세한 내용은 [docs/caching.md](./docs/caching.md))

## 11. Non-functional requirements

### NFR-1. Python quality bar

- Python 3.10+
- type hints throughout public API
- `pyproject.toml` packaging
- `src/` layout

### NFR-2. Quality gates

- lint
- format
- typecheck
- unit tests
- contract tests

### NFR-3. Public API stability

- public contracts documented
- breaking changes require changelog and versioning discipline

### NFR-4. Observability and debugging

- raw response access
- structured exception metadata
- optional logging hooks

## 12. UX requirements

The API must read like Python, not like a copied portal endpoint name.

Preferred style:

```python
client.dataset("molit.apartment_trades").list(lawd_code="11680", deal_ym="202503")
```

Avoid as the primary public surface:

```python
client.getRTMSDataSvcAptTradeDev(...)
```

## 13. Release plan

> **참고**: 아래는 초기 릴리스 계획(역사적 기록)이다. v0.1·v0.2는 출시 완료(✅)되었고 provider 확장은 v0.9까지 계속 진행되었다. 최신·향후 계획은 [ROADMAP.md](./ROADMAP.md)를 단일 출처로 참조한다. (예: MCP 어댑터는 코어에 포함하지 않고 별도 레포로 분리 예정.)

### v0.1 ✅

- core contracts
- sync transport
- 3 adapters
- XML/JSON
- raw access
- tests/docs/release skeleton

### v0.2 ✅

- richer discovery metadata
- plugin loading
- pandas adapter
- broader provider coverage

### v0.3

- thin MCP adapter
- provider scaffolding tools
- improved docs/examples

## 14. Risks

1. Over-abstracting into a fake universal API
2. Letting one provider's quirks contaminate the core model
3. Under-investing in raw/debug paths
4. Treating dataset metadata as optional rather than foundational
5. Allowing the public API surface to grow too fast

## 15. Mitigations

- keep the canonical core intentionally small
- add capabilities instead of pretending support exists
- enforce adapter contract tests
- keep raw access mandatory
- require architecture documentation for public-surface changes

---

## 관련 문서

### 이 저장소 내 문서
| 문서 | 설명 |
| :--- | :--- |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | 시스템 아키텍처 설계 |
| [ROADMAP.md](./ROADMAP.md) | 프로젝트 로드맵 및 단계별 계획 |
| [API_SPEC.md](./API_SPEC.md) | 파이썬 API 명세 |

### KPubData Product Family
| 저장소 | 문서 | 설명 |
| :--- | :--- | :--- |
| [kpubdata-builder](https://github.com/kpubdata-lab/kpubdata-builder) | [PRD.md](https://github.com/kpubdata-lab/kpubdata-builder/blob/main/PRD.md) | Builder 제품 요구사항 |
| [kpubdata-studio](https://github.com/kpubdata-lab/kpubdata-studio) | [PRD.md](https://github.com/kpubdata-lab/kpubdata-studio/blob/main/PRD.md) | Studio 제품 요구사항 |
