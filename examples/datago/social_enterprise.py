"""datago.social_enterprise 예제 — 사회적기업 인증현황.

실행 모드:
- ``KPUBDATA_MODE=replay`` — 기록된 fixture로 결정적 실행(API 키 불필요)
- 미지정 — 실호출(``KPUBDATA_DATAGO_API_KEY`` 필요)

파라미터는 spec의 예제 ``first_page``와 동일하다.
계열 특이사항: odcloud 계열(items_path = data, 총건수 = matchCount,
페이지 파라미터 page/perPage). data.go.kr serviceKey를 그대로 쓴다.
"""

from __future__ import annotations

import os

from kpubdata import Client


def main() -> None:
    """인증 사회적기업 첫 페이지 예제 조회를 실행한다."""
    api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY", "replay-mode")
    client = Client(provider_keys={"datago": api_key}, cache=False)

    dataset = client.dataset("datago.social_enterprise")
    batch = dataset.list(page=1, page_size=10)

    # 의미 있는 검증: 인증 기업의 식별 구조 + 총건수 보고
    assert batch.items, "인증 기업이 최소 1건은 있어야 한다"
    first = batch.items[0]
    missing = {"entNmV", "certiNumV", "certiIssuD"} - set(first)
    assert not missing, f"필수 인증 필드 누락: {sorted(missing)}"
    assert batch.total_count and batch.total_count > 0, "matchCount가 보고되어야 한다"

    print(f"social_enterprise: {len(batch.items)}건 / 전체 {batch.total_count}건")
    print(f"첫 기업: {first['entNmV']} ({first['certiNumV']}, 인증일 {first['certiIssuD']})")


if __name__ == "__main__":
    main()
