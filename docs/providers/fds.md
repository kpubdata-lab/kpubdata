# 식품의약품안전처 (fds)

## 개요

식품이력추적제도는 식품의 원료부터 생산·유통·판매까지 전 과정을 추적할 수 있는 시스템입니다. KPubData는 식약처 공공데이터포털 API를 통해 관리품목 등록정보를 조회합니다.

- KPubData Provider 이름: `fds`
- API 기반 URL: https://openapi.foodsafetykorea.go.kr/api/

## API 키 발급 방법

식약처 API는 data.go.kr과 동일한 서비스 키를 사용합니다.

1. [공공데이터포털](https://www.data.go.kr)에 접속하여 회원가입합니다.
2. "식품이력추적 관리품목 등록정보" Open API를 검색합니다.
3. 상세 페이지에서 "활용신청"을 클릭합니다.
4. 마이페이지에서 발급된 인증키를 확인합니다.
5. 환경변수에 설정합니다.

```bash
export KPUBDATA_DATAGO_API_KEY="your-service-key"
```

> `fds`는 `datago` 키를 공유합니다. 별도 키가 필요하지 않습니다.

## 지원 데이터셋

### traceability_item (식품이력추적 관리품목 등록정보)

식품이력추적제도에 등록된 관리품목 정보를 조회합니다.

- 품목군, 품목명, 업체명 등으로 검색 가능
- 페이지네이션: Page/Row 방식

```python
ds = client.dataset("fds.traceability_item")
result = ds.list(page_size=10)
```
