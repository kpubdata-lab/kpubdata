# 데이터셋 예제

> 이 문서는 `examples/` 스크립트에서 자동 생성했다 (`scripts/gen_docs_examples.py`).
> 직접 편집하지 않는다 — 스크립트를 고치고 다시 생성한다.

각 예제는 `KPUBDATA_MODE=replay` 환경에서 API 키 없이 결정적으로 실행된다
(`make verify` 4단계). 실호출은 해당 Provider API 키 설정 후 그대로 실행하면 된다.


## datago


### `datago.air_station`

[소스](https://github.com/kpubdata-lab/kpubdata/blob/main/examples/datago/air_station.py)

```python
"""datago.air_station 예제 — 측정소별 실시간 대기측정정보.

실행 모드:
- ``KPUBDATA_MODE=replay`` — 기록된 fixture로 결정적 실행(API 키 불필요)
- 미지정 — 실호출(``KPUBDATA_DATAGO_API_KEY`` 필요)

파라미터는 spec의 예제 ``baengnyeong_daily``와 동일하다.
계열 특이사항: items가 네이스트 배열로 온다(items_path = response.body.items).
"""

from __future__ import annotations

import os

from kpubdata import Client


def main() -> None:
    """백령도 측정소 일평균 측정정보 예제 조회를 실행한다."""
    api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY", "replay-mode")
    client = Client(provider_keys={"datago": api_key}, cache=False)

    dataset = client.dataset("datago.air_station")
    batch = dataset.list(station="백령도", term="daily", page=1, page_size=10)

    # 의미 있는 검증: 측정 항목 구조 + 측정 시각 존재
    # pm25는 행에 따라 키 자체가 없는 선택 필드 — 필수 단언에서 제외(실측 함정)
    assert batch.items, "측정값이 최소 1건은 있어야 한다"
    first = batch.items[0]
    missing = {"dataTime", "pm10Value", "khaiValue"} - set(first)
    assert not missing, f"필수 측정 필드 누락: {sorted(missing)}"
    assert batch.total_count and batch.total_count > 0, "총건수가 보고되어야 한다"

    print(f"air_station 백령도(daily): {len(batch.items)}건 / 전체 {batch.total_count}건")
    pm25 = first.get("pm25Value", "N/A")  # 선택 필드
    print(
        f"최근 측정({first['dataTime']}): PM10={first['pm10Value']}, "
        f"PM2.5={pm25}, 통합대기={first['khaiValue']}"
    )


if __name__ == "__main__":
    main()
```


### `datago.apt_trade`

[소스](https://github.com/kpubdata-lab/kpubdata/blob/main/examples/datago/apt_trade.py)

```python
"""datago.apt_trade 예제 — 아파트매매 실거래가 조회 (골든 예제: 페이지네이션).

실행 모드:
- ``KPUBDATA_MODE=replay`` — 기록된 fixture로 결정적 실행(API 키 불필요, CI/에이전트용)
- 미지정 — 실호출(``KPUBDATA_DATAGO_API_KEY`` 필요)

파라미터는 spec(``src/kpubdata/specs/datago/apt_trade.yaml``)의 예제
``seoul_gangnam_2024_01`` 와 동일하다 — replay가 fixture를 찾는 조건이다.
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

    # 의미 있는 검증: 필수 필드 + 필터 준수(LAWD_CD=11110 강남) + 페이지네이션
    assert batch.items, "거래 데이터가 최소 1건은 있어야 한다"
    assert batch.total_count and batch.total_count > 0, "전체 건수(totalCount)가 보고되어야 한다"
    first = batch.items[0]
    missing = {"aptNm", "dealAmount", "dealYear", "sggCd"} - set(first)
    assert not missing, f"필수 필드 누락: {sorted(missing)}"
    구역외 = [
        item["sggCd"] for item in batch.items if not str(item.get("sggCd", "")).startswith("11110")
    ]
    assert not 구역외, f"LAWD_CD 필터 위반 항목: {구역외[:3]}"

    print(f"apt_trade 강남 2024-01: {len(batch.items)}건 / 전체 {batch.total_count}건")
    print(f"첫 거래: {first['umdNm']} {first['aptNm']} {first['dealAmount']}만원")


if __name__ == "__main__":
    main()
```


### `datago.bus_arrival`

[소스](https://github.com/kpubdata-lab/kpubdata/blob/main/examples/datago/bus_arrival.py)

```python
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
```


### `datago.hospital_info`

[소스](https://github.com/kpubdata-lab/kpubdata/blob/main/examples/datago/hospital_info.py)

```python
"""datago.hospital_info 예제 — 병원정보서비스 조회 (골든 예제: 단순).

실행 모드:
- ``KPUBDATA_MODE=replay`` — 기록된 fixture로 결정적 실행(API 키 불필요)
- 미지정 — 실호출(``KPUBDATA_DATAGO_API_KEY`` 필요)

파라미터는 spec의 예제 ``default``(필수 필터 없음, 10건)와 동일하다.
"""

from __future__ import annotations

import os

from kpubdata import Client


def main() -> None:
    """병원 기본정보 예제 조회를 실행한다."""
    api_key = os.environ.get("KPUBDATA_DATAGO_API_KEY", "replay-mode")
    client = Client(provider_keys={"datago": api_key}, cache=False)

    dataset = client.dataset("datago.hospital_info")
    batch = dataset.list(page=1, page_size=10)

    # 의미 있는 검증: 필수 필터가 없어도 구조는 온전해야 한다
    assert batch.items, "병원 데이터가 최소 1건은 있어야 한다"
    assert batch.total_count and batch.total_count > 0, "전국 병원 총건수가 보고되어야 한다"
    first = batch.items[0]
    assert "병원명" in first or "yadmNm" in first, f"병원명 필드 누락: {sorted(first)[:8]}"

    print(f"hospital_info: {len(batch.items)}건 / 전체 {batch.total_count:,}건")
    이름후보 = first.get("병원명") or first.get("yadmNm")
    print(f"첫 병원: {이름후보} ({first.get('시도명', first.get('sidoCdNm', '?'))})")


if __name__ == "__main__":
    main()
```


### `datago.social_enterprise`

[소스](https://github.com/kpubdata-lab/kpubdata/blob/main/examples/datago/social_enterprise.py)

```python
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
```


### `datago.ultra_srt_fcst`

[소스](https://github.com/kpubdata-lab/kpubdata/blob/main/examples/datago/ultra_srt_fcst.py)

```python
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
```


### `datago.village_fcst`

[소스](https://github.com/kpubdata-lab/kpubdata/blob/main/examples/datago/village_fcst.py)

```python
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
        base_date="20260908", base_time="2300", nx=55, ny=127, page=1, page_size=100
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
```

