# 데이터셋 검증 상태

> 생성: `2026-10-12T03:39:19+00:00` — `scripts/gen_status_page.py` (직접 편집 금지)

## 요약

- spec 데이터셋: **25종** (검증 24종, 최신 검증일 2026-10-01 기준 90일 이내 24종)
- catalogue 데이터셋: 131종 (bok 4, datago 25, fds 1, kipris 1, korean 1, kosis 2, krx 3, law 3, localdata 56, lofin 6, neis 2, semas 17, seoul 7, sgis 3)
- SUPPORTED_DATA 행 분포: {'지원': 24, '활용신청 대기': 94, '스키마만': 36, '폐기': 1, '진행 중': 1, '예정': 1} (합계 157)

## 계열별 통과율

통과율 = 실API 검증을 통과한 데이터셋 / 계열 전체. 테스트 통과율 = fixture·contract 테스트를 통과한 데이터셋 / 계열 전체. 원천은 `src/kpubdata/dataset_metadata.json`.

| 계열 | 전체 | 실API 통과 | 통과율 | 테스트 통과 | 테스트 통과율 |
|---|---|---|---|---|---|
| bok | 4 | 0 | 0.0% | 4 | 100.0% |
| datago | 47 | 21 | 44.7% | 45 | 95.7% |
| fds | 1 | 0 | 0.0% | 1 | 100.0% |
| kipris | 1 | 0 | 0.0% | 1 | 100.0% |
| korean | 1 | 0 | 0.0% | 1 | 100.0% |
| kosis | 2 | 0 | 0.0% | 2 | 100.0% |
| krx | 3 | 0 | 0.0% | 3 | 100.0% |
| law | 3 | 0 | 0.0% | 3 | 100.0% |
| localdata | 59 | 3 | 5.1% | 59 | 100.0% |
| lofin | 6 | 0 | 0.0% | 6 | 100.0% |
| neis | 2 | 0 | 0.0% | 2 | 100.0% |
| semas | 17 | 0 | 0.0% | 17 | 100.0% |
| seoul | 7 | 0 | 0.0% | 7 | 100.0% |
| sgis | 3 | 0 | 0.0% | 3 | 100.0% |
| **전체** | 156 | 24 | 15.4% | 154 | 98.7% |

## spec 데이터셋별 최종 검증일

| 데이터셋 | 최종 검증 | 상태 |
|---|---|---|
| `datago.air_quality` | 2026-09-09 | active |
| `datago.air_station` | 2026-09-09 | active |
| `datago.airkorea_forecast` | 2026-09-09 | active |
| `datago.apt_rent` | 2026-09-09 | active |
| `datago.apt_trade` | 2026-09-12 | active |
| `datago.bus_arrival` | 2026-10-01 | active |
| `datago.hospital_info` | 2026-09-09 | active |
| `datago.metro_fare` | 2026-09-09 | active |
| `datago.ocean_buoy` | - | unstable |
| `datago.offi_rent` | 2026-09-09 | active |
| `datago.offi_trade` | 2026-09-09 | active |
| `datago.rh_rent` | 2026-09-09 | active |
| `datago.sh_rent` | 2026-09-09 | active |
| `datago.sh_trade` | 2026-09-09 | active |
| `datago.social_enterprise` | 2026-10-01 | active |
| `datago.tour_kor_area` | 2026-09-10 | active |
| `datago.tour_kor_festival` | 2026-09-10 | active |
| `datago.tour_kor_keyword` | 2026-09-10 | active |
| `datago.tour_kor_location` | 2026-09-10 | active |
| `datago.ultra_srt_fcst` | 2026-10-01 | active |
| `datago.ultra_srt_ncst` | 2026-10-01 | active |
| `datago.village_fcst` | 2026-09-09 | active |
| `localdata.bakery` | 2026-09-09 | active |
| `localdata.general_restaurant` | 2026-09-09 | active |
| `localdata.rest_cafe` | 2026-09-09 | active |
