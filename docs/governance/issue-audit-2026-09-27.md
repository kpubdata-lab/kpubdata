# Open Issue 전수 감사 — 2026-09-27

GOV-04. [POLICY.md](./POLICY.md) 11·12절에 따라 세 저장소의 Open Issue 28건을
전부 분류했다. 기준 시점의 main 은 kpubdata `3b2e231` 계열이다.

분류는 KEEP / MERGE / CLOSE / SPLIT / DECISION / RESEARCH / BLOCKED / EPIC 중
하나다. Priority 는 **후보**다 — 8절대로 High 승격은 사람만 하므로, 아래
표의 High 는 제안이고 확정이 아니다(14절).

## 요약

| 분류 | 건수 |
|---|---|
| KEEP | 8 |
| **DECISION** | **9** |
| MERGE | 4 |
| BLOCKED | 3 |
| EPIC | 3 |
| SPLIT | 1 |
| CLOSE | 0 |
| **합계** | **28** |

Open Issue 중 **9건이 DECISION** 이다 — 코드 작업 전에 사람의 결정이 필요하고,
그 결정이 없는 동안 에이전트가 진행하면 되돌리기 어려운 방향으로 굳는다.
이것이 현재 가장 큰 병목이다.

> 이 표는 아래 행에서 기계적으로 재집계한 것이다. 처음 적은 요약은 7행 중 5행이
> 틀렸고(KEEP 9, DECISION 8, MERGE 3, BLOCKED 4, CLOSE 1), **합계만 우연히 28로
> 맞아서 드러나지 않았다.** 존재하지 않는 CLOSE 1건이 있고 SPLIT 1건이 빠져
> 있었다. 합계가 맞는다고 내역이 맞는 것은 아니다.

---

## kpubdata (19건)

| Issue | 분류 | Priority 후보 | Epic | Required Verification | Action |
|---|---|---|---|---|---|
| #461 formatted numeric 캐스팅 정책 | **DECISION** | High | EPIC-A | V2+V3, 영향 데이터셋 V4 | TRUST-03. `"1,200"` 정규화 여부는 데이터 의미를 바꾸는 결정이라 사람이 정한다 |
| #481 페이지 단위 캐스팅 타입 혼재 | **DECISION** | High | EPIC-A | V2+V3 | #461 과 같은 결정의 다른 면. 본문의 (a)/(b)/(c) 중 선택 필요. **#461 과 한 번에 결정한다** |
| #498 검증 상태 표기 불일치 | **DECISION** | High | EPIC-A | V2 | TRUST-04. 상태 축(maturity/evidence/health/lifecycle) 확정이 선행 |
| #464 Drift → Dataset Status 전이 규칙 | **MERGE** → #498 | — | EPIC-A | — | #498 의 상태 모델이 정해지기 전에는 전이 규칙을 따로 설계할 수 없다 |
| #479 RecordBatch.meta provenance | KEEP | Medium | EPIC-A | V2 | 마스킹 계약(2번 논점)만 사람이 확인하면 나머지는 진행 가능 |
| #500 문서 정리 | KEEP | Medium | EPIC-F | V0 | #502 에서 일부 해소. 잔여 범위 재확인 후 진행 |
| #463 Production-grade Dataset 정의 통합 | KEEP | Medium | EPIC-F | V0 | #498 의 용어가 확정된 뒤에 쓰는 것이 안전 |
| #282 cross-repo E2E 부재 | **EPIC** | Medium | EPIC-D | V5-replay | #465·#467 을 묶는 상위 목표. Epic 승격은 사람이 한다(4절) |
| #465 Live API Probe 공통 인프라 | **MERGE** → #282 | — | EPIC-A | V3+V4 | #504 로 `kpubdata probe` 가 들어갔다. 이 이슈의 남은 것은 CI 통합이고 그건 #282 범위 |
| #467 E2E 대표 Dataset 확정 | **MERGE** → #282 | — | EPIC-D | V0 | 단독 이슈로 유지할 크기가 아니다 |
| #462 Catalogue 조사 소유 이슈 확정 (#375 vs #409) | **DECISION** | Medium | EPIC-F | V0 | 소유권 결정 자체가 내용이다. 결정하면 즉시 닫힌다 |
| #466 Cross-repo Compatibility Matrix 소유 확정 | **DECISION** | Medium | EPIC-D | V0 | 위와 같은 성격 |
| #409 대량 전환 잔여 백로그 (활용신청 94·파라미터 141) | **EPIC** | Medium | EPIC-E | V4 | 이슈 하나에 235종이 들어 있다. Epic 으로 올리고 실제 수요 기준으로 잘라낸다 |
| #384 [Phase 6] 스케일 및 운영 | **EPIC** | Low | EPIC-E | — | 상시 항목. Issue 가 아니라 Epic 이다 |
| #448 에이전트 기반 데이터셋 자동화 | KEEP | Low | EPIC-E | V3 | LATER. 3절의 방향에 아직 없다 |
| #221 한국도로공사 Provider | KEEP | Low | EPIC-E | V4 | 수요 확인 후 |
| #91 datago 사업자등록 상태조회 | **BLOCKED** | Low | EPIC-E | V4 | 활용신청 승인 대기 (`needs-human`) |
| #161 datago 워크넷 채용정보 | **BLOCKED** | Low | EPIC-E | V4 | 활용신청 승인 대기 |
| #162 datago 긴급재난문자 | **BLOCKED** | Low | EPIC-E | V4 | 활용신청 승인 대기 |

### 확인한 것

- **#452 는 닫혔고(2026-09-19) 실제로 해결됐다.** 컬럼 단위 all-or-nothing 으로
  바뀌었다. 다만 **#481 이 그 해결을 페이지 경계에서 되돌린다** — 한 페이지
  안에서만 일관되므로 기존 테스트가 전부 통과한다. #452 를 다시 열 일은 아니고,
  #481 이 정확한 후속이다.
- **#497·#499 는 #501·#504 병합으로 닫혔다.** 16절 기준으로는 아직 Done 이
  아니라 **Verifying** 이다 — `kpubdata probe` 는 국내 runner V4 검증을 받은 적이
  없다. TRUST-02 가 그 검증이다.

---

## kpubdata-builder (8건)

| Issue | 분류 | Priority 후보 | Epic | Required Verification | Action |
|---|---|---|---|---|---|
| #677 17개 게시 데이터셋에 공공누리 출처표시 없음 | **DECISION** | High | EPIC-C | V0 | 데이터셋별 공공누리 유형을 사람이 확인해야 한다. **유형을 틀리게 적는 것은 적지 않는 것보다 나쁘다** (ADR 0018) |
| #636 scripts/pipeline → BuildSpec 마이그레이션 | **DECISION** | High | EPIC-E | V3 | ADR 0018 의 A/B/C 선택 대기. 결정 전에 레거시를 지우지 않는다 |
| #659 #654 spec 빌드 결과가 공개 HF 와 다르다 | **DECISION** | High | EPIC-E | V3 | #636 과 같은 결정. `select`/`filters`/`deal_date` 타입 세 가지 |
| #635 다중 사용자 배포 전 필수 3종 | **SPLIT** | High | EPIC-B | V3 | 아래 참조 |
| #622 대용량 source 메모리 materialization | KEEP | Medium | EPIC-D | V2+V3 | 실제 실패 사례를 evidence 로 붙여야 High 자격이 된다(8절) |
| #596 BuilderService 도메인별 분할 | KEEP | Low | EPIC-F | V2 | #637 이 첫 조각 |
| #637 app.py 에서 publish·builds 추출 | **MERGE** → #596 | — | EPIC-F | V2 | #596 의 sub-issue 로 연결한다 |
| #648 param_grid 재시도·체크포인트 | KEEP | Medium | EPIC-D | V2 | #622 와 함께 보는 것이 자연스럽다 |

### #635 를 셋으로 나눈다

본문이 세 개의 독립적인 문제를 담고 있고, **그중 둘은 이미 해결됐다.**
하나의 이슈로 두면 해결된 부분까지 열려 있는 것으로 보인다.

| 구성 | 현재 상태 | 근거 |
|---|---|---|
| 1. 동기 `POST /build` 의 run_id 소유권 미검사 | ✅ 해결 | `routes/core.py:94` — `check_existing_run_access` 게이트 |
| 2. 전역 `HF_TOKEN` 을 모든 principal 이 사용 | ✅ 해결 | `service/publish_credentials.py` — principal 별 해석, `REQUIRE_OWN_PUBLISH_CREDENTIAL` |
| 3. OIDC 공개 가입 + `ENFORCE_OWNERSHIP` 기본 off | ⚠️ **DECISION** | `auth.py:292` 는 경고만 한다. 기본값을 뒤집으면 기존 배포가 깨진다 |

3번만 남기고 이슈 제목을 좁힌다. 기본값 전환은 BYOK-02 의 결정 항목이다.

### 확인한 것

- **#674 는 병합됐다**(내부 API coupling 을 테스트로 고정). Merged 이지 Done 이
  아니다 — coupling 자체를 없애는 일은 별건이다.
- **#675 는 병합됐지만 Verification 이 남았다.** 실제 image build/pull/start 는
  이 환경에서 Docker 데몬이 꺼져 있어 확인하지 못했다. **V3 미충족 상태다.**
  BASE-01 에서 다시 측정한다.

---

## kpubdata-studio (1건)

| Issue | 분류 | Priority 후보 | Epic | Required Verification | Action |
|---|---|---|---|---|---|
| #400 지원 Node 버전 미선언 | **DECISION** | Medium | EPIC-D | V1 | Node 20 을 계속 지원할지가 내용이다. 정하면 `engines` 한 줄 |

**#379 는 닫혔다** (BuildsPage·NewBuildPage 분할). 제품화 영향은 없다 — 내부
구조 변경이고 사용자 경로는 그대로다.

---

## 중복·고아 정리 결과

- **중복 없음.** 제목이 겹치는 이슈는 없었다.
- **고아 없음.** 28건 모두 다음 행동이 정해졌다.
- **이미 해결됐는데 열려 있는 이슈: 0건.** 다만 #635 는 **부분적으로** 해결된
  채 열려 있어 SPLIT 대상이다.

## 이 감사가 하지 않은 것

- Priority 를 확정하지 않았다. 위 표는 전부 **후보**다(POLICY 14절).
- Epic 을 만들지 않았다. #282·#409·#384 의 Epic 승격은 사람이 한다(4절).
- 라벨을 바꾸지 않았다. `P0`/`P1`/`P2` 제거는 GOV-05 의 zero-based 재판정이
  끝난 뒤다 — 먼저 지우면 재판정의 입력이 사라진다.
- 이슈를 닫거나 나누지 않았다. 위 MERGE·SPLIT·CLOSE 는 **제안**이다.
