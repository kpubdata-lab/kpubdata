"""Test module.

This file defines test scenarios and helper objects at ``tests/contract/test_krx.py````.
It verifies core flows, exceptions, and edge cases for regression prevention and
public contract validation.
"""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from kpubdata import Client
from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.providers.krx.adapter import KrxAdapter
from kpubdata.providers.manifest import BUILTIN_PROVIDERS
from tests.contract.provider_adapter import ProviderAdapterContract


def _index_frame() -> pd.DataFrame:
    """
    Internal helper for index frame handling.

    Returns:
        pd.DataFrame: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may
        propagate unchanged.
    """
    return pd.DataFrame(
        {
            "시가": [2650.0],
            "고가": [2675.0],
            "저가": [2641.0],
            "종가": [2669.0],
            "거래량": [410000000],
            "거래대금": [8100000000000],
            "상장시가총액": [2100000000000],
        },
        index=pd.DatetimeIndex(["2024-01-02"], name="날짜"),
    )


def _build_adapter() -> KrxAdapter:
    """
    Internal helper to build adapter.

    Returns:
        KrxAdapter: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may
        propagate unchanged.
    """
    adapter = KrxAdapter(config=KPubDataConfig())
    adapter._pykrx = SimpleNamespace(
        stock=SimpleNamespace(
            get_index_ohlcv=lambda *_args: _index_frame(),
            get_market_trading_value_by_date=lambda *_args, **_kwargs: pd.DataFrame(
                {
                    "개인": [100],
                    "기관합계": [50],
                    "외국인합계": [30],
                    "기타법인": [20],
                    "전체": [0],
                },
                index=pd.DatetimeIndex(["2024-01-02"], name="날짜"),
            ),
            get_market_fundamental=lambda *_args, **_kwargs: pd.DataFrame(
                {
                    "PER": [150.0],
                    "PBR": [1.5],
                    "DIV": [3.0],
                    "EPS": [1500.0],
                    "BPS": [6000.0],
                },
                index=pd.DatetimeIndex(["2024-01-02"], name="날짜"),
            ),
        )
    )
    return adapter


class TestKrxAdapterContract(ProviderAdapterContract):
    """
    TestKrxAdapterContract class that encapsulates its role.

    This class manages state and behavior within ``tests/contract/test_krx.py`` module. TestKrxAdapterContractKey methods: adapter, valid_dataset_key, invalid_dataset_key, sample_dataset, sample_query..

    Attribute descriptions:
        Properties defined in constructor and class body are reused by
        subordinate methods as common context.
    """

    @pytest.fixture()
    def adapter(self) -> ProviderAdapter:
        """
        Performs adapter fixture operation.

        Returns:
            ProviderAdapter: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return _build_adapter()

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        """
        Returns valid dataset key.

        Returns:
            str: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return "kospi_index"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        """
        inReturns valid dataset key.

        Returns:
            str: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: ProviderAdapter) -> DatasetRef:
        """
        Returns sample dataset.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.

        Returns:
            DatasetRef: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return adapter.get_dataset("kospi_index")

    @pytest.fixture()
    def sample_query(self) -> Query:
        """
        Returns sample query.

        Returns:
            Query: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return Query(start_date="20240102", end_date="20240102")

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        """
        Returns raw operation parameters.

        Returns:
            tuple[str, dict[str, object]]: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return ("list", {"start_date": "20240102", "end_date": "20240102"})


# test krx provider is registered in builtin manifest test scenario.
def test_krx_provider_is_registered_in_builtin_manifest() -> None:
    """
    Verifies KRX provider is registered in builtin manifest.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    assert ("krx", "kpubdata.providers.krx", "KrxAdapter") in BUILTIN_PROVIDERS


# test client from env lists three krx datasets test scenario.
def test_client_from_env_lists_three_krx_datasets(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Verifies client from env lists three KRX datasets.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    monkeypatch.delenv("KPUBDATA_KRX_API_KEY", raising=False)
    client = Client.from_env()

    datasets = client.datasets.list(provider="krx")

    assert [dataset.id for dataset in datasets] == [
        "krx.kospi_index",
        "krx.investor_flow",
        "krx.market_valuation",
    ]


# test client search finds krx datasets by description test scenario.
def test_client_search_finds_krx_datasets_by_description() -> None:
    """
    Verifies client search finds KRX datasets by description.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    client = Client()

    matches = client.datasets.search("investor", provider="krx")

    assert any(dataset.id == "krx.investor_flow" for dataset in matches)


# test client can resolve krx schema test scenario.
def test_client_can_resolve_krx_schema() -> None:
    """
    Verifies client can resolve KRX schema.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    client = Client()
    schema = client.dataset("krx.market_valuation").schema()

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


# test krx adapter declares authless provider test scenario.
def test_krx_adapter_declares_authless_provider() -> None:
    """
    Verifies KRX adapter declares as authless provider.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    assert KrxAdapter(config=KPubDataConfig()).requires_api_key is False


# test client iter authenticated providers excludes krx and includes bok test scenario.
def test_client_iter_authenticated_providers_excludes_krx_and_includes_bok() -> None:
    """
    Verifies authenticated providers iter excludes KRX but includes BOK.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    client = Client()

    provider_names = {adapter.name for adapter in client.iter_authenticated_providers()}

    assert "krx" not in provider_names
    assert "bok" in provider_names


def test_krx_datasets_contain_license_note() -> None:
    """Preserves license_note in KRX dataset raw_metadata."""
    client = Client()

    for ds_id in ("krx.kospi_index", "krx.investor_flow", "krx.market_valuation"):
        ds_ref = next(d for d in client.datasets.list(provider="krx") if d.id == ds_id)
        note = ds_ref.raw_metadata.get("license_note")
        assert note is not None, f"{ds_id}에 license_note가 없습니다"
        assert "KRX" in note or "재배포" in note, (
            f"{ds_id}의 license_note가 경고를 포함하지 않습니다"
        )
