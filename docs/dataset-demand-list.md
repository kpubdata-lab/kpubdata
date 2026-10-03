# Dataset Demand List and Priority ([#530](https://github.com/kpubdata-lab/kpubdata/issues/530))

Ranked list of datasets to convert from catalogue to spec next.
Every entry has a reason. Nothing without a reason is on this list.

**Relation to `docs/dataset-prioritization.yaml`.** That file scores datasets on
demand, pain, openness and stability and is the long-term ranking. This list is the
*work queue*: it puts first what builder is blocked on and what users asked for, so
its order can differ from the scores. When they disagree, this list decides what is
converted next; the YAML decides where a dataset lands once the queue is empty.

## Tier 1 — Builder already uses these (blocked on spec conversion)

These datasets are in builder's pipeline configs. Rows 1–10 are already spec; the
DUR family (rows 11–19) is still catalogue-only in kpubdata. Converting it unlocks
builder's [#636](https://github.com/kpubdata-lab/kpubdata-builder/issues/636) (rebuild HF datasets through the engine).

| # | Dataset | Reason | Builder Config |
|---|---|---|---|
| 1 | `datago.apt_trade` | Paper dataset. Builder param_grid 1,500 combos. Already spec ✅ | `seoul_apartment_trades` |
| 2 | `datago.apt_rent` | Paper dataset. Builder param_grid 1,500 combos. Already spec ✅ | `seoul_apartment_rent` |
| 3 | `bok.base_rate` | Builder uses for interest rate analysis. No activation needed. | `korea_base_rate` |
| 4 | `datago.ultra_srt_ncst` | Builder weather pipeline. Already spec ✅ | `weather_ultra_srt_ncst` |
| 5 | `datago.village_fcst` | Builder weather pipeline. Already spec ✅ | `weather_village_fcst` |
| 6 | `datago.air_quality` | Builder pipeline. Already spec ✅ | `air_quality` |
| 7 | `datago.tour_kor_area` | Builder tourism pipeline. Already spec ✅ | `tour_kor_area` |
| 8 | `datago.tour_kor_festival` | Builder tourism pipeline. Already spec ✅ | `tour_kor_festival` |
| 9 | `datago.tour_kor_keyword` | Builder tourism pipeline. Already spec ✅ | `tour_kor_keyword` |
| 10 | `datago.tour_kor_location` | Builder tourism pipeline. Already spec ✅ | `tour_kor_location` |
| 11–19 | `datago.dur_*` (9) | DUR (Drug-Use Review) family. Builder has 9 pipeline configs. All are data.go.kr JSON with standard envelope. | `dur_*` |

## Tier 2 — Requested by users (dataset-request issues)

| # | Dataset | Reason | Issue |
|---|---|---|---|
| 20 | `datago.offi_trade_view` | Officetel sale — Dev variant requested | [#402](https://github.com/kpubdata-lab/kpubdata/issues/402) |
| 21 | `datago.apt_rent_view` | Apt rent Dev variant requested | [#401](https://github.com/kpubdata-lab/kpubdata/issues/401) |
| 22 | `datago.school_info` | NEIS school basic info via data.go.kr | [#400](https://github.com/kpubdata-lab/kpubdata/issues/400) |
| 23 | `datago.airkorea_forecast` | Already spec ✅ as `airkorea_forecast` (requested as `air_forecast`) | [#399](https://github.com/kpubdata-lab/kpubdata/issues/399) |
| 24 | `datago.ultra_srt_fcst` | Already spec ✅ (was #398) | [#398](https://github.com/kpubdata-lab/kpubdata/issues/398) |
| 25 | `datago.air_station` | Already spec ✅ (was #396) | [#396](https://github.com/kpubdata-lab/kpubdata/issues/396) |

## Tier 3 — High-value catalogue datasets (high volume, public interest)

| # | Dataset | Reason |
|---|---|---|
| 26 | `localdata.*` (59) | Marked retired by [#603](https://github.com/kpubdata-lab/kpubdata/issues/603); the evidence disagrees (3 answered, 56 need activation — [#618](https://github.com/kpubdata-lab/kpubdata/issues/618)). Do not convert until #618 is decided. |
| 27 | `sgis.boundary.*` (3) | Spatial analysis foundation. Token auth is unique. |
| 28 | `krx.kospi_index` | Financial analysis. No auth needed. |
| 29 | `kosis.population_migration` | Demographic analysis. Already requested for paper. |

## Already Converted (23 spec datasets — no action needed)

All 23 spec datasets are listed in `SUPPORTED_DATA.md`. 22 pass `make verify` with
recorded fixtures; `datago.ocean_buoy` has no fixture yet and is listed as `진행 중`
(spec `status: unstable`).

## Summary

- **Already spec**: 23 datasets (real estate 7, weather 3, air 3, tourism 4, hospital, metro fare, ocean buoy, localdata 3)
- **Next priority**: 9 DUR datasets (builder uses them, standard envelope, mechanical conversion)
- **After that**: 3 requested datasets from issues #400–#402 (#399 is done as `airkorea_forecast`)
- **On hold**: 59 localdata datasets until #618 settles whether they are retired
