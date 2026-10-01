# KPubData 개발 명령 — 품질 게이트(AGENTS.md) + spec 검증 파이프라인(#379)
#
# 자주 쓰는 대상:
#   make test                  # 단위·계약(replay) 테스트 — integration 제외(기본 addopts)
#   make verify                # 전체 spec: 스키마 검증 + fixture 무결성 + replay 계약
#   make verify DATASET=datago.apt_trade   # 단일 데이터셋
#   make record DATASET=datago.apt_trade   # spec examples 실호출 fixture 기록 (API 키 필요)
#   make quality               # AGENTS.md 품질 게이트 전체

DATASET ?=

.PHONY: help test lint typecheck format format-check build docs quality \
        record verify verify-all list-datasets replay-test

help:
	@grep -E "^#   make [a-z-]+" Makefile | sed 's/^#   //' | sed 's/  \+/ — /'

test:
	uv run pytest

lint:
	uv run ruff check .
	uv run ruff format --check .

typecheck:
	uv run mypy src

format:
	uv run ruff format .
	uv run ruff check --fix .

build:
	uv run python -m build

docs:
	uv run --extra docs mkdocs build --strict

quality: lint typecheck test build docs
	@echo "품질 게이트 전체 통과"

# --- spec 검증 파이프라인 (#379) ---------------------------------------------

list-datasets:
	uv run python scripts/record.py --list

record:
	@if [ -z "$(DATASET)" ]; then echo "사용법: make record DATASET=datago.apt_trade (목록: make list-datasets)"; exit 2; fi
	uv run python scripts/record.py $(DATASET)

# verify 는 읽기만 해야 한다. record.py 가 fixtures_root 와 무관하게 spec 의
# last_verified 를 덮어쓴 적이 있고(#497), 그때는 아무도 알아채지 못했다.
#
# 예전 guard 는 실행 후 `git status --porcelain -- src/` 가 비어 있는지만 봤다.
# 그러면 **실행 전부터 dirty 인 파일과 verify 가 만든 변경을 구분하지 못한다** —
# spec 을 편집하는 중에 verify 를 돌리면 거짓 실패가 나고, 거짓 실패를 내는
# 도구는 건너뛰게 되어 결국 원래 잡으려던 mutation 이 통과한다 (#513).
#
# 이제 실행 전후로 내용 스냅샷을 떠서 차이만 실패로 본다.
#
# 레시피는 한 셸 블록이다. 주석을 블록 안에 넣으면 그 줄이 ``\`` 로 이어지지
# 않아 make 가 셸을 쪼개고, ``set +e`` 가 뒤쪽에 적용되지 않는다.
#
# mktemp 템플릿은 명시한다 — ``mktemp -t <prefix>`` 는 BSD(macOS)에서만 동작하고
# GNU coreutils 는 XXXXXX 로 끝나기를 요구해 Linux 러너에서 죽었다.
# 래칫 기준 ref 의 로컬 기본값은 origin/main 이다 (#766). 명시적으로 주지
# 않으면 verify 는 fail-closed 이므로, 셸 전개 기본값으로 여기서 채운다.
verify:
	@set +e; \
	snapshot=$$(mktemp "$${TMPDIR:-/tmp}/kpubdata-verify.XXXXXX"); \
	trap 'rm -f "$$snapshot"' EXIT; \
	uv run python scripts/verify_guard.py snapshot > "$$snapshot" || exit 2; \
	if [ -n "$(DATASET)" ]; then \
		KPUBDATA_BASELINE_BASE=$${KPUBDATA_BASELINE_BASE:-origin/main} uv run python scripts/verify_spec.py --dataset $(DATASET); \
	else \
		KPUBDATA_BASELINE_BASE=$${KPUBDATA_BASELINE_BASE:-origin/main} uv run python scripts/verify_spec.py; \
	fi; \
	verify_status=$$?; \
	uv run python scripts/verify_guard.py compare "$$snapshot"; \
	guard_status=$$?; \
	if [ $$guard_status -ne 0 ]; then exit $$guard_status; fi; \
	exit $$verify_status

verify-all: verify

# replay 모드 검증: spec 파이프라인 테스트를 재생 모드로 통과시킨다.
# (전역 replay는 자체 mock을 쓰는 기존 테스트와 무관하지 않으므로 범위를 좁힌다)
replay-test:
	KPUBDATA_MODE=replay uv run pytest tests/unit/test_verify_pipeline.py tests/unit/core
