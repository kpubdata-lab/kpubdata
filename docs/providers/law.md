# 국가법령정보센터 (law)

## 개요

법제처에서 운영하는 국가법령정보센터의 법령 검색, 본문 조회, 연혁 조회 API입니다. KPubData는 법령 검색과 조문 조회를 지원합니다.

- KPubData Provider 이름: `law`
- API 기반 URL: http://www.law.go.kr/

## API 키 발급 방법

1. [국가법령정보센터 Open API](https://www.law.go.kr/openApi/main.do)에 접속합니다.
2. 회원가입 후 로그인합니다.
3. "인증키 신청" 메뉴에서 Open API 인증키를 발급받습니다.
4. 환경변수에 설정합니다.

```bash
export KPUBDATA_LAW_API_KEY="your-key"
```

## 지원 데이터셋

### law_search (법령 검색)

법령명으로 현행 법령을 검색합니다.

- 검색어 기반 조회 (`query`)

### law_detail (법령 본문 조회)

특정 법령의 조문 본문을 XML로 조회합니다.

- 법령 ID(`law_id`)로 조회

### ordin_search (자치법규 검색)

지방자치단체의 자치법규를 검색합니다.

```python
ds = client.dataset("law.law_search")
result = ds.list(query="개인정보보호법")
```
