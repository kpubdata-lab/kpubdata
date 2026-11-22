# 통계청 통계지리정보서비스 (sgis.kostat.go.kr) — `sgis`

> README 에서 옮겨 왔다(`#546`). 발급 절차는 기관 화면이 바뀌면 낡으므로, README 가
> 아니라 여기에 둔다 — README 는 프로젝트를 평가하는 문서이고 이것은 참조 문서다.

## API 키 발급

- **가입 URL**: [https://sgis.kostat.go.kr/developer/html/main.html](https://sgis.kostat.go.kr/developer/html/main.html)
- **절차**: 회원가입 → 개발지원센터에서 서비스 ID/Secret 발급 → 인증 API로 accessToken 교환
- **인증 방식**: `consumer_key` + `consumer_secret` 2단계
- **환경 변수**:
  - `KPUBDATA_SGIS_API_KEY` (`consumer_key`)
  - `KPUBDATA_SGIS_CONSUMER_SECRET` (`consumer_secret`)
- **대안 입력**: 코드에서 `provider_keys["sgis"]`에 `"consumer_key:consumer_secret"` 형태를 직접 전달 가능

## 환경 변수

```bash
export KPUBDATA_SGIS_API_KEY="발급받은-consumer-key"
export KPUBDATA_SGIS_CONSUMER_SECRET="발급받은-consumer-secret"
```

## Access token expiry

SGIS documents `accessTimeout` as a Unix epoch in **seconds**, but its
[published authentication example](https://sgis.kostat.go.kr/developer/upload/doc/DataAPI-definition.pdf)
contains the 13-digit value `1663231271880`, representing **milliseconds**.
To accommodate this documented discrepancy, the SDK accepts positive integer
seconds and converts values of at least `10^12` from milliseconds to seconds.
Invalid or out-of-range timestamps raise a provider response error rather than
a raw Python datetime exception.

Cached access tokens are refreshed when **60 seconds or less** remain before
expiry. Very short-lived tokens may require a new token on each request.
This parsing behavior is covered by offline tests only; it does **not**
constitute a successful authenticated live SGIS verification.

## 경계(boundary) 항목의 `geometry`

경계 데이터셋의 각 항목은 속성 필드와 `feature_type` 키를 가지며, 응답에 geometry 가 있으면 중첩된 GeoJSON `geometry` 객체(`type`, `coordinates`)도 가진다.
다른 필드처럼 평평한 값이 아니므로 표 형태(DataFrame)로 바꾸면 한 칸에 딕셔너리가 들어간다.

## 지원 데이터셋

[SUPPORTED_DATA.md](https://github.com/kpubdata-lab/kpubdata/blob/main/SUPPORTED_DATA.md) 의 `sgis` 행을 본다 — 상태·검증
수준·활용신청 필요 여부가 거기 있다.

## 페이지네이션

SGIS 는 요청한 지역의 경계를 한 응답에 모두 돌려주므로 데이터셋은 페이지네이션을 선언하지 않습니다(`query_support.pagination` = `none`). `page` 가 1 이 아니면 `InvalidRequestError` 입니다. 예전에는 1페이지 행을 다시 돌려줬습니다. `page_size` 는 받아들이지만 효과가 없습니다.

## 관련

- [빠른 시작](../quickstart.md)
- [데이터셋 예제](../dataset-examples.md)
