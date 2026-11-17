# 시작하기

이 문서는 KPubData SDK를 처음 사용하는 개발자를 위한 단계별 안내입니다.

## 왜 이 가이드가 필요한가요?

한국 공공데이터 API는 기관마다 인증 방식, 파라미터, 응답 형식이 모두 다릅니다.
KPubData SDK는 이 차이를 하나의 인터페이스로 통합해, 데이터셋 이름만 알면 바로 조회할 수 있게 합니다.

## 준비물

- Python 3.11 이상
- API 키 (아래 참고)

## 1단계: 설치

```bash
pip install kpubdata
```

## 2단계: API 키 설정

가장 간단한 한국은행(BOK) 키부터 시작합니다.

1. https://ecos.bok.or.kr/api/ 에서 인증키 신청
2. 환경 변수 설정:

```bash
export KPUBDATA_BOK_API_KEY="발급받은_키"
```

## 3단계: 클라이언트 생성

```python
from kpubdata import Client

client = Client.from_env()
```

또는 키를 직접 전달:

```python
client = Client(provider_keys={"bok": "발급받은_키"})
```

## 4단계: 데이터 조회

```python
ds = client.dataset("bok.base_rate")
result = ds.list(start_date="202401", end_date="202406")

for item in result.items:
    print(f"{item['TIME']} — {item['DATA_VALUE']}%")
```

예상 출력:

```
202401 — 3.5%
202402 — 3.5%
202403 — 3.5%
202404 — 3.5%
202405 — 3.5%
202406 — 3.5%
```

## 5단계: 스키마 확인

데이터셋의 필드 구조를 확인할 수 있습니다:

```python
schema = ds.schema()
if schema:
    for field in schema.fields:
        print(f"{field.name}: {field.type}")
```

## 다음 단계

- [데이터셋 검색하기](./discovery.md) — 원하는 데이터를 찾는 방법
- [Raw API 사용하기](./raw-access.md) — 원본 API 직접 호출
- [CLI 사용법](../cli.md) — 터미널에서 바로 조회
