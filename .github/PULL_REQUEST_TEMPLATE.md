<!--
PR 제목은 Conventional Commits 형식이어야 합니다 — `PR title` 체크가 검사합니다(POLICY 2.1.3).
type: feat fix docs test perf refactor ci build chore style revert — 규칙 정본: docs/governance/POLICY.md 2.1.3
이슈 번호는 제목이 아니라 본문에 적습니다 (Closes #123). squash 병합이 PR 번호를 붙입니다.
예) feat: add KOSIS provider adapter
-->

## 요약
<!-- 이 PR이 무엇을, 왜 바꾸는지 1~3문장으로 설명하세요. -->

## 변경 내용
<!-- 주요 변경 사항을 항목으로 나열하세요. -->
-

## 관련 이슈
<!-- 예) Closes #123, Refs #456 -->

## 검증
<!-- 어떻게 검증했는지 구체적으로 적으세요. -->
- [ ] Ruff lint / format 통과
- [ ] mypy 타입 체크 통과
- [ ] 테스트 통과 (`pytest`)
- [ ] 문서 변경 시 docs strict 빌드 통과 (해당 시)
- [ ] 신규 provider adapter는 계약/통합 테스트를 포함 (해당 시)

## 체크리스트
- [ ] 기능 브랜치에서 작업했으며 `main`에 직접 push하지 않았다
- [ ] PR 제목이 POLICY 2.1.3 을 따른다 (영어, 100자 이하, 제목에 이슈 번호 없음 — 본문에 `Closes #N`)
- [ ] 공개 API 변경 시 문서/CHANGELOG를 갱신했다
- [ ] 사용자 노출 기능 변경 시 문서를 분류해 갱신했다: 제품 계약→PRD, 향후 의도→ROADMAP, 릴리스 변경→CHANGELOG (해당 시)
