# Live Probe Infrastructure (#465)

Single shared workflow that both Cross-repo E2E (#282) and Drift Detection (#382) consume.

Every status and classification name on this page is defined in
`src/kpubdata/core/status.py` ([ADR 0005](adrs/0005-dataset-status-vocabulary.md)).
`tests/unit/test_status_vocabulary.py` fails when a name here or a result code in
the classification table disagrees with the code.

## Architecture

```
.github/workflows/live-probe.yml (kpubdata repo)
        │
        ├── schedule: nightly (03:00 KST)
        ├── input: every dataset listed in docs/dataset-prioritization.yaml
        ├── output: probe-result.json (committed to docs/status/)
        │
        ├── consumer 1 (#282): Cross-repo E2E reads probe-result.json.
        │   status == available datasets run live; others fall back to fixtures.
        │   E2E never goes red from upstream failures.
        │
        └── consumer 2 (#382): Drift detection compares consecutive results.
            3 consecutive transient failures (TRANSIENT_FAILURE_STREAK)
            → drift issue filed; retired or schema/parameter/endpoint
            changes file one immediately (DATASET_STATUS.md).
```

## Python API

The probe is public on `Client` (#694). `kpubdata probe` is a thin wrapper
over the same calls.

```python
from kpubdata import Client

client = Client(provider_keys={"datago": user_key}, env_keys=False)
result = client.probe("datago.apt_trade")  # ProbeResult | None
results = client.probe_all(provider="datago")  # list[ProbeResult]
```

`result.status` is one of `kpubdata.PROBE_STATUSES` (see
[Failure Classification](#failure-classification)). With `env_keys=False` the
client uses only the keys passed to it: a provider with no key is reported as
`auth_unknown` without a call, even when an environment variable holds a key for
it. Keys never appear in `ProbeResult.detail` or in log records.

## Core Principle

> **E2E validates the pipeline. Probe validates the external API.**
> An external API failure is a Drift Event, not an E2E failure.

## probe-result.json Schema

```json
{
  "probed_at": "2026-09-29T00:00:00+00:00",
  "runner": "github-actions",
  "results": [
    {
      "dataset_id": "datago.apt_trade",
      "service_id": "RTMSDataSvcAptTrade",
      "status": "available",
      "http_status": 200,
      "result_code": null,
      "classification": "HEALTHY",
      "latency_ms": 342,
      "schema_hash": "a3f5c8d0e1b2",
      "probed_at": "2026-09-29T00:00:01+00:00",
      "detail": ""
    },
    {
      "dataset_id": "datago.airkorea_forecast",
      "service_id": "ArpltnInforInqireSvc",
      "status": "application_required",
      "http_status": 403,
      "result_code": "30",
      "classification": "APPLICATION_REQUIRED",
      "latency_ms": 187,
      "schema_hash": null,
      "probed_at": "2026-09-29T00:00:02+00:00",
      "detail": "AuthError: SERVICE_KEY_IS_NOT_REGISTERED"
    }
  ]
}
```

### Fields

- `status` is the probe outcome, one of `ProbeStatus` (see
  [Failure Classification](#failure-classification)).
- `classification` is the drift signal that outcome feeds the state machine, one of
  `DriftClassification`, or `null` when the outcome says nothing about the upstream
  API. The mapping is `PROBE_TO_DRIFT`.
- `result_code` is the provider code read off the **raised error** — on success it
  is `null`, because a successful query does not parse the envelope. `http_status`
  is `200` on success (the executor raises on anything else) and the error's status
  otherwise.
- `schema_hash` fingerprints the field names of the returned page; it is `null`
  when the call failed or the page was empty. Every evidence field is `null` where
  it could not be observed — never guessed.
- A schema change is not a probe outcome. The drift step compares `schema_hash`
  with the previous run and emits `SCHEMA_CHANGED` itself.

## Secret Naming Convention

| Secret | Provider | Notes |
|---|---|---|
| `KPUBDATA_DATAGO_API_KEY` | data.go.kr family | Shared: datago, localdata, lofin, semas |
| `KPUBDATA_NEIS_API_KEY` | 나이스 교육정보 개방포털 | Own key — the adapter reads `neis` with no fallback |
| `KPUBDATA_FDS_API_KEY` | 식품안전나라 | Own key — the adapter reads `fds` with no fallback |
| `KPUBDATA_BOK_API_KEY` | 한국은행 ECOS | |
| `KPUBDATA_KOSIS_API_KEY` | 통계청 KOSIS | |
| `KPUBDATA_SEOUL_API_KEY` | 서울 열린데이터광장 | |
| `KPUBDATA_SGIS_API_KEY` | SGIS (consumer_key) | |
| `KPUBDATA_SGIS_CONSUMER_SECRET` | SGIS (consumer_secret) | |
| `KPUBDATA_KIPRIS_API_KEY` | 특허청 KIPRIS | |
| `KPUBDATA_KOREAN_API_KEY` | 국립국어원 | |
| `KPUBDATA_LAW_API_KEY` | 법제처 | |

**Environment**: Use a `live-probe` GitHub Environment (not repo-level secrets).
This allows different keys for different contexts and protects against fork PRs.

## Fork PR Behavior

Fork PRs cannot access secrets. The workflow:
1. Detects `github.event.pull_request.head.repo.fork == true`
2. Sets `KPUBDATA_PROBE_MODE=fixture-only`
3. Skips live calls entirely; only fixture-based tests run

## Failure Classification

Provider codes are the data.go.kr result codes `kpubdata._probe` reads off
`provider_code`; HTTP statuses apply when no code is available.

| Status | HTTP | Provider Code | E2E | Drift signal |
|---|---|---|---|---|
| `available` | 200 | 00 | ✅ live | `HEALTHY` |
| `application_required` | 403 | 20, 30, 31 | fixture | `APPLICATION_REQUIRED` |
| `auth_unknown` | 401 | 32 | fixture | `AUTH` |
| `rate_limited` | 429 | 22 | fixture | `RATE_LIMIT` |
| `params_invalid` | 400 | 10 | fixture | — (probe config issue) |
| `temporarily_unavailable` | 5xx | 01, 02 | fixture | `SERVICE_DOWN` |
| `retired` | 200 | 12 | fixture | `RETIRED` (immediate drift issue) |
| `network_error` | — | — | fixture | `UNKNOWN` |
| `insufficient_metadata` | — | — | fixture | — (unparseable body) |

Code 32 (`UNREGISTERED_IP`) is `auth_unknown`, not `application_required`: the key
is registered, the caller's IP is not, and applying again would not help.

## Daily Call Budget

| Provider | Datasets | Rate Limit | Calls/Day | Headroom |
|---|---|---|---|---|
| data.go.kr | ~35 | 1,000/day per key | 35 (1 per dataset) | 96.5% |
| BOK | 4 | 500/day | 4 | 99.2% |
| KOSIS | 2 | 500/day | 2 | 99.6% |
| Seoul | 5 | 500/day | 5 | 99.0% |
| SGIS | 3 | 100/day | 3 | 97.0% |
| KRX | 3 | No auth needed | 3 | N/A |

**Conclusion**: With 1 probe call per dataset per day, no provider's rate limit is approached.

## Consumers

### #282 Cross-repo E2E
```yaml
# In builder's cross-repo-contract.yml
- name: Read probe results
  run: |
    curl -s https://raw.githubusercontent.com/kpubdata-lab/kpubdata/main/docs/status/probe-result.json
    # Filter status == "available" datasets for live E2E
```

### #382 Drift Detection

Implemented by `scripts/drift_detect.py`, run by this workflow's **drift** job
every night:

- Compares the current and the previous `probe-result.json`; a differing
  `schema_hash` emits `SCHEMA_CHANGED` itself (it is not a probe outcome).
- Applies `kpubdata.core.status.transition` per dataset
  ([DATASET_STATUS.md](DATASET_STATUS.md)): transient failures move nothing
  before `TRANSIENT_FAILURE_STREAK` (3) consecutive nights, schema/parameter/
  endpoint changes break immediately, restores file nothing.
- Streaks and `previous_status` survive between runs in the `drift-state`
  artifact.
- Files one `[drift] <dataset_id>: <from> → <to> (<classification>)` issue per
  transition that needs a person, skipping datasets with an open drift issue;
  the status_history entry to apply rides in the issue body.
