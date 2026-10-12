# 커스텀 어댑터 유지 목록 (Phase 0.2)

> 생성일: 2026-09-07 · 이슈: [#377](https://github.com/kpubdata-lab/kpubdata/issues/377)
>
> 선언적 spec으로 설명하지 않기로 결정된 데이터셋(="사람 몫" 목록). Generic Executor와 공존하며
> 기존 `ProviderAdapter` 구현체로 유지한다. 사유가 해소되면 이 목록에서 제외하고 spec으로 이전한다.

## 확정: 영구 커스텀

| 데이터셋 | 사유 | 비고 |
|---|---|---|
| `krx.kospi_index` 외 3개 | **비HTTP** — pykrx 라이브러리 기반(DataFrame). REST 호출 자체가 없어 spec의 endpoint/params/response 축이 성립하지 않음. 접근 강화(로그인/키)로 pykrx 의존 지속 관리 필요 | `providers/krx/adapter.py`, 선택 의존성 `kpubdata[krx]` |
| `datago.road_traffic` | ITS 국가교통정보센터 **별도 apiKey 인증** + `its_flat` envelope + 정책상 `call_raw` 전용(list 미지원) | `envelope_style: its_flat`는 parser가 지원하지만 list 경로 미제공 |

## 확정: 지연 전환 (executor 기능 대기)

| 데이터셋 | 사유 | 전환 조건 |
|---|---|---|
| `sgis.sido_boundaries` 외 3개 | `oauth_exchange`(consumer_key/secret → accessToken 캐시·갱신) + GeoJSON `features` 정규화 | executor가 `auth.type: oauth_exchange`와 `format: geojson`을 지원하면 spec 이전. 스키마 enum에는 이미 포함 예정이라 우선순위만 뒤로 |

## 참고: raw 비상구 (데이터셋 아님, spec 대상 제외)

- `datago.generic` — 카탈로그 밖 임의 data.go.kr endpoint 호출용 `call_raw` 전용 게이트. SSRF 방지 호스트 allowlist(`*.data.go.kr` + `KPUBDATA_DATAGO_EXTRA_HOSTS`) 유지 필수.

## catalogue 에만 있는 데이터셋 — provider 별로 남는 이유 (#898)

데이터셋은 provider catalogue(`providers/*/catalogue.json`, 해당 provider 어댑터가 처리)나
spec(`specs/<provider>/*.yaml`, spec 실행기가 처리) 가운데 **한 곳에서만** 선언한다. 같은 키가
양쪽에 있으면 `core/bridge.py` 가 spec 을 쓰므로 catalogue 쪽은 실행되지 않는 문서가 된다.
#898 에서 datago catalogue 의 그런 항목 14개(`air_quality`, `airkorea_forecast`, `apt_rent`,
`metro_fare`, `offi_rent`, `offi_trade`, `rh_rent`, `sh_rent`, `sh_trade`, `tour_kor_*` 4개,
`ultra_srt_ncst`)를 지웠다. 데이터셋 id 는 spec 이 계속 처리하므로 사용자에게 바뀌는 것은 없다.

catalogue 에만 있는 항목은 `scripts/catalogue_only_baseline.txt` 에 있고, 그 목록은 줄어들기만
한다. `scripts/check_catalogue_baseline.py` 가 CI 에서 확인한다(목록에 없는 catalogue 항목,
목록에 남은 지워진 항목, catalogue·spec 양쪽 선언이 있으면 실패). `localdata.bakery`,
`localdata.general_restaurant`, `localdata.rest_cafe` 는 spec 에서 계속 제공하고 catalogue 의
중복 선언을 제거했다.

spec 실행기의 현재 한계: 응답 envelope 은 `datago_standard` 만 실행한다
(`core/executor.py` 의 `_require_supported_envelope`). 스키마 enum 에 다른 envelope 이름이 있어도
실행 시 `NotImplementedError` 다. 아래 "실행기 한계" 는 이 이유를 말한다.

| provider (남은 수) | 남는 이유 | 옮길 수 있게 되는 조건 |
|---|---|---|
| `bok` (4) | 실행기 한계 — `bok_statistic_row` envelope, 키와 `start`/`end` 가 URL 경로에 들어가는 `index_range` 페이지 처리, `RESULT.CODE` 오류 | 실행기가 `bok_statistic_row` 를 실행하고, 경로 템플릿으로 기존 요청 URL 을 똑같이 만들 수 있을 때 |
| `datago` (25) | 아래 datago 표 | — |
| `fds` (1) | 실행기 한계 — 키가 URL 경로 조각(`/api/{KEY}/...`), `fds_row` envelope, 서비스별 최상위 키 | 실행기가 `fds_row` 를 실행할 때 |
| `kipris` (1) | 실행기 한계 — `kipris_items` envelope. `totalCount` 가 없고, 응답이 되돌려 준 `pageNo` 가 요청과 다르면 "그런 페이지 없음" 으로 읽는 처리(#837)가 어댑터에만 있다 | 실행기가 `kipris_items` 와 같은 페이지 판정을 갖출 때 |
| `korean` (1) | 실행기 한계 — `korean_channel` envelope(`channel.item`), 본문 `statusCode` 오류 | 실행기가 `korean_channel` 을 실행할 때 |
| `kosis` (2) | 실행기 한계 — 최상위 배열 응답(`kosis_top_array`), 본문 `err`/`errMsg` 오류, catalogue 기본 질의값(`org_id`/`tbl_id`) | 실행기가 최상위 배열과 `err_field` 오류를 실행할 때 |
| `krx` (3) | 영구 커스텀 — HTTP 호출이 아니라 pykrx 라이브러리 | 해당 없음 (위 "영구 커스텀") |
| `law` (3) | 실행기 한계 — 데이터셋별 `item_key`, `page`/`display` 페이지, `resultMsg` 문자열로 인증 오류를 가르는 처리 | 실행기가 `law_item_key` 를 실행할 때 |
| `localdata` (56) | 56개는 활용신청 대기(`application_required`) — 실데이터 녹화(`make record`)가 안 된다. envelope 은 datago 계열이라 실행기 한계는 아니다 | 저장소 소유자의 활용신청 승인 후 녹화 |
| `lofin` (6) | 활용신청 대기 + 실행기 한계(`lofin_head_row` envelope, 수동 query string, 서버에 맞춘 SSL 설정) | 활용신청 승인과 실행기의 `lofin_head_row` 지원 |
| `neis` (2) | 실행기 한계 — 이중 리스트 응답(`neis_double_list`)의 항목 추출은 있으나 envelope 검사에서 막힌다, `INFO-200` 빈 결과 | `_require_supported_envelope` 가 `neis_double_list` 를 받아들일 때 |
| `semas` (17) | 활용신청 대기 — envelope 은 datago 계열 | 활용신청 승인 후 녹화 |
| `seoul` (7) | 실행기 한계 — 키와 `start`/`end` 가 URL 경로에, `seoul_service_row` envelope, `INFO-200` 빈 결과 | 실행기가 `seoul_service_row` 를 실행할 때 |
| `sgis` (3) | 지연 전환 — `oauth_exchange` 인증과 GeoJSON (위 표) | 위 "지연 전환" 조건 |

datago catalogue 에 남은 25개:

| 데이터셋 | 남는 이유 |
|---|---|
| `dur_*` 9개, `rh_trade`, `subway_passengers`, `agri_price`, `mid_fcst`·`mid_land_fcst`·`mid_ta`·`mid_sea_fcst`, `bond_price`, `sports_facility`, `culture_facility`, `asos_daily`·`asos_hourly` (21) | 활용신청 대기 — 결과 코드 30(등록되지 않은 키)이 돌아와 녹화할 수 없다. 승인 뒤 spec 으로 옮긴다 |
| `g2b_catalog` | 막는 이유 없음. 녹화(`make record`)에 실 API 키가 필요해 아직 하지 않았다 |
| `airkorea_station_realtime` | `air_station` spec 과 같은 엔드포인트. 기존 호출이 깨지지 않도록 id 는 남기고, 조회하면 `DeprecationWarning` 을 낸다 (#898). 지울지는 저장소 소유자가 정한다 |
| `road_traffic` | 영구 커스텀 (위 표) |
| `generic` | raw 비상구 (위 절) — 데이터셋이 아니다 |

## catalogue 에서 spec 으로 옮길 때 같음을 확인하는 절차 (#898)

옮기는 PR 하나에서 아래를 모두 한다. catalogue 항목을 지우는 것은 마지막이다.

1. **spec 작성과 녹화.** `src/kpubdata/specs/<provider>/<key>.yaml` 을 쓰고
   `make record DATASET=<provider>.<key>` 로 fixture 를 녹화한다. 손으로 쓴 fixture 는 안 된다.
2. **인증.** spec 의 `auth.type`·`param_name`·`provider_key` 가 catalogue 의 `service_key_param`
   (또는 어댑터의 키 위치)과 같은 이름, 같은 위치(query 또는 경로)에 키를 넣는지 확인한다.
   녹화된 `meta.json` 의 요청 URL 에서 키가 가려져(masked) 있는지도 본다.
3. **요청.** 같은 필터로 두 경로가 만드는 요청을 비교한다 — `base_url`(http/https 포함),
   operation, 형식 파라미터 이름과 값(`_type`/`dataType`/`returnType`/`resultType`), 고정 질의값,
   필수 필터. catalogue 의 `request_parameters`·`required_query_filters` 가 spec `params` 의
   `required` 와 맞아야 한다. 별칭(`alias`)을 붙이면 원래 이름도 계속 받아들이는지 확인한다.
4. **페이지 처리.** 페이지 파라미터 이름, 첫 페이지 번호, 최대 크기(`max_page_size` ↔
   `pagination.max_size`), 총건수 위치, 마지막 페이지 판정이 같은지 확인한다.
   `make verify DATASET=<provider>.<key>` 가 두 페이지 이상 예제를 재생하면 더 좋다.
5. **응답.** 같은 녹화 응답을 두 경로로 읽어 항목 수, 총건수, 필드 이름이 같은지 비교한다.
   spec 의 `fields[].type` 은 값을 형 변환하므로(문자열 → 정수 등) 바뀌는 필드는 CHANGELOG
   `[Unreleased]` 에 적는다. 오류 코드(30·22·10·12·01 등)가 같은 예외로 바뀌는지도 본다.
6. **`call_raw`.** spec 경로의 `call_raw` 가 원본 페이로드를 그대로 돌려주는지 확인한다
   (`SpecDatasetAdapter.call_raw` → `request_raw`). spec 경로는 `operation` 인자를 쓰지 않고
   언제나 spec 의 `endpoint.operation` 을 부른다. catalogue 경로에서 다른 operation 을
   `call_raw` 로 부를 수 있었다면 그 차이를 CHANGELOG 에 적거나, 옮기지 않는다.
7. **catalogue 항목 제거.** 같은 PR 에서 catalogue 항목과
   `scripts/catalogue_only_baseline.txt` 의 그 줄을 지운다. 그 항목을 직접 쓰던 테스트는 지우지
   말고 spec 경로로 옮긴다. 그 다음 `scripts/check_catalogue_baseline.py`,
   `scripts/sync_supported_data.py`, `scripts/gen_dataset_status.py`,
   `scripts/gen_readme_datasets.py`, `scripts/gen_status_page.py` 를 실행해 결과를 커밋한다.

## 유지 관리 규칙

1. 이 목록의 데이터셋은 Phase 1.4 `migrate-to-spec` 대상에서 **제외**한다.
2. 커스텀 어댑터에 행위 변경이 생기면 종전대로 fixture/unit/contract 테스트와 `SUPPORTED_DATA.md`를 같은 PR에서 갱신한다(AGENTS.md 어댑터 작업 규칙 그대로 적용).
3. 사유가 무효화된 경우(예: krx가 REST API로 전환) 이 문서에서 행을 옮기고 spec 전환 이슈(`migrate-to-spec`)를 등록한다.
