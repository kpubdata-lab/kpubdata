# KPubData — Korea Public Data

**KPubData is the access layer for Korean public data.**
Discover, query, and integrate Korea's most useful public datasets through one consistent [Python](https://docs.python.org/ko/3/tutorial/index.html) interface.

공공데이터 포털의 수많은 [API](https://ko.wikipedia.org/wiki/API)(프로그램끼리 데이터를 주고받는 규칙)는 저마다 인증 방식, 응답 형식, 페이지 처리가 제각각입니다. KPubData는 이러한 차이를 어댑터가 흡수하여, 개발자가 일관된 방식으로 데이터를 탐색하고 수집할 수 있도록 돕습니다. 사용자의 공식 API 키를 그대로 사용하는 SDK 구조이므로, 데이터를 소유하거나 재배포하지 않습니다.

<!-- BEGIN: datasets -->

- **spec 기반 데이터셋**: 23종 — `make verify` 4단계 기계 검증 통과
- **catalogue 기반 데이터셋**: 150종 (bok 4, datago 41, fds 1, kipris 1, korean 1, kosis 2, krx 3, law 3, localdata 59, lofin 6, neis 2, semas 17, seoul 7, sgis 3)

| spec 데이터셋 | 검증 |
|---|---|
| `datago.air_quality` | 실API 2026-09-09 |
| `datago.air_station` | 실API 2026-09-09 |
| `datago.airkorea_forecast` | 실API 2026-09-09 |
| `datago.apt_rent` | 실API 2026-09-09 |
| `datago.apt_trade` | 실API 2026-09-12 |
| `datago.hospital_info` | 실API 2026-09-09 |
| `datago.metro_fare` | 실API 2026-09-09 |
| `datago.ocean_buoy` | 실API - |
| `datago.offi_rent` | 실API 2026-09-09 |
| `datago.offi_trade` | 실API 2026-09-09 |
| `datago.rh_rent` | 실API 2026-09-09 |
| `datago.sh_rent` | 실API 2026-09-09 |
| `datago.sh_trade` | 실API 2026-09-09 |
| `datago.tour_kor_area` | 실API 2026-09-10 |
| `datago.tour_kor_festival` | 실API 2026-09-10 |
| `datago.tour_kor_keyword` | 실API 2026-09-10 |
| `datago.tour_kor_location` | 실API 2026-09-10 |
| `datago.ultra_srt_fcst` | 실API 2026-09-09 |
| `datago.ultra_srt_ncst` | 실API 2026-09-09 |
| `datago.village_fcst` | 실API 2026-09-09 |
| `localdata.bakery` | 실API 2026-09-09 |
| `localdata.general_restaurant` | 실API 2026-09-09 |
| `localdata.rest_cafe` | 실API 2026-09-09 |

> 이 표는 `scripts/gen_readme_datasets.py`로 생성했다 — 직접 편집 금지.
<!-- END: datasets -->

## 이 프로젝트가 존재하는 이유

한국의 공공데이터 [API](https://ko.wikipedia.org/wiki/API)(프로그램으로 데이터를 가져올 수 있는 창구)는 기관마다 다음과 같은 차이점이 있어 통합 관리가 어렵습니다.

- **인증 방식**: 기관마다 "출입증"(API 키)을 확인하는 방법이 다름
- **요청 규칙**: 같은 종류의 데이터를 요청하더라도 기관마다 사용하는 변수 이름이 제각각임
- **데이터 형식**: 어떤 기관은 [XML](https://ko.wikipedia.org/wiki/XML)(태그 형식), 어떤 기관은 [JSON](https://ko.wikipedia.org/wiki/JSON)(중괄호 형식), 또 어떤 기관은 [CSV](https://ko.wikipedia.org/wiki/CSV)(엑셀 형식)로 응답하여 형태가 혼재함
- **페이지 처리**: 데이터가 많을 때 나눠 받는 방식이 `pageNo`, `numOfRows`, 시작/종료 인덱스 등 기관마다 다양함
- **에러 처리**: 요청이 실패했을 때 알려주는 방식이 기관마다 달라서, 어떤 곳은 [HTTP](https://ko.wikipedia.org/wiki/HTTP) 상태 코드(예: 404)를, 어떤 곳은 응답 안에 별도 에러 코드를 넣어 보냄
- **데이터 구조**: 응답에 포함되는 항목(필드)이 예고 없이 변경되거나, 숫자여야 할 곳에 문자가 오는 등 불안정함

KPubData는 개발자가 매번 새로운 기관의 API 문서를 처음부터 학습해야 하는 수고를 덜어주면서도, 각 기관의 특수성을 억지로 감추지 않는 유연한 구조를 지향합니다.

## 핵심 설계 원칙

1. **데이터셋 중심, 제공 기관 인지**
   - 사용자는 "기상청"이라는 기관 이름보다 "동네예보"나 "지하철 정보" 같은 **데이터 이름**에 집중합니다. 도서관에서 책을 찾을 때 출판사보다 책 제목으로 먼저 검색하는 것과 같은 원리입니다.
2. **방언(Dialect) 기반 아키텍처**
   - 마치 사투리를 표준어로 통역해주는 것처럼, 핵심 기능(표준어)은 작고 안정적으로 유지하면서 각 기관의 고유한 방식(사투리)은 전용 어댑터(통역사)가 처리합니다.
3. **기능 우선의 정직성**
   - 지원하는 기능은 명확히 "할 수 있다"고 선언하고, 지원하지 않는 기능을 요청하면 "이건 못해요"라고 솔직하게 알려줍니다. 사용자가 "왜 안 되지?" 하고 헤매는 일이 없습니다.
4. **파이썬다운(Pythonic) API**
   - 파이썬 개발자가 익숙한 `snake_case`(단어_사이_밑줄) 이름 규칙과 직관적인 메서드명을 사용하여, 별도 학습 없이도 자연스럽게 사용할 수 있습니다.
5. **표준화와 원본 데이터의 공존**
   - 정리된 형태로 데이터를 받는 것이 기본이지만, 원본 응답이 그대로 필요할 때를 위해 비상구(`call_raw`)를 항상 열어둡니다. 번역본을 읽다가 원문이 궁금하면 언제든 원본을 볼 수 있는 것과 같습니다.

## 표준화 범위

KPubData는 모든 데이터를 하나의 틀에 억지로 끼워 맞추지 않습니다. 대신 데이터에 접근하는 **방법(입구)과 결과물을 담는 그릇(봉투)**을 통일합니다. 마치 각 나라의 우편 봉투 규격은 통일하되, 봉투 안에 들어가는 편지 내용은 자유롭게 두는 것과 같습니다.

### 통일하는 것
- 클라이언트(접속 도구)를 만드는 방식
- 데이터셋을 검색하고 찾는 방법
- 주요 동작 진입점 (`list` 목록조회, `get` 단건조회, `schema` 구조확인, `call_raw` 원본호출)
- 어댑터(통역사)의 기능 선언 방식
- 결과물을 담는 표준 형식 (`RecordBatch`)
- 에러(오류)를 알려주는 공통 규칙

### 통일하지 않는 것 (기관마다 다른 채로 두는 것)
- 각 기관이 요구하는 개별 변수 이름
- 데이터셋마다 고유한 세부 검색 조건
- 기관별로 다른 페이지 나눔 규칙
- 각 데이터 레코드의 세부 항목 구조

## 멘탈 모델

KPubData가 데이터를 처리하는 흐름은 다음과 같습니다.

```mermaid
sequenceDiagram
    participant U as 사용자 (User)
    participant C as 클라이언트 (Client)
    participant Cat as 카탈로그 (Catalog)
    participant A as 어댑터 (Adapter)
    participant T as 전송 계층 (Transport)
    participant P as 공공 API (Public API)

    U->>C: 데이터셋 요청
    C->>Cat: 데이터셋 검색/확인
    Cat-->>C: 데이터셋 객체 반환
    U->>C: 데이터 조회 (list/get)
    C->>A: 요청 위임
    A->>T: HTTP 요청
    T->>P: 실제 데이터 요청
    P-->>T: 원본 데이터 응답
    T-->>A: 파싱된 데이터 전달
    A-->>U: RecordBatch 반환
```

데이터를 찾는 과정은 아래의 구조를 따릅니다.

```text
Client (클라이언트)
  -> Catalog (카탈로그에서 데이터셋 찾기)
  -> ProviderAdapter (기관별 통역사)
  -> Transport (실제 통신 담당)
  -> Parse / normalize (데이터 정리 및 정규화)
  -> RecordBatch or Record (표준 결과물 반환)
```

## 설치 방법

[pip](https://pip.pypa.io/en/stable/)(파이썬 패키지 설치 도구)를 사용하여 설치합니다.

```bash
pip install kpubdata
```

> 처음 사용하시나요? [빠른 시작 가이드](./docs/quickstart.md)를 따라하면 설치부터 데이터 조회까지 한 번에 완료할 수 있습니다.

## 빠른 시작

### 1. API 키 설정

KPubData가 지원하는 각 기관의 API 키를 발급받아 [환경 변수](https://ko.wikipedia.org/wiki/%ED%99%98%EA%B2%BD_%EB%B3%80%EC%88%98)(운영체제에 저장하는 설정값)로 설정하거나 코드에서 직접 전달합니다.

#### 공공데이터포털 (data.go.kr) — `datago`
- **가입 URL**: [https://www.data.go.kr](https://www.data.go.kr)
- **절차**: 회원가입 → 원하는 Open API 상세 페이지에서 "활용신청" 클릭 → 신청서 작성 → 마이페이지에서 인증키 확인
- **참고**: 일부 API는 자동 승인되나, 일부는 심의 후 승인까지 1~2일이 소요될 수 있습니다.
- **환경 변수**: `KPUBDATA_DATAGO_API_KEY`

#### 한국은행 ECOS (ecos.bok.or.kr) — `bok`
- **가입 URL**: [https://ecos.bok.or.kr/api/](https://ecos.bok.or.kr/api/)
- **절차**: Open API 서비스 페이지에서 "인증키 신청" → 본인인증 및 회원가입 → 마이페이지에서 API 키 확인
- **환경 변수**: `KPUBDATA_BOK_API_KEY`

#### 통계청 KOSIS (kosis.kr) — `kosis`
- **가입 URL**: [https://kosis.kr/openapi/index/index.jsp](https://kosis.kr/openapi/index/index.jsp)
- **절차**: 로그인/회원가입 → "활용신청" → 마이페이지에서 API 키 확인
- **개발 가이드**: [KOSIS 개발자 가이드](https://kosis.kr/openapi/devGuide/devGuide_0203List.do)
- **환경 변수**: `KPUBDATA_KOSIS_API_KEY`

#### 지방재정365 (lofin365.go.kr) — `lofin`
- **가입 URL**: [https://www.lofin365.go.kr](https://www.lofin365.go.kr)
- **절차**: 회원가입 → 로그인 → 마이페이지 → [인증키발급](https://www.lofin365.go.kr/portal/LF9220200.do) → "인증키 신청" 클릭 → 발급 완료
- **참고**: 지방재정365는 지방자치단체 재정 데이터를 제공합니다. 중앙정부 재정 데이터(열린재정)와는 별도 시스템입니다.
- **SSL 참고**: 이 서버는 한때 TLSv1.2와 AES256-SHA256만 제시했기 때문에, lofin
  요청에만 cipher 하한을 낮춘 컨텍스트(`DEFAULT:@SECLEVEL=1`)를 씁니다.
  **인증서 검증은 켜져 있습니다.** 다만 이 컨텍스트는 `ssl.create_default_context()`
  기반이라 시스템 CA 저장소를 쓰므로, certifi에만 CA가 있는 환경에서는 lofin만
  실패할 수 있습니다 — 그때는 시스템 CA를 설치하십시오.
- **환경 변수**: `KPUBDATA_LOFIN_API_KEY`

#### 지방행정인허가 (data.go.kr) — `localdata`
- **가입 URL**: [https://www.data.go.kr](https://www.data.go.kr)
- **절차**: 회원가입 → 지방행정인허가 Open API(일반음식점/휴게음식점) 활용신청 → 승인 후 인증키 확인
- **환경 변수**: `KPUBDATA_LOCALDATA_API_KEY`

#### 소상공인시장진흥공단 상가(상권)정보 (data.go.kr) — `semas`
- **가입 URL**: [https://www.data.go.kr](https://www.data.go.kr)
- **절차**: 회원가입 → 소상공인시장진흥공단 상가(상권)정보 Open API 활용신청 → 승인 후 인증키 확인
- **환경 변수**: `KPUBDATA_SEMAS_API_KEY`

#### 서울 열린데이터광장 (data.seoul.go.kr) — `seoul`
- **가입 URL**: [https://data.seoul.go.kr/](https://data.seoul.go.kr/)
- **절차**: 회원가입 → 원하는 Open API 페이지에서 인증키 신청/확인 → 마이페이지에서 발급 키 확인
- **참고**: 서울 Open API는 인증키를 쿼리스트링이 아니라 URL 경로 세그먼트로 전달합니다.
- **환경 변수**: `KPUBDATA_SEOUL_API_KEY`

#### 통계청 통계지리정보서비스 (sgis.kostat.go.kr) — `sgis`
- **가입 URL**: [https://sgis.kostat.go.kr/developer/html/main.html](https://sgis.kostat.go.kr/developer/html/main.html)
- **절차**: 회원가입 → 개발지원센터에서 서비스 ID/Secret 발급 → 인증 API로 accessToken 교환
- **인증 방식**: `consumer_key` + `consumer_secret` 2단계
- **환경 변수**:
  - `KPUBDATA_SGIS_API_KEY` (`consumer_key`)
  - `KPUBDATA_SGIS_CONSUMER_SECRET` (`consumer_secret`)
- **대안 입력**: 코드에서 `provider_keys["sgis"]`에 `"consumer_key:consumer_secret"` 형태를 직접 전달 가능

#### 환경 변수 설정 예시
```bash
# 공공데이터포털 (data.go.kr)
export KPUBDATA_DATAGO_API_KEY="your-datago-service-key"

# 한국은행 ECOS
export KPUBDATA_BOK_API_KEY="your-bok-api-key"

# 통계청 KOSIS
export KPUBDATA_KOSIS_API_KEY="your-kosis-api-key"

# 지방재정365
export KPUBDATA_LOFIN_API_KEY="your-lofin-api-key"

# 지방행정인허가
export KPUBDATA_LOCALDATA_API_KEY="your-localdata-service-key"

# 소상공인시장진흥공단 상가(상권)정보
export KPUBDATA_SEMAS_API_KEY="your-semas-service-key"

# 서울 열린데이터광장
export KPUBDATA_SEOUL_API_KEY="your-seoul-api-key"

# 통계청 SGIS
export KPUBDATA_SGIS_API_KEY="your-sgis-consumer-key"
export KPUBDATA_SGIS_CONSUMER_SECRET="your-sgis-consumer-secret"
```

### 2. 클라이언트 생성

```python
from kpubdata import Client

# 환경 변수에서 키를 자동으로 읽어오기
client = Client.from_env()

# 또는 키를 직접 명시하여 생성하기
client = Client(provider_keys={
    "datago": "YOUR_DATAGO_API_KEY",
    "bok": "YOUR_BOK_API_KEY",
    "kosis": "YOUR_KOSIS_API_KEY",
    "lofin": "YOUR_LOFIN_API_KEY",
    "localdata": "YOUR_DATA_GO_KR_API_KEY",
    "semas": "YOUR_SEMAS_API_KEY",
    "seoul": "YOUR_SEOUL_API_KEY",
    "sgis": "YOUR_SGIS_CONSUMER_KEY:YOUR_SGIS_CONSUMER_SECRET",
})
```

### 3. 데이터셋 탐색

```python
# 사용 가능한 모든 데이터셋 목록 보기
for ds in client.datasets.list():
    print(ds.id, ds.name)

# 키워드로 데이터셋 검색하기
for ds in client.datasets.search("예보"):
    print(ds.id, ds.name, ds.operations)
```

### CLI로 즉시 사용하기

설치가 끝나면 `kpubdata` 명령이 함께 등록됩니다. 간단한 탐색이나 파라미터 실험은 스크립트 없이 바로 실행할 수 있습니다.

```bash
kpubdata fetch bok.base_rate -p start_date=202401 -p end_date=202403 --format table
```

### 4. 레코드 조회

```python
# 특정 데이터셋 가져오기 (예: 동네예보)
ds = client.dataset("datago.village_fcst")

# 데이터 조회 요청
result = ds.list(
    base_date="20250401",
    base_time="0500",
    nx="55",
    ny="127",
)

# 결과 출력
for item in result.items:
    print(item)
```

### 5. Raw API 비상구

정규화된 기능을 지원하지 않거나 원본 응답이 그대로 필요한 경우, 원본 API를 직접 호출할 수 있습니다.

```python
ds = client.dataset("datago.air_quality")

# 기관에서 정의한 원본 메서드 이름과 파라미터 사용
raw = ds.call_raw(
    "getCtprvnRltmMesureDnsty",
    sidoName="서울",
    numOfRows="5",
)
print(raw)
```

### 6. 한국은행 기준금리 조회 (BOK ECOS)

```python
ds = client.dataset("bok.base_rate")

# 기준금리 조회 (2024년)
# 주의: 날짜 형식은 YYYYMM (월 단위)입니다. YYYYMMDD로 보내면 에러가 발생합니다.
result = ds.list(
    start_date="202401",
    end_date="202412",
)

for item in result.items:
    print(f"{item['TIME']} — {item['DATA_VALUE']}%")
# 출력 예시:
# 202401 — 3.5%
# 202402 — 3.5%
# ...
# 202412 — 3.0%
```

### 7. 통계청 인구이동 조회 (KOSIS)

```python
ds = client.dataset("kosis.population_migration")

# 시도별 이동자수 조회 (2024년 1월)
# 주의: 날짜 형식은 YYYYMM (월 단위)입니다.
result = ds.list(
    start_date="202401",
    end_date="202401",
)

for item in result.items[:5]:
    print(f"{item['C1_NM']} -> {item['C2_NM']}: {item['DT']}명")
# 출력 예시:
# 전국 -> 전국: 596969명
# 전국 -> 서울특별시: 101416명
# ...
```

### 8. 지방재정365 세출결산 조회 (LOFIN)

```python
ds = client.dataset("lofin.expenditure_budget")

# 세출결산총괄 조회 (2024 회계연도)
result = ds.list(fyr="2024")

for item in result.items[:5]:
    print(f"{item['WDER_NM']} — {item['BUDGET_CRNTAM']}원")
# 출력 예시:
# 서울특별시 — 35000000000원
# 부산광역시 — 12000000000원
# ...
```

### 9. 지방행정인허가 조회 (Localdata)

```python
# 지방행정인허가 (Localdata) - 일반음식점
client = Client(provider_keys={"localdata": "YOUR_DATA_GO_KR_API_KEY"})
ds = client.dataset("localdata.general_restaurant")
result = ds.list(page_size=10)
for item in result.items:
    print(item["BPLC_NM"], item["ROAD_NM_ADDR"])
```

### 10. 소상공인 상가정보 조회 (Semas)

```python
client = Client(provider_keys={"semas": "YOUR_SEMAS_API_KEY"})
ds = client.dataset("semas.store_radius")
result = ds.list(cx="127.02758", cy="37.49794", radius="250", page_size=10)

for item in result.items:
    print(item["bizesNm"], item["rdnmAdr"])
```

### 11. 전체 페이지 자동 조회 (list_all)

대량의 데이터를 페이지 단위로 자동 순회하려면 `list_all()`을 사용합니다.

```python
ds = client.dataset("lofin.expenditure_budget")

# 모든 페이지를 자동으로 순회하며 RecordBatch를 반환
for batch in ds.list_all(fyr="2024"):
    print(f"이번 페이지: {len(batch.items)}건")
    for item in batch.items:
        print(item)
```

### 12. pandas DataFrame 변환

조회 결과를 pandas DataFrame으로 변환하여 분석할 수 있습니다.

```bash
pip install kpubdata[pandas]
```

```python
ds = client.dataset("bok.base_rate")
result = ds.list(start_date="202401", end_date="202412")

# pandas DataFrame으로 변환
df = result.to_pandas()
print(df.head())
```

## 지원 중인 공공데이터

현재 지원 현황의 상세 정보와 진행 예정 항목은 [SUPPORTED_DATA.md](./SUPPORTED_DATA.md)에서 확인할 수 있습니다.

| Provider | 데이터셋 수 | 대표 Dataset | 상태 |
|---|---|---|---|
| 공공데이터포털 (`datago`) | 50개 | 단기예보, 대기오염, 부동산 실거래가 등 | 지원 |
| 지방행정인허가 (`localdata`) | 195개 | 일반음식점, 휴게음식점, 의원 등 | 지원 |
| 소상공인 (`semas`) | 17개 | 반경/사각형/다각형 내 상가정보 등 | 지원 |
| 지방재정365 (`lofin`) | 6개 | 세출결산, 세입결산, 재정자립도 등 | 지원 |
| 서울 열린데이터광장 (`seoul`) | 7개 | 지하철 실시간 도착, 따릉이, 공원, 실시간 도시데이터 등 | 지원 |
| 교육부 나이스 (`neis`) | 2개 | 학교 급식식단·학교기본정보 | 지원 |
| 식품의약품안전처 (`fds`) | 1개 | 식품이력추적 관리품목 | 지원 |
| 국립국어원 (`korean`) | 1개 | 표준국어대사전 검색 | 지원 |
| 특허청 KIPRIS (`kipris`) | 1개 | 특허패밀리정보 검색 | 지원 |
| 한국은행 ECOS (`bok`) | 4개 | 기준금리, 통화량, 환율, 국고채 수익률 | 지원 |
| 한국거래소 (`krx`) | 3개 | 코스피 지수, 투자자별 순매수, 밸류에이션 | 지원 |
| 통계청 SGIS (`sgis`) | 3개 | 시도/시군구/읍면동 행정구역 경계 | 지원 |
| 국가법령정보 (`law`) | 3개 | 법령 검색, 조문 조회, 연혁 조회 | 지원 |
| 통계청 KOSIS (`kosis`) | 2개 | 인구이동, 광공업생산지수 | 지원 |

> 전체 데이터셋 목록, 검증 수준, 실API 최종 검증일 등 상세 정보는 [SUPPORTED_DATA.md](./SUPPORTED_DATA.md)를 참고하세요.

### 비상구 (Escape Hatches)

정규화된 데이터셋이 아닌, 미등록 endpoint를 즉시 호출할 수 있게 해주는 raw 비상구입니다. 정규화·페이지네이션·스키마 보장이 없으며 호출자가 원본 응답을 직접 처리해야 합니다.

| Provider | 비상구 키 | 용도 |
|---|---|---|
| 공공데이터포털 (`datago`) | `datago.generic` | 카탈로그에 없는 임의의 data.go.kr API를 `call_raw(operation, _base_url=..., **params)`로 호출 |

자세한 사용법은 [docs/providers/datago.md](./docs/providers/datago.md#generic-범용-엔드포인트)와 [SUPPORTED_DATA.md](./SUPPORTED_DATA.md#비상구--고급-기능-escape-hatches)를 참고하세요.

> **참고**: 데이터셋 게시(Publishing) 및 HuggingFace/Kaggle 업로드는 [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder)에서 관리합니다. kpubdata는 데이터 수집/정규화만 담당합니다.

## 문서 가이드 (Document Guide)

KPubData의 설계 철학과 사용 방법을 안내하는 문서 목록입니다.

### 핵심 설계
- [ARCHITECTURE.md](./ARCHITECTURE.md): 시스템 전체 구조와 구성 요소 간의 상호작용 설계
- [CANONICAL_MODEL.md](./CANONICAL_MODEL.md): 다양한 API 응답을 하나로 통합하는 표준 데이터 모델 정의
- [PROVIDER_ADAPTER_CONTRACT.md](./PROVIDER_ADAPTER_CONTRACT.md): 새로운 데이터 제공 기관(Provider) 추가를 위한 어댑터 구현 규약

### API & 검증
- [API_SPEC.md](./API_SPEC.md): 사용자가 직접 사용하는 파이썬 API 명세 및 사용법
- [VALIDATION.md](./VALIDATION.md): 아키텍처 설계의 타당성 검증 및 핵심 결정 사항

### 개발 가이드
- [AGENTS.md](./AGENTS.md): AI 에이전트와 함께 개발할 때 준수해야 할 규칙 및 가이드
- [CONTRIBUTING.md](./CONTRIBUTING.md): 프로젝트 기여 방법 및 개발 환경 설정 안내
- [PACKAGING.md](./PACKAGING.md): 패키징 구조 및 배포 전략

### 프로젝트 관리
- [PRD.md](./PRD.md): 제품 요구사항 정의 및 핵심 가치
- [ROADMAP.md](./ROADMAP.md): 단계별 기능 구현 및 출시 계획
- [SUPPORTED_DATA.md](./SUPPORTED_DATA.md): 지원 공공데이터 현황 및 진행 상태

### 상세 참고 자료
- [quickstart.md](./docs/quickstart.md): **처음 사용자를 위한 단계별 빠른 시작 가이드**
- [cli.md](./docs/cli.md): **CLI 설치 확인, 서브커맨드, 출력 형식, 종료 코드**
- [caching.md](./docs/caching.md): **디스크 기반 응답 캐시 활성화, TTL, 정리 방법**
- [logging.md](./docs/logging.md): **로깅 활성화 및 로거 이름 규칙**
- [product-family-architecture.md](./docs/product-family-architecture.md): **KPubData 제품군 전체 시스템 아키텍처** (3개 저장소 관계도)
- [architecture-diagrams.md](./docs/architecture-diagrams.md): 아키텍처 시각화 다이어그램
- [datago-api-reference.md](./docs/datago-api-reference.md): 공공데이터포털(data.go.kr) API 연동 참고 자료
- [ADRs](./docs/adrs/): 주요 기술적 결정 이력 (Architecture Decision Records)

---

## 관련 문서

### KPubData Product Family
| 패키지 | 역할 | 설명 |
| :--- | :--- | :--- |
| [kpubdata](https://github.com/yeongseon/kpubdata) | **Access** | 한국 공공데이터 접근 + 파싱 + 정규화 코어 SDK |
| [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder) | **Generation** | 데이터셋 조립 + 검증 + 내보내기 파이프라인 |
| [kpubdata-studio](https://github.com/yeongseon/kpubdata-studio) | **Experience** | 빌드 작성 및 실행을 위한 시각적 인터페이스 |

## 로드맵

상세 로드맵 및 버전별 계획은 [ROADMAP.md](./ROADMAP.md)를 참고하세요.

---

## In English

Korean is the primary language of this README. This section is the minimum needed
to decide whether to keep reading — not a full translation. See
[ADR 0003](docs/adrs/0003-language-policy.md) for why it is arranged this way.

### What this is

A Python access layer for **Korean public data APIs**. Each government agency
publishes its own API with its own authentication, response envelope and
pagination scheme. KPubData absorbs those differences behind one interface:

```python
from kpubdata import Client

client = Client.from_env()                      # reads KPUBDATA_<PROVIDER>_API_KEY
batch = client.dataset("datago.apt_trade").list(
    filters={"LAWD_CD": "11110", "DEAL_YMD": "202601"}
)
```

14 providers, 23 machine-verified specs and about 150 catalogued datasets.

### What it deliberately does not do

- **It does not store or redistribute data.** You call the APIs with your own key.
  There is no hosted copy of anything.
- **It does not hide provider differences that carry meaning.** Where an agency's
  vocabulary or constraint is real, it stays visible rather than being flattened
  into a false common shape.
- **It is not a data warehouse.** Collecting, transforming and versioning data for
  SQL analysis is [kpubdata-builder](https://github.com/yeongseon/kpubdata-builder).

### You will need a Korean API key

Every dataset here is behind a Korean government API, and most require 활용신청 —
a per-service application on [data.go.kr](https://www.data.go.kr). Approval is
usually automatic within minutes, but **it cannot be skipped**, and a valid key
still returns HTTP 403 for a service you have not applied for.

`kpubdata probe` classifies what your key can reach and lists what needs applying
for, grouped per service.

Some providers also restrict non-Korean source IPs (result code 32,
`UNREGISTERED_IP`). We have not confirmed the exact policy —
see [#529](https://github.com/yeongseon/kpubdata/issues/529).

### Getting started

```bash
pip install kpubdata
export KPUBDATA_DATAGO_API_KEY=...
python -c "import kpubdata; print(kpubdata.__version__)"
```

Then read the Korean [빠른 시작](#빠른-시작) section above, or
[docs/quickstart.md](docs/quickstart.md).

### Contributing

Issues and pull requests are welcome in **Korean or English**. Titles are in
English; bodies may be either. If writing an English title is a barrier, open it
in Korean and say so — we will sort it out during triage.
[CONTRIBUTING.md](CONTRIBUTING.md) has the details.
