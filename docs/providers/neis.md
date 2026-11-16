# 교육부 나이스 (neis)

## 개요

교육부 교육행정정보시스템(NEIS)의 학교 급식식단 및 학교 기본정보를 조회합니다. KPubData는 공공데이터포털을 통해 나이스 Open API를 호출합니다.

- KPubData Provider 이름: `neis`
- API 기반 URL: https://open.neis.go.kr/hub/

## API 키 발급 방법

NEIS Open API 인증키는 **나이스 교육정보 개방포털**에서 발급받습니다. 공공데이터포털(data.go.kr)의 공통 서비스 키가 자동으로 사용되는 것은 아닙니다.

1. [나이스 Open API 이용 안내](https://open.neis.go.kr/portal/guide/apiGuidePage.do)에서 인증키 발급 절차를 확인합니다.
2. 사용할 서비스의 이용 조건과 승인 여부를 확인합니다.
3. 발급받은 NEIS 인증키를 다음 환경변수에 설정합니다.

```bash
export KPUBDATA_NEIS_API_KEY="your-neis-key"
```

SDK는 `require_provider_key("neis")`를 호출하므로 `KPUBDATA_DATAGO_API_KEY`만 설정해서는 NEIS 인증키를 대신할 수 없습니다. 인증키가 존재한다는 사실과 서비스 호출 권한이 승인됐다는 사실은 별개입니다.

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
