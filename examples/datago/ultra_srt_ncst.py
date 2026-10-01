# auto-generated: docs-exclude
"""datago.ultra_srt_ncst 예제 — 자동 생성(배치 전환).

실행 모드:
- ``KPUBDATA_MODE=replay`` — fixture 재생(키 불필요) / 미지정 — 실호출
- 파라미터는 spec의 예제 ``seoul_0600``와 동일(replay 매칭 계약)
- 필드 심화 검증은 후속 보강 대상 (배치 기준선: 구조·총건수 계약)
"""

from __future__ import annotations

import os

from kpubdata import Client


def main() -> None:
    """datago.ultra_srt_ncst 기본 조회를 실행한다."""
    api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY", "replay-mode")
    client = Client(provider_keys={"datago": api_key}, cache=False)

    dataset = client.dataset("datago.ultra_srt_ncst")
    batch = dataset.list(
        base_date="20261001", base_time="0600", nx=55, ny=127, page=1, page_size=10
    )

    # 구조 검증: envelope 계약(총건수 보고) + 레코드 형태
    assert batch.total_count is not None, "totalCount가 보고되어야 한다"
    assert isinstance(batch.items, list), "items는 리스트여야 한다"
    assert all(isinstance(item, dict) for item in batch.items), "레코드는 dict여야 한다"

    print(f"datago.ultra_srt_ncst: {len(batch.items)}건 / 전체 {batch.total_count}건")


if __name__ == "__main__":
    main()
