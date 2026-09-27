# 지방행정인허가 (data.go.kr) — `localdata`

> README 에서 옮겨 왔다(`#546`). 발급 절차는 기관 화면이 바뀌면 낡으므로, README 가
> 아니라 여기에 둔다 — README 는 프로젝트를 평가하는 문서이고 이것은 참조 문서다.

## API 키 발급

- **가입 URL**: [https://www.data.go.kr](https://www.data.go.kr)
- **절차**: 회원가입 → 지방행정인허가 Open API(일반음식점/휴게음식점) 활용신청 → 승인 후 인증키 확인
- **환경 변수**: `KPUBDATA_LOCALDATA_API_KEY`

## 환경 변수

```bash
export KPUBDATA_LOCALDATA_API_KEY="발급받은키"
```

## 지원 데이터셋

[SUPPORTED_DATA.md](https://github.com/yeongseon/kpubdata/blob/main/SUPPORTED_DATA.md) 의 `localdata` 행을 본다 — 상태·검증
수준·활용신청 필요 여부가 거기 있다.

## 관련

- [빠른 시작](../quickstart.md)
- [데이터셋 예제](../dataset-examples.md)
