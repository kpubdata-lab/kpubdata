<!--
PR 제목은 Conventional Commits 형식이어야 합니다 — `PR title` 체크가 검사합니다(POLICY 2.1.3).
type: feat fix docs test perf refactor ci build chore style revert — 규칙 정본: docs/governance/POLICY.md 2.1.3
이슈 번호는 제목이 아니라 본문에 적습니다 (Closes #123). squash 병합이 PR 번호를 붙입니다.
예) feat: add KOSIS provider adapter
-->

Closes #<이슈 번호>
<!-- 이슈 없는 PR(의존성 갱신 등)은 이 줄을 지우고, 참조만 남길 땐 Refs #N. -->

## 문제
<!-- 무엇이 잘못됐거나 무엇이 필요한지 — 대부분의 PR은 한두 문장이면 충분하다. -->

## 변경 내용
<!-- 무엇을 어떻게 바꿨는지 -->

## 검증
<!-- 돌린 게이트·테스트와 결과. ruff·mypy·pytest·docs strict 는 CI가 같은 걸 다시 돌리므로, 여기에는 로컬에서만 볼 수 있는 것(실측·재현·스크린샷)을 적는다. -->
<!-- 검증 수준은 뜻을 먼저, 코드는 괄호로: 예 "단위 테스트(V1)", "replay·계약 테스트(V2)". 리뷰 수준도 같다: 예 "작성자가 아닌 사람의 승인이 필요(R3)". 용어표: docs/governance/POLICY.md#codes (POLICY 0.2) -->
