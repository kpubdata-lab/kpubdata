# 공공데이터포털 (datago)

## 개요

공공데이터포털(data.go.kr)은 대한민국 정부에서 운영하는 공공데이터 통합 플랫폼입니다. 기상청, 국토교통부, 한국환경공단 등 수많은 기관의 데이터를 오픈 API 형태로 제공합니다.

- KPubData Provider 이름: `datago`
- API 기반 URL: https://apis.data.go.kr

## API 키 발급 방법

### 1단계: 회원가입

1. [공공데이터포털](https://www.data.go.kr)에 접속합니다.
2. 우측 상단의 "회원가입"을 클릭합니다.
3. 본인인증(휴대폰 또는 아이핀)을 거쳐 가입을 완료합니다.

### 2단계: API 활용신청

**중요: 공공데이터포털은 API별로 개별 활용신청이 필요합니다.** 인증키는 계정당 하나지만, 사용하려는 각 API에 대해 별도로 활용신청을 해야 합니다.

1. [공공데이터포털](https://www.data.go.kr)에 로그인합니다.
2. 상단 검색창에서 사용하려는 API를 검색합니다.
   - 예: "단기예보", "아파트매매 실거래", "대기오염정보" 등
3. 검색 결과에서 원하는 API의 상세 페이지로 이동합니다.
4. **"활용신청"** 버튼을 클릭합니다.
5. 활용목적 선택 화면에서 적절한 항목을 선택합니다.
   - "기타"를 선택한 경우 아래와 같이 작성합니다:

   ```
   한국 공공데이터 통합 조회 오픈소스 Python 라이브러리(KPubData) 개발 및 API 연동 테스트 목적으로 활용합니다.
   ```

6. 신청서를 제출합니다.

### 3단계: 승인 대기

- **자동 승인**: 대부분의 API는 활용신청 후 약 1~5분 안에 자동 승인됩니다.
- **심의 승인**: 국토교통부 아파트매매 실거래가 등 일부 API는 담당 기관의 심의 후 승인까지 1~2일이 소요될 수 있습니다.

### 4단계: 인증키 확인

1. 승인이 완료되면 "마이페이지"로 이동합니다.
2. **"개인 API인증키"** 섹션에서 발급된 인증키를 확인합니다.
3. 공공데이터포털은 두 종류의 인증키를 제공합니다:
   - **일반 인증키(디코딩)**: 원본 키. KPubData에서는 이 키를 사용합니다.
   - **인코딩 인증키**: URL 인코딩된 키. 직접 URL을 구성할 때 사용합니다.

### 5단계: 환경변수 설정

```bash
export KPUBDATA_DATAGO_API_KEY="발급받은-일반-인증키"
```

## API별 활용신청(활성화) 요구사항

data.go.kr은 **계정용 공통 인증키 1개만 있으면 끝나는 구조가 아닙니다.** 호출하려는 오픈 API마다 상세 페이지에서 별도로 **활용신청**을 해야 합니다.

- 같은 `KPUBDATA_DATAGO_API_KEY`를 쓰더라도 API별 활성화 상태는 서로 다를 수 있습니다.
- 활용신청 후 대부분의 API는 약 **1~5분 안에 자동 승인/활성화**됩니다.
- 활성화 전에는 KPubData 호출이 **HTTP 403**으로 실패할 수 있습니다.
- 이 경우 해당 데이터셋의 data.go.kr 상세 페이지로 가서 **"활용신청"** 버튼을 눌렀는지 먼저 확인하세요.

예시:

- `datago.village_fcst`를 쓰려면 단기예보 API 페이지에서 활용신청 필요
- `datago.air_quality`를 쓰려면 대기오염정보 API 페이지에서 활용신청 필요
- 둘은 같은 포털/같은 키를 써도 **각각 따로** 활성화해야 함

### 6단계: 활성화 확인

키가 활성화되었는지 확인하려면 다음과 같이 테스트합니다:

```bash
# curl로 직접 테스트 (단기예보 API 예시)
curl "http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst?serviceKey=YOUR_KEY&dataType=json&numOfRows=1&pageNo=1&base_date=20250401&base_time=0500&nx=55&ny=127"
```

정상 응답이 오면 활성화가 완료된 것입니다. `403 Forbidden`, `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`, 또는 인증 관련 오류가 나오면 활용신청 여부와 승인 대기 시간을 다시 확인하세요.

## KPubData에서 신청해야 할 API 목록

현재 KPubData가 지원하는 datago 데이터셋을 모두 사용하려면, 아래 API를 각각 활용신청해야 합니다. (최신 목록은 [SUPPORTED_DATA.md](https://github.com/kpubdata-lab/kpubdata/blob/main/SUPPORTED_DATA.md) 기준)

| # | data.go.kr 검색어 | 제공기관 | 승인 방식 |
|---|---|---|---|
| 1 | `단기예보 조회서비스` | 기상청 | 자동 승인 |
| 2 | `초단기실황 조회서비스` | 기상청 | 자동 승인 |
| 3 | `대기오염정보 조회서비스` | 한국환경공단 | 자동 승인 |
| 4 | `경기도 버스도착정보` | 경기도 | 자동 승인 |
| 5 | `병원정보서비스` | 건강보험심사평가원 | 자동 승인 |
| 6 | `아파트매매 실거래 상세 자료` | 국토교통부 | 심의 승인 (1~2일) |
| 7 | `아파트 전월세 자료` | 국토교통부 | 자동 승인 |
| 8 | `오피스텔 매매 신고 조회 서비스` | 국토교통부 | 자동 승인 |
| 9 | `오피스텔 전월세 신고 조회 서비스` | 국토교통부 | 자동 승인 |
| 10 | `연립다세대 매매 실거래자료 조회 서비스` | 국토교통부 | 자동 승인 |
| 11 | `연립다세대 전월세 실거래자료 조회 서비스` | 국토교통부 | 자동 승인 |
| 12 | `단독/다가구 매매 실거래 조회 서비스` | 국토교통부 | 자동 승인 |
| 13 | `단독/다가구 전월세 자료 조회 서비스` | 국토교통부 | 자동 승인 |
| 14 | `한국관광공사_국문 관광정보 서비스_GW` ([15101578](https://www.data.go.kr/data/15101578/openapi.do)) | 한국관광공사 | 자동 승인 (개발) / 심의 승인 (운영) |
| 15 | `한국관광공사_국문 관광정보 서비스_GW` (위 신청 1건으로 `tour_kor_location` 포함) | 한국관광공사 | 14번과 동일 신청 |
| 16 | `한국관광공사_국문 관광정보 서비스_GW` (위 신청 1건으로 `tour_kor_keyword` 포함) | 한국관광공사 | 14번과 동일 신청 |
| 17 | `한국관광공사_국문 관광정보 서비스_GW` (위 신청 1건으로 `tour_kor_festival` 포함) | 한국관광공사 | 14번과 동일 신청 |
| 18 | `서울교통공사_실시간운임정보` ([15143846](https://www.data.go.kr/data/15143846/openapi.do)) | 서울교통공사 | 자동 승인 |
| 19 | `서울교통공사_최단경로이동정보` ([15143842](https://www.data.go.kr/data/15143842/openapi.do)) | 서울교통공사 | 자동 승인 |
| 20 | `나라장터 조달계약정보` ([15129427](https://www.data.go.kr/data/15129427/openapi.do)) | 조달청 | 자동 승인 |
| 21 | `사회적기업 인증현황` ([15082035](https://www.data.go.kr/data/15082035/openapi.do)) | 고용노동부 | 자동 승인 |
| 22 | `나라장터 종합쇼핑몰 품목정보` ([15129471](https://www.data.go.kr/data/15129471/openapi.do)) | 조달청 | 자동 승인 |
| 23 | `중기예보 조회서비스` ([15059468](https://www.data.go.kr/data/15059468/openapi.do)) | 기상청 | 자동 승인 |

> 💡 14~17은 모두 동일한 한국관광공사 TourAPI(KorService2) 단일 활용신청으로 한꺼번에 발급됩니다 — 활용신청은 1건이지만 4개 endpoint(`areaBasedList2`, `locationBasedList2`, `searchKeyword2`, `searchFestival2`)가 KPubData에서 별도 dataset_key로 노출됩니다.
>
> 💡 23은 기상청 중기예보 조회서비스(MidFcstInfoService) 단일 활용신청으로 4개 endpoint(`getMidFcst`, `getMidLandFcst`, `getMidTa`, `getMidSeaFcst`)가 모두 발급됩니다 — KPubData에서는 `mid_fcst`, `mid_land_fcst`, `mid_ta`, `mid_sea_fcst` 4개 dataset_key로 노출됩니다.

## 지원 데이터셋

### village_fcst (단기예보 조회서비스)

기상청에서 제공하는 단기예보 정보입니다. 3시간 단위의 기온, 강수량, 하늘 상태 등을 조회할 수 있습니다.

- 제공 기관: 기상청
- 주요 파라미터: `base_date` (발표일자), `base_time` (발표시각), `nx` (예보지점 X 좌표), `ny` (예보지점 Y 좌표)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| base_date | 필수 | 발표일자 (YYYYMMDD) | "20250401" |
| base_time | 필수 | 발표시각 (HHMM) | "0500" |
| nx | 필수 | 예보지점 X좌표 | 55 |
| ny | 필수 | 예보지점 Y좌표 | 127 |

```python
from kpubdata import Client

client = Client.from_env()
ds = client.dataset("datago.village_fcst")

result = ds.list(base_date="20250401", base_time="0500", nx="55", ny="127")
for item in result.items[:5]:
    print(item)
```

### ultra_srt_ncst (초단기실황 조회서비스)

기상청에서 제공하는 실시간 기상 관측 정보입니다. 현재 시점의 기온, 강수량, 습도 등을 확인할 수 있습니다.

- 제공 기관: 기상청
- 주요 파라미터: `base_date`, `base_time`, `nx`, `ny`

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| base_date | 필수 | 발표일자 (YYYYMMDD) | "20250401" |
| base_time | 필수 | 발표시각 (HHMM) | "0600" |
| nx | 필수 | 예보지점 X좌표 | 55 |
| ny | 필수 | 예보지점 Y좌표 | 127 |

```python
ds = client.dataset("datago.ultra_srt_ncst")
result = ds.list(base_date="20250401", base_time="0600", nx="55", ny="127")
```

### air_quality (대기오염정보 조회서비스)

한국환경공단(에어코리아)에서 제공하는 대기질 측정 정보입니다. 미세먼지(PM10), 초미세먼지(PM2.5), 오존 등의 농도를 조회합니다.

- 제공 기관: 한국환경공단
- 주요 파라미터: `sidoName` (시도 명칭), `numOfRows` (한 페이지 결과 수)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| sidoName | 필수 | 시도명 | "서울" |
| numOfRows | 선택 | 조회건수 | "5" |

```python
ds = client.dataset("datago.air_quality")
raw = ds.call_raw("getCtprvnRltmMesureDnsty", sidoName="서울", numOfRows="5")
```

### bus_arrival (경기도 버스도착정보 조회서비스)

경기도 내 버스 정류소의 실시간 버스 도착 정보를 제공합니다.

- 제공 기관: 경기도
- 주요 파라미터: `stationId` (정류소 아이디)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| stationId | 필수 | 정류소 ID | "200000078" |

```python
ds = client.dataset("datago.bus_arrival")
raw = ds.call_raw("getBusArrivalListv2", stationId="200000078")
```

### hospital_info (병원정보서비스)

건강보험심사평가원에서 제공하는 전국 병의원 기본 정보 및 위치 정보입니다.

- 제공 기관: 건강보험심사평가원
- 주요 파라미터: `numOfRows` (조회 건수)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| numOfRows | 선택 | 조회건수 | "10" |

```python
ds = client.dataset("datago.hospital_info")
raw = ds.call_raw("getHospBasisList", numOfRows="10")
```

### apt_trade (아파트매매 실거래가)

국토교통부에서 제공하는 아파트 매매 실거래가 상세 정보입니다.

- 제공 기관: 국토교통부
- 주요 파라미터: `LAWD_CD` (법정동 코드 앞 5자리), `DEAL_YMD` (계약년월)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| LAWD_CD | 필수 | 법정동코드 앞5자리 | "11110" |
| DEAL_YMD | 필수 | 계약년월 (YYYYMM) | "202401" |

**참고 (LAWD_CD 법정동 코드):**
- 서울 종로구: 11110
- 서울 강남구: 11680
- 경기도 수원시 장안구: 41111
- 각 지역의 코드는 [행정표준코드관리시스템](https://www.code.go.kr)에서 확인할 수 있습니다.

```python
ds = client.dataset("datago.apt_trade")
result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")

for item in result.items[:5]:
    print(item)
```

### apt_rent (아파트 전월세 실거래가)

국토교통부에서 제공하는 아파트 전월세 실거래가 정보입니다.

- 제공 기관: 국토교통부
- 주요 파라미터: `LAWD_CD` (법정동 코드 앞 5자리), `DEAL_YMD` (계약년월)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| LAWD_CD | 필수 | 법정동코드 앞5자리 | "11110" |
| DEAL_YMD | 필수 | 계약년월 (YYYYMM) | "202401" |

```python
ds = client.dataset("datago.apt_rent")
result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")
```

### offi_trade (오피스텔 매매 실거래가)

국토교통부에서 제공하는 오피스텔 매매 실거래가 정보입니다.

- 제공 기관: 국토교통부
- 주요 파라미터: `LAWD_CD` (법정동 코드 앞 5자리), `DEAL_YMD` (계약년월)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| LAWD_CD | 필수 | 법정동코드 앞5자리 | "11110" |
| DEAL_YMD | 필수 | 계약년월 (YYYYMM) | "202401" |

```python
ds = client.dataset("datago.offi_trade")
result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")
```

### offi_rent (오피스텔 전월세 실거래가)

국토교통부에서 제공하는 오피스텔 전월세 실거래가 정보입니다.

- 제공 기관: 국토교통부
- 주요 파라미터: `LAWD_CD` (법정동 코드 앞 5자리), `DEAL_YMD` (계약년월)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| LAWD_CD | 필수 | 법정동코드 앞5자리 | "11110" |
| DEAL_YMD | 필수 | 계약년월 (YYYYMM) | "202401" |

```python
ds = client.dataset("datago.offi_rent")
result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")
```

### rh_trade (연립다세대 매매 실거래가)

국토교통부에서 제공하는 연립다세대 매매 실거래가 정보입니다.

- 제공 기관: 국토교통부
- 주요 파라미터: `LAWD_CD` (법정동 코드 앞 5자리), `DEAL_YMD` (계약년월)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| LAWD_CD | 필수 | 법정동코드 앞5자리 | "11110" |
| DEAL_YMD | 필수 | 계약년월 (YYYYMM) | "202401" |

```python
ds = client.dataset("datago.rh_trade")
result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")
```

### rh_rent (연립다세대 전월세 실거래가)

국토교통부에서 제공하는 연립다세대 전월세 실거래가 정보입니다.

- 제공 기관: 국토교통부
- 주요 파라미터: `LAWD_CD` (법정동 코드 앞 5자리), `DEAL_YMD` (계약년월)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| LAWD_CD | 필수 | 법정동코드 앞5자리 | "11110" |
| DEAL_YMD | 필수 | 계약년월 (YYYYMM) | "202401" |

```python
ds = client.dataset("datago.rh_rent")
result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")
```

### sh_trade (단독/다가구 매매 실거래가)

국토교통부에서 제공하는 단독/다가구 매매 실거래가 정보입니다.

- 제공 기관: 국토교통부
- 주요 파라미터: `LAWD_CD` (법정동 코드 앞 5자리), `DEAL_YMD` (계약년월)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| LAWD_CD | 필수 | 법정동코드 앞5자리 | "11110" |
| DEAL_YMD | 필수 | 계약년월 (YYYYMM) | "202401" |

```python
ds = client.dataset("datago.sh_trade")
result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")
```

### sh_rent (단독/다가구 전월세 실거래가)

국토교통부에서 제공하는 단독/다가구 전월세 실거래가 정보입니다.

- 제공 기관: 국토교통부
- 주요 파라미터: `LAWD_CD` (법정동 코드 앞 5자리), `DEAL_YMD` (계약년월)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| LAWD_CD | 필수 | 법정동코드 앞5자리 | "11110" |
| DEAL_YMD | 필수 | 계약년월 (YYYYMM) | "202401" |

```python
ds = client.dataset("datago.sh_rent")
result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")
```

### generic (범용 엔드포인트)

KPubData에 정식 등록되지 않은 임의의 data.go.kr 엔드포인트를 호출할 수 있는 비상구입니다. 카탈로그가 없는 API를 즉시 사용해야 할 때 활용하세요.

- 제공 기관: data.go.kr (모든 기관)
- 호출 방식: `call_raw(operation, _base_url=..., **params)` 만 지원합니다. `list()`는 지원하지 않습니다.
- 인증키(`serviceKey`)는 자동으로 주입됩니다.

| 매직 파라미터 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `_base_url` | 필수 | — | 엔드포인트 베이스 URL (`/operation` 직전까지) |
| `_envelope` | 선택 | `True` | 표준 `response.header.resultCode` 검증 여부. 비표준 응답이면 `False` |
| `_service_key_param` | 선택 | `serviceKey` | 인증키 파라미터 이름 변경 |
| `_format_param` | 선택 | `resultType` | 응답 포맷 파라미터 이름 변경 |

```python
ds = client.dataset("datago.generic")

# 예: 동네예보 API를 generic으로 호출
result = ds.call_raw(
    "getVilageFcst",
    _base_url="http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0",
    base_date="20250401",
    base_time="0500",
    nx="55",
    ny="127",
)
```

```python
# 비표준 envelope 응답을 받는 엔드포인트
result = ds.call_raw(
    "getCustomData",
    _base_url="http://apis.data.go.kr/XXXXXXX/SomeService",
    _envelope=False,
    someParam="value",
)
```

> 주의: generic은 정규화된 `RecordBatch`를 반환하지 않고 원본 응답(dict)을 그대로 돌려줍니다. 페이지네이션·필드 정규화·타입 변환은 호출자가 직접 처리해야 합니다. 자주 사용하는 데이터셋이라면 정식 카탈로그 등록(`기여자를 위한 새 데이터셋 추가 가이드` 참고)을 권장합니다.

### tour_kor_area (한국관광공사 지역기반 관광정보)

한국관광공사 TourAPI(KorService2)의 `areaBasedList2` 엔드포인트로, 지역코드 기준 관광지 목록을 조회합니다.

- 제공 기관: 한국관광공사
- 데이터 ID: [15101578](https://www.data.go.kr/data/15101578/openapi.do)
- 주요 파라미터: `MobileOS`, `MobileApp` (필수), `areaCode`, `contentTypeId`, `numOfRows`, `pageNo`

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| MobileOS | 필수 | OS 구분 | "ETC" |
| MobileApp | 필수 | 앱 이름 | "kpubdata" |
| areaCode | 선택 | 지역 코드 | "1" (서울) |
| contentTypeId | 선택 | 관광 타입 ID | "12" (관광지) |
| numOfRows | 선택 | 한 페이지 결과 수 | "10" |
| pageNo | 선택 | 페이지 번호 | "1" |

```python
ds = client.dataset("datago.tour_kor_area")
raw = ds.call_raw(
    "areaBasedList2",
    MobileOS="ETC",
    MobileApp="kpubdata",
    numOfRows="5",
    pageNo="1",
    areaCode="1",
)
```

### tour_kor_location (한국관광공사 위치기반 관광정보)

위경도 좌표와 반경을 기준으로 주변 관광 정보를 조회합니다 (`locationBasedList2`).

- 제공 기관: 한국관광공사
- 데이터 ID: [15101578](https://www.data.go.kr/data/15101578/openapi.do)
- 주요 파라미터: `MobileOS`, `MobileApp`, `mapX`, `mapY`, `radius`

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| MobileOS | 필수 | OS 구분 | "ETC" |
| MobileApp | 필수 | 앱 이름 | "kpubdata" |
| mapX | 필수 | 경도 (WGS84) | "126.9784" |
| mapY | 필수 | 위도 (WGS84) | "37.5665" |
| radius | 필수 | 반경 (m, 최대 20000) | "1000" |

```python
ds = client.dataset("datago.tour_kor_location")
raw = ds.call_raw(
    "locationBasedList2",
    MobileOS="ETC",
    MobileApp="kpubdata",
    mapX="126.9784",
    mapY="37.5665",
    radius="1000",
    numOfRows="5",
    pageNo="1",
)
```

### tour_kor_keyword (한국관광공사 키워드 검색)

키워드로 관광 정보를 검색합니다 (`searchKeyword2`).

- 제공 기관: 한국관광공사
- 데이터 ID: [15101578](https://www.data.go.kr/data/15101578/openapi.do)
- 주요 파라미터: `MobileOS`, `MobileApp`, `keyword`

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| MobileOS | 필수 | OS 구분 | "ETC" |
| MobileApp | 필수 | 앱 이름 | "kpubdata" |
| keyword | 필수 | 검색 키워드 | "경복궁" |

```python
ds = client.dataset("datago.tour_kor_keyword")
raw = ds.call_raw(
    "searchKeyword2",
    MobileOS="ETC",
    MobileApp="kpubdata",
    keyword="경복궁",
    numOfRows="5",
    pageNo="1",
)
```

### tour_kor_festival (한국관광공사 행사정보)

날짜 범위 기준으로 행사·축제 정보를 조회합니다 (`searchFestival2`).

- 제공 기관: 한국관광공사
- 데이터 ID: [15101578](https://www.data.go.kr/data/15101578/openapi.do)
- 주요 파라미터: `MobileOS`, `MobileApp`, `eventStartDate`

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| MobileOS | 필수 | OS 구분 | "ETC" |
| MobileApp | 필수 | 앱 이름 | "kpubdata" |
| eventStartDate | 필수 | 행사 시작일 (YYYYMMDD) | "20250101" |
| eventEndDate | 선택 | 행사 종료일 (YYYYMMDD) | "20251231" |

```python
ds = client.dataset("datago.tour_kor_festival")
raw = ds.call_raw(
    "searchFestival2",
    MobileOS="ETC",
    MobileApp="kpubdata",
    eventStartDate="20250101",
    numOfRows="5",
    pageNo="1",
)
```

### metro_fare (서울교통공사 실시간 운임정보)

서울교통공사의 출발역-도착역 간 실시간 운임 정보를 조회합니다 (`getRltmFare2`).

- 제공 기관: 서울교통공사
- 데이터 ID: [15143846](https://www.data.go.kr/data/15143846/openapi.do)
- 주요 파라미터: `numOfRows`, `pageNo`

```python
ds = client.dataset("datago.metro_fare")
raw = ds.call_raw("getRltmFare2", numOfRows="5", pageNo="1")
```

### metro_path (서울교통공사 최단경로 이동정보)

두 지하철역 간 최단 경로(환승·소요시간 등)를 조회합니다 (`getShtrmPath`).

- 제공 기관: 서울교통공사
- 데이터 ID: [15143842](https://www.data.go.kr/data/15143842/openapi.do)
- 주요 파라미터: `numOfRows`, `pageNo`

```python
ds = client.dataset("datago.metro_path")
raw = ds.call_raw("getShtrmPath", numOfRows="5", pageNo="1")
```

### g2b_contract (나라장터 조달계약정보)

조달청(나라장터)에서 제공하는 물품 조달 계약 정보입니다. 수요기관, 품목, 계약금액, 공급업체 등을 조회할 수 있습니다.

- 제공 기관: 조달청
- 데이터 ID: [15129427](https://www.data.go.kr/data/15129427/openapi.do)
- 주요 파라미터: `inqryBgnDt` (조회시작일), `inqryEndDt` (조회종료일), `dmndInsttNm` (수요기관명)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| inqryBgnDt | 선택 | 조회 시작 연월 (YYYYMM) | "202201" |
| inqryEndDt | 선택 | 조회 종료 연월 (YYYYMM) | "202512" |
| dmndInsttNm | 선택 | 수요기관명 | "한국환경공단" |

```python
from kpubdata import Client

client = Client.from_env()
ds = client.dataset("datago.g2b_contract")
raw = ds.call_raw("getCntrctInfoListThng", inqryBgnDt="202201", inqryEndDt="202512", numOfRows="10")
```

### social_enterprise (사회적기업 인증현황)

고용노동부에서 제공하는 사회적기업 인증 현황 정보입니다. 기업명, 소재지, 업종, 인증일 등을 조회할 수 있습니다.

> ⚠️ **ODcloud 프로토콜**: 이 데이터셋은 `apis.data.go.kr`이 아닌 `api.odcloud.kr`을 통해 제공됩니다. 페이지네이션 파라미터(`page`/`page_size`)와 응답 구조(`data[]` 플랫 배열)가 표준 data.go.kr 프로토콜과 다릅니다. KPubData가 내부적으로 자동 처리하므로 사용자는 동일한 방식으로 호출할 수 있습니다.

- 제공 기관: 고용노동부
- 데이터 ID: [15082035](https://www.data.go.kr/data/15082035/openapi.do)
- 주요 파라미터: `page` (페이지 번호), `page_size` (페이지당 건수)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| page | 선택 | 페이지 번호 | "1" |
| page_size | 선택 | 페이지당 건수 | 10 |

```python
ds = client.dataset("datago.social_enterprise")
result = ds.list(page_size=10)
for item in result.items[:3]:
    print(item)
# 응답 예시 필드: entNmV (기업명), addr (주소), busiContV (업종), certiIssuD (인증일)
```

### g2b_catalog (나라장터 종합쇼핑몰 품목정보)

조달청 종합쇼핑몰에 등록된 물품의 단가계약 정보를 제공합니다. 품목분류, 계약업체, 계약단가, 인증정보 등을 조회할 수 있습니다.

- 제공 기관: 조달청
- 데이터 ID: [15129471](https://www.data.go.kr/data/15129471/openapi.do)
- 주요 파라미터: `prdctClsfcNoNm` (품목명), `cntrctCorpNm` (계약업체명)
- 필수 파라미터 `inqryDiv`는 카탈로그 `default_filters`가 자동으로 전송합니다 (사용자 필터로 재정의 가능)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| inqryDiv | 필수 (자동 전송) | 조회구분 | "1" |
| prdctClsfcNoNm | 선택 | 품목명 | "조립식철근콘크리트암거블록" |
| prdctIdntNo | 선택 | 물품식별번호 | "23277843" |
| cntrctCorpNm | 선택 | 계약업체명 | "삼화케익블럭" |
| rgstDtBgnDt / rgstDtEndDt | 선택 | 등록일시 범위 (YYYYMMDDHHMI) | "202404010000" ~ "202404302359" |

```python
ds = client.dataset("datago.g2b_catalog")
result = ds.list(page_size=5)  # inqryDiv=1 자동 전송
for item in result.items[:3]:
    print(item)
# 응답 예시 필드: prdctClsfcNoNm (품목명), dtilPrdctClsfcNoNm (세부품명), cntrctCorpNm (계약업체명), cntrctPrceAmt (계약단가)
```

### subway_passengers (지하철역별 승하차 인원)

서울교통공사에서 제공하는 역별 일자/시간대별 승하차 인원 정보입니다. 카드종류·이용자유형별로 집계된 raw 데이터를 제공합니다.

- 제공 기관: 서울교통공사
- 데이터 ID: [15143845](https://www.data.go.kr/data/15143845/openapi.do)
- 주요 파라미터: `pasngYmd` (통행일자, 필수), `stnCd` (역코드)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| pasngYmd | 필수 | 통행일자 (YYYYMMDD, 최근 1주일치만 제공) | "20260521" |
| stnCd | 선택 | 역코드 | "2828" |
| numOfRows | 선택 | 한 페이지 결과 수 | "10" |

```python
ds = client.dataset("datago.subway_passengers")
result = ds.list(pasngYmd="20260521", numOfRows=10)
for item in result.items[:5]:
    print(item["stnNm"], item["pasngHr"], item["rideNope"], item["gffNope"])
```

### mid_fcst (중기전망조회)

기상청에서 제공하는 중기전망 정보입니다. 발표 시점 기준 향후 3~10일의 강수·기온 전망을 서술형 텍스트(`wfSv`)로 제공합니다.

- 제공 기관: 기상청
- 데이터 ID: [15059468](https://www.data.go.kr/data/15059468/openapi.do)
- 오퍼레이션: `getMidFcst`
- 주요 파라미터: `stnId` (지점 번호), `tmFc` (발표시각)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| stnId | 필수 | 지점 번호 (108=전국) | "108" |
| tmFc | 필수 | 발표시각 (YYYYMMDDHHmm). 일 2회 06시·18시 발표, 최근 24시간 조회 가능 | "202604010600" |

```python
ds = client.dataset("datago.mid_fcst")
raw = ds.call_raw("getMidFcst", stnId="108", tmFc="202604010600")
```

### mid_land_fcst (중기육상예보조회)

기상청에서 제공하는 중기육상예보 정보입니다. 지역(`regId`)별 강수확률(`rnStN`)과 날씨(`wfN`)를 3~10일 단위로 제공합니다.

- 제공 기관: 기상청
- 데이터 ID: [15059468](https://www.data.go.kr/data/15059468/openapi.do)
- 오퍼레이션: `getMidLandFcst`
- 주요 파라미터: `regId` (예보구역 코드), `tmFc` (발표시각)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| regId | 필수 | 예보구역 코드 (예: 11B00000=서울·인천·경기) | "11B00000" |
| tmFc | 필수 | 발표시각 (YYYYMMDDHHmm). 일 2회 06시·18시 발표 | "202604010600" |

```python
ds = client.dataset("datago.mid_land_fcst")
raw = ds.call_raw("getMidLandFcst", regId="11B00000", tmFc="202604010600")
```

### mid_ta (중기기온조회)

기상청에서 제공하는 중기기온 정보입니다. 지역(`regId`)별 일 최저(`taMinN`)·최고(`taMaxN`) 기온을 3~10일 단위로 제공합니다.

- 제공 기관: 기상청
- 데이터 ID: [15059468](https://www.data.go.kr/data/15059468/openapi.do)
- 오퍼레이션: `getMidTa`
- 주요 파라미터: `regId` (지점 코드), `tmFc` (발표시각)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| regId | 필수 | 지점 코드 (예: 11D20501=춘천) | "11D20501" |
| tmFc | 필수 | 발표시각 (YYYYMMDDHHmm). 일 2회 06시·18시 발표 | "202604010600" |

```python
ds = client.dataset("datago.mid_ta")
raw = ds.call_raw("getMidTa", regId="11D20501", tmFc="202604010600")
```

### mid_sea_fcst (중기해상예보조회)

기상청에서 제공하는 중기해상예보 정보입니다. 해역(`regId`)별 날씨(`wfN`)와 파고(`whNAAm`/`whNPm`)를 3~10일 단위로 제공합니다.

- 제공 기관: 기상청
- 데이터 ID: [15059468](https://www.data.go.kr/data/15059468/openapi.do)
- 오퍼레이션: `getMidSeaFcst`
- 주요 파라미터: `regId` (해역 코드), `tmFc` (발표시각)

| 파라미터 | 필수 | 설명 | 예시 |
|---|---|---|---|
| regId | 필수 | 해역 코드 (예: 12A20000=서해중부) | "12A20000" |
| tmFc | 필수 | 발표시각 (YYYYMMDDHHmm). 일 2회 06시·18시 발표 | "202604010600" |

```python
ds = client.dataset("datago.mid_sea_fcst")
raw = ds.call_raw("getMidSeaFcst", regId="12A20000", tmFc="202604010600")
```

## 공공데이터포털 API 특이사항

- **응답 형식**: JSON과 XML을 모두 지원하는 경우가 많으나, KPubData는 내부적으로 JSON 형식을 우선 사용합니다.
- **인증키 처리**: 발급받은 인증키는 인코딩된 상태로 제공될 수 있지만, KPubData가 내부적으로 적절히 처리하므로 발급받은 일반(Decoding) 키를 그대로 사용합니다.
- **정상 응답 판별**: 응답 데이터의 `header` 내 `resultCode`가 `"00"`이면 정상 응답이며, 그 외의 코드는 에러를 의미합니다.
- **일일 호출 제한**: API별로 일일 호출 제한 횟수가 설정되어 있으므로, 마이페이지에서 사용량을 확인할 수 있습니다.
- **프로토콜**: 일부 API는 `http`만 지원하고, 일부는 `https`도 지원합니다.

### ODcloud 프로토콜 (`api.odcloud.kr`)

일부 데이터셋(예: `datago.social_enterprise`)은 `apis.data.go.kr`이 아닌 `api.odcloud.kr`을 통해 제공됩니다. ODcloud 프로토콜은 표준 data.go.kr 프로토콜과 다음과 같은 차이가 있습니다:

| 항목 | data.go.kr 표준 | ODcloud |
|---|---|---|
| 기본 URL | `apis.data.go.kr` | `api.odcloud.kr` |
| 페이지네이션 파라미터 | `pageNo` / `numOfRows` | `page` / `perPage` |
| 응답 구조 | `response.header.resultCode` + `response.body.items.item[]` | 플랫 JSON: `{ currentCount, data[], matchCount, page, perPage, totalCount }` |
| 응답 포맷 파라미터 | `resultType=json` 등 | 없음 (JSON 고정) |

KPubData는 `catalogue.json`의 `provider_family: "odcloud"` 필드를 통해 자동으로 프로토콜을 전환합니다. 사용자는 표준 `list()` / `call_raw()` 인터페이스를 동일하게 사용할 수 있습니다.

## 트러블슈팅

### 401 Unauthorized / SERVICE_KEY_IS_NOT_REGISTERED_ERROR

증상: API 키를 발급받았으나 호출 시 401 에러 또는 "SERVICE_KEY_IS_NOT_REGISTERED_ERROR" 메시지가 반환됩니다.

**실제 에러 예시 (Terminal/curl):**
```text
$ curl "http://apis.data.go.kr/..."
HTTP/1.1 401 Unauthorized
Content-Type: text/xml
...
<OpenAPI_ServiceResponse>
    <cmmMsgHeader>
        <errMsg>SERVICE KEY IS NOT REGISTERED.</errMsg>
        <returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>
        <returnReasonCode>30</returnReasonCode>
    </cmmMsgHeader>
</OpenAPI_ServiceResponse>
```

**실제 에러 예시 (Python/KPubData):**
```python
Traceback (most recent call last):
  File "example.py", line 8, in <module>
    result = ds.list(base_date="20250401", ...)
  File "kpubdata/core/dataset.py", line 45, in list
    return self.adapter.list(query)
  File "kpubdata/adapters/datago/base.py", line 112, in list
    raise AuthError("SERVICE_KEY_IS_NOT_REGISTERED_ERROR (30)")
kpubdata.exceptions.AuthError: SERVICE_KEY_IS_NOT_REGISTERED_ERROR (30)
```

원인 및 해결:

1. **키 활성화 대기**: 키 발급 후 1~2시간의 동기화 시간이 필요합니다. 시간이 지난 후 다시 시도하세요.
2. **활용신청 미완료**: 해당 API에 대한 활용신청이 승인되었는지 마이페이지에서 확인합니다.
3. **키 종류 확인**: 일반 인증키(Decoding)를 사용하고 있는지 확인합니다. Encoding 키는 URL을 직접 구성할 때 사용하는 것으로, KPubData에서는 일반 키를 사용해야 합니다.

### 에러코드 30: SERVICE_KEY_IS_NOT_REGISTERED_ERROR

인증키가 해당 API에 등록되지 않았거나, 아직 동기화되지 않은 상태입니다.

**XML 응답 예시:**
```xml
<OpenAPI_ServiceResponse>
    <cmmMsgHeader>
        <errMsg>SERVICE KEY IS NOT REGISTERED.</errMsg>
        <returnAuthMsg>SERVICE_KEY_IS_NOT_REGISTERED_ERROR</returnAuthMsg>
        <returnReasonCode>30</returnReasonCode>
    </cmmMsgHeader>
</OpenAPI_ServiceResponse>
```

- 활용신청 완료 여부를 마이페이지에서 확인합니다.
- 발급 직후라면 1~2시간 후 재시도합니다.
- 3시간 이상 지속되면 공공데이터 활용지원센터(1566-0025)에 문의합니다.

### 에러코드 31: SERVICE_KEY_EXPIRED

인증키가 만료되었습니다. 마이페이지에서 키를 갱신합니다.

### 에러코드 32: UNREGISTERED_IP

호출하는 IP가 등록되지 않은 경우입니다. 일부 API는 IP 화이트리스트를 요구합니다.

### SSL/TLS 관련 에러

일부 API에서 `https`로 호출할 때 SSL 에러가 발생할 수 있습니다.

- KPubData의 catalogue.json에 정의된 base_url은 `http`를 사용합니다.
- 로컬 테스트 환경에서 SSL 에러가 발생하면 `http` 프로토콜로 호출되는지 확인합니다.

### 심의 승인 대기 중

국토교통부 등 일부 기관의 API는 자동 승인이 아닌 심의 승인 방식입니다.

- 마이페이지에서 처리상태가 "승인"인지 확인합니다.
- 심의 중인 경우 1~2일(영업일) 기다려야 합니다.
- 반려된 경우 활용 목적을 보다 구체적으로 작성하여 재신청합니다.

## 기여자를 위한 새 데이터셋 추가 가이드

공공데이터포털에는 수천 개의 Open API가 존재합니다. 새로운 datago 데이터셋을 KPubData에 추가하려면 다음 절차를 따릅니다.

### 1. API 선정 및 이슈 등록

1. [data.go.kr](https://www.data.go.kr)에서 추가하려는 API를 검색합니다.
2. API 상세 페이지에서 다음 정보를 확인합니다:
   - **서비스 유형**: REST 인지 확인 (SOAP은 지원 불가)
   - **데이터 포맷**: JSON 또는 XML 지원 여부
   - **End Point**: base URL
   - **오퍼레이션 목록**: 사용 가능한 API 메서드명
3. GitHub에 이슈를 등록합니다 (제목: `feat: datago - [API명] 어댑터 추가`).

### 2. API 키 발급 및 활용신청

1. 위 "API 키 발급 방법" 절차를 따라 해당 API에 대한 활용신청을 완료합니다.
2. 키 활성화까지 1~2시간 대기합니다.
3. curl 또는 브라우저에서 API 호출이 성공하는지 확인합니다.

### 3. Fixture 저장

API의 실제 응답을 fixture 파일로 저장합니다.

```bash
# API를 직접 호출하여 응답을 fixture로 저장
curl "http://apis.data.go.kr/[SERVICE_PATH]/[OPERATION]?serviceKey=YOUR_KEY&..." > tests/fixtures/datago/[dataset_name].json
```

- 저장 위치: `tests/fixtures/datago/[dataset_name].json`
- JSON과 XML 응답 모두 저장하는 것을 권장합니다.

### 4. catalogue.json에 데이터셋 등록

`src/kpubdata/providers/datago/catalogue.json`에 새 데이터셋 항목을 추가합니다.

```json
{
  "dataset_key": "your_dataset",
  "name": "데이터셋 한글명 (English Name)",
  "base_url": "http://apis.data.go.kr/[SERVICE_PATH]",
  "default_operation": "[DEFAULT_OPERATION]",
  "representation": "api_json",
  "service_key_param": "serviceKey",
  "format_param": "resultType",
  "description": "English description of the dataset",
  "operations": ["list", "raw"],
  "query_support": {
    "pagination": "offset",
    "max_page_size": 1000
  }
}
```

주의 사항:
- `format_param`은 API마다 다릅니다 (`resultType`, `dataType`, `returnType`, `_type` 등). API 문서를 확인하세요.
- `base_url`은 API 상세 페이지의 End Point를 참고합니다.

### 5. 테스트 작성

- **unit test**: `tests/unit/adapters/test_datago_[dataset].py`
- **contract test**: `tests/contract/` 디렉토리에 추가
- **integration test**: `tests/integration/test_datago_live.py`에 테스트 추가

### 6. 문서 업데이트

- 이 문서(`docs/providers/datago.md`)의 "지원 데이터셋" 섹션에 새 데이터셋 추가
- `SUPPORTED_DATA.md` 업데이트

### 7. PR 제출

- 브랜치명: `feat/issue-[NUMBER]-[dataset-name]`
- PR에 포함해야 할 것: fixture, catalogue.json 변경, 테스트, 문서 업데이트

## Integration 테스트 실행

datago의 실 API 테스트를 실행하려면:

```bash
# 환경변수 설정
export KPUBDATA_DATAGO_API_KEY="your-key"

# datago integration 테스트만 실행
uv run pytest tests/integration/test_datago_live.py -m integration -ra -v
```

## 검증 현황

데이터셋별 검증 수준(텍스트 검증 / 실API 검증)은 [SUPPORTED_DATA.md](https://github.com/kpubdata-lab/kpubdata/blob/main/SUPPORTED_DATA.md)를 참고하세요.
## 관련 문서

- [공공데이터포털 공식 사이트](https://www.data.go.kr)
- [공공데이터 활용지원센터](https://www.data.go.kr/bbs/qna/list.do) (문의: 1566-0025)
- [datago API 기술 참고자료](../datago-api-reference.md)
- [SUPPORTED_DATA.md](https://github.com/kpubdata-lab/kpubdata/blob/main/SUPPORTED_DATA.md)
