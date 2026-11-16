# Manual live API smoke during the MVP

The SDK's normal CI runs unit and fixture/replay tests on GitHub-hosted runners.
A separate real-provider smoke workflow historically used a Korean
`self-hosted, kr` runner; it is not currently evidence of live verification.
During the MVP, **do not install or operate an always-on runner**. Real API
checks are performed only when needed on a trusted workstation with a
Korean outbound IP. The scheduled `Smoke (live)` trigger is paused (#887).
The separate `Live probe` workflow is not a substitute for a passing
authenticated integration test.

## Prerequisites

1. The relevant public-data API service is approved for the operator's own key.
   Approval may be specific to a dataset or service.
2. **Transport safety is a blocker:** #893 tracks remaining plain-HTTP spec
   endpoints. Do **not** run credentialed tests against these endpoints until
   they use verified HTTPS without unsafe credential-bearing redirects. Check
   the exact dataset/adapter call path, not just the example URL. If this
   cannot be established, use fixture/replay tests instead.
3. The machine is trusted, has a domestic egress IP and has `uv` installed.
   No repository secrets, runner registration or cloud AI agent are required.

## One-time, on-demand verification

On that workstation, from a clean checkout:

```bash
uv sync --frozen --extra dev
uv run pytest
```

The default `pytest` run intentionally excludes live integration tests. After
selecting **a specific test whose outbound requests were verified HTTPS** and
ensuring approval for its API, enter the key without displaying it or writing
it to shell history:

```bash
read -r -s -p "Approved data.go.kr key: " KPUBDATA_DATAGO_API_KEY
printf '\n'
export KPUBDATA_DATAGO_API_KEY

# Replace the test name only after checking its entire request path is HTTPS.
KPUBDATA_MODE= KPUBDATA_CACHE=0 uv run pytest -o addopts= -m integration tests/integration/test_datago_live.py \
  -k 'REPLACE_WITH_VERIFIED_HTTPS_TEST_NAME' -ra --junitxml=smoke-datago.xml

# Must contain consistent testcase outcomes and at least one pass.
uv run python scripts/junit_summary.py smoke-datago.xml \
  --label "datago live" --require-passed

unset KPUBDATA_DATAGO_API_KEY
```

The command explicitly disables replay and response caching. The shared live
client also refuses replay mode and disables ambient caching: a replay or cached
result cannot stand in for current provider traffic. The strict JUnit check
rejects missing or contradictory testcase records as well as all-skipped runs.

Set `KPUBDATA_DATAGO_REALESTATE_ENABLED=1` only when the relevant real-estate
API has been approved. Never commit credentials, raw authenticated HTTP logs,
or private provider responses. If a test fails or is skipped, record it as
**failed / not verified**, not as healthy. Run the summary even if pytest fails
so that the attempted test counts are visible, and inspect `-ra` skip reasons.

Capture only a concise evidence record in the existing issue: date/time (KST),
commit, executed test names, approved dataset IDs, count of passed/failed/skipped,
the command, and any sanitized error classification. Do not claim full dataset
coverage from one selected smoke test.

This issue record does not satisfy trusted fixture-recorder authorship checks
and does not promote dataset support or verification status. Those require the
existing reviewed recording and metadata workflow.

## After the MVP

If repeated manual checks become necessary, consider an isolated, resource-
limited **ephemeral** domestic runner with single-job concurrency. Re-enable
an optional limited schedule only in a separate reviewed change after HTTPS
safety, runner isolation, measured host impact and real-call evidence are
confirmed. Do not use a persistent public-repository runner by default.

Tracking: [#887](https://github.com/kpubdata-lab/kpubdata/issues/887)
(runtime) and [#893](https://github.com/kpubdata-lab/kpubdata/issues/893)
(HTTPS/credentials).
