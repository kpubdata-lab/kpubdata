# 지방재정365 (lofin365.go.kr) — `lofin`

> README 에서 옮겨 왔다(`#546`). 발급 절차는 기관 화면이 바뀌면 낡으므로, README 가
> 아니라 여기에 둔다 — README 는 프로젝트를 평가하는 문서이고 이것은 참조 문서다.

## API 키 발급

- **가입 URL**: [https://www.lofin365.go.kr](https://www.lofin365.go.kr)
- **절차**: 회원가입 → 로그인 → 마이페이지 → [인증키발급](https://www.lofin365.go.kr/portal/LF9220200.do) → "인증키 신청" 클릭 → 발급 완료
- **참고**: 지방재정365는 지방자치단체 재정 데이터를 제공합니다. 중앙정부 재정 데이터(열린재정)와는 별도 시스템입니다.
- **SSL 참고**: 이 서버는 한때 TLSv1.2와 AES256-SHA256만 제시했기 때문에, lofin
  요청에만 cipher 하한을 낮춘 컨텍스트(`DEFAULT:@SECLEVEL=1`)를 씁니다.
  **인증서 검증은 켜져 있습니다.** 다만 이 컨텍스트는 `ssl.create_default_context()`
  기반이라 시스템 CA 저장소를 쓰므로, certifi에만 CA가 있는 환경에서는 lofin만
  실패할 수 있습니다 — 그때는 시스템 CA를 설치하십시오.
- **환경 변수**: `KPUBDATA_LOFIN_API_KEY`

## 환경 변수

```bash
export KPUBDATA_LOFIN_API_KEY="발급받은키"
```

> **현재 구현 주의:** 이 문서의 LOFIN 발급 안내와 달리 SDK의 `LofinAdapter._require_api_key()`는 현재 `datago` 키를 조회합니다. 따라서 위 환경변수만 설정하면 지금 버전의 해당 어댑터가 키를 사용한다고 보장할 수 없습니다. 이 불일치는 [#986](https://github.com/kpubdata-lab/kpubdata/issues/986)에서 발급기관과 실제 인증 방식을 검증한 뒤 수정할 예정입니다. 다른 기관의 인증키를 임의로 LOFIN 서버에 전송하거나 실API 성공을 가정하지 마세요.

## 지원 데이터셋

[SUPPORTED_DATA.md](https://github.com/kpubdata-lab/kpubdata/blob/main/SUPPORTED_DATA.md) 의 `lofin` 행을 본다 — 상태·검증
수준·활용신청 필요 여부가 거기 있다.

## 관련

- [빠른 시작](../quickstart.md)
- [데이터셋 예제](../dataset-examples.md)
