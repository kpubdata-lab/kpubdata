# 서울 열린데이터광장 (seoul)

## 개요

서울 열린데이터광장은 서울시 교통·환경·행정 데이터를 오픈 API로 제공합니다. KPubData의 `seoul` Provider는 서울 오픈 API의 경로 기반 인증키, 서비스별 최상위 envelope, 시작/종료 인덱스 기반 페이지네이션을 그대로 존중하면서 `list()`와 `call_raw()`를 제공합니다.

- KPubData Provider 이름: `seoul`
- 포털: <https://data.seoul.go.kr/>

## 인증키 발급 및 환경 변수 설정

1. [서울 열린데이터광장](https://data.seoul.go.kr/)에 가입합니다.
2. 로그인 후 우측 상단 **인증키 신청** 메뉴를 클릭합니다.
3. 이용약관 동의 후 신청 폼을 작성합니다:
   - 서비스(사용) 환경: **연구(논문 등)** 또는 **웹 사이트 개발**
   - 사용URL: 프로젝트 URL (예: `https://github.com/yeongseon/kpubdata`)
   - 관리용 대표 이메일: 본인 이메일
   - 활용용도/내용: 간단한 설명
4. **인증키 신청** 버튼 클릭 → 즉시 발급됩니다 (별도 심사 없음).
5. **인증키 관리** 메뉴에서 발급된 키를 확인합니다.
6. 환경 변수에 설정합니다.

```bash
export KPUBDATA_SEOUL_API_KEY="your-seoul-api-key"
```

`Client.from_env()`는 위 환경 변수를 자동으로 읽습니다.

## 서울 오픈 API 호출 규칙

- 인증키는 **쿼리 파라미터가 아니라 URL 경로 세그먼트**입니다.
- 응답 형식은 `json`으로 고정합니다.
- 페이지네이션은 `start_index` / `end_index` 기반입니다.
- KPubData의 `list(page=..., page_size=...)`는 아래 규칙으로 변환됩니다.

```text
start_index = (page - 1) * page_size + 1
end_index = page * page_size
```

- 최대 `page_size`는 `1000`입니다.

### URL 패턴

#### 1) 지하철 실시간 도착정보

```text
http://swopenAPI.seoul.go.kr/api/subway/{KEY}/json/realtimeStationArrival/{START_INDEX}/{END_INDEX}/{stationName}
```

#### 2) 따릉이 이용정보(월별)

```text
http://openapi.seoul.go.kr:8088/{KEY}/json/tbCycleRentUseMonthInfo/{START_INDEX}/{END_INDEX}/{RENT_NM}
```

#### 3) 따릉이 실시간 대여정보

```text
http://openapi.seoul.go.kr:8088/{KEY}/json/bikeList/{START_INDEX}/{END_INDEX}
```

- envelope 키: `rentBikeStatus` (서비스명 `bikeList`와 다름)
- 필수 경로 파라미터 없음

#### 4) 따릉이 대여소 마스터 정보

```text
http://openapi.seoul.go.kr:8088/{KEY}/json/tbCycleStationInfo/{START_INDEX}/{END_INDEX}
```

- envelope 키: `stationInfo` (서비스명 `tbCycleStationInfo`와 다름)
- 필수 경로 파라미터 없음

#### 5) 서울시 공원 정보

```text
http://openapi.seoul.go.kr:8088/{KEY}/json/SearchParkInfoService/{START_INDEX}/{END_INDEX}
```

- 필수 경로 파라미터 없음
#### 6) 실시간 도시데이터 인구현황

```text
http://openapi.seoul.go.kr:8088/{KEY}/json/citydata_ppltn/{START_INDEX}/{END_INDEX}/{area}
```

- envelope 키: `SeoulRtd.citydata_ppltn` (top-level `RESULT`와 같은 레벨)
- 필수 경로 파라미터: `area`

## 지원 데이터셋

### 1. `subway_realtime_arrival`

- 서비스명: `realtimeStationArrival`
- 필수 경로 파라미터: `stationName`
- 예시 값: `"강남"`

### 2. `bike_rent_month`

- 서비스명: `tbCycleRentUseMonthInfo`
- 필수 경로 파라미터: `RENT_NM`
- 예시 값: `"202401"`

### 3. `bike_realtime`

- 서비스명: `bikeList`
- envelope 키: `rentBikeStatus`
- 필수 경로 파라미터: 없음
- 설명: 따릉이 대여소 실시간 자전거 가용 현황

### 4. `bike_station_master`

- 서비스명: `tbCycleStationInfo`
- envelope 키: `stationInfo`
- 필수 경로 파라미터: 없음
- 설명: 따릉이 대여소 마스터 정보 (위치, 거치대 수 등)

### 5. `park_usage`

- 서비스명: `SearchParkInfoService`
- 필수 경로 파라미터: 없음
- 설명: 서울시 공원 위치, 면적, 시설 정보
### 6. `citydata`

- 서비스명: `citydata_ppltn`
- envelope 키: `SeoulRtd.citydata_ppltn`
- 필수 경로 파라미터: `area`
- 예시 값: `"광화문·덕수궁"`
- 설명: 서울 주요 장소의 실시간 인구현황 도시데이터

## 에러 코드 매핑

| 코드 | 의미 | KPubData 예외 |
|---|---|---|
| `INFO-000` | 정상 처리 | 예외 없음 |
| `INFO-100` | 인증키 오류 | `AuthError` |
| `INFO-200` | 데이터 없음 | 빈 `RecordBatch` 반환 |
| `INFO-300` | 인증키 권한 없음 | `AuthError` |
| `INFO-400` | HTTP/요청 오류 | `InvalidRequestError` |
| `INFO-500` | 서버 오류 | `ProviderResponseError` |
| `ERROR-300` | 필수값 누락 | `InvalidRequestError` |
| `ERROR-301` | 서비스명 오류 | `InvalidRequestError` |
| `ERROR-310` | 서비스 미존재 | `InvalidRequestError` |
| `ERROR-336` | 페이지 인덱스 오류 | `InvalidRequestError` |
| `ERROR-500` | 일반 서버 오류 | `ProviderResponseError` |
| `ERROR-600` | 일반 서버 오류 | `ProviderResponseError` |
| `ERROR-601` | 일반 서버 오류 | `ProviderResponseError` |

알 수 없는 코드도 `ProviderResponseError`로 매핑합니다.

## 사용 예제

### 지하철 실시간 도착정보 `list()`

```python
from kpubdata import Client

client = Client.from_env()
ds = client.dataset("seoul.subway_realtime_arrival")

result = ds.list(stationName="강남", page_size=5)

for item in result.items:
    print(item["statnNm"], item["arvlMsg2"], item["arvlMsg3"])
```

### 지하철 실시간 도착정보 `call_raw()`

```python
raw = ds.call_raw("realtimeStationArrival", stationName="강남", page_no=1, page_size=5)
print(raw["realtimeStationArrival"]["RESULT"])
```

### 따릉이 월별 이용정보 `list()`

```python
from kpubdata import Client

client = Client.from_env()
ds = client.dataset("seoul.bike_rent_month")

result = ds.list(RENT_NM="202401", page=1, page_size=10)

for item in result.items:
    print(item["RENT_NO"], item["RENT_USE_CNT"], item["MOVE_METER"])
```

### 따릉이 월별 이용정보 `call_raw()`

```python
raw = ds.call_raw("tbCycleRentUseMonthInfo", RENT_NM="202401", page_no=1, page_size=10)
print(raw["tbCycleRentUseMonthInfo"]["list_total_count"])
```

### 따릉이 실시간 대여정보 `list()`

```python
from kpubdata import Client

client = Client.from_env()
ds = client.dataset("seoul.bike_realtime")

result = ds.list(page_size=5)

for item in result.items:
    print(
        item["stationName"], f"거치대:{item['rackTotCnt']}", f"자전거:{item['parkingBikeTotCnt']}"
    )
```

### 따릉이 대여소 마스터 정보 `list()`

```python
ds = client.dataset("seoul.bike_station_master")

result = ds.list(page_size=10)

for item in result.items:
    print(item["RENT_ID_NM"], item["STA_ADD1"])
```

### 서울시 공원 정보 `list()`

```python
ds = client.dataset("seoul.park_usage")

result = ds.list(page_size=10)

for item in result.items:
    print(item["P_PARK"], item["P_ADDR"])
### 실시간 도시데이터 인구현황 `list()`

```python
ds = client.dataset("seoul.citydata")

result = ds.list(area="광화문·덕수궁", page_size=1)

for item in result.items:
    print(item["AREA_NM"], item["AREA_CONGEST_LVL"])
```

## 참고

- `list()`는 한 번에 한 페이지만 반환하며, 다음 페이지가 있으면 `RecordBatch.next_page`가 채워집니다.
- 서울 오픈 API의 서비스명과 경로 파라미터 이름은 Provider 고유 의미론이므로 그대로 유지합니다.
- 일부 서울 오픈 API는 응답 envelope 키가 서비스명과 다릅니다 (예: `bikeList` → `rentBikeStatus`). KPubData는 catalogue의 `envelope_key` 메타데이터로 이를 처리합니다.
- 일부 실시간 도시데이터 API는 `RESULT`와 데이터 배열이 같은 최상위 객체에 있습니다. KPubData는 catalogue의 `top_level_result` 메타데이터로 이를 처리합니다.
- 실API 검증 완료: `subway_realtime_arrival`, `bike_rent_month`, `bike_realtime`, `bike_station_master` (2026-05-05)
- 테스트 검증 완료: `park_info`, `park_usage`


> 데이터셋 게시(Publishing) 및 HuggingFace/Kaggle 업로드는 [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder)에서 관리합니다.
