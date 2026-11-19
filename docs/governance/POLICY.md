# KPubData Product Family — Project Management & Review Policy

> 적용 대상
>
> - `kpubdata`
> - `kpubdata-builder`
> - `kpubdata-studio`
> - `kpubdata-watch`
>
> 목적
>
> 네 저장소를 독립 프로젝트가 아니라 하나의 제품군으로 관리한다.
> Issue 수, PR 수, 테스트 수, 구현된 기능 수가 아니라
> **검증되어 사용자에게 전달할 수 있는 제품 가치**를 진척으로 본다.
>
> 핵심 관리 구조:
>
> `Discussion (optional) → Issue → focused PR → Verification / risk-based review → Merge → approved Release`
>
> Milestone은 사용하지 않는다.
> ROADMAP과 README는 작업 진행상태 데이터베이스로 사용하지 않는다.

---

# 0. 문서 위치와 우선순위

- 이 문서의 정본은 `kpubdata/docs/governance/POLICY.md` 하나다.
- 네 저장소의 `AGENTS.md`, `CONTRIBUTING.md`는 이 문서를 링크하고, 여기와 충돌하는 규칙을 두지 않는다.
- 충돌이 생기면 이 문서가 우선한다.
- 저장소별 문서에는 해당 저장소 고유의 절차(빌드 명령, 디렉터리 규칙)만 남긴다.
- 이 문서를 바꾸는 변경은 보안·릴리스 영향과 실제 검증 결과를 검토한다. 네 저장소의 리뷰 승인 의무는 14.1절의 2026-11-19 소유자 결정에 따르며, 실제 GitHub 브랜치 보호 설정은 별도로 일치시켜야 한다.

<a id="writing-codes"></a>

## 0.1 작성 규칙 — 뜻을 먼저, 코드는 괄호로 — 2026-10-08 추가

리뷰 수준(R0~R3)과 검증 수준(V0~V5)은 내부 코드다. 프로젝트 밖 사람은 `V2` 만 보고
뜻을 알 수 없고, 쓰는 사람도 틀린다 — 2026-10-08 새 이슈 4건이 단위 테스트를 `V2` 로
적었다(정의상 단위 테스트는 V1, V2 는 replay·계약 테스트). 그래서(#878):

- **뜻을 먼저 쓰고, 코드는 괄호에 넣는다.** "단위 테스트(V1)", "위험도 높은 변경의 검증(R3)".
  영어로는 "unit tests (V1)", "risk-based verification for sensitive changes (R3)".
- 코드만 쓰고 싶으면 [아래 용어표](#codes)로 링크한다: `[R3](POLICY.md#codes)`.
- 라벨·체크·스크립트 이름(`review:R3`, `R3 review`, `scripts/r3_review.py`)은 이름이다.
  바꾸지 않고 코드 서식(backtick)으로 쓴다.
- 검사는 `scripts/check_plain_codes.py` 가 한다(CI `Lint & Type Check` 작업). `git ls-files` 가 주는
  모든 Markdown 과 `.github/ISSUE_TEMPLATE/` 이슈 양식을 본다. 코드 서식·코드 블록 안,
  `<!-- plain-codes: off -->` 와 `<!-- plain-codes: on -->` 사이(아래 용어표와 18·18.1절의
  정의 표)는 보지 않는다. `CHANGELOG.md` 는 `## [Unreleased]` 절만 본다 — 지난 릴리스
  절은 기록이라 고치지 않는다.
- 절 번호 참조("POLICY 14.1")는 이 규칙의 범위가 아니다.

<a id="codes"></a>

## 0.2 코드 용어표

<!-- plain-codes: off -->
| 코드 | 뜻 | 정의 |
|---|---|---|
| R0 | 리뷰 수준 0 — 오타·링크·포맷·생성 파일. 가장 가벼운 확인 | 18.1절 |
| R1 | 리뷰 수준 1 — 일반 버그 수정·작은 기능 | 18.1절 |
| R2 | 리뷰 수준 2 — public API·spec·데이터 변환을 바꾸는 변경 | 18.1절 |
| R3 | 위험도 높은 변경 — BYOK·인증·캐시 격리, 게시 정책·개인정보, 워크플로·CI 근거, 릴리스. **강화된 검증을 뜻하며 독립 사람 승인 의무는 없음** | 18.1절, 14.1절 |
| V0 | 정적 검사 — lint, 타입 검사, 스키마 검증 | 18절 |
| V1 | 단위 테스트 | 18절 |
| V2 | replay·계약 테스트 — 녹화한 fixture 로 돌린다 | 18절 |
| V3 | 구성요소 통합 테스트 — 실제 구성요소끼리 붙여 본다 | 18절 |
| V4 | 실제 provider API 호출 검증 — 국내 runner 와 CI secret 이 필요 | 18절 |
| V5-replay | 제품 E2E(replay) — Studio → Builder → kpubdata 를 replay provider 로 | 18절 |
| V5-live | 제품 E2E(실제) — Studio → Builder → kpubdata 를 실제 provider 로 | 18절 |
<!-- plain-codes: on -->

---

# 1. 프로젝트 관리 원칙

## 1.1 One Product, Multiple Repositories

| Repository | 책임 |
|---|---|
| `kpubdata` | Provider / Data Access / Spec / Validation |
| `kpubdata-builder` | Build / Transform / Policy / Publish |
| `kpubdata-studio` | User Experience / Onboarding |
| `kpubdata-watch` | Public Data Reliability / 관측 · Public Status |
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


## 1.3 안정화 전용 개발 모드 — 2026-10-12

**상태: 적용 중.** 이 절은 `kpubdata`, `kpubdata-builder`, `kpubdata-studio`
세 저장소의 **현재 제품 범위를 동결**한다. `kpubdata-watch`에는 자동 적용하지 않는다.
기준은 각각 2026-10-12 착수 당시 `main`의 `590110cd`, `8bedc648`, `8aa85cf1`이다.
동결은 달력 날짜나 다음 릴리스만으로 끝나지 않는다. 메인테이너가 검증 근거를 확인하고
이 정책의 변경을 별도 PR로 소유자가 명시적으로 허가할 때만 해제한다. 별도의 독립 리뷰 승인 의무는 없다(14.1절).

**성공의 기준은 기능·Issue·PR의 수가 아니라 기존 사용자 여정의 안정성과 검증 증거다.**
현재 없는 기능을 새로 만드는 것, 새로운 외부 의존성이나 상시 운영 책임을 만드는 것은
기본적으로 시작하지 않는다. 백로그에 이슈가 존재하거나 ADR이 제안됐다는 사실만으로
이미 승인된 현재 제품 범위라고 해석하지 않는다. 열려 있는 확장 이슈는 삭제하지 않고
후속 작업으로 보류한다.

### 허용하는 작업

- **버그·회귀·보안·개인정보 위험 수정:** 재현 → 원인 확인 → 수정 전 실패 테스트
  → 최소 수정 → 관련 기존 기능과 교차 저장소 검증. 긴급 위험은 즉시 차단하거나 기능을
  비활성화할 수 있다. 승인·검증 절차를 없애는 예외는 만들지 않는다.
- **기존 사용자 여정 완성:** 공공데이터 선택 → 수집 → 표준화·품질·PII·이용조건 확인
  → 테이블·SQL·산출물 → 이력·재시도. 기존에 제공 중인 화면·API의 정확성, 설명,
  오류 처리, 접근성, 사용자 격리와 이미 정의된 계약을 개선한다.
- **기존 서비스의 안정적 운영:** 백업·복원, 사용자 삭제, 자원·디스크 제한,
  인증·배포 검증, 로그·관측성, CI 신뢰성, 릴리스 호환성 등 **이미 운영 중인 경로의
  필수 안전장치**를 완성한다. 새 운영 시스템이나 스케줄을 만드는 해법보다 기존의 것을
  검증·수정하는 해법을 우선한다.
- **행동 보존 리팩터링:** 실제 결함·회귀 위험이나 측정된 유지보수 비용을 줄이고
  이전·이후 동작을 테스트로 비교할 수 있을 때만 한다. 파일 길이만 줄이는 작업,
  무관한 이름 바꾸기, 테스트 없이 대규모 구조 재설계는 보류한다.
- **릴리스 안정화:** 동결 범위 안에서 릴리스 후보를 묶어 replay 제품 E2E(V5-replay),
  실제 구성요소 테스트(V3), 복구 리허설, 호환되는 Builder·Studio 버전 쌍으로 검증한다.
  기존 릴리스 주간 동결 규칙은 그대로 적용한다.

### 기본적으로 보류하는 작업

- 신규 Provider·데이터셋·소스 종류·Export 형식·게시 목적지 및 신규 외부 서비스 연동.
- 새로운 API/CLI 명령, 신규 화면·제품 흐름, 파생 Snapshot·셀 수정·멀티 테이블
  확장, 선택적 한국어 NER/AI 모델 및 기능 시나리오 확대.
- 새 데이터베이스·상태 백엔드·배포 프로파일·런타임 모드, 새로운 배치/예약 작업·
  에이전트 자동화·상시 모니터링 서비스와 이를 운영하기 위한 추가 계정·키·인프라.
- 새 기능의 선행 개발을 안정화라고 이름만 바꾼 작업. `fix`·`refactor` 제목도
  실질적으로 사용자 기능이나 운영 책임을 늘리면 보류한다. `feat` 제목이라도 기존
  서비스의 필수 결함을 메우는 일이라면 아래의 엄격한 예외 심사를 받는다.

### 범위 예외와 기계 검사

1. 새로운 표면이 **이미 제공하는 경로의 확인된 장애·보안 위험을 없애는 유일하게
   합리적인 최소 수정**인 경우에만 예외를 검토한다. 기존 이슈 링크, 재현 증거,
   확장이 없는 대안, 추가 유지보수·외부 데이터 전송 부담, 되돌리기 방법을 PR에 적는다.
   편의성·향후 확장성·미래 공모전이나 신규 기획은 예외 근거가 아니다.
2. 예외 PR에는 정확히 `Scope exception: YES`, 구체적인 한 줄
   `Existing flow or risk: ...`, `Refs #N` 또는 `Closes #N`을 적고
   `review:R3` 라벨을 위험도·범위 예외 표식으로 단다. **소유자가 범위 확장을 명시적으로 승인**해야 한다.
   PR 작성자 외 사람의 승인 리뷰는 필수가 아니다(14.1절). 실제 검증 증거와 범위 승인 기록은 유지한다.
   PR 본문의 자기 선언은 범위 승인이 아니다. 없는 승인이나 실행 결과를 만들지 않는다.
3. 세 저장소의 `scripts/check_stabilization_scope.py`는 `feat` PR 및 새
   Spec/Provider, HTTP 경로, 화면, 워크플로·예약 실행처럼 기계적으로 인지 가능한
   확장을 **기본 거부**한다. `review:R3`와 위 PR 필드가 없으면 범위 게이트가 실패한다.
   그러나 `review:R3`는 위험도 표식일 뿐 사람의 승인 리뷰를 요구하지 않는다(14.1절).
   범위 게이트 및 관련 스크립트를 바꾸는 PR도 실제 테스트 증거와 명시적 소유자 결정을 기록한다.
4. **한계:** CI가 새 기능의 의미를 완벽하게 이해하지는 못한다. 새 의존성, 새
   데이터 전송 및 숨은 운영 책임은 PR 작성자와 리뷰어가 변경 전후를 직접 비교해
   판단해야 한다. 특히 `fix`로 위장한 확장은 검사를 통과해도 병합하지 않는다.
5. 같은 저장소·제품군에서 독립적인 안정화 이슈는 서로 다른 브랜치/PR에서
   병렬로 진행할 수 있지만, 같은 계약·파일을 동시에 편집하지 않는다. 동일
   이슈의 중복 구현이나 비밀정보가 있는 워크플로의 무검증 병렬 실행은 금지한다.
6. 모든 범위 밖 작업은 기존 이슈를 남겨 두고 결정을 기다린다. 제품의
   `priority:critical` 위험을 `priority:low`로 낮추는 근거로 이 모드를
   사용하지 않는다. 출시 전 필수 안전 조건도 임의로 제외하지 않는다.

### 안정화 중 Issue 접수·후속 작업 통제 — 2026-10-13

**기능 동결은 Issue 수를 숨기는 정책이 아니다.** 새로 확인된 독립 버그, 보안 위험,
사용자 데이터 손상, 기존 운영 장애는 즉시 기록한다. 기존 문제를 억지로 합쳐
영향을 숨기거나 버그 제보 자체를 막지 않는다. 반대로 이미 알려진 문제의 증거,
재시도 실패, 리뷰에서 나온 같은 범위의 잔여 작업을 매번 새 Issue로 만들지 않는다.

1. **먼저 조회한다.** 해당 저장소와 다른 두 제품 저장소의 Open/Closed Issue 및
   연결된 PR을 증상·원인·경로·오류 코드로 검색한다. 현재 Issue/PR에 넣을 수 있는
   재현 로그·실패 테스트·설계 질문·진행 상황이면 새 Issue가 아니라 댓글이나
   체크리스트로 갱신한다. 닫힌 이슈의 동일 결함이 재발했다면 기존 해결의 회귀인지
   먼저 확인하고, 동일 범위는 재오픈을 우선 검토한다.
2. **신규 독립 결함만 별도로 연다.** 재현 조건, 영향받는 기존 사용자 여정,
   코드/워크플로/CI 실행 근거, 기존 이슈와 다른 이유, 완료 조건과 검증 방법이
   제시될 때 별도 Issue가 정당하다. 아직 재현되지 않은 가능성은 현재 PR의
   `Follow-up Candidate`로 남기고 triage한다. 중요한 보안 위험의 긴급 격리와
   제보는 근거 수집을 기다리느라 지연하지 않는다.
3. **PR 후속을 쪼개서 완료를 가장하지 않는다.** 원래 Acceptance Criteria가
   미충족이면 기존 Issue를 유지한다(17절). 리뷰에서 발견된 같은 수정 범위의
   문제는 같은 PR에서 해결한다. 새로운 원인·소유자·검증 범위가 명확히 분리되고
   기존 Issue와 중복되지 않는 경우에만 별도 Issue로 승격한다.
4. **자동 모니터링은 기존 경보를 갱신한다.** 새 취약점과 예약 작업 실패는
   감추지 않는다. 동일한 배포 이미지 구성요소는 태그·digest가 바뀌어도 기존
   보안 Issue를 갱신하고, 재검증 전 사람이 쓴 위험 판정은 보존한다. 예약 게시
   실패는 워크플로 단위의 기존 incident를 재사용하고 실행 링크를 추가한다.
   서로 다른 원인·서비스 영향은 단순히 이슈 수를 줄이려고 무리하게 합치지 않는다.
   알림·이슈 기록이 실패하면 실행 자체가 실패로 남아야 한다.
5. **신규 데이터셋 확대 자동화는 동결 중 보류한다.** 활용신청 승인 감지와
   새로운 spec 초안 생성을 위한 예약 실행은 중단한다. 필요할 때 사람이 시작하는
   읽기 전용 dry run은 허용하지만, 새 Issue·Spec·PR을 만들지 않는다.
   동결 해제는 이 정책의 별도 검토·승인을 필요로 한다.
6. **발행자와 승인자는 다르다.** 사람은 버그와 취약점을 계속 제보할 수 있다.
   자동화·에이전트가 신규 Issue를 생성하는 코드는 정해진 중복 제거 키와
   부정 테스트를 요구한다. 인위적으로 `fix` 제목으로 바꾸거나 우선순위를
   낮춰 새 기능을 안정화 작업으로 포장할 수 없다.

기존 기능의 보안 이슈와 운영 경고는 계속 추적하지만, **이슈를 새로 발행하는
워크플로를 만드는 것 자체는 새로운 운영 책임**이므로 동결 예외 승인이 필요하다.
GitHub 자체의 사람 작성 Issue를 생성 전에 차단할 수 있다는 의미는 아니다.
triage 단계에서 위 근거를 검토하고, 중복 Issue는 기존 Issue로 연결해 정리한다.

### 데이터셋 요청은 주 단위로 묶어 처리하고, 자동 병합은 허용하지 않는다 — 2026-10-12 결정

저장소 소유자(yeongseon)가 2026-10-12에 kpubdata-lab/kpubdata 이슈 #899 에서 정했다.

- **주 단위 묶음 처리.** 데이터셋 요청은 들어오는 즉시 처리하지 않고 한 주에 한 번 묶어서
  처리한다. 요청 이슈는 그 사이 열어 둔 채 대기열(`priority:*` 라벨)에 쌓인다. 안정화 전용
  모드(위 1.3절)가 풀리기 전에는 신규 데이터셋 자체를 보류하므로, 이 주기는 동결이 풀린 뒤부터
  적용한다.
- **자동 병합 금지.** 요청을 처리한 PR을 워크플로나 봇이 스스로 병합하지 않는다. 브랜치
  보호에는 승인 요구가 없으므로, 자동 병합을 허용하면 사람의 검토가 통째로 빠진다. 워크플로가
  병합하는 것은 이미 `tests/unit/test_no_workflow_merges.py` 가 막고 있고, 이 결정은 그
  검사를 풀지 않는다는 뜻이다. 병합은 사람이 한다.
- **아직 정하지 않은 것.** 키 교체 주기와 분기별 도구 비교 주기는 메인테이너가 숫자를
  정할 때까지 비워 둔다. 추측으로 채우지 않는다.

### 동결 해제 조건

메인테이너는 최소한 현재 사용자 여정의 교차 저장소 E2E, 핵심 CI, 보안 차단,
백업·복원 리허설, 운영 장애 대응, 릴리스 쌍의 호환성에 관한 실행 증거를 검토한다.
이후 별도 정책 PR에서 확장 가능 범위를 명시하고 소유자의 범위 변경 허가를 기록한 후 해제한다.
그전까지 새 기능 제안은 우선순위가 높아졌다는 이유만으로 착수하지 않는다.

---

# 2. 단순 Issue 관리 (Lean Engineering Process)

작업의 기준은 **실제 문제를 해결하는 독립 Issue와 검증 가능한 PR**이다. 별도 Epic, Project 보드, Milestone, 사이즈·단계별 상태 라벨을 요구하지 않는다. 이 결정은 보안·개인정보·출처 조건·테스트·릴리스 게이트를 완화하지 않는다.

```text
Discussion (optional) → Issue (Open) → focused PR → checks / risk review → merge → Issue (Closed, when verified)
```

## 2.1 상태 정보의 기록 위치

- **Issue:** GitHub 기본 Open / Closed. 재현 증거, 범위, 완료 조건 및 막힌 이유는 본문/댓글에 기록한다. PR을 연결한다.
- **우선순위:** 필요한 경우만 `priority:*` 라벨. 높은 우선순위에는 실제 영향 근거를 남긴다(8절).
- **검증·리뷰:** 변경 위험에 맞춘 테스트, CI 및 기존 보호 규칙을 적용한다(14·18절). 새 리뷰·크기·상태 라벨을 의무화하지 않는다.
- **릴리스:** 기존 릴리스 정책·승인·호환성 검증을 따른다. 별도 보드의 Target Release 필드를 요구하지 않는다.
- **방향:** `ROADMAP.md`에는 Now / Next / Later 수준의 방향만 기록한다. Issue 수나 보드는 진행률 지표가 아니다.

## 2.1.1 Epic 및 보드 중단

SDK 저장소에서는 신규 Epic 이슈, `epic:*` 라벨, GitHub Projects 보드를 만들거나 요구하지 않는다. 다른 제품군 저장소의 기존 검증·자동화는 해당 저장소에서 별도 이전할 때까지 유지한다. 기존 열린 Issue의 Epic 라벨은 제거하되 이슈 내용과 이력은 보존한다. 기존 닫힌 이슈·과거 PR·릴리스의 역사적인 표기는 일괄 수정하지 않는다. 이전 정책에서 사용하던 Epic 분류는 더 이상 작업 결정 기준이 아니다.

## 2.1.2 선택적 우선순위

`priority:critical`, `priority:high`, `priority:medium`, `priority:low`는 필요한 경우만 사용한다. Severity는 실제 결함 영향에 관한 근거가 있을 때만 구분한다. 일률적인 재분류, 신규 보드, 추가 관리 이슈를 만들지 않는다.

## 2.1.3 Issue 제목은 자유롭게, PR 제목은 Conventional Commits

PR과 기본 브랜치의 최종 squash 커밋 제목은 아래 형식을 따른다. GitHub Issue 제목은 영어로 문제/목표가 잘 드러나면 충분하며 Conventional Commits 접두사를 강제하지 않는다. 다른 제품군 저장소의 이슈 제목 자동화는 각 저장소에서 별도로 이전한다.

```text
type: description
type(scope): description
type!: description          # 호환성을 깨는 변경 표기
type(scope)!: description
```

- 제목은 영어. `type` 과 `scope` 는 소문자, 콜론 뒤 공백 한 칸, 끝에 마침표를 붙이지 않는다.
- `scope` 는 선택이다. 통일을 위해 모든 제목에 억지로 붙이지 않는다.
- `description` 은 변경 대상과 의도를 구체적으로 쓴다. 소문자로 시작하되 API 이름·약어·
  고유명사 표기는 유지한다. 짧게 만들려고 오류 코드·API 이름·핵심 증상을 지우지 않는다.
- Issue 제목은 실제 문제나 목표를 기술한다. PR 제목은 적용한 변경을 기술한다. 원인이 불명확한 조사 Issue에 해결 방법을 미리 강요하지 않는다.
- 우선순위·크기·상태·담당자, `[Bug]` `[Feature]` `[WIP]` 같은 접두사를 넣지 않는다 —
  라벨과 Draft 상태가 그 일을 한다.
- **PR 제목에 이슈 번호를 붙이지 않는다** — 끝의 `(#123)` 만이 아니라 제목 어디에도
  `#123` · `repo#123` · `owner/repo#123` · 이슈·PR URL 을 쓰지 않는다 (#742). 본문에
  `Closes #123` · `Refs owner/repo#123` 으로 연결한다. squash 병합이 최종 커밋 제목 끝에 PR
  번호를 붙인다: `fix: decode nonempty NULL-only collection results (#503)`.
- **PR 제목은 영어이며, Conventional Commits 형식과 제한을 검사한다.** Issue 제목은 영어를 권장하되 형식 위반 댓글·자동 라벨링·차단을 수행하지 않는다.
- **PR 제목은 100자 이하이고 이슈·PR URL 을 담지 않는다** (#741). 이 둘은 PR 제목에만
  검사한다. GitHub 의 `Revert "…"` 제목은 되돌리는 커밋의 제목을 번호까지 그대로
  인용하므로 모든 규칙의 예외다.

| type | 용도 |
|---|---|
| `feat` | 사용자에게 제공하는 기능 추가 |
| `fix` | 제품 동작의 버그 수정 |
| `docs` | 문서 변경 |
| `test` | 테스트 추가·수정 |
| `perf` | 성능 개선 |
| `refactor` | 외부 동작을 유지하는 내부 구조 개선 |
| `ci` | CI·자동화 워크플로 변경 |
| `build` | 빌드·패키징·의존성 |
| `chore` | 위에 해당하지 않는 유지보수 |
| `style` | 동작 변경 없는 서식 변경 |
| `revert` | 기존 변경 되돌리기 (GitHub 의 `Revert "…"` 제목도 허용) |

`i18n` 은 2026-09-29 에 뺐다 — 번역은 `docs` 또는 `chore(i18n)` 이다. 그 전에 병합된 제목은
이력이므로 고치지 않는다.

**제목이 버전을 정한다 — 2026-10-11 개정 (#819, #895).** kpubdata 는 release-please
(`release-please.yml`)가 마지막 태그 뒤의 커밋 제목을 읽어 다음 버전을 계산하고 release PR 을
연다 — 0.x 에서 BREAKING(`!`)이나 `feat` 이 있으면 minor, `fix` 만 있으면 patch 다. 그래서 틀린
type 은 틀린 버전이 된다. 병합 전에 제목을 고친다. 사람이 하는 것은 그 release PR 을 검토하고
병합할지 정하는 것이다(14절 "Release 수행"). `release.yml` prepare 의 `bump` 입력은 release-please
가 하지 않는 pre-release 와 critical patch 에만 쓴다. 릴리스 노트는 여전히 사람이 쓴 CHANGELOG
절이 정한다 — release-please 는 CHANGELOG 를 쓰지 않는다. kpubdata-builder 는 아직
release-please 로 옮기지 않았으므로 그 `release.yml` prepare 의 `bump` 를 사람이 고른다(#895).
kpubdata-studio 의 prepare 에는 `bump` 입력이 없다 — Builder 의 최신 릴리스 태그를 읽어 같은
버전을 쓴다. Studio 는 Builder 를 옮긴 뒤에도 release-please 로 버전을 따로 계산하지 않고
Builder 의 태그를 따른다(같은 버전 정책 ADR 0004, 2026-10-12 소유자 결정, #895).

**병합은 squash 하나뿐이다** (2026-09-29, 네 저장소 설정): merge commit·rebase merge 는 꺼져
있고, squash 커밋 제목은 PR 제목, **본문은 PR 본문**이다 (2026-10-01 에 커밋 메시지 모음에서
바꿨다 — #743). 그래서 PR 제목이 곧 기본 브랜치의 커밋 제목이 되고, 브랜치의 개별 커밋
메시지는 기본 브랜치에 남지 않는다. 공동 작성자를 남기려면 `Co-authored-by:` 줄을 **PR
본문**에 쓴다.

**언어** (ADR 0003, 2026-10-01 확인): 커밋 **제목**(= PR 제목)은 영어다. 커밋 **본문**(= PR
본문)은 PR 본문 규칙을 따라 자유다.

**Issue 유형 라벨은 선택 사항**이다. `.github/workflows/titles.yml`은 PR의 필수 `PR title` 검사만 실행하며, Issue 제목에서 `type:*` 라벨을 생성·삭제하거나 안내 댓글을 남기지 않는다. 이미 붙은 유형 라벨은 과거 이력으로 유지할 수 있지만 새 이슈에 필수로 부여하지 않는다. PR/squash 제목 검사는 릴리스 버전 계산을 위해 유지한다.

[BACKLOG.md](BACKLOG.md) 의 "제목에 접두사를 붙이지 않는다" 는 **백로그 일련번호**
(`GOV-01:`)에 대한 결정이고 그대로 유효하다. 이 절이 허용하는 접두사는 type 하나뿐이다.

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

# 4. 작업 분류 원칙

Epic / parent tracking issue / 별도 Project 보드를 신규로 만들지 않는다. 기존 독립 Issue에서 근거·우선순위·완료 조건을 직접 업데이트하고 실제 코드 변경은 작은 PR로 연결한다. 독립적인 위험·버그만 별도 Issue로 분리하며 중복 Issue는 생성하지 않는다.

# 5. 제품 방향 (Now / Next / Later)

`ROADMAP.md`는 현재 집중 영역(Now), 다음 후보(Next), 장기 보류(Later)의 **방향**만 적는다. 이슈·PR 실제 상태는 GitHub가 정본이며, 릴리스 범위와 일정은 승인된 출시 정책으로 관리한다. SDK·Engine 및 기타 저장소의 배포와 운영 경계는 분리한다.

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

## 7.1 기본 템플릿 — 일반 버그 수정·작은 기능 이상(R1 이상)

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

검증 수준을 뜻과 함께 적는다. 예: 단위 테스트(V1), replay·계약 테스트(V2).
정적 검사(V0) / 단위 테스트(V1) / replay·계약 테스트(V2) / 구성요소 통합 테스트(V3) /
실제 provider API 검증(V4) / replay 제품 E2E(V5-replay) / 실제 제품 E2E(V5-live)

# Dependencies

Blocked by:
Blocks:

# Notes

추가 정보.
```

## 7.2 경량 템플릿 — 오타·링크·포맷·생성 파일 전용(R0)

```markdown
# Problem

# Acceptance Criteria

- [ ]

# Required Verification

정적 검사(V0)
```

---

# 8. Priority 정책

기록 위치는 `priority:*` 라벨이다(2.1.2절).

기존 `P0 / P1 / P2` 표기는 사용하지 않는다. **라벨도 폐기한다** — 표기를 쓰지 않기로
하고도 라벨이 남아 있어서 열린 이슈 10건이 계속 그것을 달고 있었다.

기존 문서의 Priority는 기계적으로 치환하지 않는다.

- 기존 P0 → High 후보
- 기존 P1 → Medium 후보
- 기존 P2 → Low 후보

이후 triage에서 다시 판정한다. **치환이 아니라 원점 재판정이다** — 잘못된
우선순위가 이름만 바꿔 살아남지 않게 한다.

## Critical — 2026-09-27 추가

**이미 노출돼 있거나 피해가 발생 중이다.** 다른 작업을 멈추고 이것부터 한다.

High 와 가르는 기준은 심각성이 아니라 **지금 노출돼 있는가**다. 같은 결함이라도
배포되지 않았으면 High 이고, 배포된 버전에서 재현되면 Critical 이다.

예:

- 배포된 버전이 credential 을 로그·응답·백업에 남긴다
- 운영 중인 배포에서 사용자가 다른 사용자의 데이터를 읽을 수 있다
- 게시된 데이터가 지금 약관을 위반하고 있다
- 릴리스된 산출물이 잘못된 데이터를 담고 있다

Critical 에는 High 와 같은 `Impact:` · `Blocks:` · `Evidence:` 가 필요하고,
**`Evidence:` 는 재현 경로여야 한다** — 가능성이 아니라 지금 그렇다는 것을 보여야
Critical 이다.

Critical 은 Severity 가 아니다(9절). Severity 는 bug 의 성질이고 Critical 은 *지금
무엇을 먼저 하는가*다. 심각한 버그가 배포되지 않았다면 Critical 이 아니다.

## High

현재 제품 흐름, 보안 또는 데이터 정확성에 실제로 영향을 주거나 이미 선택된 필수 작업을 막는다.

예:

- credential leakage
- 사용자 간 데이터 노출
- 금지 데이터 publish 가능
- 핵심 build 실패
- 잘못된 데이터 생성
- `make verify`가 정상 workflow를 차단
- release artifact가 실행되지 않음
- evidence pipeline 신뢰 불가

High 이상에는 반드시 다음이 있어야 한다.

```text
Impact:
Blocks:
Evidence:
```

열린 이슈 85건 중 **35건에 `Evidence:` 절이 없다.** 그 이슈들은 지금 High 로 올릴
수 없다. 근거를 채우는 것이 GOV-05(#510)의 실제 작업이다.

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
Repo | Issue | Classification | Priority (optional) | Action
```

감사는 다음 시점에 수행한다.

- 분기마다 1회
- 릴리스 직전
- 대규모 제품 방향 변경 후

---

# 13. Agent의 Issue 생성 제한

Agent는 문제를 발견했다고 자동으로 Issue를 만들지 않는다.
안정화 기간에는 1.3절의 Issue 접수·중복 제거 기준을 먼저 적용한다. 기존 문제의
미완료 항목이나 단순 후속 조사 결과는 **원본 Issue/PR에 추가**한다. 독립적인 새
버그·보안 위험의 기록은 허용하며, 긴급한 위험 대응을 지연하지 않는다.

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
- Stable 승격
- Release scope 변경
- 약관 최종 허용 판정
- Security policy 변경
- Branch protection 변경
- Release 수행
- Secret 접근 승인
- 자신의 PR에 타인의 승인 기록을 꾸미거나 허위 리뷰를 제출
- 자신의 evidence를 신뢰 evidence로 승인
- 자신의 Issue를 완료 판단하여 close.
  **Required Verification 이 PR 에서 이미 충족된 가벼운 이슈(R0)는 워크플로 자동화가
  close 할 수 있다.** 그 판단을 에이전트가 직접 하지는 않는다 — 자동화는 조건을
  기계적으로 확인하고, 에이전트는 자기 작업의 완료를 선언하지 않는다.
- Review Level 하향

## 14.1 네 저장소의 의무 독립 리뷰 폐지 — 소유자 결정, 2026-11-19

**적용:** `kpubdata`, `kpubdata-builder`, `kpubdata-studio`, `kpubdata-watch`.
소유자는 네 저장소 모두에서 **PR 작성자 외 인적 `APPROVED` 리뷰를 병합 전제조건으로 요구하지 않기로** 결정했다. 이는 2026-11-16의 SDK-only 예외를 제품군으로 확대한 것이다.
리뷰는 자발적으로 받을 수 있으나, 독립 리뷰어 부재만으로 병합을 막지 않는다. 에이전트가 사람의 승인 기록을 꾸미거나 자신의 PR에 대한 허위 승인 리뷰를 제출하지 않는다.

- `review:R3`는 고위험 변경의 **위험/검증 분류**일 뿐 인적 승인 요건이 아니다. 작성자와 오너는 영향 범위와 검증 근거를 PR에 남긴다.
- `CI gate`, `PR title`, 보안·비밀정보 검사, 계약·단위·통합 테스트 등 **기존 기계 검증의 필수 통과**는 유지한다. 실패한 필수 검사를 리뷰 면제와 혼동하거나 우회하지 않는다.
- 본 결정은 새로운 기능 범위의 승인, 개인정보·약관 예외, 릴리스·배포·게시·시크릿 접근 승인, 브랜치 보호의 기타 요구를 변경하지 않는다.
- 기존 `R3 review` GitHub Actions 필수 상태 검사와 오래된 워크플로/액션은 **실제 GitHub 설정과 코드가 수정되기 전까지 여전히 병합을 막을 수 있다**. 운영 변경은 각 저장소에서 이 레거시 사람-승인 게이트를 제거하거나 항상 중립적으로 통과시키고, 필수 검사 목록도 맞추어야 한다. 필수 검사 이름만 삭제해 영원히 대기하게 만들지 않는다.
- 오래된 `R3 review` 판정 스크립트와 이전 리뷰 정책 설명은 **과거 기록**이다. 새 병합 정책의 정본은 이 절이다. 병합은 요청된 작업에 대한 소유자의 권한 부여와 해당 PR의 실제 필수 검사 결과에 따른다.

## 14.2 PR 제목 검사가 머지를 막는다 — 2026-10-01

`PR title` 이 네 저장소 branch protection 의 required check 다(kpubdata#741).
그 전까지 titles.yml 은 빨간 X 만 보여줬다 — 병합 버튼은 열려 있었고, 규칙이
지켜지던 건 사람 기억 덕분이었다.

- 판정 로직은 하나다: `scripts/conventional_title.py` (kpubdata). 네 저장소가
  `@main` 액션으로 같은 검사를 부른다(§14.1 과 같은 구조).
- check 는 모든 PR 에서 돈다 — 열기·제목 수정(`edited`)·재오픈·push 마다. 제목
  수정은 ci.yml 을 다시 돌리지 않으므로, 검사를 CI gate 의 needs 에 넣는 대신
  required check 로 등록했다. 제목을 고치면 titles.yml 만 재실행되고 그 결과가
  머지를 통제한다.
- 거부하는 제목: 형식 위반(`type(scope): description`), 허용 밖 type, 줄바꿈,
  끝의 `(#N)`(#699), 제목 어디에든 있는 한글·`#N`(#742). `Revert "..."` 는
  예외다 — 되돌리기가 검사에 막혀선 안 된다.
- 이슈 제목은 별도 검증·자동 라벨링을 하지 않는다. PR의 `PR title` 필수 체크는 유지한다.
- required 목록은 `scripts/check_required_checks.py` 로 검증한다(studio#416 —
  존재하지 않는 체크를 required 로 두면 모든 PR 이 영원히 BLOCKED 다).
- release PR 제목(`chore(release): ...`)과 revert 제목은 형식에 맞으므로
  막히지 않는다.

---

# 15. Issue Lifecycle

GitHub의 **Open / Closed** 상태만 필수로 사용한다. 작업 중이면 기존 Issue에 PR을 연결하고, 외부 조건으로 막히면 본문·댓글에 이유와 다음 확인 사항을 적는다. Ready / In Progress / In Review / Verifying / Needs Human / Deferred 같은 Project 상태나 상태 라벨은 필수가 아니다.

## 15.1 완료 판단

PR의 병합은 구현 사건일 뿐 Issue 완료와 동일하지 않다. 완료 조건과 필요한 검증을 충족한 다음 Issue를 닫는다(16절). 반복 실패는 실제 증거와 필요한 사람 결정을 기존 Issue에 남기며 별도 관리 이슈를 만들지 않는다.

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

<!-- plain-codes: off -->
| Level | 내용 | 신뢰 evidence 생성 위치 |
|---|---|---|
| V0 — Static | lint, typecheck, schema validation | CI |
| V1 — Unit | 단위 테스트 | CI |
| V2 — Replay / Contract | fixture/replay 기반 계약 테스트 | CI |
| V3 — Component Integration | 실제 component 간 통합 | CI |
| V4 — Live Provider | 실제 provider API 호출 | 국내 runner CI + CI secret |
| V5-replay — Product E2E | Studio → Builder → kpubdata → replay provider → Artifact | CI |
| V5-live — Product E2E | Studio → Builder → kpubdata → 실제 Provider → Artifact | 국내 runner CI |
<!-- plain-codes: on -->

PR에서는 replay provider 로 도는 제품 E2E(V5-replay)를 사용할 수 있다.

실제 provider 로 도는 제품 E2E(V5-live)는 실제 Provider가 필요한 release 수준 검증에 사용한다.

## 18.1 변경 유형별 기본 요구

<!-- plain-codes: off -->
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
<!-- plain-codes: on -->

표보다 높은 검증 수준을 요구하는 것은 자유다. 검증 요건을 낮추려면 소유자의 명시적 결정과 사유 기록이 필요하며, 독립 사람 승인 리뷰를 요구하지 않는다.

---

# 18.2 확인은 기계가 한다 — 2026-09-27 추가

[VERIFICATION.md](VERIFICATION.md) 가 정본이다. 요지는 하나다.

> **확인할 수 있는 것을 확인하지 않고 단정하지 않는다. 그리고 확인을 사람의 조심함에
> 맡기지 않는다.**

2026-09-27 하루에 같은 형태의 실수가 여섯 번 났고, **막힌 것은 전부 기계가 막았고
빠져나간 것은 전부 기계가 없던 자리였다.** 조심함의 차이가 아니었다.

그래서 새 규칙을 정할 때 셋을 같이 만든다.

1. 규칙을 검사하는 명령
2. 그 명령을 CI 에 연결
3. **그 명령이 실패하는 것을 보여주는 테스트**

세 번째가 빠지면 작동하는지 아무도 모른다. `AGENTS.md` 는 처음부터 "주석은 영어" 라고
적고 있었고, 그 사이에 한국어 주석이 9,298건 쌓였다.

기존 부채는 **래칫**으로 동결한다 — 파일별 현재 건수를 baseline 에 두고 늘어날 때만
실패한다. 전부 고치고 시작하려면 아무것도 시작되지 않는다.

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
| 0절, 14·18절 | **25절** | 위험별 리뷰 가이드 |
| 릴리스 정책 | **33절** | 릴리스 계획 |
| 1.2절 | **34절** | Stable 정의 |

그동안 이 세 가지는 다음과 같이 읽는다 — 20~34절이 도착하면 이 절은 통째로
교체한다.

- **리뷰 수준(R0~R3)**: 18.1절의 변경 유형 표가 사실상의 기준이다. 가장 무거운 수준(R3)은 사람 리뷰가
  반드시 필요한 등급이고, 이 문서를 바꾸는 변경이 여기 해당한다(0절).
  작성자가 아닌 사람의 승인이 없으면 `R3 review` check 가 머지를 막는다(14.1절).
- **릴리스 계획**: Project 필드를 강제하지 않는다. 기존 호환성·릴리스 검증 정책은 [compatibility.md 5.1절](../compatibility.md#release-cadence)을 따른다.
- **Stable**: 증거 기반 지원 대상(1.2절). 승격 결정은 사람이 한다(14절).

이 구간이 채워지기 전까지 리뷰 수준(R0~R3) 라벨의 자동 부여 규칙(2.1절)은 구현하지 않는다.
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
| 14 | 가벼운 이슈(R0)는 워크플로 자동화가 close 가능, 에이전트는 불가 | ✅ 반영 |
| 15 | 과거 Project 상태에서 `Merged` 제거 | ✅ 반영 |
| 15.1 | 병합 시 병합 이후 검증 | ✅ 반영 |
| **25** | spec `base_url` 호스트 변경은 무거운 리뷰 수준(R3)으로 자동 승격 | ❌ 절 자체가 없다 |
| **31** | 신뢰 recorder 의 호스트 허용 목록 검사, DNS rebinding | ❌ 절 자체가 없다 |
| **34** | 등급 표를 축 분리 모델로 교체, `user_access` 제외 | ❌ 절 자체가 없다 |
| **35** | 규칙을 설정으로 강제 | ❌ 절 자체가 없다 |
| **37** | 원점 재판정 | ❌ 절 자체가 없다 |

미반영 4개 중 **25절과 31절은 열려 있는 보안 이슈와 직접 연결된다** —
`base_url` 호스트를 검사하지 않고 provider 키를 전송하는 경로가 실제로
있다(#519). 그 이슈는 이 문서와 무관하게 진행하지만, 무거운 리뷰 수준(R3)으로의 자동 승격 규칙은
25절이 도착해야 쓸 수 있다.
