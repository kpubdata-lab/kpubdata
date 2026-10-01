"""datago.bus_arrival 예제 — 경기도 버스도착정보.

실행 모드:
- ``KPUBDATA_MODE=replay`` — 기록된 fixture로 결정적 실행(API 키 불필요)
- 미지정 — 실호출(``KPUBDATA_DATAGO_API_KEY`` 필요)

파라미터는 spec의 예제 ``station_200000078``과 동일하다.
계열 특이사항: 경기도 msgHeader/msgBody envelope(resultCode 0 = 정상),
정류장 단위 조회라 총건수와 페이지네이션이 없다.
"""

from __future__ import annotations

import os

from kpubdata import Client


def main() -> None:
    """정류장 200000078의 도착 예정 버스 예제 조회를 실행한다."""
    api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY", "replay-mode")
    client = Client(provider_keys={"datago": api_key}, cache=False)

    dataset = client.dataset("datago.bus_arrival")
    batch = dataset.list(station="200000078", page=1, page_size=10)

    # 의미 있는 검증: 도착 예정 버스의 노선·차량 구조.
    # 실측 함정: 해당 없음·운행 종료 시 flag="PASS"와 빈 문자열 필드로 온다 —
    # 필수 단언은 항상 채워지는 식별자 3종으로만 한다.
    assert batch.items, "도착 목록이 최소 1건은 있어야 한다"
    first = batch.items[0]
    missing = {"routeId", "routeName", "stationId"} - set(first)
    assert not missing, f"필수 노선/정류장 필드 누락: {sorted(missing)}"

    print(f"bus_arrival 정류장 200000078: {len(batch.items)}대 도착 예정")
    for bus in batch.items[:3]:
        minutes = bus.get("predictTime1") or "N/A"
        dest = bus.get("routeDestName", "?")
        plate = bus.get("plateNo1", "?")
        print(f"  {bus['routeName']} → {dest} ({minutes}분 후, {plate})")


if __name__ == "__main__":
    main()
