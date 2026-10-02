# 데이터셋 검색하기

사용 가능한 데이터셋을 찾고, 원하는 데이터를 빠르게 발견하는 방법을 안내합니다.

## 왜 검색이 필요한가요?

KPubData는 다수의 공공데이터 기관을 지원합니다.
최신 지원 목록은 [SUPPORTED_DATA.md](https://github.com/kpubdata-lab/kpubdata/blob/main/SUPPORTED_DATA.md)를 참고하세요.
정확한 데이터셋 ID를 외울 필요 없이, 키워드로 검색하면 됩니다.

## 키워드 검색

`search()`는 데이터셋의 이름, 설명, 태그, ID를 모두 검색합니다:

```python
results = client.datasets.search("예보")
for ds in results:
    print(ds.id, ds.name, ds.tags)
```

예상 출력:

```
datago.village_fcst 동네예보 ('weather', 'forecast', '기상')
datago.ultra_srt_ncst 초단기실황 ('weather', 'realtime', '기상')
```

## 정밀도 조절 (threshold)

검색 결과가 너무 많으면 `threshold`를 올려 엄격하게, 적으면 내려 느슨하게 조절합니다:

```python
# 엄격한 검색 (정확한 일치에 가까운 결과만)
strict = client.datasets.search("기준금리", threshold=0.8)

# 느슨한 검색 (오타 허용)
loose = client.datasets.search("기준금리", threshold=0.3)
```

기본값은 `0.5`입니다.

## 검색 결과 활용

검색으로 찾은 `DatasetRef`는 다음 정보를 포함합니다:

| 속성 | 설명 |
|---|---|
| `id` | 정규화된 데이터셋 ID (예: `bok.base_rate`) |
| `name` | 데이터셋 이름 |
| `description` | 설명 (없을 수 있음) |
| `tags` | 분류 태그 |
| `source_url` | 원본 API 문서 링크 |
| `operations` | 지원 연산 (list, raw 등) |

검색으로 ID를 알았으면 바로 데이터를 조회할 수 있습니다:

```python
ds = client.dataset("datago.village_fcst")
result = ds.list(base_date="20250401", base_time="0500", nx="55", ny="127")
```

## 다음 단계

- [시작하기](./getting-started.md) — 처음부터 데이터 조회까지
- [Raw API 사용하기](./raw-access.md) — 정규화되지 않은 원본 호출
