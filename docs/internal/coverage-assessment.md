# Spec 전환 커버리지 판정 (Phase 0.2)

> 생성일: 2026-09-07 · 이슈: [#377](https://github.com/kpubdata-lab/kpubdata/issues/377)
>
> 판정 기준(원 계획): "가장 흔한 조합 상위 N개"로 설명되는 데이터셋 비율이 **80% 이상이면 Phase 1 진행**.

## 조합 패밀리별 분포

| # | 패밀리 (인증 × envelope × 페이지네이션) | 데이터셋 수 | 비율 |
|---|---|---:|---:|
| 1 | query `serviceKey` × datago standard 계열 envelope(변형 포함) × `pageNo`+`numOfRows` — datago 49(standard 48 + gyeonggi 1 + odcloud 1) + localdata 195 + semas 17 + kipris 1 | 262 | 88.8% |
| 2 | query `KEY` × neis 이중 리스트 envelope × `pageNo`+`numOfRows` | 2 | 0.7% |
| 3 | query `Key` × lofin head/row × `pIndex`+`pSize` | 6 | 2.0% |
| 4 | path segment 키 × seoul 서비스키 envelope × `index_range` | 7 | 2.4% |
| 5 | path segment 키 × bok `StatisticSearch.row` × `index_range` | 4 | 1.4% |
| 6 | query `OC` × law `item_key` × `page`+`display` | 3 | 1.0% |
| 7 | query `apiKey` × kosis 최상위 배열 × none / query `key` × korean `channel` × none | 3 | 1.0% |
| 8 | path segment 키 × fds `RESULT.CODE` × none | 1 | 0.3% |
| — | **spec 설명 가능 소계** | **288** | **97.6%** |
| — | oauth_exchange × sgis geojson (executor 인증 지원 후 전환 가능 — 지연 전환) | 3 | 1.0% |
| — | **커스텀 유지 확정** (krx 비HTTP 3 + road_traffic call_raw 전용 1) | 4 | 1.4% |

> 주석: 패밀리 1의 datago 49개는 catalogue `envelope_style` 집계(standard 48 · `gyeonggi_msg` 1 · odcloud `pagination_params` 1)에서 `its_flat`(road_traffic)을 뺀 값으로, 세 변형 모두 executor envelope enum 3종으로 커버된다. road_traffic은 `call_raw` 전용이라 [custom-adapters.md](./custom-adapters.md)로 분류했다. sgis는 스키마 enum에 `oauth_exchange`·`geojson`이 포함될 예정이라 executor 구현 시 전환 가능(지연 전환). 총합 검증: 288 + 3 + 4 = 295.

## 판정

- **상위 1개 패밀리만으로 88.8% — 80% 기준 통과 → Phase 1 진행 (GO)**
- spec 범위를 datago 계열로 한정할 필요 없이, 전 Provider 상위집합 스키마로 설계해도 enum 크기가 감당 가능하다 (envelope 12 / pagination 6 / auth 4 / format 3).

## Phase 1 스키마 enum 권고 (본 인벤토리에서 직접 도출)

```text
auth.type:            query_param | path_segment | oauth_exchange | none
pagination.type:      page_no_rows | page_display | pindex_psize | index_range | date_window | none
response.format:      json | xml | geojson
response.envelope:    datago_standard | datago_gyeonggi_msg | datago_its_flat | datago_odcloud |
                      localdata_rows | semas_rows | lofin_head_row | neis_double_list |
                      kipris_items | seoul_service_row | bok_statistic_row |
                      kosis_top_array | law_item_key | korean_channel | fds_row
error.style:          header_result_code | result_code | status_code | err_cd | err_field | http_status
fields[].transform:   (현재 중앙 변환기 없음 — date_yyyymm, date_yyyymmdd, to_int, to_float 정도로 신설)
```

## 골든 예제 3종 후보 (Phase 1.3)

| 역할 | 후보 | 근거 |
|---|---|---|
| 단순 | `datago.hospital_info` | 필수 필터 없음, standard envelope, 실API 검증(2026-04-21), fixture 존재 (`success_hospital_info` 계열) |
| 페이지네이션 | `datago.apt_trade` | `pageNo`/`numOfRows` + `totalCount` 기반 next_page, 실API 검증(2026-04-21), 대량 데이터, fixture `success_apt_trade.json` |
| XML 응답 | datago 계열 `_type=xml` 사용 데이터셋 (예: `village_fcst`) | `decode_xml` 경로 + XML fixture 이미 존재 (`success_xml.xml`, `success_xml_single_item.xml`, `error_xml_auth_30.xml`) — record 시 `dataType=XML`으로 원본 확보 가능 |

## 기존 자산 → Phase 1/2 재사용 매핑

| 자산 | 위치 | 재사용처 |
|---|---|---|
| `catalogue.json` 14종 (Provider별 키 방언) | `providers/*/catalogue.json` | spec 상위집합 스키마의 원재료. 신규 `specs/`와 병합 레지스트리 구성(원 계획 1.2) 또는 catalogue 직접 확장 중 택일 |
| `load_catalogue`/`build_dataset_ref` | `providers/_common.py` | spec 로더(`core/spec.py`)가 호출할 기존 진입점 |
| `DataGoEnvelopeParser` | `datago/envelope.py` | executor의 datago 계열 parser dispatch |
| `FixtureTransport`/`FakeResponse` | `tests/unit/providers/datago/conftest.py` | Phase 2 replay 모드의 훅 설계 원형 |
| `@pytest.mark.integration` + `require_*` fixtures | `pyproject.toml`, `tests/integration/conftest.py` | Phase 2/5의 replay vs live 분리 (별도 `live` 마커 신설 불필요) |
| `Dataset.list_all` (사이클 검출·빈페이지 가드) | `core/dataset.py` | executor `fetch_all`의 종료 판정 규칙 |
| `integration.yml` (workflow_dispatch + Secrets) | `.github/workflows/integration.yml` | Phase 5 `smoke.yml`의 씨앗 |
| SUPPORTED_DATA.md `실API 최종 검증일` 열 | `SUPPORTED_DATA.md` | spec `status`/`last_verified`와 단일 기준 연계 |
