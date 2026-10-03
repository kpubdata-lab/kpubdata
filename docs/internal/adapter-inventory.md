# 어댑터 인벤토리 (Phase 0.1)

> 생성일: 2026-09-07 · 이슈: [#377](https://github.com/kpubdata-lab/kpubdata/issues/377) · 상위: [#385](https://github.com/kpubdata-lab/kpubdata/issues/385)
>
> 작성 방법: 코드 전수 조사(병렬 explore agent 5건 + 직접 정독). 모든 값은 `src/kpubdata/` 코드와
> `catalogue.json`을 근거로 하며, 추측값을 포함하지 않는다. 문서 목적: 선언적 spec 스키마
> (`specs/schema.json`)의 enum 범위 확정.

## 총괄

- Provider: **14개** (AGENTS.md 파일 구조 항목은 10개로 구버전 — kipris/korean/neis/fds 누락)
- 데이터셋: **295개** (catalogue.json 기준 집계)

| Provider | 데이터셋 수 |
|---|---:|
| localdata | 195 |
| datago | 50 |
| semas | 17 |
| seoul | 7 |
| lofin | 6 |
| bok | 4 |
| krx | 3 |
| sgis | 3 |
| law | 3 |
| neis | 2 |
| kosis | 2 |
| fds | 1 |
| korean | 1 |
| kipris | 1 |

## 축별 고유값 집계 (spec 스키마 enum의 원재료)

| 축 | 고유값 수 | 값 |
|---|---:|---|
| 인증 | 4 | `query_param` / `path_segment` / `oauth_exchange` / `none` |
| 요청 인코딩 | 3 | 일반 query / **path-key**(URL 경로에 키+페이지 범위 삽입) / 어댑터 수동 querystring(lofin) |
| 응답 포맷 | 3 | `json` / `xml`(선택적 `_type=xml`, xmltodict 선택 의존성) / `geojson`(sgis) |
| Envelope 형태 | 12 | 아래 표 참조 |
| 페이지네이션 | 6 | `page_no_rows` / `page_display` / `pindex_psize` / `index_range` / `date_window` / `none` |
| 총건수 위치 | 5계열 | `response.body.totalCount` / `head.list_total_count`(lofin·neis·seoul) / `StatisticSearch.list_total_count`(bok) / `totalCnt`(law) / 없음(len(items) 대체) |
| 에러 표현 | 6계열 | 아래 표 참조 |
| 날짜 특이사항 | 3 | `YYYYMM`(bok·kosis start/end) / `YYYYMMDD`(datago·krx 정규화 대상) / epoch 정수(sgis 토큰 만료) |
| 금액 단위 | 0 | 중앙 단위 변환 헬퍼 없음 — 필요 시 `fields[].transform`으로 신설 (lofin 원 단위, krx 문자열 숫자 등은 현재 원문 전달) |
| 파라미터 코드 조회 | 0 | 사전 fetch형 코드표 조회 없음 — kosis `org_id`/`tbl_id`, sgis `default_adm_cd`/`default_year` 등 catalogue 기본값 방식 |

## Provider × 축 인벤토리

| Provider | 인증 | 요청 | 포맷 | items 경로 | 총건수 경로 | 페이지네이션 | 에러 표현 | 비고 |
|---|---|---|---|---|---|---|---|---|
| **datago** (50) | query `serviceKey` (데이터셋별 `service_key_param` override) | GET + query | json (xml 선택) | `response.body.items.item` (변형 4종 — 아래 표) | `response.body.totalCount` | `pageNo`+`numOfRows` (odcloud 계열은 `pagination_params`로 파라미터명 override) | `response.header.resultCode` — `"00"`/`"000"`/수치 0 성공, `30·31·20·32`→AuthError, `22`→RateLimit, `10`→InvalidRequest, `12`→NotFound, `01·02`→ServiceUnavailable (`envelope.py`) | HTTP 403 → 활용신청 안내 AuthError. `datago.generic` raw 비상구 별도 |
| **localdata** (195) | query `serviceKey` (`require_provider_key("datago")` 공유) | GET + query | json | `response.body.items.item` | `response.body.totalCount` | `pageNo`+`numOfRows` | datago standard와 동일 계열 | datago와 동일 envelope/parser 구조 |
| **semas** (17) | query `serviceKey` (datago 키 공유) | GET + query | json | `response.body.items(.item)` — **2026-09-10 정정**: header 하위가 아니라 표준 경로 | `response.body.totalCount` | `pageNo`+`numOfRows` | datago standard 동일 계열 | 소상공인 상가정보 |
| **lofin** (6) | query `Key` (datago 키 공유) | GET + 어댑터 수동 querystring (`?Key=...&Type=json&pIndex=...`) | json | `payload[<api_code>][1].row` (배열 본문: [0]=head, [1]=rows) | head 내 `list_total_count` | `pIndex`+`pSize` | head의 `RESULT.CODE` (`"000"` 정상) | SSL 자동 조정 특기사항 |
| **seoul** (7) | **path segment** (`{base}/{KEY}/json/{service}/{start}/{end}`) — `secret_values` 마스킹 | GET + path | json | `{서비스명}.row` (dataset별 `envelope_key`) | `list_total_count` | `index_range` (start/end를 URL 경로에, page_size ≤ 1000 강제) | `RESULT.CODE` — `INFO-000` 성공, `INFO-200` 빈 결과 (`seoul/envelope.py`) | `required_path_params` (예: stationName) |
| **bok** (4) | **path segment** (`{base}/{키}/json/{op}/{start}/{end}/...`) | GET + path | json | `StatisticSearch.row` | `StatisticSearch.list_total_count` | `index_range` (start/end를 경로에) | `RESULT.CODE` 매핑 (`adapter.py` `_raise_for_result_code`) | `stat_code`/`item_code1` catalogue 기본값, 날짜 `YYYYMM` |
| **kosis** (2) | query `apiKey` | GET + query (`format=json`, `jsonVD`) | json | **최상위 배열** 그 자체 | 없음 (`len(items)`) | `none` (단발) | 본문 `err`/`errMsg` 필드 검사 (`adapter.py`) | `org_id`/`tbl_id`/`default_query_params`, `startPrdDe`/`endPrdDe` 필수 |
| **law** (3) | query `OC` | GET + query | json | `payload[<item_key>]` (데이터셋별 item_key) | `totalCnt` | `page`+`display` | `resultCode`/`resultMsg` (+resultMsg에 "인증" 문자열 탐지) | `target` 파라미터로 법령/자치법규 구분 |
| **neis** (2) | query `KEY` | GET + query | json | **이중 리스트** `{operation}[].head/[].row` — 모든 block의 row 결합 | head `list_total_count` | `pageNo`+`numOfRows` | `INFO-000`/`INFO-200` + `ERROR-*` | `required_query_filters` (ATPT_OFCDC_SC_CODE 등) |
| **kipris** (1) | query `serviceKey` | GET + query | json | `response.body.items.item` | 없음 (len 대체) | `pageNo`+`numOfRows` | resultCode 매핑 | 특허패밀리, `required_query_filters` |
| **korean** (1) | query `key` | GET + query | json | `channel.item` | `channel.total` | `none` (start/end 파라미터는 있으나 어댑터 미지원) | `statusCode` — `"000"` 성공 | 표준국어대사전 |
| **fds** (1) | **path segment** (`openapi.foodsafetykorea.go.kr/api/{KEY}/...`) | GET + path | json | 서비스별 최상위 키 내 `row` (body/row 폴백) | 상황별 | `none` | `RESULT.CODE` — `"000"` 정상 | 식품이력추적 |
| **sgis** (3) | **oauth_exchange**: consumer_key+secret → accessToken (만료 캐시, AuthError 시 force refresh) 후 query `accessToken` | GET + query | **geojson** | `features` | 없음 (`len(features)`) | `none` | `errCd` 매핑 (`adapter.py` `_raise_for_err_code`), 토큰 만료 epoch 처리 | 행정구역 경계. spec 전환은 executor oauth 지원 전까지 보류 |
| **krx** (3) | **none** (`requires_api_key=False`) | **비HTTP** — pykrx 라이브러리 | DataFrame | 라이브러리 반환값 → 레코드 | `len(items)` | `date_window` (일자별 순회, >90일 경고) | 라이브러리 예외 | **영구 커스텀 어댑터** (spec 대상 아님) |

## datago envelope 변형 (같은 Provider 내 4종)

| envelope_style | 데이터셋 | items 경로 | 에러 코드 위치 |
|---|---|---|---|
| `standard` (기본) | 48개 | `response.body.items.item` | `response.header.resultCode` |
| `gyeonggi_msg` | `bus_arrival` | `response.msgBody` 내 유일 리스트 | `response.msgHeader.resultCode`/`resultMessage` |
| `its_flat` | `road_traffic` (call_raw 전용) | 최상위 `items` | 최상위 `resultCode` |
| odcloud (`pagination_params`) | `social_enterprise` | 최상위 `data` 배열 | — |

근거: `src/kpubdata/providers/datago/envelope.py`, `datago/catalogue.json`

## 에러 → 예외 매핑 (공통, `src/kpubdata/exceptions.py`)

> **2026-09-10 보충**: 한국관광공사 KorService2는 성공은 표준 envelope이지만
> **에러를 envelope 밖 최상단 `{resultCode, resultMsg}`로 평면 반환**한다 —
> 실행기 check_payload_error의 flat 폴백으로 처리된다(PR #422).

모든 어댑터가 `provider_code`를 실어 다음 표준 예외로 매핑한다. Generic executor도 이 계층을 그대로 재사용한다.

- `AuthError` — 인증키 미등록/오류 (datago `30·31·20·32`, UNREGISTERED_IP 포함, HTTP 403 포함)
- `RateLimitError` — datago `22`
- `InvalidRequestError` — datago `10`
- `DatasetNotFoundError` — datago `12`
- `ServiceUnavailableError` — datago `01·02`
- `ProviderResponseError` — 그 외 전부 + malformed envelope
- `ParseError` — JSON/XML 디코딩 실패 (`transport/decode.py`)

## 페이지네이션 상세

| 타입 | 파라미터 | 사용 Provider | 종료 판정 |
|---|---|---|---|
| `page_no_rows` | `pageNo`/`numOfRows` | datago·localdata·semas·neis·kipris | `totalCount` 비교, 없으면 `len(items)==page_size` |
| `page_display` | `page`/`display` | law | `totalCnt` 비교 |
| `pindex_psize` | `pIndex`/`pSize` | lofin | head `list_total_count` 비교 |
| `index_range` | start/end (URL 경로 삽입) | bok·seoul | `list_total_count` 비교 |
| `date_window` | 내부 일자 분할 | krx (커스텀 유지) | 어댑터 내부 |
| `none` | — | kosis·sgis·korean·fds | 단발 |

공용 반복기: `Dataset.list_all` (`core/dataset.py`) — `RecordBatch.next_page`/`next_cursor` 기반, 최대 1000페이지 가드, 사이클 검출, 연속 빈 페이지 가드. transport 계층에는 반복기 없음.

## 근거 파일 인덱스

- 인증: `config.py`, `sgis/auth.py`, 각 `adapter.py`의 `_require_api_key`/`_build_base_params`
- envelope: `datago/envelope.py`, `seoul/envelope.py`, lofin/neis/kipris/korean/fds 각 `adapter.py`
- 페이지네이션: 각 `adapter.py`의 `query_records`, `core/dataset.py`
- 카탈로그: `providers/*/catalogue.json` 14종 (Provider별 키 방언 존재 — `envelope_key`·`top_level_result`·`org_id`·`tbl_id`·`stat_code`·`item_key`·`required_path_params`·`required_query_filters` 등)
