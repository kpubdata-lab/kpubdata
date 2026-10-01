"""datago.ultra_srt_fcst 예제 — 초단기예보 조회.

실행 모드:
- ``KPUBDATA_MODE=replay`` — 기록된 fixture로 결정적 실행(API 키 불필요)
- 미지정 — 실호출(``KPUBDATA_DATAGO_API_KEY`` 필요)

파라미터는 spec의 예제 ``seoul_0600``과 동일하다. 발표 시각(base_time)은
30분 간격이며 오래된 값은 응답하지 않는다 — `make record`로 갱신.
초단기 카테고리는 단기(TMP/PCP)와 달리 T1H/RN1을 쓴다(함정 주의).
"""

from __future__ import annotations

import os

from kpubdata import Client


def main() -> None:
    """서울 격자 초단기예보 예제 조회를 실행한다."""
    api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY", "replay-mode")
    client = Client(provider_keys={"datago": api_key}, cache=False)

    dataset = client.dataset("datago.ultra_srt_fcst")
    batch = dataset.list(
        base_date="20261001", base_time="0600", nx=55, ny=127, page=1, page_size=50
    )

    # 의미 있는 검증: 초단기 카테고리 구조 + 예보 필드
    assert batch.items, "예보 항목이 최소 1개는 있어야 한다"
    categories = {item.get("category") for item in batch.items}
    assert "T1H" in categories or "RN1" in categories, (
        f"기온/강수 카테고리 누락: {sorted(categories)}"
    )
    first = batch.items[0]
    missing = {"baseDate", "category", "fcstTime", "fcstValue"} - set(first)
    assert not missing, f"필수 필드 누락: {sorted(missing)}"
    assert batch.total_count and batch.total_count > 0, "총 예보 항목수가 보고되어야 한다"

    온도 = next(
        (item.get("fcstValue") for item in batch.items if item.get("category") == "T1H"), None
    )
    print(f"ultra_srt_fcst 서울(55,127): {len(batch.items)}항목 / 전체 {batch.total_count}항목")
    print(f"기온(T1H): {온도}℃")


if __name__ == "__main__":
    main()
