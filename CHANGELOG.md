# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Security

- `RecordBatch.meta["provenance"]["url"]` no longer leaks the API key. It was masked with `str.replace` of the plain key, which missed a percent-encoded data.go.kr key (`+`, `/`, `=`) and a path-segment key; it is now masked by parameter name (including the spec's own auth parameter) and by every encoded form of the key, and omitted if a key form survives (#612).

### Added

- ADR 0006: the column-metadata contract separates storage type (`type`), meaning (`semantic_kind`: code, measure, date, period, text, flag) and display (reusing `FieldDescriptor.title` and `FieldConstraints.format`). Implementation is #651 (#644).
- `kpubdata.core.status` — one canonical dataset status vocabulary
  (`DatasetStatus`) with mappings from the spec, probe, `SUPPORTED_DATA.md` and
  production-grade vocabularies; `spec._STATUSES` and `_probe.PROBE_STATUSES` are
  now derived from it. ADR 0005 records the decision, and
  `tests/unit/test_status_vocabulary.py` fails when a design document uses a name
  the code does not define (#619).

- `kpubdata.core.status.transition()` — the pure dataset status state machine from `docs/DATASET_STATUS.md`. A table-driven test runs every row of that document's transition table against the function. `unstable` now also breaks immediately on a structural change, and `application_required` recovers on `HEALTHY` (#625).

### Fixed

- A provider-reported total of `0` is kept as `RecordBatch.total_count == 0` instead of becoming `None`, so "no results" and "count unknown" are distinguishable; a reported 0 explicitly ends paging (#642).
- `Client(...).dataset(...).list_all()` now reaches the spec path with column casting decided across all pages. `CompositeProviderAdapter` had no `query_records_all`, so every spec dataset reached through `Client` still cast per page and a column could be `int` on one page and `str` on the next — the split 0.7.0 recorded as fixed (#611).
- `docs/status.md` no longer depends on the calendar: "recent" is measured from the newest `last_verified`, so `--check` stops failing every pull request from 2026-12-09. It also counts all six SUPPORTED_DATA levels instead of three (#620).
- `docs/DATASET_STATUS.md` and `docs/LIVE_PROBE.md` contradicted each other and the
  code: the failure threshold (3 against "2+"), code 32's classification, the
  `PARAM_CHANGED` spelling, a nonexistent dataset key, a nonexistent module and the
  neis/fds key sharing claim (#619).

### Fixed

- `scripts/release_notes.py promote` for a final version folds that version's pre-release sections (`aN`, `bN`, `rcN`) into one section, instead of failing with "nothing to release" after a pre-release. A `prerelease` command and the release-notes action's `prerelease` output tell the release job to mark a pre-release (#622).

### Fixed

- The spec-dataset `list_all()` path honours `page_size`, `max_size` and `max_pages` (#614). `page_size` drives pagination instead of going out as a raw `page_size` parameter; a `page_size` above the spec's `max_size` no longer ends the walk after the first page; exceeding `max_pages` raises `InvalidRequestError` like the legacy path instead of truncating silently; and each batch keeps its own `raw`, `meta["provenance"]`, `next_page` and `validation`, with the whole-result report in `meta["validation_total"]`. The path still buffers every page before the first batch, because casting is decided across all pages (#481); this is now documented.
- The field validation report no longer miscounts (#615): a 0-row page is reported clean instead of every declared field being `missing`; numeric null markers (`""`, `"-"`) count as nulls rather than non-null values; undeclared columns are detected across all records, not only the first.

### Changed

- **BREAKING:** code columns keep their leading zeros and come back as `str` (#613). Declared `string` now: `apt_trade` `bonbun`/`bubun`/`roadNmBonbun`/`roadNmBubun`/`roadNmSeq`, `apt_rent` `roadnmbonbun`/`roadnmbubun`, `hospital_info` `clCd`/`postNo`, `metro_fare` `arvlStnCd`/`dptreStnCd`, `tour_kor_*` `zipcode`, `village_fcst` `fcstTime`. As a safety net, a zero-led value (`"06102"`) no longer casts to a number, so a code column declared numeric stays text and is reported `uncastable`. Replay verification (`make verify`) now also fails when normalization drops a leading zero. See kpubdata-builder#702.
- `FieldIssue.kind` and `ValidationReport.issues_of()` take the `IssueKind` literal (`"uncastable"`, `"missing"`, `"undeclared"`); `issues_of()` raises `ValueError` on an unknown kind instead of silently returning nothing (#615).

### Added

- `ValidationReport.to_dict()` returns a JSON-serialisable form of the report (#615).
- Provenance now reports `cached=True` for responses served from the response cache, and `fetched_at` keeps the original fetch time instead of the time of the cache read. The transport marks a cache hit in `httpx.Response.extensions`, and `ResponseCache.get_entry()` returns the stored `created_at` (#616).

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

### Removed (Breaking)
- **Removed 141 datasets for retired services** (#412): 136 localdata, 5 datago (building_area·building_floor·building_recap_title·building_title·metro_path).
  Confirmed NO_OPENAPI_SERVICE by a full probe of response bodies on 2026-09-09 (`tests/fixtures/batch-reclass.json`).
  The corresponding catalogue entries, fixtures and tests are removed with them. The 94 that need 활용신청 are kept (#409).

### Added
- 18 spec-based datasets (3 golden + air_station + ultra_srt_fcst + air_quality + ultra_srt_ncst + 6 real estate + 3 localdata + airkorea_forecast + metro_fare) — machine-verified by the 4 stages of `make verify`.
- Bulk conversion tools: `gen_specs_from_catalogue.py`·`batch_record.py`·`gen_example_scripts.py`.


### Recorded after release

These shipped in 0.6.0 but were left under Unreleased until 0.7.0.

- HTTP transport layer logs/exception messages now mask query parameters containing API keys as `[REDACTED]` (#260)
- Canonical Query validation now prevents invalid canonical query values from reaching provider adapters (#264)
- `Dataset.list()` now validates canonical query parameters (`page`, `page_size`, `cursor`, `start_date`, `end_date`, `fields`, `sort`) before adapter invocation
- Canonical keys are now routed by name (not by type) to prevent bypass via type mismatch (e.g., `dataset.list(page="1")` now raises `InvalidRequestError` instead of falling through to filters)
- Date fields now reject empty strings and whitespace-only values
- All query validation errors now raise `InvalidRequestError` instead of generic `TypeError`/`ValueError`
- Query validation now performs type checking and basic value validation at Query creation time
- Empty cursor strings (`""`) are now rejected as invalid


## [0.5.0] - 2026-04-28

### Added
- `krx` provider — Korea Exchange market data adapter (optional `pykrx` backend, authless configuration). Introduces a new `requires_api_key` protocol flag and `Client.iter_authenticated_providers()` (#199)
- `krx.kospi_index` — KOSPI index daily data (#200)
- `krx.investor_flow` — net purchase trend by investor type (`net_value = buy_value - sell_value`) (#200)
- `krx.market_valuation` — market valuation indicators (per-day `get_market_fundamental_by_ticker` aggregation) (#200)
- `bok.usd_krw` — KRW/USD exchange rate ECOS daily data (731Y003/0000003) (#197)
- `bok.bond_yield_3y` — 3-year government bond ECOS daily data (817Y002/010200000) (#198)
- `kosis.industrial_production` — Mining and Manufacturing Production Index (DT_1J22003) (#196)
- Dataset-level `default_query_params` support in the KOSIS adapter (objL1-objL8/itmId/prdSe/newEstPrdCnt/prdInterval allowlist; caller filters override defaults) (#196)
- Add the `pandas-stubs` dev dependency and remove the `# type: ignore` in `core/models.py`
- ODcloud `provider_family` protocol support: separate pagination (`page`/`perPage`) and response parsing (`data[]` flat array) for `api.odcloud.kr`-based endpoints
- 3 datasets added for the k-eco-navigator integration:
  - `datago.g2b_contract` — KONEPS procurement contract information (`apis.data.go.kr/1230000/ao/CntrctInfoService`)
  - `datago.social_enterprise` — social enterprise certification status (`api.odcloud.kr/api/socialEnterpriseList/v1`, ODcloud protocol)
  - `datago.g2b_catalog` — KONEPS shopping mall product information (`apis.data.go.kr/1230000/at/ShoppingMallPrdctInfoService`)

### Changed
- The `social_enterprise` dataset uses the `api.odcloud.kr` endpoint rather than `apis.data.go.kr` (ODcloud protocol)

### Removed
- Remove the `datago.coop` (cooperative establishment status) dataset — confirmed that no nationwide API exists

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
- Add a real-API last-verified-date column to `SUPPORTED_DATA.md`
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

## [0.1.0] - 2026-04-17

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
- `LofinAdapter` for lofin365.go.kr (지방재정365, local government finance) (#105):
  - `lofin.expenditure_budget`, `lofin.expenditure_function`, `lofin.revenue_budget`,
    `lofin.debt_ratio`, `lofin.fiscal_independence`
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
