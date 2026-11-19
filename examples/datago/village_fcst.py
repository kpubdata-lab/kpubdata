"""datago.village_fcst 예제 — 동네예보 조회 (골든 예제: XML 응답).

실행 모드:
- ``KPUBDATA_MODE=replay`` — 기록된 fixture로 결정적 실행(API 키 불필요)
- 미지정 — 실호출(``KPUBDATA_DATAGO_API_KEY`` 필요)

파라미터는 spec의 예제 ``seoul_default``(전일 23시 발표, 서울 격자)와 동일하다.
날짜가 오래되면 ``make record DATASET=datago.village_fcst`` 로 예제와 fixture를
갱신한다(기상청은 최근 발표만 응답).
"""

from __future__ import annotations

import os

from kpubdata import Client


def main() -> None:
    """동네예보 예제 조회를 실행한다."""
    api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY", "replay-mode")
    client = Client(provider_keys={"datago": api_key}, cache=False)

    dataset = client.dataset("datago.village_fcst")
    batch = dataset.list(
        base_date="20261118", base_time="2300", nx=55, ny=127, page=1, page_size=100
    )

    # 의미 있는 검증: 예보 카테고리 구조
    assert batch.items, "예보 항목이 최소 1개는 있어야 한다"
    categories = {item.get("category") for item in batch.items}
    assert "TMP" in categories or "PCP" in categories, (
        f"기온/강수 카테고리 누락: {sorted(categories)}"
    )
    assert batch.total_count and batch.total_count > 0, "총 예보 항목수가 보고되어야 한다"

    온도 = next(
        (item.get("fcstValue") for item in batch.items if item.get("category") == "TMP"), None
    )
    print(f"village_fcst 서울(55,127): {len(batch.items)}항목 / 전체 {batch.total_count}항목")
    print(f"기온(TMP): {온도}℃")


if __name__ == "__main__":
    main()
