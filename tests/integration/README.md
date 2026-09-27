# Integration test notes

`tests/integration/test_datago_live.py` includes a small opt-in gate for endpoints that require extra data.go.kr activation approval scope on top of `KPUBDATA_DATAGO_API_KEY`.

## data.go.kr live test env gates

- Base data.go.kr live tests run when `KPUBDATA_DATAGO_API_KEY` is set.
- Real-estate scoped endpoints and the current `bus_arrival` live check additionally require:

```bash
export KPUBDATA_DATAGO_REALESTATE_ENABLED=1
```

Keep this flag **off by default** unless the current key has already been approved for the required data.go.kr activation approval scope. Otherwise those tests skip with a message explaining how to enable them.

## Why this exists

- KMA (Korea Meteorological Administration) date-bound live tests use runtime KST dates so they do not expire.
- Ministry of Land real-estate (RTMS-series APIs) may return 403/404 until approval is granted per service, so base runs skip them.
- Seoul Metro Authority (SMA) metro live tests are unconditionally skipped until upstream issues are resolved:
  - `metro_fare`: issue [#139](https://github.com/yeongseon/kpubdata/issues/139)
  - `metro_path`: issue [#140](https://github.com/yeongseon/kpubdata/issues/140)
