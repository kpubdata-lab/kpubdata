"""Test module for data.go.kr integration tests.

Defines test scenarios and helper functions in ``tests/integration/test_datago_live.py``.
Verifies core flows, exceptions, and edge cases to prevent regressions and validate
the public contract.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timedelta
from importlib.resources import files
from zoneinfo import ZoneInfo

import pytest

from kpubdata.client import Client
from kpubdata.core.models import RecordBatch
from kpubdata.exceptions import AuthError


def _yesterday_kst_ymd() -> str:
    """
    Helper to compute yesterday's date as KST YYYYMMDD string.

    Returns:
        str: Yesterday's date in YYYYMMDD format (KST).

    Raises:
        Exceptions from internal implementation or dependencies may propagate.
    """
    return (datetime.now(ZoneInfo("Asia/Seoul")) - timedelta(days=1)).strftime("%Y%m%d")


def _awaiting_application(dataset_id: str) -> bool:
    """Whether ``dataset_metadata.json`` records the dataset as awaiting its usage application."""
    metadata = json.loads(files("kpubdata").joinpath("dataset_metadata.json").read_text("utf-8"))
    entry = metadata.get(dataset_id, {})
    return isinstance(entry, dict) and entry.get("level") == "application_required"


def _list_or_await_application(dataset_id: str, call: Callable[[], RecordBatch]) -> RecordBatch:
    """Run ``call``; a 403 is an expected failure while the metadata says we await approval.

    A dataset recorded as ``application_required`` has no access for this key yet, so its
    403 is the known state rather than a regression, and must not fail the smoke run
    (#896). The moment the provider answers, the record is stale: the test then fails and
    asks for ``dataset_metadata.json`` to be updated, so an approval cannot go unnoticed.
    A 403 for any other dataset still fails.
    """
    awaiting = _awaiting_application(dataset_id)
    try:
        result = call()
    except AuthError:
        if awaiting:
            pytest.xfail(
                f"{dataset_id} awaits its data.go.kr usage application for this key (application_required)"
            )
        raise
    if awaiting:
        pytest.fail(
            f"{dataset_id} answered, so its usage application was approved: move its level in "
            "dataset_metadata.json off application_required and run the sync scripts"
        )
    return result


def _latest_mid_fcst_kst() -> str:
    """Return the latest KST mid-range forecast publication time (06:00/18:00, -1h delay)."""
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    # Mid-range forecast published at 06:00, 18:00. Account for ~1-hour reflection delay.
    if now.hour >= 19:
        return now.strftime("%Y%m%d") + "1800"
    if now.hour >= 7:
        return now.strftime("%Y%m%d") + "0600"
    # Before 07:00, use yesterday's 18:00 forecast
    yesterday = (now - timedelta(days=1)).strftime("%Y%m%d")
    return yesterday + "1800"


# Verify village forecast scenario.
@pytest.mark.integration
def test_datago_village_fcst(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.village_fcst scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.village_fcst")

    result = ds.list(base_date=_yesterday_kst_ymd(), base_time="2300", nx="55", ny="127")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert isinstance(result.items[0], dict)


# Verify ultra short-range nowcast scenario.
@pytest.mark.integration
def test_datago_ultra_srt_ncst(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.ultra_srt_ncst scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.ultra_srt_ncst")

    result = ds.list(base_date=_yesterday_kst_ymd(), base_time="2300", nx="55", ny="127")

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert isinstance(result.items[0], dict)


@pytest.mark.integration
def test_datago_mid_fcst(require_datago_key: None, live_client: Client) -> None:
    """Call mid-range forecast API with latest KST 06:00 publication time."""
    _ = require_datago_key
    ds = live_client.dataset("datago.mid_fcst")

    result = _list_or_await_application(
        "datago.mid_fcst",
        lambda: ds.list(stnId="109", tmFc=_latest_mid_fcst_kst(), page_size=1),
    )

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert isinstance(result.items[0], dict)


# Verify air quality scenario.
@pytest.mark.integration
def test_datago_air_quality(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.air_quality scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.air_quality")

    result = ds.call_raw("getCtprvnRltmMesureDnsty", sidoName="서울", numOfRows="5")

    assert isinstance(result, dict)
    assert "response" in result


# Verify bus arrival scenario.
@pytest.mark.integration
def test_datago_bus_arrival(
    require_datago_key: None,
    require_realestate_key: None,
    live_client: Client,
) -> None:
    """
    Verify datago.bus_arrival scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        require_realestate_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    _ = require_realestate_key
    ds = live_client.dataset("datago.bus_arrival")

    result = ds.call_raw("getBusArrivalListv2", stationId="228000704", numOfRows="5")

    assert isinstance(result, dict)
    assert "response" in result


# Verify hospital info scenario.
@pytest.mark.integration
def test_datago_hospital_info(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.hospital_info scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.hospital_info")

    result = ds.call_raw("getHospBasisList", numOfRows="5")

    assert isinstance(result, dict)
    assert "response" in result


# Verify apartment trade scenario.
@pytest.mark.integration
def test_datago_apt_trade(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.apt_trade scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.apt_trade")

    result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")

    assert isinstance(result, RecordBatch)
    assert isinstance(result.items, list)


# Verify apartment rent scenario.
@pytest.mark.integration
def test_datago_apt_rent(
    require_datago_key: None,
    require_realestate_key: None,
    live_client: Client,
) -> None:
    """
    Verify datago.apt_rent scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        require_realestate_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    _ = require_realestate_key
    ds = live_client.dataset("datago.apt_rent")

    result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")

    assert isinstance(result, RecordBatch)
    assert isinstance(result.items, list)


# Verify office building trade scenario.
@pytest.mark.integration
def test_datago_offi_trade(
    require_datago_key: None,
    require_realestate_key: None,
    live_client: Client,
) -> None:
    """
    Verify datago.offi_trade scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        require_realestate_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    _ = require_realestate_key
    ds = live_client.dataset("datago.offi_trade")

    result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")

    assert isinstance(result, RecordBatch)
    assert isinstance(result.items, list)


# Verify office building rent scenario.
@pytest.mark.integration
def test_datago_offi_rent(
    require_datago_key: None,
    require_realestate_key: None,
    live_client: Client,
) -> None:
    """
    Verify datago.offi_rent scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        require_realestate_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    _ = require_realestate_key
    ds = live_client.dataset("datago.offi_rent")

    result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")

    assert isinstance(result, RecordBatch)
    assert isinstance(result.items, list)


# Verify rowhouse/studio trade scenario.
@pytest.mark.integration
def test_datago_rh_trade(
    require_datago_key: None,
    require_realestate_key: None,
    live_client: Client,
) -> None:
    """
    Verify datago.rh_trade scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        require_realestate_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    _ = require_realestate_key
    ds = live_client.dataset("datago.rh_trade")

    result = _list_or_await_application(
        "datago.rh_trade", lambda: ds.list(LAWD_CD="11110", DEAL_YMD="202401")
    )

    assert isinstance(result, RecordBatch)
    assert isinstance(result.items, list)


# Verify rowhouse/studio rent scenario.
@pytest.mark.integration
def test_datago_rh_rent(
    require_datago_key: None,
    require_realestate_key: None,
    live_client: Client,
) -> None:
    """
    Verify datago.rh_rent scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        require_realestate_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    _ = require_realestate_key
    ds = live_client.dataset("datago.rh_rent")

    result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")

    assert isinstance(result, RecordBatch)
    assert isinstance(result.items, list)


# Verify subdivision/land trade scenario.
@pytest.mark.integration
def test_datago_sh_trade(
    require_datago_key: None,
    require_realestate_key: None,
    live_client: Client,
) -> None:
    """
    Verify datago.sh_trade scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        require_realestate_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    _ = require_realestate_key
    ds = live_client.dataset("datago.sh_trade")

    result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")

    assert isinstance(result, RecordBatch)
    assert isinstance(result.items, list)


# Verify subdivision/land rent scenario.
@pytest.mark.integration
def test_datago_sh_rent(
    require_datago_key: None,
    require_realestate_key: None,
    live_client: Client,
) -> None:
    """
    Verify datago.sh_rent scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        require_realestate_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    _ = require_realestate_key
    ds = live_client.dataset("datago.sh_rent")

    result = ds.list(LAWD_CD="11110", DEAL_YMD="202401")

    assert isinstance(result, RecordBatch)
    assert isinstance(result.items, list)


# Verify Korean tourism area scenario.
@pytest.mark.integration
def test_datago_tour_kor_area(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.tour_kor_area scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.tour_kor_area")

    result = ds.call_raw(
        "areaBasedList2",
        MobileOS="ETC",
        MobileApp="kpubdata",
        numOfRows="5",
        pageNo="1",
        areaCode="1",
    )

    assert isinstance(result, dict)
    assert "response" in result


# Verify Korean tourism location scenario.
@pytest.mark.integration
def test_datago_tour_kor_location(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.tour_kor_location scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.tour_kor_location")

    result = ds.call_raw(
        "locationBasedList2",
        MobileOS="ETC",
        MobileApp="kpubdata",
        numOfRows="5",
        pageNo="1",
        mapX="126.9784",
        mapY="37.5665",
        radius="1000",
    )

    assert isinstance(result, dict)
    assert "response" in result


# Verify Korean tourism keyword scenario.
@pytest.mark.integration
def test_datago_tour_kor_keyword(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.tour_kor_keyword scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.tour_kor_keyword")

    result = ds.call_raw(
        "searchKeyword2",
        MobileOS="ETC",
        MobileApp="kpubdata",
        numOfRows="5",
        pageNo="1",
        keyword="경복궁",
    )

    assert isinstance(result, dict)
    assert "response" in result


# Verify Korean tourism festival scenario.
@pytest.mark.integration
def test_datago_tour_kor_festival(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.tour_kor_festival scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.tour_kor_festival")

    result = ds.call_raw(
        "searchFestival2",
        MobileOS="ETC",
        MobileApp="kpubdata",
        numOfRows="5",
        pageNo="1",
        eventStartDate="20250101",
    )

    assert isinstance(result, dict)
    assert "response" in result


@pytest.mark.skip(
    reason="External infra issue: see https://github.com/kpubdata-lab/kpubdata/issues/139"
)
def test_datago_metro_fare(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.metro_fare scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.metro_fare")

    result = ds.call_raw(
        "getRltmFare2",
        numOfRows="5",
        pageNo="1",
        dptreStnNm="서울역",
        avrlStnNm="시청",
    )

    assert isinstance(result, dict)
    assert "response" in result


@pytest.mark.skip(
    reason="Blocked by metro_fare upstream SSL issue (#139); params confirmed per #140"
)
def test_datago_metro_path(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.metro_path scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.metro_path")

    result = ds.call_raw(
        "getShtrmPath",
        dptreStnNm="신도림",
        arvlStnNm="서울역",
        searchDt="2026-04-22 13:00:00",
    )

    assert isinstance(result, dict)
    assert "response" in result


@pytest.mark.skip(
    reason="ITS Open API requires a separate apiKey from openapi.its.go.kr "
    "(not data.go.kr serviceKey)"
)
def test_datago_road_traffic(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.road_traffic scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.road_traffic")

    result = ds.call_raw("trafficInfo", type="all", drcType="all")

    assert isinstance(result, dict)
    assert "resultCode" in result


# Verify social enterprise scenario.
@pytest.mark.integration
def test_datago_social_enterprise(require_datago_key: None, live_client: Client) -> None:
    """
    Verify datago.social_enterprise scenario.

    Args:
        require_datago_key (None): Input provided by caller.
        live_client (Client): Input provided by caller.

    Returns:
        None: Test passes if result assertions succeed.

    Raises:
        Exceptions from internal implementation or dependencies may propagate.

    Example:
        Test verifies expected behavior described by test name persists without regression.
    """
    _ = require_datago_key
    ds = live_client.dataset("datago.social_enterprise")

    result = ds.list(page_size=5)

    assert isinstance(result, RecordBatch)
    assert len(result.items) > 0
    assert isinstance(result.items[0], dict)
