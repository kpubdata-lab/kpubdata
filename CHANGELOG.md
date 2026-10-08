# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A dataset's verification and its need for an application are read separately (#842). `DatasetRef.status` gives one name, so `application_required` hid whether the dataset behind it had passed its fixtures. `DatasetRef.verification` (`VerificationLevel`) stays `fixture_verified` while an application is pending, and `DatasetRef.application_requirement` (`ApplicationRequirement`: `required`, `not_required`, `unknown`) says only what is recorded — `unknown` is not "none needed". `to_dict()` gains the keys `verification` and `application_requirement`; `status` and every existing key are unchanged.

### Fixed

- A dataset pull request opened by the agent workflow carries everything the procedure asks for (#862). `build-dataset.yml` committed the spec, the fixtures and the insecure-http baseline. It left out the example script, the `SUPPORTED_DATA.md` row, the `dataset_metadata.json` entry and the generated `dataset_status.json` and `docs/dataset-examples.md`, so the pull request it opened lacked what `AGENTS.md` requires. `AGENTS.md`, the agent definition and the workflow also named different paths, and the agent definition told the agent to commit and open the pull request, which makes the workflow stop. Now:
  - `scripts/dataset_artifacts.py` is the one list of what a dataset adds: what is written by hand, what a generator writes, and the baseline.
  - The workflow reads that list from the commit it checked out. It stops the run on a change under a path dataset work may not touch. That includes untracked files whatever the ignore rules say, file names with spaces or non-ASCII characters, and a file moved out of such a path; Python's `__pycache__` is left out. It then runs `sync_supported_data.py`, `gen_dataset_status.py` and `gen_docs_examples.py` itself, commits only the listed paths, and names any other stray file it leaves out.
  - `AGENTS.md` and the agent definition name the same paths, `docs/dataset-examples.md` included. The agent no longer commits or opens the pull request.
  - `tests/unit/scripts/test_dataset_artifacts.py` holds the two documents and the workflow to the list, and runs the check against a real git repository.
- The dataset workflow's verifier checks the pull request its run opened, and a verification that did not pass fails the run (#858). The verifier step looked for the pull request by branch name, using a `DATASET` that only the previous step's shell had set. It therefore searched for `agent/issue-N` while the branch was `agent/datago.x`, and both the search and the verifier ended in `|| true`: a run whose verifier never ran, or rejected the pull request, finished green. Now `build-dataset.yml` works as follows:
  - The pull request step outputs `dataset`, `branch` and `pr_number`. The number is read from the URL `gh pr create` prints, and a failed creation fails the step.
  - The verifier runs on that number. Its output is posted on the pull request, and a rejection, an output with no verdict or a failed run fails the workflow.
  - The run summary says whether the verifier approved, did not pass or never ran. A pull request whose verification did not pass is told so in a comment.
  - `tests/unit/scripts/test_build_dataset_verifier.py` reads the workflow and runs the verifier and record steps against a fake `opencode` and `gh`.
- The drift report says what it found, or that it could not look (#859). `scripts/report_drift.py` read a failed `gh` call as an empty answer: a refused run list ended as "not enough history" with exit status 0, a failed run with no result artifact counted as a run with no failures, and a failed `gh issue create` printed that the issue had been filed. It now ends with one of five verdicts — `ok`, `drift`, `insufficient_history`, `undetermined` (exit 2: the runs or their results could not be read) and `report_failed` (exit 1: drift was found and could not be filed). A failed issue search files nothing, so it cannot produce a second issue for a dataset; one failed report does not stop the others. Only the runs a streak is counted over are read. The `drift-report` job now declares `contents: read`, `actions: read` and `issues: write`, which the script needs and the workflow's `contents: read` did not give it; a test holds the declaration. No change to the package.
- The R3 review gate looks up an approver whose login holds an underscore (#860). The action put a name into the permission lookup only when it was letters, digits and hyphens, so an Enterprise Managed User (`name_shortcode`) was left out and their approval could never count. Underscores are accepted; a name with any other character is still refused rather than put into a URL. No change to the package.
- The R3 review gate counts an approval only from someone who can push now (#860). `scripts/r3_review.py` trusted a review whose `author_association` was `OWNER`, `MEMBER` or `COLLABORATOR`. That says how an account is related to the repository, not what it may do: an organisation member or a collaborator with read or triage access satisfied the required review of a `review:R3` pull request. The action now looks up each such approver's repository permission and the rule counts `admin` and `write` only; a permission that cannot be read is not an approval, and one failed lookup does not hide another approver's review. The permission is the one held when the check runs, so an approval from someone who has since lost write access stops counting at the next run. A pull request without the label makes no lookup. kpubdata-builder and kpubdata-studio call this action at a pinned commit and take the change when they raise the pin. No change to the package.
- A data.go.kr `resultCode` is read the same way on every path (#843). The spec executor and the shared localdata/semas adapter compared NODATA to the text `"03"` while the datago adapter compared it to the number 3, so `"3"` or `"003"` was an empty result on one path and a provider error on the others; and the datago and family adapters refused a standard envelope whose code was a JSON number, which the spec path accepted. One reader (`core/_result_code.py`) now serves all three.
- LOFIN encodes its key in the request query (#840). The URL was built with the key as it is, so a key holding `&` or `#` cut the query short or began another parameter, and `+` or `%XX` reached the provider as a different character. The whole query — key, paging and filters, names and values — now goes through one encoder, once. A key made only of letters, digits, `-`, `.`, `_` and `~` is sent exactly as before.
- A refusal that a provider names with a word is no longer cached (#838). Seoul Open Data, BOK ECOS, NEIS and LOFIN answer HTTP 200 with `RESULT: {CODE}` and codes such as `INFO-100` or `ERROR-290`; the response cache judged numeric codes only, so an invalid-key or server-error answer was kept and served again like a success. The codes these providers' adapters already treat as errors (`INFO-100`, `INFO-300`, `INFO-400`, `INFO-500`, `ERROR`, `ERROR-<number>`) are now recognised and not cached. `INFO-000` and `INFO-200` (no data) are cached as before, and a word outside that list is still not judged.
- KIPRIS `patent_family` sends the page it asks for, and `list_all` stops when a provider answers the same page twice (#837). The adapter computed `next_page` and never sent a page number, so every "next page" was the same request: a full first page made `list_all` fetch it again up to its 1,000-page limit and return the same rows each time. `pageNo` and `numOfRows` are now sent, and an envelope that echoes a page other than the one asked for is read as "no such page". Whether this service pages at all has not been checked against the provider; both cases end after at most one extra request. For **every** provider, `list_all` now raises `InvalidRequestError` when a page holds exactly the records of the page before it, instead of repeating the request up to its page limit — a new error from the core, not only from this adapter.
- A `path_segment` key with no `param_name` goes into the URL path and nowhere else, and a key in a path is masked when the URL also has a query (#839). The executor stored such a key under `__path_key__` and read it back under an empty name: the URL was built with an empty key, and the real one was sent as a query parameter named `__path_key__` with nothing marking it secret. No bundled spec is written that way; the spec schema allows it. Separately, URL masking returned the URL unmasked when the key was in the path and the query held nothing to mask — the path had been masked and the original was then returned. No provider that keeps its key in the path sends a query today, so neither reached a log.
- A spec that declares `method: POST` is refused when it is executed, and the transport no longer retries a method that is not idempotent (#844). The spec schema allows `POST`, and the executor sent every request as a `GET` whatever the spec said; where a POST's parameters would go is not defined, so it now raises `InvalidRequestError` instead of sending something else. The transport retried every method on a timeout or a retryable status; `POST` and `PATCH` are now sent once. Every bundled spec is `GET` and nothing in the library sends a `POST`, so nothing that ships behaves differently.
- The line httpx logs for each request no longer holds a key in a URL path or under an unlisted parameter name (#821). The filter on the `httpx` logger masked by parameter name only, so the keys of seoul, fds and bok — sent as a path segment — and a key under a name the list lacks went to any application that logs `httpx` at INFO. The transport now makes the values it is sending known for the length of the call, and the line is masked by them as well. A key in a path is matched whole even when it contains `/`, and in its percent-encoded forms; this also applies to the URLs in kpubdata's own logs and errors, where a key containing `/` was not masked in a path before.
- A client shared between threads builds its HTTP client once and requests its SGIS token once (#823). Both were checked and then assigned with no lock: threads that arrived together each built an `httpx.Client`, of which all but one were never closed, and each requested a token. The catalog's search index and its key are now kept as one value; assigned separately, a thread reading between the two got one provider's index under another's key.

### Changed

- CI does less work for the same verdict. No change to the package.
  - A push to `main` no longer cancels the CI or Security run of the push before it, running or queued, so every merged commit keeps a finished run. A pull request still cancels its own older run.
  - The coverage gate runs on the Python 3.12 test leg instead of in a job that ran the whole suite a fifth time. The floor is still `fail_under` in `pyproject.toml`, and falling below it still fails `CI gate`.
  - The package build and the base install no longer wait for the lint and test jobs. They read nothing those jobs produce.
  - The docs build in `ci.yml` and `docs.yml` installs the `docs` extra from `uv.lock` instead of the latest `mkdocs-material`.
  - Every job has a `timeout-minutes`.
- `src/kpubdata/dataset_metadata.json` is the source for a dataset's level (#842). SUPPORTED_DATA.md's three level columns and `dataset_status.json` are written from it by `scripts/sync_supported_data.py` and `scripts/gen_dataset_status.py`; the document was the source before, and a level is no longer changed by editing the table. The retired `g2b_contract` row, which had its provider written into the date cell, is a nine-cell row again.
- The architecture documents describe the 0.9 code (#845). `ARCHITECTURE.md` listed files that do not exist and left out the spec path (`SpecExecutor`, `SpecDatasetAdapter`, `CompositeProviderAdapter`, `query_records_all`); `PROVIDER_ADAPTER_CONTRACT.md` now matches `core/protocol.py` (`requires_api_key`, `get_dataset(dataset_key)`, the optional `query_records_all`); `CANONICAL_MODEL.md` gains `DatasetRef.status` / `to_dict()` and the validation report; `PRD.md` names the fourteen built-in providers and the current version; `docs/product-family-architecture.md` no longer says Builder does not authenticate its callers. The documents say that the SDK's own version is not the supported Builder/Studio combination, which `docs/compatibility.md` records and which is unchanged here.
- **Breaking for callers that read `total_count` from seoul or kipris:** a result with no rows now reports `total_count == 0`, as every other adapter has since 0.9.0 (#806, #824). seoul reported `None` for it. kipris reported `None` when empty and otherwise the number of rows **on the page**, which is not a total — its envelope carries none — so a non-empty kipris result now reports `None` (not known). A caller that tested `total_count is None` for "no rows" on these two providers must test `== 0`; one that used kipris's value as the full count was using a page length.
- The specs shipped in the package are read and validated once per process (#822). `discover_specs()` had no cache and a client called it for every provider it resolved, so listing every provider's datasets read 350 files for 25 specs. Each call still returns its own copy, so changing a returned spec's dictionaries affects nobody else. A directory passed to `discover_specs(root)` is read on every call, as before. A spec file edited inside the installed package while a process runs is not seen until the process restarts.
- A new client lists every provider's datasets in a tenth of the time. The specs were read once, but each of the fourteen providers then copied all 25 of them, which took most of a listing's time; a provider now copies only its own. The spec files are parsed with libyaml's safe loader when PyYAML has it and the pure-Python one otherwise. Both resolve every bundled spec to the same `SpecDefinition`, which a test checks. On a 6-core development machine with Python 3.14, the first `Client().datasets.list()` in a process took 0.256 s and now takes 0.029 s, and a later one went from 0.116 s to 0.013 s. Nothing in the public API changes, and `discover_specs()` still returns its own copy on every call.
- release-please runs once a day and by hand, not on every push to `main` (#819). Each run that changes the release pull request pushes its branch twice, and GitHub mails every subscriber for each push: a day with a dozen merges sent two dozen mails about a pull request that may not be merged for a week. Run the workflow by hand to bring the pull request up to date before a release.
- The release job recognises the branch release-please actually uses (#819). It names the branch `release-please--branches--main--components--kpubdata`; `release.yml` compared for exactly `release-please--branches--main`, so merging the first release pull request (#830) would have started no release job. It now matches the prefix.
- **release-please opens the release pull request** (#819). `release-please.yml` works out the next version from the commit titles on `main` since the last tag — a breaking change or a `feat` raises the minor, fixes alone the patch — and keeps one pull request open that raises it. It does only that: the CHANGELOG stays hand-written under `[Unreleased]`, the same workflow adds the `uv.lock` version and the dated CHANGELOG section to the release branch, and nothing is tagged until the pull request is merged and `release.yml` has checked the release window and run the gates. `scripts/set_version.py` also writes `.release-please-manifest.json`, so a release prepared by hand does not leave release-please bumping from an old version. `mode=prepare` remains for a pre-release and a critical patch. No change to the package.

## [0.9.0] — 2026-10-06

### Added

- **`DatasetRef.to_dict()`** (#784): a dataset reference serialises to a JSON-safe dict with a stable set of keys — identity, `status` (#783), `query_support`, `license`, `request_parameters`, `application` and `verified_at`. `dataclasses.asdict(ref)` raised `TypeError` on `raw_metadata`, so a consumer had to read `raw_metadata`, which carries no stability promise. Every key is always present; `None` means nothing is declared. The key list is in `docs/compatibility.md` §3. `kpubdata datasets list --format json` and `datasets show --format json` print this dict: `list` entries gain the new keys next to `id`, `name`, `provider` and `operations`, and `show` keeps `capabilities` and `raw_metadata_keys` beside them.
- **`kpubdata.SENSITIVE_PARAM_KEYS`** (#782): the names kpubdata masks as credentials — `servicekey`, `service_key`, `api_key`, `apikey`, `token`, `authorization`, `secret`, `password`, `key`, `oc`, `accesstoken`, `consumer_key`, `consumer_secret` — are importable from `kpubdata` and `kpubdata.transport`. They lived only in the private `kpubdata.transport._sensitive`, so Builder kept its own list, and that list lacks `key`, `oc`, `consumer_key` and `consumer_secret`. Names are casefolded and matched exactly; a release only adds names. Value-based masking stays private.
- **`DatasetRef.status`** (#783): a dataset reference says how far the dataset has been verified, as a `DatasetStatus` (now exported from `kpubdata`). A dataset awaiting an application, one checked against fixtures only and one verified against the live API used to look the same at run time; the levels lived only in `SUPPORTED_DATA.md`, which is not in the wheel. `scripts/gen_dataset_status.py` writes `src/kpubdata/dataset_status.json` from that document's level column (through `SUPPORTED_DATA_LEVELS`, with a spec's `status:` override applied), and `tests/unit/test_dataset_ref_status.py` fails when the two differ. Of the 155 datasets the table and the runtime share: 94 `application_required`, 36 `fixture_verified`, 24 `live_verified`, 1 `unstable` (`datago.ocean_buoy`, by its spec's override); `datago.generic` is not in the table and reports `None`. The status is the recorded one, not a live check — that is `Client.probe`.
- **Evidence bound to the spec, the commit and the run** (#522, #713): a recorded fixture's `meta.json` now carries `spec_sha256`, a digest of the spec file's pipeline-relevant content (`kpubdata.core.spec.spec_file_digest`, which normalises away the `last_verified` line the recorder itself rewrites), and `record_commit`/`run_ref` from the CI environment (`GITHUB_SHA`/`GITHUB_RUN_ID`) when present. `make verify` gains a spec-binding step: a fixture whose recorded digest no longer matches its spec is void — the spec changed after recording — and fails with re-record guidance. Fixtures recorded before the digest existed are reported as legacy evidence rather than failed — since #717, only those on a frozen baseline.
- **Public probe API** (#694): `Client.probe(dataset_id) -> ProbeResult | None` and `Client.probe_all(*, provider=None) -> list[ProbeResult]` classify reachability with the client's own keys, and `ProbeResult` and `PROBE_STATUSES` (the ADR 0005 `ProbeStatus` vocabulary) are exported from `kpubdata`. Probing keeps its fast-fail transport (`PROBE_TIMEOUT_SECONDS`, `PROBE_RETRIES`, no cache), and a run shares one transport that is closed at the end — previously every dataset opened its own and none was closed. `kpubdata probe` now goes through these methods; its output and report are unchanged, and it now honors the global `--provider-key` option, which it silently ignored before.
- **Explicit-keys-only mode** (#694): `Client(..., env_keys=False)` (backed by `KPubDataConfig.env_fallback`) uses only `provider_keys` and never reads a credential from the environment — not `KPUBDATA_<P>_API_KEY`, `<P>_API_KEY` or `KPUBDATA_SGIS_CONSUMER_SECRET`. A service probing with a user's key no longer has a missing entry silently filled with the operator's key. With no key the probe makes no call and reports `auth_unknown`. The default (`env_keys=True`) is unchanged.
- **R3 review gate** (#722, kpubdata-builder#905): a pull request labelled `review:R3` now needs an approval from someone other than its author before it can merge. `scripts/r3_review.py`, wrapped by the `.github/actions/r3-review` composite action, is the one implementation all four repositories call; the `R3 review` workflow runs it on every pull request (passing when it is not R3) and again on label changes, pushes and review submissions or dismissals, with `pull-requests: read` only. Each reviewer's latest approving or change-requesting review decides; approvals on an older head count, as with branch protection's stale-approval dismissal off; the author, bots and accounts without write access do not count. POLICY 14.1 and AGENTS.md describe it. `R3 review` becomes a required status check next to `CI gate`; the approval count in branch protection stays at 0.
- **Probe evidence fields** (#625, #710): `ProbeResult` carries `http_status` (200 on success — the executor raises on anything else — and the raised error's status otherwise), `result_code` (read off the raised error; a successful query does not parse the envelope), `latency_ms`, `schema_hash` (a fingerprint of the returned field names — data changes daily, field names are the contract) and `classification` (the `DriftClassification` this outcome feeds the dataset status machine), each `None` where it could not be observed — never guessed. The report envelope records who ran the probe (`runner`; the nightly workflow passes `github-actions`).
- **Nightly drift detection** (#625, #711): `scripts/drift_detect.py` runs the dataset status machine over two consecutive probe reports — a differing `schema_hash` emits `SCHEMA_CHANGED` itself (it is not a probe outcome), transient failures move nothing before the third consecutive night, restores restore `previous_status` and file nothing, `RETIRED` moves nothing but files. The live-probe workflow grows a drift job that chains the previous night's artifacts, keeps streak state in a `drift-state` artifact, and files one `[drift]` issue per transition that needs a person — skipping datasets that already have an open one, with the `status_history.json` entry riding in the issue body. The exit status is always 0: an upstream failure is a drift event, not a CI failure.
- **Production-grade gate** (#463, #711): `scripts/check_production_grade.py` evaluates the machine-checkable criteria of `docs/production_grade.yaml` — source and listing gate every spec; a recorded fixture (any `*.meta.json`: the recorder names fixtures after the example, `tour_kor_area` records `seoul_restaurants.meta.json`) and an example script gate the verified tier only (an in-progress row gates nothing — ocean_buoy's missing fixture is #627, not a surprise); `fields_declared` is reported, not gated. Its unit test is the CI gate: every spec dataset in the repository must pass.
- **Example recency windows** (#734, #750): a spec can declare `params[].max_age_days`, and `make verify` fails an example outside the window *before* the live call does — naming the cause (expired, or a future issue that does not answer yet — the #731 morning trap) and the refresh route. Parameters without a window emit nothing. The relative-time representation the issue considered first was rejected: replay matches on recorded literals, and issue-slot granularity would leak provider specifics into the generic schema.
- **Recorder run reference** (#523, #729, #739): the evidence-authorship gate grows a second layer — a changed `meta.json` by a recorder name must also carry `record_commit` and `run_ref`, and `run_ref` must resolve to a run of this repository's Build Dataset workflow whose head SHA is exactly that commit (`gh run view`; any lookup failure fails closed). A local tool committing under the recorder's name — the #728 path — no longer passes. `ci.yml` gains `actions: read` and the job token for the lookup.
- **Unconfirmed terms are not redistributable** (#732): a spec whose licence says `redistribution: allowed` must carry the `attribution` text that proves the terms were confirmed from the provider page (#525); terms nobody checked say `redistribution: unknown` — the two claims #728 wrongly shipped (bus_arrival, social_enterprise) were fixed to unknown first (#740, #744), because Builder's publish gate (kpubdata-builder#892) reads exactly this flag. `make verify` enforces the rule with a shrink-only baseline, `scripts/unconfirmed_terms_baseline.txt`, frozen at the 16 legacy violators — mirroring the legacy evidence ratchet (#717): a listed spec passes while its terms stay unconfirmed, an unlisted violation fails verify, and a stale entry (terms confirmed, or the claim withdrawn) must be removed from the list.
- **PR title blocks the merge** (#741): `PR title` joined `CI gate` and `R3 review` as a required status check in all four product repositories, so a failing title check now closes the merge button instead of only showing a red X. The check re-runs on title edits (`titles.yml`), which `ci.yml` cannot see, so it is registered in branch protection rather than added to the aggregate gate's needs. `scripts/check_required_checks.py` verifies the required list against the workflows (the studio#416 lesson), and POLICY 14.2 records the rule.
- **Unjustified plain http is refused** (#738): a spec whose `endpoint.base_url` says `http://` must carry `endpoint.insecure_http_reason` — the service key rides the query string, and over plain http anyone on the network path reads it. `make verify` gains a transport-security step enforced with a shrink-only baseline, `scripts/insecure_http_baseline.txt`, frozen at the 23 legacy http specs — all of them on `apis.data.go.kr`, which answers https with identical envelopes (the reproducible record — commands and raw envelopes for every service path behind the baseline — sits as a comment on #738), so each entry leaves the list by switching schemes (a switch moves the spec digest, so the fixtures are re-recorded through the Build Dataset workflow).
- **The agent PR may shrink the insecure-http baseline, and nothing else** (#738): the Build Dataset commit step stages `scripts/insecure_http_baseline.txt` next to the spec and the fixtures, because an https conversion must land with its baseline line removed or `make verify` fails the ratchet. `scripts/check_baseline_shrink.py` guards the staging: the diff may delete exactly the converting dataset's line, add nothing, and only when that spec's `base_url` now says `https://` — an addition, a swap or an unearned removal stops the run with `needs-human`, so the agent cannot widen a count-only ratchet through its own pull request. Negative tests pin each refusal; the base-branch comparison those ceilings really want is #766.

### Changed

- **A request that carries a credential is not redirected** (#816, decided in #812): the transport followed every redirect, so a request with the key in its query string was re-sent — key and all — to wherever the answer pointed, and over `http://` anyone on the path can write that answer. Such a request is now sent without following redirects; a 3xx answer raises `TransportError` naming the target host (never the location, which can carry the key). A request without a credential is redirected as before. **Behaviour change:** a provider that redirects a keyed request in normal operation now fails; `TransportConfig(follow_credentialed_redirects=True)` restores following for it. No provider was checked live for this.
- A release pull request no longer fails the compatibility check it cannot satisfy (#780). `tests/unit/test_compatibility_json.py` required the package's version to be inside the `supported` range of `compatibility.json`. That row is Builder's pin, and Builder pins only a released kpubdata, so raising the version to 0.9.0 failed the test unless the row claimed a pin Builder does not have yet. The test now holds what can be true at every point: the version is never behind the supported range. `compatibility.json` says when the row moves — with the Builder and Studio release, as `docs/compatibility.md` §5.1 already orders it — where its `update_policy` said "on every kpubdata release".
- **Unconfirmed terms are reported as `unknown`** (#813, decided in #812): a spec that says `redistribution: allowed` without the `attribution` text that shows its terms were confirmed reported `allowed` on its `DatasetRef`. It now reports `unknown` — on `ref.license`, `ref.to_dict()` and `raw_metadata["license"]`. **Behaviour change:** the 16 specs frozen in `scripts/unconfirmed_terms_baseline.txt` no longer read as redistributable to a direct user of kpubdata; the three with attribution (`datago.apt_rent`, `datago.apt_trade`, `datago.village_fcst`) are unchanged. `find_spec(...).license` still returns what the spec file declares.
- **`list_all()` on a spec dataset holds one page in memory, not the whole result** (#789). Global column casting (#481) needs every page before any is cast, and the fetched pages waited in a list, so memory grew with the row count: 40 pages of 500 rows peaked at 16.5 MB against 1.7 MB for 4 pages. Each page now goes to a temporary file and only its evidence for the casting decision is kept; the pages are read back, cast and yielded one at a time once the last is in — 1.3 MB for 4 pages and for 40. The casting rule, the batches and their reports are unchanged, and `SpecExecutor._finalize_casting` now uses the same decision code. What a failing page does is now documented, not changed: the exception propagates, no batch is yielded and the earlier pages are discarded.
- The package metadata names its repository (#791): `[project.urls]` gives the homepage, documentation, repository, issue tracker and changelog under `kpubdata-lab/kpubdata`, so the PyPI page links back to the source. There was no `[project.urls]` at all.
- `compatibility.json` says what it is (#788). Its description claimed "Builder and Studio CI read this file to check their kpubdata dependency range"; no workflow or script in kpubdata, kpubdata-builder or kpubdata-studio reads it. The sentence is replaced: the file is a record for people and release notes. `tests/unit/test_compatibility_json.py` checks what can be checked without another repository — the file's shape, that exactly one range is `supported` and the package's own version is inside it, and that the range is the pin `docs/compatibility.md` states.
- **Only a dataset that declares its terms can be published publicly** (#785). 25 of the 156 datasets declare a `license` — exactly the spec-backed ones — and Builder's publish gate reads `license.redistribution`, so the other 131 gave it nothing to read. The decision, recorded in `docs/policy/terms-matrix.md`: they are not filled in from a provider-level default, `DatasetRef.license` stays `None` (unknown) for them, Builder refuses a public publish of such a source with `redistribution_unknown`, and a dataset becomes publishable when it is migrated to a spec with terms confirmed from its provider page. `tests/unit/test_declared_terms_decision.py` holds that every dataset with terms is spec-backed and no catalogue-only dataset has any.
- **HTTP 401 raises `AuthError` and HTTP 503 raises `ServiceUnavailableError`** (#786). Both used to leave the transport as a plain `TransportError`, told apart only by `status_code`; 429 was already `RateLimitError`. **Behaviour change:** `AuthError` is not a `TransportError`, so `except TransportError` no longer catches a 401 — catch `AuthError` (or `PublicDataError`). A 503 is still a `TransportError` (its subclass), still retried, and typed once the retries run out. The `kpubdata` CLI exits `3` instead of `4` on a 401. `Client.probe` reports a 401 as `auth_unknown`, as before. Every error now has a stable `code` (`auth_error`, `service_unavailable`, `rate_limited`, …) and `to_dict()`, a JSON-serialisable dict of `code`, `type`, `message`, `provider`, `dataset_id`, `operation`, `status_code`, `provider_code` and `retryable`, so a consumer maps an error without comparing message text; the table is in `API_SPEC.md` §7.
- **Breaking: `Client` refuses an unknown keyword argument** (#781). `Client(**extra)` accepted any keyword and dropped it without an error or a warning — `Client(timeoutt=5)` built a client with the default timeout, and `env_keys=False` passed to 0.8.0, which does not have it, left the environment keys in use (#780). It is now a `TypeError` naming the argument. `Client.from_env(extra=...)`, whose dict was forwarded into the same channel, is removed with it; `from_env` takes `provider_keys`, `timeout`, `max_retries`, `cache` and `cache_ttl_seconds`. Nothing in the library read the dropped values, so a caller passing only documented options is unaffected.
- The repository moved from `yeongseon/kpubdata` to `kpubdata-lab/kpubdata`. Links, the documentation site (`https://kpubdata-lab.github.io/kpubdata/`) and the shared GitHub Actions references now use the new owner.
- A pull request title now blocks the merge when it breaks POLICY 2.1.3 (#741). On top of #742's Hangul and inline issue-number rules, `scripts/conventional_title.py --pull-request` refuses issue and pull request URLs and titles over 100 characters. GitHub's `Revert "…"` title is now exempt before any rule, as it should have been: it quotes the reverted squash commit, whose title ends in its PR number, so undoing a merge with GitHub's button used to fail the check. The `PR title` check reads the title from the API instead of the event payload, and becomes a required check in all four repositories; it is not folded into `CI gate` so that a title edit does not re-run the whole CI. The squash commit body is now the PR body (2026-10-01), so POLICY 2.1.3, AGENTS.md and CONTRIBUTING say commit titles (= PR titles) are English and commit bodies (= PR bodies) are free (#743).
- A required check that failed no longer keeps a pull request blocked after a later run of the same check passes (#759). Each event starts its own check suite, and branch protection read a failed suite as failing even after another passed, so `R3 review` stayed blocked after an approval until someone re-ran the run the label had failed. `required-check-refresh.yml` re-runs the failed and cancelled runs of `R3 review` and `Titles` on the same head once one passes; both read the pull request live.
- CODEOWNERS covers every ratchet baseline with one pattern (#764): `/scripts/*_baseline.txt` replaces the single legacy-evidence entry, so the unconfirmed-terms (#732) and insecure-http (#738) baselines sit behind an owner too — a count-only ratchet cannot stop one entry being swapped for another, which is why #723 put the first baseline there. `tests/unit/test_codeowners.py` checks the reverse direction as well: every `scripts/*_baseline.txt` file must match an owned pattern, so a baseline added without coverage fails a test instead of silently missing review.
- **The baseline ratchets compare sets against the base branch, not counts against frozen ceilings** (#766): a count-only ratchet lets a shrunk list grow back toward its ceiling — filling the freed slots with exactly the violations it exists to stop — and a one-for-one swap never moved the count at all; #765 gives the dataset agent a path to try exactly that. `verify_spec.py` reads each baseline at an explicit ref — `KPUBDATA_BASELINE_BASE`: the pull request's base branch in `ci.yml`, `HEAD` on the Build Dataset runner (it verifies uncommitted edits on main), `origin/main` as the Makefile's local default — fails any entry the ref does not carry, and fails closed when the ref is missing or unreadable; there is no implicit `HEAD` fallback, which in a pull request's CI would compare the PR against itself. A baseline the ref does not carry reads as the empty set, so a creating change may only land it empty — freezing existing violations is the failure that names its human-reviewed moment. The frozen-size constants (`LEGACY_CEILING` and friends) and their count tests are gone — the ref's entry set is the ceiling, and an after-shrink addition or a swap now fails for all three baselines (#717, #732, #738).
- **The https evidence is recorded, and the transport rule runs outside make verify** (#767): the insecure-http gate's citations pointed at "the keyless probe in the issue", but the issue held a results table without commands or raw envelopes, and 10 of the 16 service paths behind the baseline — ocean_buoy, the three localdata specs, six of the seven RTMS trade services — had never been probed at all. A reproducible record now sits on #738: the exact request per path over both schemes, byte-identical envelopes for all 16 (code 30 from ten real services, code 12 at the gateway for the rest), and no service needing `insecure_http_reason`. The CHANGELOG, the baseline header and the verify comment point at it, and the rule moved to `kpubdata.core.spec.insecure_http_problem` — shared by `verify_spec.py` and `validate_spec.py` the way #725 shares the licence contradictions — so an unjustified `http://` base_url fails `validate_spec` (the CI spec validation) and not only `make verify`, with the same shrink-only baseline exemption on both paths.
- **CODEOWNERS covers the evidence path** (#715): `scripts/record.py`, `scripts/verify_spec.py`, `scripts/check_fixture_authorship.py`, the recorded fixtures and the whole `src/kpubdata/specs/` tree (previously only `schema.json`) now need a code owner's review, because whoever changes them changes what "verified" means. `tests/unit/test_codeowners.py` checks glob patterns too: a wildcard entry must match at least one file, since GitHub silently ignores a pattern that matches nothing. Enforcing code-owner review in branch protection stays a person's decision (POLICY 14).
- **Release rule** (#685): kpubdata now releases on demand — when a downstream repository is blocked, for a security fix, or for accumulated changes — at most once every seven days, and is no longer part of the monthly release week, which stays for kpubdata-builder and kpubdata-studio. `scripts/release_window.py`, wrapped by the `.github/actions/release-window` composite action, is the one implementation: `on-demand` refuses a release less than seven days after the last final GitHub Release, `monthly` refuses outside the Monday-to-Sunday week holding the month's last Thursday, both in KST, and a critical patch passes either only when it names its issue (`critical_patch`/`critical_issue` inputs, or a `Critical-Patch: #N` line in the release pull request). `release.yml` runs it first on both the prepare and the release path; a dry run reports the decision without stopping. `docs/compatibility.md` §5.1, AGENTS.md and POLICY say the same.
- **bus_arrival and social_enterprise migrated to specs** (#409, #728): both leave the catalogue for spec YAML with recorded live evidence. User-visible: `datago.bus_arrival` serves over https and reports no pagination (a station query is one page — previously offset-style, max 1000), and `datago.social_enterprise` caps `page_size` at 100 (previously 1000) and declares its PII columns (CEO name, phone, fax) per #693.
- **ultra_srt examples renamed with a fresh issue slot** (#731, #736): `seoul_1530`/`seoul_1500` → `seoul_0600` (base 2026-10-01 06:00) — the KMA APIs answer only recent issues, so the old example dates had drifted outside the window and every live call reported `params_invalid`. Replay matching and the example scripts follow the names; the legacy evidence baseline shrank 35 → 32.

### Fixed

- **Every provider request passes its credential's value for masking** (#810): after #805, seven adapters (`kipris`, `korean`, `kosis`, `law`, `lofin`, `neis`, `sgis`) still relied on the parameter name alone. Their names are all on the sensitive list, so nothing leaked; they now pass the value too, and a test fails when a transport request under `providers/` or `core/` is added without it.
- **`list_all` no longer fails on a lone surrogate** (#804): pages are spooled to a temporary file as JSON lines (#789), and a row whose text held a lone surrogate — what a broken character in a provider's response decodes to — serialised but could not be written, so the whole read raised `UnicodeEncodeError` where `list` would have returned the page. The spool is now written and read with `surrogatepass`, and the rows come back unchanged.
- **A key sent under an unlisted parameter name is masked** (#805): the spec executor and the legacy `datago` adapter relied on the parameter's name alone, so a key sent under a name outside `SENSITIVE_PARAM_KEYS` — a spec's own `auth.param_name`, or `datago.generic`'s `_service_key_param` — appeared in the traceback of a failed request. Both now pass the key's value to the transport, as `bok`, `fds` and `seoul` do, and so does the shared `localdata`/`semas` request.
- **A total count of zero is `0`, not `None`** (#806): the hand-written adapters reported `RecordBatch.total_count` as `None` whenever the provider's count was zero, so "the provider said there are no rows" could not be told from "the provider did not say". `datago`, the datago family (`localdata`, `semas`), `lofin`, `law`, `bok`, `korean`, `neis` and `fds` now report `0` when the response carries a zero and `None` only when it carries no count (or one that is not a number). **Behaviour change:** code that tests `total_count is None` to detect an empty result must test `not batch.items` or `total_count == 0` instead. Paging is unchanged, and the spec-based path already kept the two apart.
- `API_SPEC.md`'s examples for `datago.apt_trade` pass `LAWD_CD` and `DEAL_YMD`, the names the spec declares (#790). They passed `lawd_code` and `deal_ym`, which the library sends to the provider verbatim, so the documented call could not work. `tests/unit/test_doc_example_params.py` reads the Python examples of `API_SPEC.md`, the READMEs and `docs/quickstart.md` and fails when a call on a spec-backed dataset passes a filter its spec does not declare.
- **NODATA is an empty result on every path** (#787): data.go.kr's `resultCode` 03 (`NODATA_ERROR`, no record matched the request) came back as an empty batch from localdata and semas (#470) but raised `ProviderResponseError` from the datago envelope parser (the standard, `gyeonggi_msg` and `its_flat` envelopes) and from every spec dataset, since `check_payload_error` had no branch for it and no spec lists it in `ok_values`. All of them now return an empty result — `items == []`, and `total_count` as the response states it. **Behaviour change:** code that caught `ProviderResponseError` with `provider_code == "03"` to detect an empty answer now gets the empty batch instead; every other code raises as before.
- The `R3 review` failure message cites POLICY 14.1, the section that defines the gate, instead of sections 14 and 25 (#722).
- A KOGL licence may no longer waive attribution (#725): every KOGL type requires it, so `attribution_required: false` under `공공누리_1유형`–`4유형` now fails to load, like the commercial-use and modification contradictions #719 added. The rule now lives in one public function, `kpubdata.core.spec.licence_conflicts`, which the loader and `scripts/validate_spec.py` both call — before, `validate_spec.py` checked only the schema and field contradictions, so an external spec author saw a KOGL contradiction only when the spec was loaded.
- `datago.air_quality`'s licence contradicted itself: its attribution and `redistribution: forbidden` follow the source's KOGL type 3 (attribution, no modification), but it said `type: 공공누리_1유형` and `modification_allowed: true`. It now says `공공누리_3유형` and `modification_allowed: false` (#719). A spec whose KOGL type contradicts an explicit `commercial_use: true` (types 2 and 4) or `modification_allowed: true` (types 3 and 4) now fails to load, so a consumer reading the type and one reading the flag cannot be told two different things.
- A missing or null spec digest no longer passes as legacy evidence (#717). #713 (#522) let any fixture whose meta had no non-empty `spec_sha256` through `make verify` as legacy, so deleting the key or setting it to `null`/`""` unbound a fixture from its spec in one edit, and `scripts/record.py` wrote `"spec_sha256": null` when it could not read the spec. Legacy is now the frozen baseline `scripts/legacy_evidence_baseline.txt` — the 28 fixtures tracked without a digest — and only a listed fixture whose meta has no `spec_sha256` key passes unbound; any other missing, `null` or `""` digest fails the spec-binding step. The baseline is a ratchet: it fails when it grows past 28, repeats an entry, or keeps an entry that no longer exists or now carries a digest. `scripts/record.py` stops before calling or writing anything when it cannot compute the digest. The baseline is code-owned like the recorder and verifier.
- The release workflows after #683 (ref validation): `publish-pypi.yml`'s tag pattern was written `\\.`, which grep reads as a literal backslash, so no version tag matched and every dispatched publish failed — it is one pattern now, `v0.8.0` and `v0.7.1a1` match and `v0.8` does not. The ref is validated on the `release: published` path too, reaches the shell through the environment instead of `${{ inputs.ref }}`, must be a tag in this repository and must be on `main` (`git merge-base --is-ancestor`). In `release.yml` the merge path only fires for pull requests into `main`, a re-run after the tag was pushed but `gh release create` failed finishes the release when the tag is on the same commit instead of stopping at "tag must not exist", and the `release` concurrency group moved from the workflow to the two jobs, so ordinary pull requests closing no longer queue in it and cannot cancel a waiting release. #683 itself had no CHANGELOG entry: it makes a release run only from `main` and validates the publish ref.
- `datago.bus_arrival`'s licence and code columns (#732, #733, via #740): the licence drops its unconfirmed `공공누리_1유형` type and says `redistribution: unknown` until the terms are confirmed from the provider page, and six ID columns (`stationId`, `routeId`, `routeDestId`, `vehId1`, `vehId2`, `routeTypeCd`) are text with `semantic_kind: code` — a column named like a request parameter is not a number (ADR 0006).

### Security

- **`Secret scan (gitleaks)` no longer fails on another branch's commits** (#774). Without `--log-opts`, gitleaks runs `git log --all`, which — combined with `fetch-depth: 0` pulling in every remote branch — walked unmerged PR branches too, so a synthetic test key on someone else's open branch turned this job, which `CI gate` needs, red for runs that never touched that branch. The job now scopes `--log-opts` to the run's own commits: a pull request scans `base..head`, a push to `main` scans `before..sha` (or just `sha` for a brand-new branch, where `before` is all zeros), and `schedule`/`workflow_dispatch` scan the default branch's full history only — never another branch. `.gitleaksignore` is unaffected. Ported from kpubdata-studio#685/#686.
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
