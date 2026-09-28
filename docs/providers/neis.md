# 교육부 나이스 (neis)

## 개요

교육부 교육행정정보시스템(NEIS)의 학교 급식식단 및 학교 기본정보를 조회합니다. KPubData는 공공데이터포털을 통해 나이스 Open API를 호출합니다.

- KPubData Provider 이름: `neis`
- API 기반 URL: https://open.neis.go.kr/hub/

## API 키 발급 방법

나이스 API는 data.go.kr과 동일한 서비스 키를 사용합니다.

1. [공공데이터포털](https://www.data.go.kr)에 접속하여 회원가입합니다.
2. "교육부_급식식단정보" 또는 "교육부_학교기본정보" Open API를 검색합니다.
3. "활용신청" 후 마이페이지에서 인증키를 확인합니다.
4. 환경변수에 설정합니다.

```bash
export KPUBDATA_DATAGO_API_KEY="your-service-key"
```

> `neis`는 `datago` 키를 공유합니다. 별도 키가 필요하지 않습니다.

## 지원 데이터셋

### meal_diet (급식식단정보)

학교의 일별 급식 식단을 조회합니다.

- 지역 교육청 코드(`atpt_code`)와 학교 코드(`school_code`)로 조회
- 급식 코드: 1=조식, 2=중식, 3=석식

### school_info (학교기본정보)

학교의 기본 정보(학교명, 주소, 연락처 등)를 조회합니다.

```python
ds = client.dataset("neis.meal_diet")
result = ds.list(atpt_code="B10", school_code="7021105")
```
