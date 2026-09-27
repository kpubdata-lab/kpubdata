"""Batch example script generator — stamps out examples from recorded specs using a template.

Usage:
    uv run python scripts/gen_example_scripts.py --provider localdata

Generation rules:
- Only specs with recorded fixtures
  (``tests/fixtures/{provider}/{key}/default.meta.json``)
- Structure-verification asserts: total count reported + items dict shape
  (an honest baseline for batch output)
- An ``auto-generated`` marker in the header → ``gen_docs_examples.py``
  excludes it from documentation
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from kpubdata.core.spec import discover_specs

REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_DIR = REPO_ROOT / "examples"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

_TEMPLATE = '''# auto-generated: docs-exclude
"""{dataset_id} 예제 — 자동 생성(배치 전환).

실행 모드:
- ``KPUBDATA_MODE=replay`` — fixture 재생(키 불필요) / 미지정 — 실호출
- 파라미터는 spec의 예제 ``{example_name}``와 동일(replay 매칭 계약)
- 필드 심화 검증은 후속 보강 대상 (배치 기준선: 구조·총건수 계약)
"""

from __future__ import annotations

import os

from kpubdata import Client


def main() -> None:
    """{dataset_id} 기본 조회를 실행한다."""
    api_key = os.environ.get("KPUBDATA_{env_key}_API_KEY", "replay-mode")
    client = Client(provider_keys={{"datago": api_key}}, cache=False)

    dataset = client.dataset("{dataset_id}")
    batch = dataset.list({list_args})

    # 구조 검증: envelope 계약(총건수 보고) + 레코드 형태
    assert batch.total_count is not None, "totalCount가 보고되어야 한다"
    assert isinstance(batch.items, list), "items는 리스트여야 한다"
    assert all(isinstance(item, dict) for item in batch.items), "레코드는 dict여야 한다"

    print(f"{dataset_id}: {{len(batch.items)}}건 / 전체 {{batch.total_count}}건")


if __name__ == "__main__":
    main()
'''


def generate(provider: str) -> list[str]:
    """Generate example scripts for recorded specs."""
    created: list[str] = []
    for spec in discover_specs():
        if spec.provider != provider:
            continue
        fixture_dir = FIXTURES_DIR / provider / spec.dataset_key
        if not fixture_dir.is_dir() or not list(fixture_dir.glob("*.meta.json")):
            continue
        out = EXAMPLES_DIR / provider / f"{spec.dataset_key}.py"
        if out.exists():
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        example = spec.examples[0] if spec.examples else None
        if example is None:
            continue
        call_parts = [f"{key}={value!r}" for key, value in example.params.items()]
        if example.page is not None:
            call_parts.append(f"page={example.page}")
        if example.page_size is not None:
            call_parts.append(f"page_size={example.page_size}")
        content = _TEMPLATE.format(
            dataset_id=spec.id,
            env_key="DATAGO",
            example_name=example.name,
            list_args=", ".join(call_parts),
        )
        out.write_text(content, encoding="utf-8")
        created.append(spec.id)
    return created


def main(argv: list[str] | None = None) -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="배치 예제 생성")
    parser.add_argument("--provider", required=True)
    args = parser.parse_args(argv)
    created = generate(args.provider)
    print(f"[{args.provider}] 예제 {len(created)}건 생성")
    return 0


if __name__ == "__main__":
    sys.exit(main())
