"""Test module.

This module defines tests and helpers for the surrounding test suite.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.capability import Operation
from kpubdata.core.models import Query
from kpubdata.exceptions import (
    ConfigError,
    DatasetNotFoundError,
    InvalidRequestError,
    ProviderResponseError,
)
from kpubdata.providers._common import build_dataset_ref
from kpubdata.providers.krx.adapter import KrxAdapter


class _ExposedKrxAdapter(KrxAdapter):
    """Tests for _ExposedKrxAdapter.

    This class groups related test cases and helpers for _ExposedKrxAdapter.
    """

    def load_pykrx_for_test(self) -> object:
        """load_pykrx_for_test

        Validates the scenario described by the test name.
        """
        return self._load_pykrx()


def _fixture_path(name: str) -> Path:
    """_fixture_path

    Validates the scenario described by the test name.
    """
    return Path(__file__).resolve().parents[3] / "fixtures" / "krx" / name


def _load_snapshot(name: str) -> list[dict[str, object]]:
    """_load_snapshot

    Validates the scenario described by the test name.
    """
    return json.loads(_fixture_path(name).read_text(encoding="utf-8"))


def _build_adapter() -> KrxAdapter:
    """_build_adapter

    Validates the scenario described by the test name.
    """
    return KrxAdapter(config=KPubDataConfig())


def _set_pykrx(adapter: KrxAdapter, **stock_methods: object) -> None:
    """_set_pykrx

    Validates the scenario described by the test name.
    """
    adapter._pykrx = SimpleNamespace(stock=SimpleNamespace(**stock_methods))


def _kospi_index_frame() -> pd.DataFrame:
    """_kospi_index_frame

    Validates the scenario described by the test name.
    """
    return pd.DataFrame(
        {
            "시가": [2650.0, 2661.0, 2644.0, 2632.0, 2629.0],
            "고가": [2675.0, 2678.0, 2662.0, 2644.0, 2665.0],
            "저가": [2641.0, 2649.0, 2620.0, 2614.0, 2622.0],
            "종가": [2669.0, 2651.0, 2634.0, 2620.0, 2660.0],
            "거래량": [410000000, 420000000, 430000000, 440000000, 450000000],
            "거래대금": [8100000000000, 8200000000000, 8300000000000, 8400000000000, 8500000000000],
            "상장시가총액": [
                2100000000000,
                2110000000000,
                2120000000000,
                2130000000000,
                2140000000000,
            ],
        },
        index=pd.DatetimeIndex(
            [
                "2024-01-02",
                "2024-01-03",
                "2024-01-04",
                "2024-01-05",
                "2024-01-08",
            ],
            name="날짜",
        ),
    )


def _investor_frame(multiplier: int) -> pd.DataFrame:
    """_investor_frame

    Validates the scenario described by the test name.
    """
    return (
        pd.DataFrame(
            {
                "개인": [100, 110, 120, 130, 140],
                "기관합계": [50, 55, 60, 65, 70],
                "외국인합계": [30, 35, 40, 45, 50],
                "기타법인": [20, 25, 30, 35, 40],
                "전체": [0, 0, 0, 0, 0],
            },
            index=pd.DatetimeIndex(
                [
                    "2024-01-02",
                    "2024-01-03",
                    "2024-01-04",
                    "2024-01-05",
                    "2024-01-08",
                ],
                name="날짜",
            ),
        )
        * multiplier
    )


def _market_fundamental_frame(day: str) -> pd.DataFrame:
    """_market_fundamental_frame

    Validates the scenario described by the test name.
    """
    rows = {
        "20240102": [(100.0, 1.0, 2.0, 1000, 5000), (200.0, 2.0, 4.0, 2000, 7000)],
        "20240103": [(110.0, 1.1, 2.2, 1100, 5100), (210.0, 2.1, 4.2, 2100, 7100)],
        "20240104": [(120.0, 1.2, 2.4, 1200, 5200), (220.0, 2.2, 4.4, 2200, 7200)],
        "20240105": [(130.0, 1.3, 2.6, 1300, 5300), (230.0, 2.3, 4.6, 2300, 7300)],
        "20240108": [(140.0, 1.4, 2.8, 1400, 5400), (240.0, 2.4, 4.8, 2400, 7400)],
    }
    day_rows = rows[day]
    return pd.DataFrame(
        {
            "PER": [row[0] for row in day_rows],
            "PBR": [row[1] for row in day_rows],
            "DIV": [row[2] for row in day_rows],
            "EPS": [row[3] for row in day_rows],
            "BPS": [row[4] for row in day_rows],
            "DPS": [100, 200],
        },
        index=pd.Index(["000001", "000002"], name="티커"),
    )


# test catalogue includes three krx datasets Describes the scenario verified by the test.
def test_catalogue_includes_three_krx_datasets() -> None:
    """
    test catalogue includes three krx datasets Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()

    datasets = adapter.list_datasets()

    assert [dataset.id for dataset in datasets] == [
        "krx.kospi_index",
        "krx.investor_flow",
        "krx.market_valuation",
    ]
    assert all(
        dataset.description is not None and "KRX" in dataset.description for dataset in datasets
    )


# test get dataset unknown key raises dataset not found Describes the scenario verified by the test.
def test_get_dataset_unknown_key_raises_dataset_not_found() -> None:
    """
    test get dataset unknown key raises dataset not found Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()

    with pytest.raises(DatasetNotFoundError, match="krx.unknown"):
        _ = adapter.get_dataset("unknown")


# test query records kospi index normalizes snapshot Describes the scenario verified by the test.
def test_query_records_kospi_index_normalizes_snapshot() -> None:
    """
    test query records kospi index normalizes snapshot Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("kospi_index")
    calls: list[tuple[str, str, str]] = []

    def _get_index_ohlcv(start_date: str, end_date: str, ticker: str) -> pd.DataFrame:
        """_get_index_ohlcv

        Validates the scenario described by the test name.
        """
        calls.append((start_date, end_date, ticker))
        return _kospi_index_frame()

    _set_pykrx(adapter, get_index_ohlcv=_get_index_ohlcv)

    batch = adapter.query_records(dataset, Query(start_date="20240102", end_date="20240108"))

    assert batch.items == _load_snapshot("kospi_index_5days.json")
    assert batch.total_count == 5
    assert calls == [("20240102", "20240108", "1001")]


# test query records kospi index supports custom ticker filter Describes the scenario verified by the test.
def test_query_records_kospi_index_supports_custom_ticker_filter() -> None:
    """
    test query records kospi index supports custom ticker filter Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("kospi_index")
    tickers: list[str] = []

    def _get_index_ohlcv(start_date: str, end_date: str, ticker: str) -> pd.DataFrame:
        """_get_index_ohlcv

        Validates the scenario described by the test name.
        """
        _ = start_date, end_date
        tickers.append(ticker)
        return _kospi_index_frame()

    _set_pykrx(adapter, get_index_ohlcv=_get_index_ohlcv)

    _ = adapter.query_records(
        dataset,
        Query(start_date="20240102", end_date="20240108", filters={"ticker": "2001"}),
    )

    assert tickers == ["2001"]


# test call raw kospi index returns raw dataframe records Describes the scenario verified by the test.
def test_call_raw_kospi_index_returns_raw_dataframe_records() -> None:
    """
    test call raw kospi index returns raw dataframe records Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("kospi_index")
    _set_pykrx(adapter, get_index_ohlcv=lambda *_args: _kospi_index_frame())

    payload = adapter.call_raw(
        dataset,
        "list",
        {"start_date": "20240102", "end_date": "20240108"},
    )

    assert payload == [
        {
            "날짜": "2024-01-02",
            "시가": 2650.0,
            "고가": 2675.0,
            "저가": 2641.0,
            "종가": 2669.0,
            "거래량": 410000000,
            "거래대금": 8100000000000,
            "상장시가총액": 2100000000000,
        },
        {
            "날짜": "2024-01-03",
            "시가": 2661.0,
            "고가": 2678.0,
            "저가": 2649.0,
            "종가": 2651.0,
            "거래량": 420000000,
            "거래대금": 8200000000000,
            "상장시가총액": 2110000000000,
        },
        {
            "날짜": "2024-01-04",
            "시가": 2644.0,
            "고가": 2662.0,
            "저가": 2620.0,
            "종가": 2634.0,
            "거래량": 430000000,
            "거래대금": 8300000000000,
            "상장시가총액": 2120000000000,
        },
        {
            "날짜": "2024-01-05",
            "시가": 2632.0,
            "고가": 2644.0,
            "저가": 2614.0,
            "종가": 2620.0,
            "거래량": 440000000,
            "거래대금": 8400000000000,
            "상장시가총액": 2130000000000,
        },
        {
            "날짜": "2024-01-08",
            "시가": 2629.0,
            "고가": 2665.0,
            "저가": 2622.0,
            "종가": 2660.0,
            "거래량": 450000000,
            "거래대금": 8500000000000,
            "상장시가총액": 2140000000000,
        },
    ]


# test query records kospi index uses get index ohlcv by date fallback Describes the scenario verified by the test.
def test_query_records_kospi_index_uses_get_index_ohlcv_by_date_fallback() -> None:
    """
    test query records kospi index uses get index ohlcv by date fallback Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("kospi_index")
    fallback_calls: list[tuple[str, str, str, bool]] = []

    def _raise_index_error(*_args: object) -> pd.DataFrame:
        """_raise_index_error

        Validates the scenario described by the test name.
        """
        raise ValueError("primary failed")

    def _get_index_ohlcv_by_date(
        start_date: str,
        end_date: str,
        ticker: str,
        *,
        name_display: bool,
    ) -> pd.DataFrame:
        """Validates the scenario described by the test name."""
        fallback_calls.append((start_date, end_date, ticker, name_display))
        return _kospi_index_frame()

    _set_pykrx(
        adapter,
        get_index_ohlcv=_raise_index_error,
        get_index_ohlcv_by_date=_get_index_ohlcv_by_date,
    )

    batch = adapter.query_records(dataset, Query(start_date="20240102", end_date="20240108"))

    assert batch.items == _load_snapshot("kospi_index_5days.json")
    assert fallback_calls == [("20240102", "20240108", "1001", False)]


# test query records investor flow normalizes snapshot Describes the scenario verified by the test.
def test_query_records_investor_flow_normalizes_snapshot() -> None:
    """
    test query records investor flow normalizes snapshot Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("investor_flow")
    calls: list[tuple[str, str, str, str]] = []

    def _get_market_trading_value_by_date(
        start_date: str,
        end_date: str,
        market: str,
        *,
        on: str = "순매수",
        **_kwargs: object,
    ) -> pd.DataFrame:
        """Validates the scenario described by the test name."""
        calls.append((start_date, end_date, market, on))
        frames = {
            "매수": _investor_frame(10),
            "매도": _investor_frame(6),
        }
        return frames[on]

    _set_pykrx(adapter, get_market_trading_value_by_date=_get_market_trading_value_by_date)

    batch = adapter.query_records(dataset, Query(start_date="20240102", end_date="20240108"))

    assert batch.items == _load_snapshot("investor_flow_5days.json")
    assert batch.total_count == 20
    assert calls == [
        ("20240102", "20240108", "KOSPI", "매수"),
        ("20240102", "20240108", "KOSPI", "매도"),
    ]


# test query records investor flow supports custom market filter Describes the scenario verified by the test.
def test_query_records_investor_flow_supports_custom_market_filter() -> None:
    """
    test query records investor flow supports custom market filter Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("investor_flow")
    markets: list[str] = []

    def _get_market_trading_value_by_date(
        start_date: str,
        end_date: str,
        market: str,
        *,
        on: str = "순매수",
        **_kwargs: object,
    ) -> pd.DataFrame:
        """Validates the scenario described by the test name."""
        _ = start_date, end_date, on
        markets.append(market)
        return _investor_frame(1)

    _set_pykrx(adapter, get_market_trading_value_by_date=_get_market_trading_value_by_date)

    _ = adapter.query_records(
        dataset,
        Query(start_date="20240102", end_date="20240108", filters={"market": "KOSDAQ"}),
    )

    assert markets == ["KOSDAQ", "KOSDAQ"]


# test call raw investor flow uses requested on parameter Describes the scenario verified by the test.
def test_call_raw_investor_flow_uses_requested_on_parameter() -> None:
    """
    test call raw investor flow uses requested on parameter Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("investor_flow")
    calls: list[tuple[str, str, str, str]] = []

    def _get_market_trading_value_by_date(
        start_date: str,
        end_date: str,
        market: str,
        *,
        on: str = "순매수",
        **_kwargs: object,
    ) -> pd.DataFrame:
        """Validates the scenario described by the test name."""
        calls.append((start_date, end_date, market, on))
        return _investor_frame(1)

    _set_pykrx(adapter, get_market_trading_value_by_date=_get_market_trading_value_by_date)

    payload = adapter.call_raw(
        dataset,
        "list",
        {"start_date": "20240102", "end_date": "20240108", "market": "KOSDAQ", "on": "매수"},
    )

    assert calls == [("20240102", "20240108", "KOSDAQ", "매수")]
    assert isinstance(payload, list)
    assert payload[0]["날짜"] == "2024-01-02"


# test call raw empty dataframe returns empty list Describes the scenario verified by the test.
def test_call_raw_empty_dataframe_returns_empty_list() -> None:
    """
    test call raw empty dataframe returns empty list Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("investor_flow")
    _set_pykrx(adapter, get_market_trading_value_by_date=lambda *_args, **_kwargs: pd.DataFrame())

    payload = adapter.call_raw(
        dataset,
        "list",
        {"start_date": "20240102", "end_date": "20240108"},
    )

    assert payload == []


# test query records market valuation normalizes snapshot Describes the scenario verified by the test.
def test_query_records_market_valuation_normalizes_snapshot() -> None:
    """
    test query records market valuation normalizes snapshot Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("market_valuation")
    days_called: list[str] = []

    def _get_market_fundamental_by_ticker(date: str, market: str = "KOSPI") -> pd.DataFrame:
        """_get_market_fundamental_by_ticker

        Validates the scenario described by the test name.
        """
        _ = market
        days_called.append(date)
        if date in {"20240106", "20240107"}:
            return pd.DataFrame(columns=["PER", "PBR", "DIV", "EPS", "BPS", "DPS"])
        return _market_fundamental_frame(date)

    _set_pykrx(
        adapter,
        get_market_fundamental_by_ticker=_get_market_fundamental_by_ticker,
    )

    batch = adapter.query_records(dataset, Query(start_date="20240102", end_date="20240108"))

    assert batch.items == _load_snapshot("market_valuation_5days.json")
    assert batch.total_count == 5
    assert days_called == [
        "20240102",
        "20240103",
        "20240104",
        "20240105",
        "20240106",
        "20240107",
        "20240108",
    ]


# test query records market valuation supports custom market filter Describes the scenario verified by the test.
def test_query_records_market_valuation_supports_custom_market_filter() -> None:
    """
    test query records market valuation supports custom market filter Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("market_valuation")
    markets: list[str] = []

    def _get_market_fundamental_by_ticker(date: str, market: str = "KOSPI") -> pd.DataFrame:
        """_get_market_fundamental_by_ticker

        Validates the scenario described by the test name.
        """
        _ = date
        markets.append(market)
        return _market_fundamental_frame("20240102")

    _set_pykrx(adapter, get_market_fundamental_by_ticker=_get_market_fundamental_by_ticker)

    batch = adapter.query_records(
        dataset,
        Query(start_date="20240102", end_date="20240102", filters={"market": "KOSDAQ"}),
    )

    assert batch.items[0]["market"] == "KOSDAQ"
    assert markets == ["KOSDAQ"]


# test market valuation skips days with missing columns and zero rows Describes the scenario verified by the test.
def test_market_valuation_skips_days_with_missing_columns_and_zero_rows() -> None:
    """
    test market valuation skips days with missing columns and zero rows Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("market_valuation")

    def _get_market_fundamental_by_ticker(date: str, market: str = "KOSPI") -> pd.DataFrame:
        """_get_market_fundamental_by_ticker

        Validates the scenario described by the test name.
        """
        _ = market
        if date == "20240102":
            return pd.DataFrame(columns=["PER"])
        if date == "20240103":
            return pd.DataFrame(
                {
                    "PER": [0.0],
                    "PBR": [0.0],
                    "DIV": [0.0],
                    "EPS": [0.0],
                    "BPS": [0.0],
                },
                index=pd.Index(["000001"], name="티커"),
            )
        return _market_fundamental_frame(date)

    _set_pykrx(adapter, get_market_fundamental_by_ticker=_get_market_fundamental_by_ticker)

    batch = adapter.query_records(dataset, Query(start_date="20240102", end_date="20240104"))

    assert [item["date"] for item in batch.items] == ["2024-01-04"]


# test market valuation returns empty when all days are skipped Describes the scenario verified by the test.
def test_market_valuation_returns_empty_when_all_days_are_skipped() -> None:
    """
    test market valuation returns empty when all days are skipped Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("market_valuation")

    def _get_market_fundamental_by_ticker(date: str, market: str = "KOSPI") -> pd.DataFrame:
        """_get_market_fundamental_by_ticker

        Validates the scenario described by the test name.
        """
        _ = date, market
        return pd.DataFrame(columns=["PER", "PBR", "DIV", "EPS", "BPS"])

    _set_pykrx(adapter, get_market_fundamental_by_ticker=_get_market_fundamental_by_ticker)

    batch = adapter.query_records(dataset, Query(start_date="20240102", end_date="20240103"))

    assert batch.items == []


# test fetch market valuation returns empty frame when aggregation is empty Describes the scenario verified by the test.
def test_fetch_market_valuation_returns_empty_frame_when_aggregation_is_empty() -> None:
    """
    test fetch market valuation returns empty frame when aggregation is empty Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("market_valuation")
    _set_pykrx(adapter, get_market_fundamental_by_ticker=lambda *_args, **_kwargs: pd.DataFrame())

    frame = adapter._fetch_market_valuation(
        dataset, Query(start_date="20240102", end_date="20240103")
    )

    assert frame.empty


# test fetch market valuation returns passthrough frame when columns are missing Describes the scenario verified by the test.
def test_fetch_market_valuation_returns_passthrough_frame_when_columns_are_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    test fetch market valuation returns passthrough frame when columns are missing Validates the scenario described by the test name.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("market_valuation")

    def _fake_fetch_by_day(
        _stock: object,
        _start_date: str,
        _end_date: str,
        _market: str,
    ) -> pd.DataFrame:
        """Validates the scenario described by the test name."""
        return pd.DataFrame({"date": [pd.Timestamp("2024-01-02")], "close": [100.0]}).set_index(
            "date"
        )

    monkeypatch.setattr(adapter, "_fetch_market_valuation_by_day", _fake_fetch_by_day)

    frame = adapter._fetch_market_valuation(
        dataset, Query(start_date="20240102", end_date="20240102")
    )

    assert list(frame.columns) == ["close"]


# test empty dataframe returns empty record batch Describes the scenario verified by the test.
@pytest.mark.parametrize(
    ("dataset_key", "methods"),
    [
        (
            "kospi_index",
            {"get_index_ohlcv": lambda *_args: pd.DataFrame()},
        ),
        (
            "investor_flow",
            {"get_market_trading_value_by_date": lambda *_args, **_kwargs: pd.DataFrame()},
        ),
        (
            "market_valuation",
            {"get_market_fundamental_by_ticker": lambda *_args, **_kwargs: pd.DataFrame()},
        ),
    ],
)
def test_empty_dataframe_returns_empty_record_batch(
    dataset_key: str,
    methods: dict[str, object],
) -> None:
    """
    test empty dataframe returns empty record batch Validates the scenario described by the test name.

    Args:
        dataset_key (str): Input parameter.
        methods (dict[str, object]): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset(dataset_key)
    _set_pykrx(adapter, **methods)

    batch = adapter.query_records(dataset, Query(start_date="20240102", end_date="20240108"))

    assert batch.items == []
    assert batch.total_count == 0
    assert batch.next_page is None


# test pykrx exception is wrapped with cause Describes the scenario verified by the test.
@pytest.mark.parametrize(
    ("dataset_key", "methods"),
    [
        (
            "kospi_index",
            {"get_index_ohlcv": lambda *_args: (_ for _ in ()).throw(RuntimeError("boom"))},
        ),
        (
            "investor_flow",
            {
                "get_market_trading_value_by_date": lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("boom")
                )
            },
        ),
        (
            "market_valuation",
            {
                "get_market_fundamental_by_ticker": lambda *_args, **_kwargs: (_ for _ in ()).throw(
                    RuntimeError("boom")
                )
            },
        ),
    ],
)
def test_pykrx_exception_is_wrapped_with_cause(
    dataset_key: str,
    methods: dict[str, object],
) -> None:
    """
    test pykrx exception is wrapped with cause Validates the scenario described by the test name.

    Args:
        dataset_key (str): Input parameter.
        methods (dict[str, object]): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset(dataset_key)
    _set_pykrx(adapter, **methods)

    with pytest.raises(ProviderResponseError, match="KRX backend error: boom") as excinfo:
        _ = adapter.query_records(dataset, Query(start_date="20240102", end_date="20240108"))

    assert excinfo.value.provider == "krx"
    assert excinfo.value.dataset_id == dataset.id
    assert isinstance(excinfo.value.__cause__, RuntimeError)


# test get schema builds from catalogue metadata Describes the scenario verified by the test.
def test_get_schema_builds_from_catalogue_metadata() -> None:
    """
    test get schema builds from catalogue metadata Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("market_valuation")

    schema = adapter.get_schema(dataset)

    assert schema is not None
    assert [field.name for field in schema.fields] == [
        "date",
        "market",
        "per",
        "pbr",
        "dividend_yield",
        "eps",
        "bps",
    ]


# test search datasets matches tags and description Describes the scenario verified by the test.
def test_search_datasets_matches_tags_and_description() -> None:
    """
    test search datasets matches tags and description Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()

    assert [dataset.id for dataset in adapter.search_datasets("valuation")] == [
        "krx.market_valuation"
    ]
    assert [dataset.id for dataset in adapter.search_datasets("ohlcv")] == ["krx.kospi_index"]


# test query records uses query extra for filters Describes the scenario verified by the test.
def test_query_records_uses_query_extra_for_filters() -> None:
    """
    test query records uses query extra for filters Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("investor_flow")
    calls: list[tuple[str, str, str, str]] = []

    def _get_market_trading_value_by_date(
        start_date: str,
        end_date: str,
        market: str,
        *,
        on: str = "순매수",
        **_kwargs: object,
    ) -> pd.DataFrame:
        """Validates the scenario described by the test name."""
        calls.append((start_date, end_date, market, on))
        return _investor_frame(1)

    _set_pykrx(adapter, get_market_trading_value_by_date=_get_market_trading_value_by_date)

    _ = adapter.query_records(
        dataset,
        Query(start_date="20240102", end_date="20240108", extra={"market": "KONEX"}),
    )

    assert calls == [
        ("20240102", "20240108", "KONEX", "매수"),
        ("20240102", "20240108", "KONEX", "매도"),
    ]


# test query records requires start and end dates Describes the scenario verified by the test.
def test_query_records_requires_start_and_end_dates() -> None:
    """
    test query records requires start and end dates Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = adapter.get_dataset("kospi_index")

    with pytest.raises(InvalidRequestError, match="start_date and end_date"):
        _ = adapter.query_records(dataset, Query())


# test query records raises when default query param metadata is missing Describes the scenario verified by the test.
def test_query_records_raises_when_default_query_param_metadata_is_missing() -> None:
    """
    test query records raises when default query param metadata is missing Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    dataset = build_dataset_ref(
        "krx",
        {
            "dataset_key": "kospi_index",
            "name": "Broken KRX dataset",
            "representation": "other",
            "description": "KRX broken dataset",
            "operations": [Operation.LIST.value],
        },
    )
    adapter = KrxAdapter(config=KPubDataConfig(), catalogue=[dataset])
    _set_pykrx(adapter, get_index_ohlcv=lambda *_args: _kospi_index_frame())

    with pytest.raises(ProviderResponseError, match="default_query_params.ticker"):
        _ = adapter.query_records(dataset, Query(start_date="20240102", end_date="20240108"))


# test aggregate market valuation frame handles date column and passthrough Describes the scenario verified by the test.
def test_aggregate_market_valuation_frame_handles_date_column_and_passthrough() -> None:
    """
    test aggregate market valuation frame handles date column and passthrough Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dated = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02")],
            "PER": [100.0],
            "PBR": [1.0],
            "DIV": [2.0],
            "EPS": [1000.0],
            "BPS": [5000.0],
        }
    )
    passthrough = pd.DataFrame({"PER": [100.0]})

    dated_result = adapter._aggregate_market_valuation_frame(dated)
    passthrough_result = adapter._aggregate_market_valuation_frame(passthrough)

    assert isinstance(dated_result.index, pd.DatetimeIndex)
    assert passthrough_result is passthrough


# test combine investor frames skips missing columns and can return empty Describes the scenario verified by the test.
def test_combine_investor_frames_skips_missing_columns_and_can_return_empty() -> None:
    """
    test combine investor frames skips missing columns and can return empty Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    buy_frame = pd.DataFrame({"개인": [100]}, index=pd.DatetimeIndex(["2024-01-02"], name="날짜"))
    sell_frame = pd.DataFrame({"전체": [0]}, index=pd.DatetimeIndex(["2024-01-02"], name="날짜"))

    frame = adapter._combine_investor_frames(buy_frame, sell_frame)

    assert frame.empty


# test format date handles iso string and invalid value Describes the scenario verified by the test.
def test_format_date_handles_iso_string_and_invalid_value() -> None:
    """
    test format date handles iso string and invalid value Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    assert KrxAdapter._format_date("2024-01-02") == "2024-01-02"
    assert KrxAdapter._format_date("20240102") == "2024-01-02"
    assert KrxAdapter._format_date(pd.Timestamp("2024-01-02")) == "2024-01-02"

    with pytest.raises(ProviderResponseError, match="Invalid KRX date value"):
        _ = KrxAdapter._format_date(123)


# test to python value formats timestamps Describes the scenario verified by the test.
def test_to_python_value_formats_timestamps() -> None:
    """
    test to python value formats timestamps Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()

    assert adapter._to_python_value(pd.Timestamp("2024-01-02")) == "2024-01-02"
    assert adapter._to_python_value(1) == 1


# test coerce numeric value handles numeric and invalid values Describes the scenario verified by the test.
def test_coerce_numeric_value_handles_numeric_and_invalid_values() -> None:
    """
    test coerce numeric value handles numeric and invalid values Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    assert KrxAdapter._coerce_numeric_value(1) == 1
    assert KrxAdapter._coerce_numeric_value(1.5) == 1.5
    assert KrxAdapter._coerce_numeric_value(True) == 1

    with pytest.raises(ProviderResponseError, match="Invalid KRX numeric value"):
        _ = KrxAdapter._coerce_numeric_value("1")


# test dispatch dataframe raises dataset not found for unknown handler Describes the scenario verified by the test.
def test_dispatch_dataframe_raises_dataset_not_found_for_unknown_handler() -> None:
    """
    test dispatch dataframe raises dataset not found for unknown handler Validates the scenario described by the test name.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _build_adapter()
    dataset = build_dataset_ref(
        "krx",
        {
            "dataset_key": "unknown",
            "name": "Unknown KRX dataset",
            "representation": "other",
            "description": "KRX unknown dataset",
            "operations": [Operation.LIST.value],
        },
    )

    with pytest.raises(DatasetNotFoundError, match="Dataset not found: krx.unknown"):
        _ = adapter._dispatch_dataframe(dataset, Query(), {})


# test load pykrx raises install hint when dependency missing Describes the scenario verified by the test.
def test_load_pykrx_raises_install_hint_when_dependency_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    test load pykrx raises install hint when dependency missing Validates the scenario described by the test name.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _ExposedKrxAdapter(config=KPubDataConfig())

    def _raise_import_error() -> SimpleNamespace:
        """_raise_import_error

        Validates the scenario described by the test name.
        """
        raise ImportError("pykrx is unavailable")

    monkeypatch.setattr(adapter, "_import_pykrx", _raise_import_error)

    with pytest.raises(ConfigError, match=r"Install kpubdata\[krx\] to enable KRX provider"):
        _ = adapter.load_pykrx_for_test()


# test load pykrx returns imported module Describes the scenario verified by the test.
def test_load_pykrx_returns_imported_module(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    test load pykrx returns imported module Validates the scenario described by the test name.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    adapter = _ExposedKrxAdapter(config=KPubDataConfig())
    pykrx_module = SimpleNamespace(stock=SimpleNamespace())

    def _import_module(name: str) -> SimpleNamespace:
        """_import_module

        Validates the scenario described by the test name.
        """
        assert name == "pykrx"
        return pykrx_module

    monkeypatch.setattr(importlib, "import_module", _import_module)

    assert adapter.load_pykrx_for_test() is pykrx_module


# test adapter is constructible without krx api key Describes the scenario verified by the test.
def test_adapter_is_constructible_without_krx_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    test adapter is constructible without krx api key Validates the scenario described by the test name.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    monkeypatch.delenv("KPUBDATA_KRX_API_KEY", raising=False)

    adapter = KrxAdapter(config=KPubDataConfig.from_env())

    assert adapter.name == "krx"
    assert adapter.requires_api_key is False


# test adapter construction does not import pykrx Describes the scenario verified by the test.
def test_adapter_construction_does_not_import_pykrx(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    test adapter construction does not import pykrx Validates the scenario described by the test name.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input parameter.

    Returns:
        None: Result.

    Raises:
        Exceptions propagated."""
    monkeypatch.delitem(sys.modules, "pykrx", raising=False)

    _ = KrxAdapter(config=KPubDataConfig())

    assert "pykrx" not in sys.modules


class TestCallRawRejectsUnknownOperations:
    """Tests for TestCallRawRejectsUnknownOperations.

    This class groups related test cases and helpers for TestCallRawRejectsUnknownOperations.
    """

    def test_an_unknown_operation_is_rejected(self) -> None:
        adapter = KrxAdapter()
        dataset = adapter.get_dataset("kospi_index")

        with pytest.raises(InvalidRequestError, match="no raw operation"):
            _ = adapter.call_raw(dataset, "detail", {})

    def test_the_error_names_what_is_supported(self) -> None:
        adapter = KrxAdapter()
        dataset = adapter.get_dataset("kospi_index")

        with pytest.raises(InvalidRequestError, match="list"):
            _ = adapter.call_raw(dataset, "typo", {})

    def test_an_empty_operation_is_still_accepted(self) -> None:
        """test_an_empty_operation_is_still_accepted

        Validates the scenario described by the test name.
        """
        adapter = KrxAdapter()
        dataset = adapter.get_dataset("kospi_index")
        _set_pykrx(adapter, get_index_ohlcv=lambda *_args: _kospi_index_frame())

        payload = adapter.call_raw(dataset, "", {"start_date": "20240102", "end_date": "20240108"})

        assert isinstance(payload, list)
