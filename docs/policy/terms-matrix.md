# Provider × Dataset Terms Matrix (#524)

> Single source of truth for redistribution rights per provider.
> The spec's `license` fields (#617) are filled FROM this matrix, not the other way round.
> Re-check quarterly. Last checked: 2026-09-30.

## Which datasets can be published (#785)

**Decision (2026-10-04): only a dataset that declares its terms can be published
publicly.** Terms are declared in a dataset's spec (`license`), so today that is the
spec-backed datasets and no catalogue-only one. The others are not filled in from the
provider-level table below: a KOGL type is set per service on its data.go.kr page, and
a term nobody confirmed there must not read as permission (#525, #732).

What follows from it, and where it is enforced:

- `DatasetRef.license` is `None` for a dataset that declares nothing, and `None` means
  unknown — never "no restrictions". `tests/unit/test_declared_terms_decision.py` holds
  that every dataset with terms is spec-backed and every catalogue-only dataset has none.
- Builder reads `license.redistribution` at publish. A source whose dataset declares
  nothing is `unknown`, and a public publish of it is refused with
  `redistribution_unknown` ("the dataset declares no redistribution terms"); a private
  one is still possible (kpubdata-builder#688, `tests/unit/test_redistribution.py`).
- A catalogue-only dataset becomes publishable when it is migrated to a spec with terms
  confirmed from its provider page — the same step that records its live evidence
  (#409). There is no separate "fill in the licence" path.

## Legend

- **Redistribution**: `allowed` / `non_commercial` / `forbidden` / `unknown`
- **Commercial**: `yes` / `no` / `unknown`
- **Modification**: `yes` / `no` / `unknown`
- **KOGL**: 공공누리 (Korea Open Government License) type

## data.go.kr (datago, localdata, lofin, semas, neis, fds)

data.go.kr datasets carry a KOGL type per service. The type determines everything.

| KOGL Type | Redistribution | Commercial | Modification | Attribution |
|---|---|---|---|---|
| 제1유형 (Type 1) | allowed | yes | yes | 출처표시 (source attribution) |
| 제2유형 (Type 2) | allowed | non-commercial | yes | 출처표시 |
| 제3유형 (Type 3) | allowed | yes | **no** | 출처표시 + 변경금지 표시 |
| 제4유형 (Type 4) | allowed | non-commercial | **no** | 출처표시 + 변경금지 표시 |

### Per-dataset breakdown (spec-backed)

| Dataset | KOGL | Redistribution | Commercial | Modification | Attribution Format | Source URL | Checked |
|---|---|---|---|---|---|---|---|
| `apt_trade` | 1 | allowed | yes | yes | 공공누리 제1유형(출처표시) — 국토교통부 | [link](https://www.data.go.kr/data/15098249/openapi.do) | 2026-09-30 |
| `apt_rent` | 1 | allowed | yes | yes | 공공누리 제1유형(출처표시) — 국토교통부 | [link](https://www.data.go.kr/data/15098191/openapi.do) | 2026-09-30 |
| `offi_trade` | 1 | allowed | yes | yes | 공공누리 제1유형 — 국토교통부 | [link](https://www.data.go.kr/data/15098530/openapi.do) | 2026-09-30 |
| `offi_rent` | 1 | allowed | yes | yes | 공공누리 제1유형 — 국토교통부 | [link](https://www.data.go.kr/data/15098527/openapi.do) | 2026-09-30 |
| `rh_rent` | 1 | allowed | yes | yes | 공공누리 제1유형 — 국토교통부 | [link](https://www.data.go.kr/data/15099144/openapi.do) | 2026-09-30 |
| `sh_rent` | 1 | allowed | yes | yes | 공공누리 제1유형 — 국토교통부 | [link](https://www.data.go.kr/data/15099149/openapi.do) | 2026-09-30 |
| `sh_trade` | 1 | allowed | yes | yes | 공공누리 제1유형 — 국토교통부 | [link](https://www.data.go.kr/data/15099147/openapi.do) | 2026-09-30 |
| `village_fcst` | 1 | allowed | yes | yes | 공공누리 제1유형(출처표시) — 기상청 | [link](https://www.data.go.kr/data/15084084/openapi.do) | 2026-09-30 |
| `ultra_srt_fcst` | 1 | allowed | yes | yes | 공공누리 제1유형 — 기상청 | [link](https://www.data.go.kr/data/15084086/openapi.do) | 2026-09-30 |
| `ultra_srt_ncst` | 1 | allowed | yes | yes | 공공누리 제1유형 — 기상청 | [link](https://www.data.go.kr/data/15084085/openapi.do) | 2026-09-30 |
| `air_quality` | **3** | **forbidden** (변경금지) | yes | **no** | 공공누리 제3유형(변경금지) — 한국환경공단 | [link](https://www.data.go.kr/data/15000581/openapi.do) | 2026-09-30 |
| `air_station` | 1 | allowed | yes | yes | 공공누리 제1유형 — 한국환경공단 | [link](https://www.data.go.kr/data/15073877/openapi.do) | 2026-09-30 |
| `airkorea_forecast` | 1 | allowed | yes | yes | 공공누리 제1유형 — 한국환경공단 | [link](https://www.data.go.kr/data/15073892/openapi.do) | 2026-09-30 |
| `hospital_info` | 1 | allowed | yes | yes | 공공누리 제1유형 — 보건복지부 | [link](https://www.data.go.kr/data/15001671/openapi.do) | 2026-09-30 |
| `metro_fare` | 1 | allowed | yes | yes | 공공누리 제1유형 — 국토교통부 | [link](https://www.data.go.kr/data/15093677/openapi.do) | 2026-09-30 |
| `ocean_buoy` | 1 | allowed | yes | yes | 공공누리 제1유형 — 해양수산부 | [link](https://www.data.go.kr/data/15044873/openapi.do) | 2026-09-30 |
| `tour_kor_area` | 1 | allowed | yes | yes | 공공누리 제1유형 — 문화체육관광부 | [link](https://www.data.go.kr/data/15004575/openapi.do) | 2026-09-30 |
| `tour_kor_festival` | 1 | allowed | yes | yes | 공공누리 제1유형 — 문화체육관광부 | [link](https://www.data.go.kr/data/15044652/openapi.do) | 2026-09-30 |
| `tour_kor_keyword` | 1 | allowed | yes | yes | 공공누리 제1유형 — 문화체육관광부 | [link](https://www.data.go.kr/data/15044653/openapi.do) | 2026-09-30 |
| `tour_kor_location` | 1 | allowed | yes | yes | 공공누리 제1유형 — 문화체육관광부 | [link](https://www.data.go.kr/data/15044654/openapi.do) | 2026-09-30 |
| `localdata.bakery` | 1 | allowed | yes | yes | 공공누리 제1유형 — 행정안전부 | [link](https://www.data.go.kr/data/15044750/openapi.do) | 2026-09-30 |
| `localdata.general_restaurant` | 1 | allowed | yes | yes | 공공누리 제1유형 — 행정안전부 | [link](https://www.data.go.kr/data/15044750/openapi.do) | 2026-09-30 |
| `localdata.rest_cafe` | 1 | allowed | yes | yes | 공공누리 제1유형 — 행정안전부 | [link](https://www.data.go.kr/data/15044750/openapi.do) | 2026-09-30 |

### Call quota (data.go.kr family)

| Plan | Daily calls | Note |
|---|---|---|
| Default (무료) | 1,000/day per key | Per service, not per dataset |
| 활용목적 increase | Up to 10,000/day | Request via 마이페이지 |

## 한국은행 ECOS (bok)

| Item | Value |
|---|---|
| Redistribution | allowed |
| Commercial | yes |
| Modification | yes |
| Attribution | 출처: 한국은행 경제통계시스템 |
| Quota | 500/day per key |
| Source | [ECOS 이용약관](https://ecos.bok.or.kr/api/) |
| Checked | 2026-09-30 |

## 통계청 KOSIS (kosis)

| Item | Value |
|---|---|
| Redistribution | allowed (with attribution) |
| Commercial | yes (statistical tables only) |
| Modification | no (통계표 변형 금지) |
| Attribution | 출처: 통계청(KOSIS) |
| Quota | 500/day per key |
| Source | [KOSIS 이용안내](https://kosis.kr/openapi/) |
| Note | 국내/국제/북한 통계 각각 이용조건 상이 — 개별 확인 필요 |
| Checked | 2026-09-30 |

## 한국거래소 KRX (krx)

| Item | Value |
|---|---|
| Redistribution | unknown |
| Commercial | unknown |
| Attribution | unknown |
| Source | [KRX 정보데이터시스템](http://data.krx.co.kr/) |
| Note | 크롤링 기반 — 이용약관 확인 필요 (#529) |
| Checked | — |

## 특허청 KIPRIS (kipris)

| Item | Value |
|---|---|
| Redistribution | allowed (with attribution) |
| Commercial | unknown |
| Attribution | 출처: 특허정보검색서비스(KIPRIS) |
| Quota | 10,000/day per key |
| Source | [KIPRIS Open API](https://kipris.or.kr/openapi/) |
| Checked | 2026-09-30 |

## 국립국어원 (korean)

| Item | Value |
|---|---|
| Redistribution | allowed (검색 API 결과) |
| Commercial | no |
| Attribution | 출처: 국립국어원 표준국어대사전 |
| Quota | 2,000/day per key |
| Source | [표준국어대사전 Open API](https://stdict.korean.go.kr/openapi/) |
| Checked | 2026-09-30 |

## 국가법령정보센터 (law)

| Item | Value |
|---|---|
| Redistribution | allowed |
| Commercial | yes |
| Attribution | 출처: 국가법령정보센터 |
| Quota | 500/day per key |
| Source | [법제처 Open API](https://www.law.go.kr/openApi/) |
| Checked | 2026-09-30 |

## 서울 열린데이터광장 (seoul)

| Item | Value |
|---|---|
| Redistribution | allowed (per dataset license) |
| Commercial | varies |
| Attribution | varies |
| Quota | 500/day per key |
| Source | [서울 열린데이터광장](https://data.seoul.go.kr/) |
| Note | Dataset별 라이선스 확인 필요 |
| Checked | 2026-09-30 |

## 통계청 SGIS (sgis)

| Item | Value |
|---|---|
| Redistribution | allowed (with attribution) |
| Commercial | no |
| Attribution | 출처: 통계지리정보서비스(SGIS) |
| Quota | 100/day per key |
| Source | [SGIS](https://sgis.kostat.go.kr/) |
| Note | 지리정보 데이터는 지리정보법 적용 |
| Checked | 2026-09-30 |
