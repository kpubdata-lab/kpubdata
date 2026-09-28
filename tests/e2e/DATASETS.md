# Cross-repo E2E Dataset Selection (#467)

## Selection Axes

Each E2E representative dataset must cover at least one axis below.
A dataset may cover multiple axes (noted in the Coverage column).

| Axis | Value | Dataset | Coverage |
|---|---|---|---|
| Envelope | JSON (standard) | `datago.apt_trade` | Envelope, Auth(query), Pagination(page), Numeric casting, 활용신청 |
| Envelope | XML | `datago.village_fcst` | Envelope(XML), Auth(query) |
| Envelope | Seoul own | `seoul.bike_station_master` | Envelope(Seoul), Pagination(index), Auth(app key) |
| Pagination | None | `bok.base_rate` | Pagination(none), Auth(query), Small response, No 활용신청 |
| Pagination | Page/Row | `datago.air_station` | Pagination(page/row) |
| Auth | Header/Token | `sgis.boundary.sido` | Auth(consumer key+secret), Geometry |
| Field type | Geometry | `sgis.boundary.sido` | GeoJSON coordinates |
| 활용신청 | Required | `datago.apt_trade` | Activation-gated |
| 활용신청 | Not required | `bok.base_rate` | Open |

## PR Lightweight E2E (2–3 datasets, runs on every PR)

1. **`datago.apt_trade`** — JSON envelope, page pagination, numeric casting (#452 regression), 활용신청 required. Covers the most axes in one dataset.
2. **`bok.base_rate`** — No pagination, no 활용신청, small response. Fastest complete path.

## Nightly Full E2E (all datasets above plus)

3. **`datago.village_fcst`** — XML envelope parsing.
4. **`seoul.bike_station_master`** — Seoul's own envelope + index-based pagination.
5. **`sgis.boundary.sido`** — Token-based auth + GeoJSON geometry.

## Reasoning

- `datago.apt_trade` is the golden example throughout the codebase (AGENTS.md, README, spec pipeline). It exercises the formatted-numeric casting from #452/#461 (`dealAmount: "1,200"`).
- `bok.base_rate` is the simplest complete path — no pagination, no activation, always available. If this fails, the entire pipeline is broken.
- `datago.village_fcst` is the only XML-envelope spec; dropping it would leave XML parsing untested.
- `seoul.bike_station_master` covers Seoul's non-standard envelope and their index-window pagination, which no datago dataset exercises.
- `sgis.boundary.sido` is the only dataset with consumer-key+secret token auth and GeoJSON geometry responses.

## Prerequisites

All selected datasets must have recorded fixtures for offline replay testing.
`datago.apt_trade`, `bok.base_rate`, `datago.village_fcst` are spec-backed with fixtures.
`seoul.bike_station_master` and `sgis.boundary.sido` are catalogue-based; their adapters have unit tests with fixtures.

## Related

- #282 (cross-repo E2E test)
- #452, #461 (numeric casting)
