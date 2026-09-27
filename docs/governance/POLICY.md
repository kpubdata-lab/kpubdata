# KPubData Product Family — Project Management & Review Policy

> 적용 대상
>
> - `kpubdata`
> - `kpubdata-builder`
> - `kpubdata-studio`
>
> 목적
>
> 세 저장소를 독립 프로젝트가 아니라 하나의 제품군으로 관리한다.
> Issue 수, PR 수, 테스트 수, 구현된 기능 수가 아니라
> **검증되어 사용자에게 전달할 수 있는 제품 가치**를 진척으로 본다.
>
> 핵심 관리 구조:
>
> `Epic → Issue → PR → Review → Verification → Release`
>
> Milestone은 사용하지 않는다.
> ROADMAP과 README는 작업 진행상태 데이터베이스로 사용하지 않는다.

---

# 0. 문서 위치와 우선순위

- 이 문서의 정본은 `kpubdata/docs/governance/POLICY.md` 하나다.
- 세 저장소의 `AGENTS.md`, `CONTRIBUTING.md`는 이 문서를 링크하고, 여기와 충돌하는 규칙을 두지 않는다.
- 충돌이 생기면 이 문서가 우선한다.
- 저장소별 문서에는 해당 저장소 고유의 절차(빌드 명령, 디렉터리 규칙)만 남긴다.
- 이 문서를 바꾸는 변경은 R3(25절)로 취급한다.

---

# 1. 프로젝트 관리 원칙

## 1.1 One Product, Multiple Repositories

| Repository | 책임 |
|---|---|
| `kpubdata` | Provider / Data Access / Spec / Validation |
| `kpubdata-builder` | Build / Transform / Policy / Publish |
| `kpubdata-studio` | User Experience / Onboarding |
| Cross-repo | 실제 제품 사용자 여정 |

저장소별로 최적화하지 않는다.

예를 들어 `kpubdata`의 변경이 자체 테스트를 모두 통과해도
Builder를 깨뜨린다면 제품 관점에서는 완료가 아니다.

## 1.2 제품 원칙

1. **BYOK**: 모든 데이터 호출은 요청한 사용자 본인의 키로 한다.
2. **키 비저장**: 키는 요청·작업이 도는 동안 메모리에만 두고 영속 저장하지 않는다.
   적용 범위는 실행 형태에 따라 다르다.

   | 실행 형태 | 키 출처 | 원칙 |
   |---|---|---|
   | kpubdata 라이브러리·CLI (사용자 자신의 프로세스) | 사용자 환경변수, 인자 | **유지.** 그 자체가 BYOK 다 |
   | builder self-hosted 단일 사용자 | 운영자 = 사용자 | 환경변수 허용 여부를 결정한다 |
   | builder 다중 사용자 (self-hosted OIDC, hosted) | 요청마다 사용자 입력 | 영속 저장 금지, 운영자 키 폴백 금지 |
3. **키 풀링 금지**: 운영자 키, 다른 사용자 키, 공유 캐시로 대신 호출하지 않는다.
4. **약관 우선**: 내보내기는 데이터셋 단위 정책 판정을 통과해야 한다.
5. **증거 기반 지원**: Stable(34절)에만 호환성을 약속한다.

---

# 2. 관리 계층

```text
Product Direction
       ↓
      Epic
       ↓
     Issue
       ↓
       PR
       ↓
     Review
       ↓
 Verification
       ↓
    Release
```

Milestone 계층은 만들지 않는다.

## 2.1 상태 정보의 기록 위치

| 정보 | 기록 위치 | 설정 주체 |
|---|---|---|
| Status (15절) | GitHub Project 필드 | 사람·자동화 (Done은 사람만) |
| Priority (8절) | Project 필드 | 사람 (High 승격은 사람만) |
| Epic (5절) | **`epic:*` 라벨** (2.1.1절) | 사람 |
| Required Verification (18절) | Project 필드 + 이슈 본문 | 이슈 작성자, triage에서 확정 |
| Target Release (33절) | Project 필드 | 사람 |
| 유형 (bug / feat / docs / chore) | 라벨 | 누구나 |
| Review Level (R0~R3) | 라벨 (경로 기반 자동 부여) | 자동. 낮추는 것은 사람만 |
| Severity (9절) | 라벨 (bug만) | triage |
| Triage 분류 (11절) | 감사 결과표에만 기록. 라벨로 만들지 않음 | triage |

- 세 저장소를 묶는 GitHub Project 하나를 사용한다.
- **Epic 이슈는 `kpubdata` 저장소에 둔다.** 다른 저장소의 이슈는 sub-issue로 연결한다.
- **Blocked · Needs Human 은 Status 필드로만 관리하고 라벨로 중복하지 않는다.**
  같은 정보를 두 곳에 두면 한쪽이 반드시 뒤처진다.
- 위 표에 없는 라벨은 새로 만들지 않는다.
- 라벨 추가는 `epic:governance` 를 거친다.

## 2.1.1 Epic 을 라벨로 옮긴 이유 — 2026-09-27 개정

이 절은 원래 Epic 을 *Project 필드 + Epic 이슈의 sub-issue* 로 기록하라고 했다.
그 방식은 채택되지 않았고, 다음 세 가지가 이유다.

- **Project 가 없다.** 세 저장소를 묶는 Project 를 만들려면 `gh` 의 `project`
  scope 가 필요하고, 그것이 아직 없다. Epic 을 Project 필드에 두라는 규칙은
  Project 가 생기기 전까지 **아무것도 기록하지 못한다.**
- **Epic 이슈가 없었다.** `EPIC-A` ~ `EPIC-G` 는 5절의 표에만 있었고 이슈로
  만들어진 적이 없다. 57개 이슈 본문이 `EPIC-G` 를 적고 있었지만 sub-issue 로
  연결된 것은 0건이다. 규칙이 아니라 **관례가 존재하지 않았다.**
- **`EPIC-A` 는 이름이 아니다.** 읽는 사람이 5절 표를 찾아야 뜻을 안다.

그래서 `epic:*` 라벨 9개를 만들고 **열린 이슈 전부에 붙였다.** 이름이 곧 뜻이고,
검색·필터가 되고, 저장소를 넘나들어도 같은 이름이다.

| 라벨 | 담는 것 |
|---|---|
| `epic:trust` | 검증·증거·drift·provenance |
| `epic:warehouse` | table · snapshot · SQL · query run |
| `epic:governance` | 정책·라벨·CI 강제 |
| `epic:byok` | credential·격리·누출 |
| `epic:policy` | 약관·라이선스·PII·publish gate |
| `epic:datasets` | catalogue → spec, provider 온보딩 |
| `epic:distribution` | 버전·이미지·릴리스·공급망 |
| `epic:brand` | 브랜드·용어 |
| `epic:onboarding` | 키 입력·probe·첫 경험 |

5절의 `EPIC-A` ~ `EPIC-G` 는 이 라벨들로 **대체된다.** 이 표가 정본이다.

**Blocked · Needs Human 은 여전히 라벨로 만들지 않는다.** 위의 근거는 Epic 에만
해당한다 — Epic 은 Project 가 없으면 기록할 곳이 아예 없지만, Blocked 는 이슈
본문의 `Blocked by:` 절이 이미 담고 있고 라벨을 더하면 두 곳이 어긋난다.

Project 가 생기면 Status·Priority·Target Release 는 표대로 Project 필드로 간다.
Epic 은 라벨로 남긴다 — 위의 세 번째 이유는 Project 가 생겨도 사라지지 않는다.

---

# 3. Product Direction

제품 방향은 Issue 목록이 아니다.

```text
NOW
Self-hosted BYOK productization

NEXT
Evidence-based dataset onboarding
Policy-safe publishing

LATER
Hosted BYOK
Scheduled builds
Async collection
```

이 정도만 ROADMAP에 유지한다.

**데이터셋 지원 상태는 README·ROADMAP에 손으로 적지 않는다.**

spec과 evidence에서 생성된 파일:

- `SUPPORTED_DATA.md`
- `docs/status.md`

만 기준으로 사용하고 CI `--check`로 드리프트를 막는다.

---

# 4. Epic 정책

Epic은 하나의 사용자 가치 또는 제품 위험을 해결한다.

권장 크기:

- 약 1~4주
- Issue 약 3~15개
- 여러 저장소 포함 가능

## 4.1 Epic 이슈는 만들지 않는다 — 2026-09-27 개정

Epic 은 **라벨이다**(2.1.1절). Epic 이슈를 따로 만들지 않는다.

그래서 "Epic 은 사람만 만들고 닫는다" 는 원래 문장은 이렇게 바뀐다.

- **`epic:*` 라벨을 새로 만드는 것은 사람만 한다.** 에이전트는 기존 라벨만 붙인다.
- **Epic 을 닫는다는 개념은 없다.** 라벨이 붙은 열린 이슈가 0건이 되면 그 Epic 이
  끝난 것이다. 닫을 대상이 없다.

Epic 이슈를 만들지 않는 이유는 그것이 **낡을 두 번째 장소**이기 때문이다. Epic
이슈의 체크리스트와 실제로 그 라벨이 붙은 이슈 목록은 반드시 갈라진다. 목록은
라벨 필터가 언제나 정확하게 답한다.

Epic 의 목표·범위·순서는 커밋되는 파일 한 곳에 둔다 —
[BACKLOG.md](BACKLOG.md). PR 리뷰를 거쳐야 바뀐다.

`kpubdata#1`~`#4` 처럼 과거에 만들어진 `[Epic]` 이슈 9건은 모두 닫혀 있고, 그
방식으로 돌아가지 않는다.

## 4.2 권장 크기는 라벨의 점검 기준이 된다

위의 "Issue 약 3~15개" 는 이제 **라벨이 너무 넓은지 재는 자**다. 한 라벨에 이슈가
계속 쌓이면 그 Epic 이 여러 개를 담고 있다는 뜻이다.

`EPIC-G` 가 온보딩·브랜드·i18n 을 다 담아 15건이 몰렸던 것이 그 예이고, 그래서
`epic:brand` 를 분리했다. 현재 `epic:governance` 가 18건으로 권장 범위를 넘는다 —
정책·라벨·CI 강제가 한 칸에 있다. 다음 점검 대상이다.

---

# 5. 현재 권장 Epic

> **이 절의 `EPIC-A` ~ `EPIC-G` 코드는 2.1.1절의 `epic:*` 라벨로 대체됐다.**
> 아래 서술은 각 Epic 이 *무엇을 하는지* 를 설명하는 부분만 유효하다. 코드로
> 이슈를 분류하지 않는다.
>
> | 이 절의 코드 | 지금 쓰는 라벨 |
> |---|---|
> | EPIC-A | `epic:trust` |
> | EPIC-B | `epic:byok` |
> | EPIC-C | `epic:policy` |
> | EPIC-D | `epic:distribution` |
> | EPIC-E | `epic:datasets` |
> | EPIC-F | `epic:governance` |
> | EPIC-G | `epic:onboarding` · `epic:brand` |
>
> `EPIC-G` 하나가 온보딩·브랜드·i18n 을 다 담고 있었다. 15건이 그 코드에 몰린
> 것이 칸이 부족했다는 증거다. `epic:warehouse` 는 대응하는 코드가 없다 — 그
> 작업이 trust 와 distribution 으로 흩어져 있었다.

## EPIC-A — Trust & Evidence

> "지원한다"는 말을 증명할 수 있게 한다.

**검증 장치를 만든다.**
개별 데이터셋에 적용하는 일은 EPIC-E가 한다.

- `make verify`
- `probe`
- dataset status
- CI evidence
- Stable definition
- fixture provenance
- drift detection
- live validation 인프라
- 국내 runner 운영

## EPIC-B — BYOK Security

> 사용자 자신의 키로 실행하되 제품은 키를 영속 저장하지 않는다.

- credential persistence 제거
- ephemeral credential context
- cache isolation
- user isolation
- secret leakage test
- SSRF protection
- proxy/APM redaction

## EPIC-C — Policy-Safe Data

> 허용되는 데이터를 허용되는 방법으로만 내보낸다.

- license metadata
- provider terms
- 약관 매트릭스
- redistribution policy
- commercial-use policy
- PII handling
- publish gate
- attribution
- dataset card

## EPIC-D — Distribution

> Git checkout이 아니라 실제 배포 artifact로 제품을 사용할 수 있게 한다.

- Python wheel
- container image
- Studio image
- Compose
- version compatibility
- clean installation
- release E2E

## EPIC-E — Dataset Migration

> 실제 수요가 있는 dataset을 검증 가능한 spec으로 전환한다.

**EPIC-A가 만든 장치를 데이터셋에 적용한다.**

- 수요 목록 기반 우선순위
- catalogue → spec
- localdata migration
- provider onboarding
- Stable 승격 신청
- 승격 결정은 사람이 수행

## EPIC-F — Project Governance

> Issue / PR / Review / Release 상태 자체를 신뢰할 수 있게 한다.

- issue cleanup
- label cleanup
- review policy
- release policy
- agent policy와 강제 장치
- documentation SSOT
- project board

## EPIC-G — User Onboarding

> 사용자가 키를 넣으면 무엇을 쓸 수 있고 무엇을 신청해야 하는지 바로 알 수 있게 한다.

- 키 입력 UI
- 메모리 전용 credential
- 사용자 키 probe
- 사용 가능 / 신청 필요 / 승인 대기 / 파라미터 확인 상태
- 서비스 단위 활용신청 안내
- 직접 신청 링크
- 키별 quota 표시
- provider별 가입·키 발급 가이드
- 결과는 키가 아니라 계정 기준으로 저장

---

# 6. Issue 기본 원칙

Issue 하나는 **검증 가능한 하나의 문제**를 다룬다.

Issue를 만들기 전에 반드시 다음 질문에 답한다.

1. 실제 문제가 무엇인가?
2. 근거가 있는가?
3. 독립적인 작업인가?
4. 기존 Issue와 중복되지 않는가?
5. 어떤 조건이면 끝났다고 판단할 수 있는가?

답할 수 없다면 Issue를 만들지 않는다.

---

# 7. Issue Template

## 7.1 기본 템플릿 — R1 이상

```markdown
# Problem

현재 어떤 문제가 있는지 설명한다.

# Evidence

재현 명령, 코드 위치, 로그, 공식 문서 등을 기록한다.

# User / Product Impact

이 문제가 실제 사용자 또는 제품에 어떤 영향을 주는지 설명한다.

# Expected Behavior

원하는 결과를 기술한다.

# Scope

이번 Issue에서 수정할 범위.

# Non-goals

이번 Issue에서 하지 않을 것.

# Acceptance Criteria

- [ ]
- [ ]
- [ ]

# Required Verification

V0 / V1 / V2 / V3 / V4 / V5-replay / V5-live

# Dependencies

Blocked by:
Blocks:

# Product Epic

연결된 Epic.

# Notes

추가 정보.
```

## 7.2 경량 템플릿 — R0 전용

```markdown
# Problem

# Acceptance Criteria

- [ ]

# Required Verification

V0
```

---

# 8. Priority 정책

기존 `P0 / P1 / P2` 표기는 사용하지 않는다.

기존 문서의 Priority는 기계적으로 치환하지 않는다.

- 기존 P0 → High 후보
- 기존 P1 → Medium 후보
- 기존 P2 → Low 후보

이후 triage에서 다시 판정한다. **치환이 아니라 원점 재판정이다** — 잘못된
우선순위가 이름만 바꿔 살아남지 않게 한다.

## High

현재 제품 흐름, 보안, 데이터 정확성 또는 현재 Epic 진행을 실질적으로 막는다.

예:

- credential leakage
- 사용자 간 데이터 노출
- 금지 데이터 publish 가능
- 핵심 build 실패
- 잘못된 데이터 생성
- `make verify`가 정상 workflow를 차단
- release artifact가 실행되지 않음
- evidence pipeline 신뢰 불가

High에는 반드시 다음이 있어야 한다.

```text
Impact:
Blocks:
Evidence:
```

High라는 이유만으로 긴급 릴리스한다는 의미는 아니다.

## Medium

현재 제품화를 위해 필요하지만 다른 작업을 즉시 중단시킬 정도는 아니다.

예:

- public API 정리
- provider documentation
- quota management
- status page
- deployment documentation
- large-file streaming
- observability

대부분의 정상적인 제품 개발 작업은 Medium이어야 한다.

## Low

장기 개선, 최적화, 편의성, 미래 확장.

예:

- async client
- UI component refactoring
- performance optimization
- additional providers
- OpenSSF badge
- advanced scheduling

---

# 9. Priority와 Severity를 혼동하지 않는다

Priority는 **현재 작업 순서**를 의미한다.

Severity는 **문제의 영향도**를 의미한다.

보안 문제라는 이유만으로 자동 High가 되는 것은 아니다.

## 9.1 Severity 척도

| Severity | 정의 | 예 |
|---|---|---|
| Critical | 키·개인정보 유출, 사용자 간 데이터 노출, 금지 데이터 공개 게시 | 로그에 서비스키 평문 |
| Major | 잘못된 데이터 생성, 핵심 흐름 실패, 우회 가능한 정책 게이트 | 타입 캐스팅으로 값 손상 |
| Minor | 기능 일부 오동작, 우회 가능한 불편 | 잘못된 에러 분류 |
| Trivial | 표기·문서 오류 | 오타 |

예:

```text
Severity: Critical
Priority: High
```

또는:

```text
Severity: Minor
Priority: Medium
```

---

# 10. High 제한

동시에 진행하는 High 작업은 제품군 전체에서 최대 3개를 권장한다.

High가 지나치게 많다면 모든 문제가 긴급한 것이 아니라
Priority 분류가 실패한 것으로 본다.

새로운 High가 발견되면 기존 High의 우선순위를 다시 검토한다.

**Critical 보안·개인정보·법률 사건은 이 WIP 제한보다 우선한다.** 실제 사고가
났는데 슬롯이 찼다는 이유로 기다리는 일은 없다.

---

# 11. Issue Triage 정책

세 저장소의 모든 Open Issue를 다음 중 하나로 분류한다.

| 분류 | 의미 |
|---|---|
| KEEP | 실제 독립적인 미해결 문제 |
| MERGE | 다른 Issue와 본질적으로 동일 |
| CLOSE | 이미 해결됐거나 제품 방향에서 제외 |
| SPLIT | 서로 독립적인 문제가 하나의 Issue에 섞임 |
| DECISION | 코드 작업 전에 사람의 결정 필요 |
| RESEARCH | 사실 확인 필요 |
| BLOCKED | 외부 조건 때문에 진행 불가 |
| EPIC | 여러 Issue를 묶는 목표 |

---

# 12. Issue 전수 감사

각 Open Issue에서 확인한다.

- [ ] 현재 main에서도 재현되는가?
- [ ] 이미 다른 PR에서 해결되지 않았는가?
- [ ] 후속 Issue가 존재하는가?
- [ ] 중복 Issue가 있는가?
- [ ] 제품 방향과 아직 관련 있는가?
- [ ] Acceptance Criteria가 있는가?
- [ ] Verification Level이 있는가?
- [ ] Priority가 적절한가?
- [ ] 저장소가 맞는가?
- [ ] cross-repo 문제인가?
- [ ] 사람 결정이 먼저 필요한가?
- [ ] 실제 사용자에게 영향이 있는가?

결과:

```text
Repo | Issue | Classification | Priority | Epic | Action
```

감사는 다음 시점에 수행한다.

- 분기마다 1회
- 릴리스 직전
- 대규모 제품 방향 변경 후

---

# 13. Agent의 Issue 생성 제한

Agent는 문제를 발견했다고 자동으로 Issue를 만들지 않는다.

기본 동작:

```markdown
## Follow-up Candidate

Problem:

Evidence:

Impact:

Suggested Scope:

Blocks Current Work:
Yes / No
```

현재 Issue 또는 PR에 기록한다.

이후 triage에서 다음 중 하나로 결정한다.

- Promote to Issue
- Merge with existing
- Research
- Ignore

---

# 14. Agent가 독자적으로 하면 안 되는 것

Agent는 다음을 단독으로 결정하지 않는다.

- Priority를 High로 승격
- Epic 생성
- Stable 승격
- Release scope 변경
- 약관 최종 허용 판정
- Security policy 변경
- Branch protection 변경
- Release 수행
- Secret 접근 승인
- 자신의 PR 최종 승인
- 자신의 evidence를 신뢰 evidence로 승인
- 자신의 Issue를 완료 판단하여 close.
  **Required Verification 이 PR 에서 이미 충족된 R0 이슈는 워크플로 자동화가
  close 할 수 있다.** 그 판단을 에이전트가 직접 하지는 않는다 — 자동화는 조건을
  기계적으로 확인하고, 에이전트는 자기 작업의 완료를 선언하지 않는다.
- Review Level 하향

---

# 15. Issue Lifecycle

```text
Triage
   ↓
Ready
   ↓
In Progress
   ↓
In Review
   ↓
Verifying
   ↓
Done
```

**`Merged` 는 Project 상태가 아니다.** 병합은 사건이고 상태가 아니며, 상태로
두면 16절("Merged != Done")이 상태 이름으로 부정된다. PR 이 병합되면
`In Review → Verifying` 으로 넘어간다.

보조 상태:

```text
Blocked
Needs Human
Deferred
```

## 15.1 상태 전이 책임

| 전이 | 누가 |
|---|---|
| Triage → Ready | 사람 |
| Ready → In Progress | 구현자 |
| In Progress → In Review | 구현자 |
| In Review → Verifying | PR 병합 시. 병합 자체는 사람 |
| Verifying 진행 | CI 또는 지정된 사람 |
| Verifying → Done | 사람 |
| 같은 지점 3회 실패 | Needs Human 전환 |

같은 지점에서 3회 실패하면 구현자는 작업을 계속 반복하지 않는다.

다음을 남긴다.

```markdown
## Needs Human

Failed Stage:

Attempts:

Observed Behavior:

Evidence:

What Was Tried:

Decision Needed:
```

---

# 16. Merged != Done

PR merge는 Issue 완료가 아니다.

Issue를 Done으로 만들려면:

- [ ] 코드가 merge됐다.
- [ ] Acceptance Criteria가 충족됐다.
- [ ] Required Verification을 신뢰 evidence로 통과했다.
- [ ] 필요한 문서가 업데이트됐다.
- [ ] cross-repo 영향이 확인됐다.
- [ ] release artifact 검증이 필요한 경우 완료됐다.

그 후 사람이 Issue를 close한다.

---

# 17. 후속 Issue 정책

원 Issue의 Acceptance Criteria가 충족되지 않았다면
후속 Issue를 만들어 원 Issue를 닫지 않는다.

원 Issue를 유지한다.

별개의 개선사항일 때만 후속 Issue로 분리한다.

예:

```text
Bug
 ↓
원래 문제 해결
 ↓
Issue Done

추가 normalization 개선
 ↓
Follow-up Issue
```

---

# 18. Verification Level

모든 Issue에는 Required Verification을 지정한다.

| Level | 내용 | 신뢰 evidence 생성 위치 |
|---|---|---|
| V0 — Static | lint, typecheck, schema validation | CI |
| V1 — Unit | 단위 테스트 | CI |
| V2 — Replay / Contract | fixture/replay 기반 계약 테스트 | CI |
| V3 — Component Integration | 실제 component 간 통합 | CI |
| V4 — Live Provider | 실제 provider API 호출 | 국내 runner CI + CI secret |
| V5-replay — Product E2E | Studio → Builder → kpubdata → replay provider → Artifact | CI |
| V5-live — Product E2E | Studio → Builder → kpubdata → 실제 Provider → Artifact | 국내 runner CI |

PR에서는 V5-replay를 사용할 수 있다.

V5-live는 실제 Provider가 필요한 release 수준 검증에 사용한다.

## 18.1 변경 유형별 기본 요구

| 변경 유형 | Review | Required Verification |
|---|---|---|
| 오타·링크·포맷·생성 파일 | R0 | V0 |
| 일반 버그 수정·작은 기능 | R1 | V1 이상 |
| public API, builder API, OpenAPI | R2 | V2 + V3 |
| spec 추가·수정 | R2 | V2 + V4 |
| dataset transformation | R2 | V2 + V3, 영향 데이터셋 V4 |
| BYOK·auth·cache isolation | R3 | V3 + 부정 테스트 + leakage test |
| publish policy·PII | R3 | V3 + 부정 테스트 |
| workflow·CI evidence | R3 | V3 이상 |
| release | R3 | V5-live |

표보다 높은 수준을 요구하는 것은 자유다.

낮추려면 사람의 승인과 사유 기록이 필요하다.

---

# 19. Verification 규칙

Issue:

```text
Required Verification: V4
```

> **19절은 여기서 끊겨 있다.** 전달받은 원문이 `PR:` 예시 블록 직전에서
> 끝났다. 아래 20~34절도 아직 전달되지 않았다.

---

# 20~34. 미수신 구간

이 문서는 **아직 완성본이 아니다.** 0~19절만 전달받았고, 20절 이후는 비어 있다.
앞 절이 이미 참조하고 있는데 본문이 없는 것은 다음 세 개다.

| 참조 위치 | 가리키는 절 | 내용 |
|---|---|---|
| 0절, 2.1절 | **25절** | Review Level R0~R3 정의 |
| 2.1절 | **33절** | Target Release |
| 1.2절, 5절(EPIC-A) | **34절** | Stable 정의 |

그동안 이 세 가지는 다음과 같이 읽는다 — 20~34절이 도착하면 이 절은 통째로
교체한다.

- **R0~R3**: 18.1절의 변경 유형 표가 사실상의 기준이다. R3는 사람 리뷰가
  반드시 필요한 등급이고, 이 문서를 바꾸는 변경이 여기 해당한다(0절).
- **Target Release**: GitHub Project 필드로만 관리하고 사람이 설정한다(2.1절).
- **Stable**: 증거 기반 지원 대상(1.2절). 승격 결정은 사람이 한다(14절).

이 구간이 채워지기 전까지 R0~R3 라벨의 자동 부여 규칙(2.1절)은 구현하지 않는다.
기준이 없는 상태로 자동화하면 라벨이 틀린 채로 쌓인다.

## 백로그 부록 A 중 아직 반영하지 못한 것

2026-09-26 백로그의 부록 A 는 POLICY 11곳을 고치라고 한다. **그중 7곳은
반영했고 4곳은 미수신 구간이라 반영할 수 없다.**

| 절 | 수정 내용 | 상태 |
|---|---|---|
| 1.2 | 키 비저장 적용 범위(라이브러리·CLI 는 환경변수 허용) | ✅ 반영 |
| 2.1 | Blocked·Needs Human 은 Status 필드로만 | ✅ 반영 |
| 8 | P0/P1/P2 는 치환이 아니라 원점 재판정 | ✅ 반영 |
| 10 | Critical 보안·개인정보·법률은 WIP 제한보다 우선 | ✅ 반영 |
| 14 | R0 는 워크플로 자동화가 close 가능, 에이전트는 불가 | ✅ 반영 |
| 15 | Project 상태에서 `Merged` 제거 | ✅ 반영 |
| 15.1 | 병합 시 `In Review → Verifying` | ✅ 반영 |
| **25** | spec `base_url` 호스트 변경은 R3 자동 승격 | ❌ 절 자체가 없다 |
| **31** | 신뢰 recorder 의 호스트 허용 목록 검사, DNS rebinding | ❌ 절 자체가 없다 |
| **34** | 등급 표를 축 분리 모델로 교체, `user_access` 제외 | ❌ 절 자체가 없다 |
| **35** | 규칙을 설정으로 강제 | ❌ 절 자체가 없다 |
| **37** | 원점 재판정 | ❌ 절 자체가 없다 |

미반영 4개 중 **25절과 31절은 열려 있는 보안 이슈와 직접 연결된다** —
`base_url` 호스트를 검사하지 않고 provider 키를 전송하는 경로가 실제로
있다(#519). 그 이슈는 이 문서와 무관하게 진행하지만, R3 자동 승격 규칙은
25절이 도착해야 쓸 수 있다.
