# Dataset Demand List and Priority (#530)

Ranked list of datasets to convert from catalogue to spec next.
Every entry has a reason. Nothing without a reason is on this list.

## Tier 1 — Builder already uses these (blocked on spec conversion)

These datasets are in builder's pipeline configs but still catalogue-only in kpubdata.
Converting them unlocks builder's `#636` (rebuild HF datasets through the engine).

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
| 11–20 | `datago.dur_*` (10) | DUR (Drug-Use Review) family. Builder has 10 pipeline configs. All are data.go.kr JSON with standard envelope. | `dur_*` |

## Tier 2 — Requested by users (dataset-request issues)

| # | Dataset | Reason | Issue |
|---|---|---|---|
| 21 | `datago.offi_trade_view` | Officetel sale — Dev variant requested | #402 |
| 22 | `datago.apt_rent_view` | Apt rent Dev variant requested | #401 |
| 23 | `datago.school_info` | NEIS school basic info via data.go.kr | #400 |
| 24 | `datago.air_forecast` | MinuDust forecast (replaces retired pharmacy svc) | #399 |
| 25 | `datago.ultra_srt_fcst` | Already spec ✅ (was #398) | #398 |
| 26 | `datago.air_station` | Already spec ✅ (was #396) | #396 |

## Tier 3 — High-value catalogue datasets (high volume, public interest)

| # | Dataset | Reason |
|---|---|---|
| 27 | `localdata.*` (59) | **Upstream closed** (#527). Mark retired; do NOT convert. |
| 28 | `sgis.boundary.*` (3) | Spatial analysis foundation. Token auth is unique. |
| 29 | `krx.kospi_index` | Financial analysis. No auth needed. |
| 30 | `kosis.population_migration` | Demographic analysis. Already requested for paper. |

## Already Converted (23 spec datasets — no action needed)

All 23 spec datasets are listed in `SUPPORTED_DATA.md` and pass `make verify`.

## Summary

- **Already spec**: 23 datasets (apt_trade, apt_rent, air_quality, weather, tourism, localdata 3)
- **Next priority**: 10 DUR datasets (builder uses them, standard envelope, mechanical conversion)
- **After that**: 4 requested datasets from issues #399-#402
- **Do NOT convert**: 59 localdata datasets (upstream closed)
