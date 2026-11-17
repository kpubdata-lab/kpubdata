# Raw API 사용하기

정규화된 인터페이스 대신, 기관의 원본 API를 직접 호출하는 방법을 안내합니다.

## 왜 Raw 호출이 필요한가요?

KPubData SDK의 `list()`, `schema()` 등은 기관마다 다른 파라미터를 표준화합니다.
하지만 때로는 원본 API의 특수한 파라미터나 operation이 필요할 수 있습니다.

`call_raw()`는 이런 경우를 위한 비상구다.

## 기본 사용법

```python
from kpubdata import Client

client = Client.from_env()
ds = client.dataset("datago.air_quality")

raw = ds.call_raw(
    "getCtprvnRltmMesureDnsty",
    sidoName="서울",
    numOfRows="5",
)
print(raw)
```

첫 번째 인자는 기관에서 정의한 operation 이름이고,
나머지는 원본 API의 파라미터를 그대로 전달합니다.

## 정규화 vs Raw 비교

| | `list()` | `call_raw()` |
|---|---|---|
| 파라미터 | KPubData SDK 표준 | 기관 원본 그대로 |
| 반환값 | `RecordBatch` | 원본 응답 (dict/list) |
| 페이지네이션 | 자동 (`list_all()`) | 직접 처리 |
| 스키마 보장 | 있음 | 없음 |

## 범용 엔드포인트 (datago)

카탈로그에 등록되지 않은 data.go.kr API도 `datago.generic`으로 호출 가능합니다:

```python
ds = client.dataset("datago.generic")
raw = ds.call_raw(
    "getUltraSrtFcst",
    _base_url="http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0",
    base_date="20250401",
    base_time="0600",
    nx="55",
    ny="127",
)
```

## 언제 Raw를 쓰나요?

- KPubData SDK가 아직 정규화하지 않은 operation을 호출할 때
- 원본 응답의 특정 필드를 확인해야 할 때
- 디버깅 시 기관 API의 실제 응답을 보고 싶을 때

일반적인 데이터 조회에는 `list()`를 권장합니다.

## 다음 단계

- [시작하기](./getting-started.md) — 처음부터 데이터 조회까지
- [데이터셋 검색하기](./discovery.md) — 원하는 데이터를 찾는 방법
