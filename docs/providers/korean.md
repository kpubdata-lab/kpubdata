# 국립국어원 표준국어대사전 (korean)

## 개요

국립국어원에서 운영하는 표준국어대사전의 어휘를 검색하는 Open API입니다. KPubData는 어휘 검색 및 다의어 전개를 지원합니다.

- KPubData Provider 이름: `korean`
- API 기반 URL: https://stdict.korean.go.kr/api/

## API 키 발급 방법

1. [표준국어대사전 Open API](https://stdict.korean.go.kr/openapi/openapi/search.do)에 접속합니다.
2. 회원가입 후 로그인합니다.
3. "API 키 신청" 메뉴에서 키를 발급받습니다.
4. 환경변수에 설정합니다.

```bash
export KPUBDATA_KOREAN_API_KEY="your-key"
```

## 지원 데이터셋

### dict_search (표준국어대사전 검색)

표준국어대사전에서 어휘를 검색합니다.

- 검색어로 시작하는 어휘 조회 (`q` 파라미터)
- 다의어는 sense 단위로 전개됨 (예: "나무" 2 senses + "나무꾼" 1 sense = 3 records)
- 페이지네이션: Page 기반 (`start`, `num`)

```python
ds = client.dataset("korean.dict_search")
result = ds.list(q="나무", num=10)

for item in result.items:
    print(item["word"], item["sense"]["definition"])
```
