# 기여 가이드

이 문서는 프로젝트 루트의 [CONTRIBUTING.md](https://github.com/kpubdata-lab/kpubdata/blob/main/CONTRIBUTING.md)를 mkdocs 사이트에서 제공하기 위한 래퍼입니다.

전체 기여 가이드(개발 환경 설정, 브랜치 전략, PR 절차, AI 에이전트 워크플로우 등)는 아래 링크를 참고하세요:

👉 **[CONTRIBUTING.md (전체 기여 가이드)](https://github.com/kpubdata-lab/kpubdata/blob/main/CONTRIBUTING.md)**

---

## 빠른 요약

1. **포크 및 클론** → 개인 계정으로 포크 후 로컬에 클론
2. **브랜치 생성** → `feat/issue-<번호>-<설명>` 형태
3. **개발 환경** → `uv sync --extra dev`
4. **품질 검증** → `uv run ruff check . && uv run pytest && uv run mypy src`
5. **PR 생성** → 템플릿에 맞게 작성 후 리뷰 요청

자세한 내용은 루트 [CONTRIBUTING.md](https://github.com/kpubdata-lab/kpubdata/blob/main/CONTRIBUTING.md)를 참고하세요.
