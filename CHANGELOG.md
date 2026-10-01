# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Evidence bound to the spec, the commit and the run** (#522, #713): a recorded fixture's `meta.json` now carries `spec_sha256`, a digest of the spec file's pipeline-relevant content (`kpubdata.core.spec.spec_file_digest`, which normalises away the `last_verified` line the recorder itself rewrites), and `record_commit`/`run_ref` from the CI environment (`GITHUB_SHA`/`GITHUB_RUN_ID`) when present. `make verify` gains a spec-binding step: a fixture whose recorded digest no longer matches its spec is void — the spec changed after recording — and fails with re-record guidance. Fixtures recorded before the digest existed are reported as legacy evidence rather than failed — since #717, only those on a frozen baseline.
- **Public probe API** (#694): `Client.probe(dataset_id) -> ProbeResult | None` and `Client.probe_all(*, provider=None) -> list[ProbeResult]` classify reachability with the client's own keys, and `ProbeResult` and `PROBE_STATUSES` (the ADR 0005 `ProbeStatus` vocabulary) are exported from `kpubdata`. Probing keeps its fast-fail transport (`PROBE_TIMEOUT_SECONDS`, `PROBE_RETRIES`, no cache), and a run shares one transport that is closed at the end — previously every dataset opened its own and none was closed. `kpubdata probe` now goes through these methods; its output and report are unchanged, and it now honors the global `--provider-key` option, which it silently ignored before.
- **Explicit-keys-only mode** (#694): `Client(..., env_keys=False)` (backed by `KPubDataConfig.env_fallback`) uses only `provider_keys` and never reads a credential from the environment — not `KPUBDATA_<P>_API_KEY`, `<P>_API_KEY` or `KPUBDATA_SGIS_CONSUMER_SECRET`. A service probing with a user's key no longer has a missing entry silently filled with the operator's key. With no key the probe makes no call and reports `auth_unknown`. The default (`env_keys=True`) is unchanged.
- **R3 review gate** (#722, kpubdata-builder#905): a pull request labelled `review:R3` now needs an approval from someone other than its author before it can merge. `scripts/r3_review.py`, wrapped by the `.github/actions/r3-review` composite action, is the one implementation all four repositories call; the `R3 review` workflow runs it on every pull request (passing when it is not R3) and again on label changes, pushes and review submissions or dismissals, with `pull-requests: read` only. Each reviewer's latest approving or change-requesting review decides; approvals on an older head count, as with branch protection's stale-approval dismissal off; the author, bots and accounts without write access do not count. POLICY 14.1 and AGENTS.md describe it. `R3 review` becomes a required status check next to `CI gate`; the approval count in branch protection stays at 0.

### Changed

- **CODEOWNERS covers the evidence path** (#715): `scripts/record.py`, `scripts/verify_spec.py`, `scripts/check_fixture_authorship.py`, the recorded fixtures and the whole `src/kpubdata/specs/` tree (previously only `schema.json`) now need a code owner's review, because whoever changes them changes what "verified" means. `tests/unit/test_codeowners.py` checks glob patterns too: a wildcard entry must match at least one file, since GitHub silently ignores a pattern that matches nothing. Enforcing code-owner review in branch protection stays a person's decision (POLICY 14).
- **Release rule** (#685): kpubdata now releases on demand — when a downstream repository is blocked, for a security fix, or for accumulated changes — at most once every seven days, and is no longer part of the monthly release week, which stays for kpubdata-builder and kpubdata-studio. `scripts/release_window.py`, wrapped by the `.github/actions/release-window` composite action, is the one implementation: `on-demand` refuses a release less than seven days after the last final GitHub Release, `monthly` refuses outside the Monday-to-Sunday week holding the month's last Thursday, both in KST, and a critical patch passes either only when it names its issue (`critical_patch`/`critical_issue` inputs, or a `Critical-Patch: #N` line in the release pull request). `release.yml` runs it first on both the prepare and the release path; a dry run reports the decision without stopping. `docs/compatibility.md` §5.1, AGENTS.md and POLICY say the same.

### Fixed

- The `R3 review` failure message cites POLICY 14.1, the section that defines the gate, instead of sections 14 and 25 (#722).
- `datago.air_quality`'s licence contradicted itself: its attribution and `redistribution: forbidden` follow the source's KOGL type 3 (attribution, no modification), but it said `type: 공공누리_1유형` and `modification_allowed: true`. It now says `공공누리_3유형` and `modification_allowed: false` (#719). A spec whose KOGL type contradicts an explicit `commercial_use: true` (types 2 and 4) or `modification_allowed: true` (types 3 and 4) now fails to load, so a consumer reading the type and one reading the flag cannot be told two different things.
- A missing or null spec digest no longer passes as legacy evidence (#717). #713 (#522) let any fixture whose meta had no non-empty `spec_sha256` through `make verify` as legacy, so deleting the key or setting it to `null`/`""` unbound a fixture from its spec in one edit, and `scripts/record.py` wrote `"spec_sha256": null` when it could not read the spec. Legacy is now the frozen baseline `scripts/legacy_evidence_baseline.txt` — the 28 fixtures tracked without a digest — and only a listed fixture whose meta has no `spec_sha256` key passes unbound; any other missing, `null` or `""` digest fails the spec-binding step. The baseline is a ratchet: it fails when it grows past 28, repeats an entry, or keeps an entry that no longer exists or now carries a digest. `scripts/record.py` stops before calling or writing anything when it cannot compute the digest. The baseline is code-owned like the recorder and verifier.
- The release workflows after #683 (ref validation): `publish-pypi.yml`'s tag pattern was written `\\.`, which grep reads as a literal backslash, so no version tag matched and every dispatched publish failed — it is one pattern now, `v0.8.0` and `v0.7.1a1` match and `v0.8` does not. The ref is validated on the `release: published` path too, reaches the shell through the environment instead of `${{ inputs.ref }}`, must be a tag in this repository and must be on `main` (`git merge-base --is-ancestor`). In `release.yml` the merge path only fires for pull requests into `main`, a re-run after the tag was pushed but `gh release create` failed finishes the release when the tag is on the same commit instead of stopping at "tag must not exist", and the `release` concurrency group moved from the workflow to the two jobs, so ordinary pull requests closing no longer queue in it and cannot cancel a waiting release. #683 itself had no CHANGELOG entry: it makes a release run only from `main` and validates the publish ref.

### Security

- Configured keys are masked out of `ProbeResult.detail` by value (every percent-encoded form) before the message is truncated, so a key cut at the boundary cannot survive as a prefix (#694).
- httpx's own INFO line `HTTP Request: GET <url> ...` carried the query string, and with it a data.go.kr `serviceKey`, verbatim. A filter on the `httpx` logger now masks the credential parameters named in `SENSITIVE_PARAM_KEYS` (#694).

### Documentation

- Docs follow the 2026-09-30 decisions (#695): the compatibility page names the three products and the one-way dependency (Studio → Builder → KPubData) and moves the `main` row to kpubdata 0.8.0 with Builder's `>=0.8.0,<0.9` pin; TERMINOLOGY says Builder owns the Access vocabulary; `RELEASE_POLICY.md` points to §5.1 for cadence, adds the `release-window` step, and states the real latest releases; PACKAGING describes the window gate, the manual release-PR step while Actions cannot open PRs, and re-runs after #687; SECURITY no longer says versions and tags are being reconciled.

## [0.8.0] — 2026-09-30

### Security

- `RecordBatch.meta["provenance"]["url"]` no longer leaks the API key. It was masked with `str.replace` of the plain key, which missed a percent-encoded data.go.kr key (`+`, `/`, `=`) and a path-segment key; it is now masked by parameter name (including the spec's own auth parameter) and by every encoded form of the key, and omitted if a key form survives (#612).
- Dependencies with known vulnerabilities are upgraded in `uv.lock` (kpubdata-builder#691). pip-audit over every extra reported 87 findings (48 distinct advisories) in 14 packages; none remain. urllib3 2.6.3 → 2.8.0, idna 3.11 → 3.20, cryptography 46.0.6 → 50.0.1, pyjwt 2.12.1 → 2.15.1, pillow 12.2.0 → 12.3.0, mcp 1.26.0 → 2.2.0 (with starlette 1.7.0, python-multipart 0.0.32, click 8.5.0; anyio 4.14.2 on Python < 3.12 and 4.15.1 on ≥ 3.12, typing-extensions 4.15.0 / 4.16.0 likewise; adds httpx2, httpcore2, httpx2-jsfetch, truststore, opentelemetry-api and mcp-types; drops httpx-sse, python-dotenv and pydantic-settings), pytest 9.1.1, mkdocs-material 9.7.7, pymdown-extensions 12.1 — all inside the declared ranges, so only the lock moves. The gitleaks secret scan over the full history now runs in CI and gates merges through `CI gate`; a `Security` workflow runs pip-audit over the locked dependencies (for Python 3.10 and 3.12, so both sides of the `< 3.12` markers are audited) and CodeQL on every pull request and weekly — gating those two is left to #631.

### Added

- Spec fields can declare `semantic_kind` (`code`, `measure`, `date`, `period`, `text`, `flag`), `title` and `format` (ADR 0006). `Dataset.schema()` returns them as `FieldDescriptor.semantic_kind`, `FieldDescriptor.title` and `FieldConstraints.format`. A kind that contradicts the storage type, a numeric transform on a `code`, a `unit` on anything but a `measure`, or an unknown kind fails the spec load and `validate_spec.py`; fields without a kind are not checked. The 16 code columns from #613 declare `semantic_kind: code` (#651).

- Spec `license` gains `redistribution` (`allowed` / `non_commercial` / `forbidden` / `unknown`; absent means unknown), `attribution` (the exact text to display), `quota` and `pii_columns` (#525, #605).
- `DatasetRef.license` carries a spec's licence terms — redistribution, attribution, `quota`, PII columns — exactly as declared, and `LicenseSpec` is exported from `kpubdata` (#609). A dataset that declares no licence has `None`, which means unknown rather than unrestricted; `quota` is the provider's own wording and is not parsed. Catalogue-only datasets have `None`.
- `Dataset.schema()` returns a `SchemaDescriptor` for spec datasets, built from the spec's `fields` in declaration order (name, type, description; `unit`, `source_name`, `transform` in `raw`), and spec datasets with fields declare `Operation.SCHEMA`. A spec with no fields still returns `None`. `title`/`format` stay unset until the column-metadata contract (#644) decides them (#643).
- ADR 0006: the column-metadata contract separates storage type (`type`), meaning (`semantic_kind`: code, measure, date, period, text, flag) and display (reusing `FieldDescriptor.title` and `FieldConstraints.format`). Implementation is #651 (#644).
- `kpubdata.core.status` — one canonical dataset status vocabulary
  (`DatasetStatus`) with mappings from the spec, probe, `SUPPORTED_DATA.md` and
  production-grade vocabularies; `spec._STATUSES` and `_probe.PROBE_STATUSES` are
  now derived from it. ADR 0005 records the decision, and
  `tests/unit/test_status_vocabulary.py` fails when a design document uses a name
  the code does not define (#619).

- `kpubdata.core.status.transition()` — the pure dataset status state machine from `docs/DATASET_STATUS.md`. A table-driven test runs every row of that document's transition table against the function. `unstable` now also breaks immediately on a structural change, and `application_required` recovers on `HEALTHY` (#625).

- `ValidationReport.to_dict()` returns a JSON-serialisable form of the report (#615).
- Provenance now reports `cached=True` for responses served from the response cache, and `fetched_at` keeps the original fetch time instead of the time of the cache read. The transport marks a cache hit in `httpx.Response.extensions`, and `ResponseCache.get_entry()` returns the stored `created_at` (#616).

### Changed

- **BREAKING:** code columns keep their leading zeros and come back as `str` (#613). Declared `string` now: `apt_trade` `bonbun`/`bubun`/`roadNmBonbun`/`roadNmBubun`/`roadNmSeq`, `apt_rent` `roadnmbonbun`/`roadnmbubun`, `hospital_info` `clCd`/`postNo`, `metro_fare` `arvlStnCd`/`dptreStnCd`, `tour_kor_*` `zipcode`, `village_fcst` `fcstTime`. As a safety net, a zero-led value (`"06102"`) no longer casts to a number, so a code column declared numeric stays text and is reported `uncastable`. Replay verification (`make verify`) now also fails when normalization drops a leading zero. See kpubdata-builder#702.

- KPubData is documented as a standalone Python SDK; KPubData Builder and KPubData Studio are listed as related projects, not as stages after it (#666). ADR 0007 records the independence rules — dependencies run Studio → Builder → KPubData only, and the public API is what `kpubdata.__all__` and `API_SPEC.md` name (#667) — and `scripts/check_independence.py` fails CI if KPubData imports or depends on Builder or Studio (#668).

- All 59 `localdata` catalogue datasets are marked retired and `LocaldataAdapter.query_records` emits a `DeprecationWarning` (#527, #603). The retirement is disputed by the recorded evidence — see #618.
- CODEOWNERS covers the credential host allowlist, the scripts run by `contents: write` release jobs, `pyproject.toml` and `uv.lock`; a test checks the required paths and that every pattern still names an existing path (#629).
- `FieldIssue.kind` and `ValidationReport.issues_of()` take the `IssueKind` literal (`"uncastable"`, `"missing"`, `"undeclared"`); `issues_of()` raises `ValueError` on an unknown kind instead of silently returning nothing (#615).

### Fixed

- `scripts/release_notes.py promote` keeps a CRLF CHANGELOG's line endings instead of rewriting every line as LF (#628).
- `kpubdata scaffold` generates English docstrings, so the files it writes pass `check_english_comments.py`; a test runs the gate on the generated files (#626).
- A provider-reported total of `0` is kept as `RecordBatch.total_count == 0` instead of becoming `None`, so "no results" and "count unknown" are distinguishable; a reported 0 explicitly ends paging (#642).
- `Client(...).dataset(...).list_all()` now reaches the spec path with column casting decided across all pages. `CompositeProviderAdapter` had no `query_records_all`, so every spec dataset reached through `Client` still cast per page and a column could be `int` on one page and `str` on the next — the split 0.7.0 recorded as fixed (#611).
- `docs/status.md` no longer depends on the calendar: "recent" is measured from the newest `last_verified`, so `--check` stops failing every pull request from 2026-12-09. It also counts all six SUPPORTED_DATA levels instead of three (#620).
- `docs/DATASET_STATUS.md` and `docs/LIVE_PROBE.md` contradicted each other and the
  code: the failure threshold (3 against "2+"), code 32's classification, the
  `PARAM_CHANGED` spelling, a nonexistent dataset key, a nonexistent module and the
  neis/fds key sharing claim (#619).

- `scripts/release_notes.py promote` for a final version folds that version's pre-release sections (`aN`, `bN`, `rcN`) into one section, instead of failing with "nothing to release" after a pre-release. A `prerelease` command and the release-notes action's `prerelease` output tell the release job to mark a pre-release (#622).

- The spec-dataset `list_all()` path honours `page_size`, `max_size` and `max_pages` (#614). `page_size` drives pagination instead of going out as a raw `page_size` parameter; a `page_size` above the spec's `max_size` no longer ends the walk after the first page; exceeding `max_pages` raises `InvalidRequestError` like the legacy path instead of truncating silently; and each batch keeps its own `raw`, `meta["provenance"]`, `next_page` and `validation`, with the whole-result report in `meta["validation_total"]`. The path still buffers every page before the first batch, because casting is decided across all pages (#481); this is now documented.
- The field validation report no longer miscounts (#615): a 0-row page is reported clean instead of every declared field being `missing`; numeric null markers (`""`, `"-"`) count as nulls rather than non-null values; undeclared columns are detected across all records, not only the first.

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
