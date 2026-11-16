# 식품의약품안전처 (fds)

## 개요

식품이력추적제도는 식품의 원료부터 생산·유통·판매까지 전 과정을 추적할 수 있는 시스템입니다. KPubData는 식약처 공공데이터포털 API를 통해 관리품목 등록정보를 조회합니다.

- KPubData Provider 이름: `fds`
- API 기반 URL: https://openapi.foodsafetykorea.go.kr/api/

## API 키 발급 방법

식품안전나라 Open API 인증키는 **식품안전나라 Open API 서비스**에서 발급받습니다. 공공데이터포털(data.go.kr) 서비스 키와 자동 공유된다고 안내하면 안 됩니다.

1. [식품안전나라 Open API 이용 안내](https://www.foodsafetykorea.go.kr/api/howToUseApi.do)에서 발급·신청 절차를 확인합니다.
2. 조회할 서비스의 이용 허용 범위를 확인합니다.
3. 발급받은 인증키를 다음 환경변수에 설정합니다.

```bash
export KPUBDATA_FDS_API_KEY="your-foodsafety-key"
```

SDK는 `require_provider_key("fds")`를 사용합니다. 이 API는 요청 URL 경로에 인증키가 포함될 수 있으므로 실제 통신이 HTTPS인지 확인하고, 요청 URL과 원본 응답을 로그에 남기지 마세요. 인증키 존재만으로 실API 검증 완료를 주장하지 않습니다.

## 지원 데이터셋

### traceability_item (식품이력추적 관리품목 등록정보)

식품이력추적제도에 등록된 관리품목 정보를 조회합니다.

- 품목군, 품목명, 업체명 등으로 검색 가능
- 페이지네이션: Page/Row 방식

```python
ds = client.dataset("fds.traceability_item")
result = ds.list(page_size=10)
```
