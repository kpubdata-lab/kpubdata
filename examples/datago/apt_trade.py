"""datago.apt_trade 예제 — 아파트매매 실거래가 조회 (첫 페이지 조회).

실행 모드:
- ``KPUBDATA_MODE=replay`` — 기록된 fixture로 결정적 실행(API 키 불필요, CI/에이전트용)
- 미지정 — 실호출(``KPUBDATA_DATAGO_API_KEY`` 필요)

파라미터는 spec(``src/kpubdata/specs/datago/apt_trade.yaml``)의 예제
``seoul_gangnam_2024_01`` 와 동일하다. 이 예제 ID는 기존 녹화 파일을 식별한다.
예제 파라미터를 바꾸려면 spec과 ``make record DATASET=datago.apt_trade`` 를 함께.
"""

from __future__ import annotations

import os

from kpubdata import Client


def main() -> None:
    """아파트매매 실거래가 예제 조회를 실행한다."""
    # replay 모드에서는 키 값이 매칭에 쓰이지 않으므로 더미로 대체할 수 있다.
    api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY", "replay-mode")
    client = Client(provider_keys={"datago": api_key}, cache=False)

    dataset = client.dataset("datago.apt_trade")
    batch = dataset.list(LAWD_CD="11110", DEAL_YMD="202401", page=1, page_size=100)

    # 의미 있는 검증: 필수 필드 + 지역 필터 준수(LAWD_CD=11110, 종로구) + 전체 건수
    assert batch.items, "거래 데이터가 최소 1건은 있어야 한다"
    assert batch.total_count and batch.total_count > 0, "전체 건수(totalCount)가 보고되어야 한다"
    first = batch.items[0]
    missing = {"aptNm", "dealAmount", "dealYear", "sggCd"} - set(first)
    assert not missing, f"필수 필드 누락: {sorted(missing)}"
    구역외 = [
        item["sggCd"] for item in batch.items if not str(item.get("sggCd", "")).startswith("11110")
    ]
    assert not 구역외, f"LAWD_CD 필터 위반 항목: {구역외[:3]}"

    print(f"apt_trade 종로구 2024-01: {len(batch.items)}건 / 전체 {batch.total_count}건")
    print(f"첫 거래: {first['umdNm']} {first['aptNm']} {first['dealAmount']}만원")


if __name__ == "__main__":
    main()
