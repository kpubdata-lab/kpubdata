# KPubData

**한국 공공데이터 접근 프레임워크**

KPubData는 한국 공공데이터(data.go.kr 등)의 파편화된 API를 하나의 일관된 인터페이스로 통합하는 Python 프레임워크입니다.

## 특징

- 🏛️ **다기관 통합** — 공공데이터포털, 한국은행, 통계청, 서울시 등 다수 기관 지원 (상세: [SUPPORTED_DATA.md](https://github.com/kpubdata-lab/kpubdata/blob/main/SUPPORTED_DATA.md))
- 🔌 **방언(Dialect) 아키텍처** — 핵심은 작고 안정적으로, 기관별 차이는 어댑터가 처리
- 🐍 **파이썬다운 API** — `snake_case`, 타입 힌트, 직관적 메서드명
- 🚪 **원본(Raw) 비상구** — 표준화된 접근과 원본 API 직접 호출을 모두 지원
- 📊 **pandas 통합** — 조회 결과를 DataFrame으로 즉시 변환

## 설치

```bash
pip install kpubdata
```

## 빠른 예제

```python
from kpubdata import Client

client = Client.from_env()

# 데이터셋 탐색
for ds in client.datasets.search("예보"):
    print(ds.id, ds.name)

# 데이터 조회
ds = client.dataset("datago.village_fcst")
result = ds.list(base_date="20250401", base_time="0500", nx="55", ny="127")

for item in result.items:
    print(item)
```

## 다음 단계

- [빠른 시작 가이드](quickstart.md) — 설치부터 첫 조회까지
- [CLI 사용법](cli.md) — 터미널에서 바로 사용하기
- [예제 모음(Cookbook)](cookbook/getting-started.md) — 실전 예제 모음
