# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.7.0] — 2026-09-28

Mostly a security and correctness release. Users of 0.6.x should upgrade.

### Security

- API keys passed as query parameters (`params=`) no longer reach the exception chain, logs or tracebacks. This is the path datago, localdata, semas, sgis and every spec dataset use (#486).
- bok's key in the URL path and law's `OC` parameter are masked (#475); so are sgis `accessToken`, `consumer_key` and `consumer_secret` (#484).
- lofin no longer disables TLS certificate verification; only the cipher level is relaxed (#488).
- The spec executor refuses to send a provider credential to a host not listed for that provider (#532, #519).
- Error envelopes and tokens are no longer cached. Quota and key errors arrive as HTTP 200, so a momentary quota breach was served from cache for 24 hours (#490).

### Changed

- **BREAKING:** a declared numeric column is cast only when every value in it casts (#468), thousands separators are understood (`"1,200"` → `1200`), and `datago.apt_trade.dealAmount` is now an integer (#574). `list_all()` casts across all pages at once (#575). Consumers that relied on string values in these columns must adjust.
- **BREAKING:** an invalid `license` field in a spec now fails the load instead of being dropped (#476).
- 4xx responses are no longer retried (#490). A `Retry-After` beyond `TransportConfig.max_retry_delay` (default 60 s) raises a retryable `RateLimitError` instead of blocking (#477).
- krx rejects raw operation names it does not have (#493).

### Added

- `RecordBatch.validation`: a typed report of uncastable, missing and undeclared fields with counts and samples (#576, #582).
- `RecordBatch.meta["provenance"]`: fetch time, SHA-256 of the raw body, content type, cache hit, masked URL and parameters (#583).
- `kpubdata probe`: classify each dataset as reachable, needing 활용신청, needing parameters, or retired (#504).
- Spec request parameters exposed on `DatasetRef` metadata (#469); datago catalogue metadata enriched (#376).
- Spec datasets 18 → 23, including the ocean buoy observation spec (#446, marked unstable until checked against the live API); a `license` field in the spec schema (#443).

### Fixed

- data.go.kr gateway rejections are reported as such on the adapter and spec paths (#478, #485).
- The documented `localdata` / `semas` key names work; the shared datago key is still accepted (#492).
- `datasets.list()` no longer needs pandas (#487).
- HTTP errors carry `status_code`; a 429 that exhausts retries raises `RateLimitError`; the cache is written atomically and keeps `Content-Type` (#484, #496).
- localdata returns an empty result for `resultCode "03"`, drops phantom rows from empty wrappers, and handles a trailing slash in `base_url` (#482, #483).
- `datago.g2b_catalog` sends its required `inqryDiv` (#421).

### Removed

- Agent tool logs committed under `.omx/` (#485).

## [0.6.0] — 2026-09-09

### 제거 (Breaking)
- **폐기 서비스 데이터셋 141종 제거** (#412): localdata 136종, datago 5종(building_area·building_floor·building_recap_title·building_title·metro_path).
  2026-09-09 본문 전수 프로브(`tests/fixtures/batch-reclass.json`)로 NO_OPENAPI_SERVICE 확정.
  해당 catalogue 항목·fixture·테스트를 함께 제거했다. 활용신청 필요 94종은 유지(#409).

### 추가
- spec 기반 데이터셋 18종(골든 3 + air_station + ultra_srt_fcst + air_quality + ultra_srt_ncst + 부동산 6 + localdata 3 + airkorea_forecast + metro_fare) — `make verify` 4단계 기계 검증.
- 대량 전환 도구: `gen_specs_from_catalogue.py`·`batch_record.py`·`gen_example_scripts.py`.


### Recorded after release

These shipped in 0.6.0 but were left under Unreleased until 0.7.0.

- HTTP 전송 계층 로그/예외 메시지에서 API 키가 포함된 query parameter가 `[REDACTED]`로 마스킹되도록 수정 (#260)
- Canonical Query validation now prevents invalid canonical query values from reaching provider adapters (#264)
- `Dataset.list()` now validates canonical query parameters (`page`, `page_size`, `cursor`, `start_date`, `end_date`, `fields`, `sort`) before adapter invocation
- Canonical keys are now routed by name (not by type) to prevent bypass via type mismatch (e.g., `dataset.list(page="1")` now raises `InvalidRequestError` instead of falling through to filters)
- Date fields now reject empty strings and whitespace-only values
- All query validation errors now raise `InvalidRequestError` instead of generic `TypeError`/`ValueError`
- Query validation now performs type checking and basic value validation at Query creation time
- Empty cursor strings (`""`) are now rejected as invalid


## [0.5.0] - 2026-04-28

### Added
- `krx` provider — 한국거래소 시세 어댑터 (선택적 `pykrx` 백엔드, authless 구성). 새로운 `requires_api_key` 프로토콜 플래그와 `Client.iter_authenticated_providers()` 도입 (#199)
- `krx.kospi_index` — 코스피 지수 일별 시세 (#200)
- `krx.investor_flow` — 투자자별 순매수 추이 (`net_value = buy_value - sell_value`) (#200)
- `krx.market_valuation` — 시장 밸류에이션 지표 (per-day `get_market_fundamental_by_ticker` 집계) (#200)
- `bok.usd_krw` — 원/달러 환율 ECOS 일별 시세 (731Y003/0000003) (#197)
- `bok.bond_yield_3y` — 국고채 3년 ECOS 일별 시세 (817Y002/010200000) (#198)
- `kosis.industrial_production` — 광공업생산지수 (DT_1J22003) (#196)
- KOSIS 어댑터의 dataset-level `default_query_params` 지원 (objL1-objL8/itmId/prdSe/newEstPrdCnt/prdInterval allowlist; caller filters override defaults) (#196)
- `pandas-stubs` dev 의존성 추가로 `core/models.py`의 `# type: ignore` 제거
- ODcloud `provider_family` 프로토콜 지원: `api.odcloud.kr` 기반 엔드포인트를 위한 별도 페이지네이션(`page`/`perPage`) 및 응답 파싱(`data[]` 플랫 배열) 처리
- k-eco-navigator 연동용 3개 데이터셋 추가:
  - `datago.g2b_contract` — 나라장터 조달계약정보 (`apis.data.go.kr/1230000/ao/CntrctInfoService`)
  - `datago.social_enterprise` — 사회적기업 인증현황 (`api.odcloud.kr/api/socialEnterpriseList/v1`, ODcloud 프로토콜)
  - `datago.g2b_catalog` — 나라장터 종합쇼핑몰 품목정보 (`apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService`)

### Changed
- `social_enterprise` 데이터셋은 `apis.data.go.kr`이 아닌 `api.odcloud.kr` 엔드포인트 사용 (ODcloud 프로토콜)

### Removed
- `datago.coop` (협동조합 설립현황) 데이터셋 삭제 — 전국 단위 API 미존재 확인

## [0.3.1] - 2026-04-23

### Fixed
- Source `__version__` from `importlib.metadata` instead of hardcoded string (#127)
- Add 활용신청 (activation request) hint to datago 403 `AuthError` and document API key activation requirement (#128)
- Add required parameters to metro integration tests (#140)

## [0.3.0] - 2026-04-22

### Added
- `localdata` provider: expand permit datasets from 26 to **195**, covering all official KSIC categories — health (13), animal (18), culture (53), living (26), food (32), resources & environment (37), other (16)
- `sgis` provider adapter for administrative boundary GeoJSON datasets:
  - `sgis.boundary.sido`
  - `sgis.boundary.sigungu`
  - `sgis.boundary.emd`
- SGIS access-token authentication flow (`consumer_key` + `consumer_secret`) with in-memory token cache and refresh-on-auth-failure behavior
- Unit and contract tests plus SGIS fixture responses for boundary and auth/error scenarios
- Full fixture, unit test, and contract test coverage for all 195 localdata datasets

## [0.2.3] - 2026-04-19

### Fixed
- `LofinAdapter` SSL context ignored when `Client` passes shared transport

### Added
- 7 real estate transaction datasets to datago provider (`apt_rent`, `offi_trade`, `offi_rent`, `rh_trade`, `rh_rent`, `sh_trade`, `sh_rent`)
- Treat `resultCode` `'000'` as success for RTMS endpoints

## [0.2.2] - 2026-04-17

### Added
- Cursor pagination support and pagination documentation

## [0.2.1] - 2026-04-17

### Added
- `SUPPORTED_DATA.md` 실API 최종 검증일 컬럼 추가
- Single-page pagination contract and `list_all()` implementation

## [0.2.0] - 2026-04-17

### Added
- Single-page pagination contract for all adapters (datago, bok, lofin, kosis)
- `Dataset.list_all()` generator for automatic multi-page iteration
- `RecordBatch.to_pandas()` for pandas DataFrame conversion (optional `pandas` dependency)
- Unit tests for BOK and LOFIN adapters

### Changed
- Default `page_size` increased from 10 to 100
- **Breaking**: `query_records()` now returns a single page instead of auto-draining all pages

### Removed
- Unreachable single-record adapter stubs
- Single-record access from the provider and dataset public APIs

## [0.1.0] - 2026-04-10

### Added

- Core framework: `Client`, `Dataset`, `Catalog`, `Query`, `RecordBatch` public API
- Canonical error hierarchy with structured context (`PublicDataError` and subclasses)
- `DataGoAdapter` for data.go.kr with 6 curated datasets:
  - `datago.village_fcst` — KMA short-range forecast
  - `datago.ultra_srt_ncst` — KMA ultra short-term nowcast
  - `datago.air_quality` — real-time air quality (PM2.5/PM10)
  - `datago.bus_arrival` — Gyeonggi-do bus arrival info
  - `datago.hospital_info` — hospital/medical institution lookup
  - `datago.apt_trade` — MOLIT apartment trade price
- `BokAdapter` for ecos.bok.or.kr (Bank of Korea):
  - `bok.base_rate` — BOK base interest rate historical data
- `KosisAdapter` for kosis.kr (KOSTAT):
  - `kosis.population_migration` — inter-regional population migration statistics
- Environment-based configuration for all providers (`KPUBDATA_BOK_API_KEY`, `KPUBDATA_KOSIS_API_KEY`)
- Dataset discovery via `client.datasets.list()` and `client.datasets.search()`
- Record querying via `client.dataset("datago.village_fcst").list(**params)`
- Raw API escape hatch via `dataset.call_raw(operation, **params)`
- Schema metadata via `dataset.schema()` (catalogue-backed)
- XML and JSON response decoding with automatic content-type detection
- HTTP transport with configurable retry and exponential backoff
- Rate-limit aware retry with `Retry-After` header support (delta-seconds and HTTP-date)
- DEBUG-level request/response logging with credential redaction (`_sanitize_params`)
- Environment-based configuration (`KPUBDATA_DATAGO_API_KEY`)
- Provider adapter protocol with registration-time validation
- Contract test framework for adapter conformance
- GitHub Actions CI (lint, type check, test on Python 3.10–3.13, build)
- 90%+ unit test coverage for core framework modules (291 tests)
- PEP 257 docstrings for full public API surface
- MIT LICENSE
