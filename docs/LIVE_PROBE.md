# Live Probe Infrastructure (#465)

Single shared workflow that both Cross-repo E2E (#282) and Drift Detection (#382) consume.

## Architecture

```
.github/workflows/live-probe.yml (kpubdata repo)
        │
        ├── schedule: nightly (03:00 KST)
        ├── input: Top 50 datasets from docs/dataset-prioritization.yaml
        ├── output: probe-result.json (committed to docs/status/)
        │
        ├── consumer 1 (#282): Cross-repo E2E reads probe-result.json.
        │   status == HEALTHY datasets run live; others fall back to fixtures.
        │   E2E never goes red from upstream failures.
        │
        └── consumer 2 (#382): Drift detection compares consecutive results.
            2+ consecutive failures → drift issue filed automatically.
```

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
      "dataset": "datago.apt_trade",
      "status": "healthy",
      "http_status": 200,
      "result_code": "00",
      "classification": "available",
      "latency_ms": 342,
      "schema_hash": "a3f5c8...",
      "probed_at": "2026-09-29T00:00:01+00:00"
    },
    {
      "dataset": "datago.air_forecast",
      "status": "unhealthy",
      "http_status": 403,
      "result_code": "30",
      "classification": "application_required",
      "latency_ms": 0,
      "probed_at": "2026-09-29T00:00:02+00:00"
    }
  ]
}
```

### Status Values

| Status | Meaning | E2E Action | Drift Action |
|---|---|---|---|
| `healthy` | API responds, data valid | Run live | Record pass |
| `degraded` | API responds, schema changed | Run live + warn | Record + compare schema_hash |
| `unhealthy` | API fails (403, 429, 5xx, timeout) | Fall back to fixture | Record failure |
| `retired` | Permanently gone (NO_OPENAPI_SERVICE) | Fall back to fixture | File drift issue |
| `unknown` | Probe itself failed (network error) | Fall back to fixture | Record unknown |

## Secret Naming Convention

| Secret | Provider | Notes |
|---|---|---|
| `KPUBDATA_DATAGO_API_KEY` | data.go.kr family | Shared: datago, localdata, lofin, semas, neis, fds |
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

| Classification | HTTP | Provider Code | E2E | Drift |
|---|---|---|---|---|
| `available` | 200 | 00 | ✅ live | pass |
| `application_required` | 403 | 20, 30, 31, 32 | fixture | pass (not an outage) |
| `rate_limited` | 429 | 22 | fixture | pass (quota, not drift) |
| `params_invalid` | 400 | 10, 11 | fixture | pass (probe config issue) |
| `temporarily_unavailable` | 5xx | 01, 02 | fixture | count toward drift |
| `retired` | 200 | 12 | fixture | immediate drift issue |
| `network_error` | — | — | fixture | count toward drift |

## Daily Call Budget

| Provider | Datasets (Top 50) | Rate Limit | Calls/Day | Headroom |
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
    curl -s https://raw.githubusercontent.com/yeongseon/kpubdata/main/docs/status/probe-result.json
    # Filter healthy datasets for live E2E
```

### #382 Drift Detection
```yaml
# In kpubdata's drift workflow  
- name: Compare with previous probe
  run: |
    # Load previous + current probe-result.json
    # File drift issue for 2+ consecutive unhealthy
```
