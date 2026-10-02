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
export KPUBDATA_SGIS_API_KEY="발급받은키"
```

## 지원 데이터셋

[SUPPORTED_DATA.md](https://github.com/kpubdata-lab/kpubdata/blob/main/SUPPORTED_DATA.md) 의 `sgis` 행을 본다 — 상태·검증
수준·활용신청 필요 여부가 거기 있다.

## 관련

- [빠른 시작](../quickstart.md)
- [데이터셋 예제](../dataset-examples.md)
