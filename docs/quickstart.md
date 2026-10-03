# 빠른 시작 가이드: 처음부터 끝까지

이 문서를 따라하면 KPubData를 설치하고, API 키를 설정하고, 실제 공공데이터를 조회하는 것까지 한 번에 완료할 수 있습니다.

## 필요한 것
- Python 3.10 이상 (확인: `python --version`)
- 인터넷 연결
- 공공데이터 API 키 (아래에서 발급 방법 안내)

## 1단계: Python 설치 확인
```bash
python --version
# Python 3.10.x 이상이면 정상
# 설치 안 되어 있다면: https://www.python.org/downloads/
```

## 2단계: KPubData 설치
```bash
pip install kpubdata
```
설치 확인:
```bash
python -c "import kpubdata; print('설치 성공!')"
# 설치 성공!
```

## 3단계: API 키 발급
가장 쉬운 한국은행(BOK) API부터 시작합니다.

> BOK 로 시작하는 이유는 **활용신청이 없기 때문**입니다. data.go.kr 계열(datago 등)은
> 회원가입 뒤 API 마다 활용신청을 하고 승인을 기다려야 해서, 첫 실행까지 시간이 걸립니다.
> README·AGENTS 의 예제와 spec 파이프라인은 datago 기준이므로, 여기서 감을 잡은 뒤
> 그쪽으로 넘어가면 됩니다.

1. https://ecos.bok.or.kr/api/ 접속
2. "인증키 신청" 클릭
3. 본인인증 후 회원가입
4. 마이페이지에서 발급된 키 확인 (예: `ABCD1234EFGH5678`)

## 4단계: API 키 설정

> 키는 해당 provider 의 공식 호스트로만 전송된다. 사내 프록시를 거쳐야 하는
> 배포라면 [Provider 키가 전송될 수 있는 호스트](host-allowlist.md)를 먼저 읽는다.
### macOS / Linux
```bash
export KPUBDATA_BOK_API_KEY="여기에-발급받은-키-붙여넣기"
```

### Windows (PowerShell)
```powershell
$env:KPUBDATA_BOK_API_KEY="여기에-발급받은-키-붙여넣기"
```

### Windows (명령 프롬프트)
```cmd
set KPUBDATA_BOK_API_KEY=여기에-발급받은-키-붙여넣기
```

설정 확인:
```bash
python -c "import os; print(os.environ.get('KPUBDATA_BOK_API_KEY', '설정 안됨'))"
# ABCD1234EFGH5678  ← 이런 식으로 키가 출력되면 OK
```

## 5단계: 첫 번째 데이터 조회
Python 파일을 하나 만들겠습니다.

```bash
# 작업 폴더 만들기
mkdir my-first-kpubdata
cd my-first-kpubdata
```

`first_query.py` 파일을 만들고 아래 내용을 붙여넣으세요:

```python
from kpubdata import Client

# 1. 클라이언트 생성 (환경변수에서 API 키 자동 로드)
client = Client.from_env()

# 2. 한국은행 기준금리 데이터셋 선택
ds = client.dataset("bok.base_rate")

# 3. 2024년 월별 기준금리 조회
result = ds.list(start_date="202401", end_date="202412")

# 4. 결과 출력
print(f"총 {len(result.items)}건의 데이터를 가져왔습니다.\n")

print("| 기간   | 기준금리 |")
print("|--------|----------|")
for item in result.items:
    print(f"| {item['TIME']} | {item['DATA_VALUE']}%   |")
```

실행:
```bash
python first_query.py
```

예상 출력:
```
총 12건의 데이터를 가져왔습니다.

| 기간   | 기준금리 |
|--------|----------|
| 202401 | 3.5%   |
| 202402 | 3.5%   |
| 202403 | 3.5%   |
| ...    |        |
| 202412 | 3.0%   |
```

## 6단계: 에러가 났을 때

### "API 키가 설정되지 않았습니다"
```
kpubdata.exceptions.ConfigError: Missing provider API key for 'bok'
```
→ 4단계의 환경 변수 설정을 다시 확인하세요. 터미널을 새로 열었다면 export 명령을 다시 실행해야 합니다.

### "날짜 형식 오류"
```
ProviderResponseError: BOK ECOS returned error
```
→ 날짜를 `"20240101"` 대신 `"202401"` (YYYYMM) 형식으로 입력했는지 확인하세요.

### "data.go.kr에서 403이 나옵니다"
```
AuthError: data.go.kr returned 403...
```
→ data.go.kr은 공통 인증키만으로는 부족하고 **API별 활용신청**이 필요합니다. 사용하려는 API 상세 페이지에서 "활용신청"을 눌렀는지 확인하세요. 대부분 1~5분 안에 자동 승인되지만 일부 API는 더 오래 걸릴 수 있습니다.

## 7단계: 다른 데이터도 조회해보기

### 사용 가능한 전체 데이터셋 목록 보기

```python
from kpubdata import Client

client = Client.from_env()

for ds in client.datasets.list():
    print(f"{ds.id} — {ds.name}")
```

출력 예시:
```
datago.village_fcst — 동네예보 조회서비스 (Village Forecast)
datago.ultra_srt_ncst — 초단기실황 조회서비스 (Ultra Short-term Nowcast)
datago.air_quality — 대기오염정보 조회서비스 (Air Quality)
datago.bus_arrival — 경기도 버스도착정보 조회서비스 (Bus Arrival)
datago.hospital_info — 병원정보서비스 (Hospital Information)
datago.apt_trade — 아파트매매 실거래자료 (Apartment Trade)
bok.base_rate — 한국은행 기준금리 (BOK Base Rate)
kosis.population_migration — 시도별 이동자수 (Population Migration)
```

### 다른 Provider 사용하려면
- 공공데이터포털(datago): [datago API 키 발급 가이드](./providers/datago.md)
- 통계청 KOSIS: [KOSIS API 키 발급 가이드](./providers/kosis.md)

> 참고: `datago`는 인증키 발급 후에도 **데이터셋별 활용신청**이 필요합니다. 활용신청 전에는 403이 발생할 수 있습니다.

## 8단계: 전체 페이지 자동 조회

데이터가 많을 때 `list_all()`을 사용하면 모든 페이지를 자동으로 순회합니다.

```python
ds = client.dataset("bok.base_rate")

for batch in ds.list_all(start_date="202401", end_date="202412"):
    print(f"{len(batch.items)}건 조회")
```

## 9단계: pandas로 데이터 분석하기

```bash
pip install kpubdata[pandas]
```

```python
result = ds.list(start_date="202401", end_date="202412")
df = result.to_pandas()
print(df)
```

## 다음 단계
- 각 Provider별 상세 사용법: [공공데이터포털](providers/datago.md) · [서울](providers/seoul.md) · [KOSIS](providers/kosis.md) · [BOK](providers/bok.md)
- 프로젝트에 기여하기: [CONTRIBUTING.md](contributing.md)
- 전체 API 명세: [API_SPEC.md](https://github.com/kpubdata-lab/kpubdata/blob/main/API_SPEC.md)
