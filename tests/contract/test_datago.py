"""Test module.

This file defines test scenarios and helper objects at ``tests/contract/test_datago.py````.
It verifies core flows, exceptions, and edge cases for regression prevention and
public contract validation.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.capability import Operation, PaginationMode
from kpubdata.core.models import DatasetRef, Query
from kpubdata.providers.datago.adapter import DataGoAdapter
from kpubdata.transport.http import HttpTransport
from tests.contract.provider_adapter import ProviderAdapterContract


def _fixture_path(name: str) -> Path:
    """
    Internal helper for fixture path handling.

    Args:
        name (str): Input value provided by caller.

    Returns:
        Path: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may
        propagate unchanged.
    """
    return Path(__file__).resolve().parents[1] / "fixtures" / "datago" / name


def _load_fixture_bytes(name: str) -> bytes:
    """
    Internal helper for load fixture bytes handling.

    Args:
        name (str): Input value provided by caller.

    Returns:
        bytes: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may
        propagate unchanged.
    """
    return _fixture_path(name).read_bytes()


class _FakeResponse:
    """
    _FakeResponse class that encapsulates its role.

    This class manages state and behavior within ``tests/contract/test_datago.py`` module. _FakeResponseKey methods: __init__..

    Attribute descriptions:
        Properties defined in constructor and class body are reused by
        subordinate methods as common context.
    """

    def __init__(self, data: bytes, content_type: str = "application/json") -> None:
        """
        Initializes internal state for the object.

        Args:
            data (bytes): Input value provided by caller.
            content_type (str): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        self.headers: dict[str, str] = {"content-type": content_type}
        self.content: bytes = data
        self.text: str = data.decode("utf-8")


class _FixtureTransport:
    """
    _FixtureTransport class that encapsulates its role.

    This class manages state and behavior within ``tests/contract/test_datago.py`` module. _FixtureTransportKey methods: __init__, request..

    Attribute descriptions:
        Properties defined in constructor and class body are reused by
        subordinate methods as common context.
    """

    def __init__(self, fixture_names: list[str]) -> None:
        """
        Initializes internal state for the object.

        Args:
            fixture_names (list[str]): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        self._responses: list[_FakeResponse] = [
            _FakeResponse(_load_fixture_bytes(name)) for name in fixture_names
        ]
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        """
        Performs HTTP request operation.

        Args:
            method (str): Input value provided by caller.
            url (str): Input value provided by caller.
            **kwargs (object): Input value provided by caller.

        Returns:
            _FakeResponse: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No fixture responses remaining")
        return self._responses.pop(0)


def _build_adapter(fixture_names: list[str]) -> DataGoAdapter:
    """
    Internal helper to build adapter.

    Args:
        fixture_names (list[str]): Input value provided by caller.

    Returns:
        DataGoAdapter: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may
        propagate unchanged.
    """
    transport = _FixtureTransport(fixture_names)
    config = KPubDataConfig(provider_keys={"datago": "test-key"})
    return DataGoAdapter(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )


class TestDataGoAdapterContract(ProviderAdapterContract):
    """
    TestDataGoAdapterContract class that encapsulates its role.

    This class manages state and behavior within ``tests/contract/test_datago.py`` module. TestDataGoAdapterContractKey methods: adapter, valid_dataset_key, invalid_dataset_key, sample_dataset, sample_query..

    Attribute descriptions:
        Properties defined in constructor and class body are reused by
        subordinate methods as common context.
    """

    @pytest.fixture()
    def adapter(self) -> DataGoAdapter:
        """
        Performs adapter fixture operation.

        Returns:
            DataGoAdapter: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return _build_adapter(["success_single_page.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        """
        Returns valid dataset key.

        Returns:
            str: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return "metro_fare"

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
    def sample_dataset(self, adapter: DataGoAdapter) -> DatasetRef:
        """
        Returns sample dataset.

        Args:
            adapter (DataGoAdapter): Input value provided by caller.

        Returns:
            DatasetRef: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return adapter.get_dataset("metro_fare")

    @pytest.fixture()
    def sample_query(self) -> Query:
        """
        Returns sample query.

        Returns:
            Query: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return Query()

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        """
        Returns raw operation parameters.

        Returns:
            tuple[str, dict[str, object]]: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may propagate unchanged.
        """
        return ("getVilageFcst", {})


# test dur usjnt taboo dataset contract metadata test scenario.
def test_dur_usjnt_taboo_dataset_contract_metadata() -> None:
    """
    Verifies DUR USJNT taboo dataset contract metadata.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_usjnt_taboo.json"])

    dataset = adapter.get_dataset("dur_usjnt_taboo")

    assert dataset.id == "datago.dur_usjnt_taboo"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


# test dur usjnt taboo dataset contract query and raw test scenario.
def test_dur_usjnt_taboo_dataset_contract_query_and_raw() -> None:
    """
    Verifies DUR USJNT taboo dataset query and raw contract.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_usjnt_taboo.json", "success_dur_usjnt_taboo.json"])
    dataset = adapter.get_dataset("dur_usjnt_taboo")

    batch = adapter.query_records(dataset, Query(filters={"itemName": "샘플"}))
    raw = adapter.call_raw(dataset, "getUsjntTabooInfoList03", {"itemName": "샘플"})

    assert batch.dataset is dataset
    assert len(batch.items) == 2
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


# test dur older adult caution dataset contract metadata test scenario.
def test_dur_older_adult_caution_dataset_contract_metadata() -> None:
    """
    Verifies DUR older adult caution dataset contract metadata.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_older_adult_caution.json"])

    dataset = adapter.get_dataset("dur_older_adult_caution")

    assert dataset.id == "datago.dur_older_adult_caution"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


# test dur older adult caution dataset contract query and raw test scenario.
def test_dur_older_adult_caution_dataset_contract_query_and_raw() -> None:
    """
    Verifies DUR older adult caution dataset query and raw contract.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(
        [
            "success_dur_older_adult_caution.json",
            "success_dur_older_adult_caution.json",
        ]
    )
    dataset = adapter.get_dataset("dur_older_adult_caution")

    batch = adapter.query_records(dataset, Query(filters={"itemName": "샘플"}))
    raw = adapter.call_raw(dataset, "getOdsnAtentInfoList03", {"itemName": "샘플"})

    assert batch.dataset is dataset
    assert len(batch.items) == 2
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


# test dur product info dataset contract metadata test scenario.
def test_dur_product_info_dataset_contract_metadata() -> None:
    """
    Verifies DUR product info dataset contract metadata.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_product_info.json"])

    dataset = adapter.get_dataset("dur_product_info")

    assert dataset.id == "datago.dur_product_info"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


# test dur product info dataset contract query and raw test scenario.
def test_dur_product_info_dataset_contract_query_and_raw() -> None:
    """
    Verifies DUR product info dataset query and raw contract.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(
        [
            "success_dur_product_info.json",
            "success_dur_product_info.json",
        ]
    )
    dataset = adapter.get_dataset("dur_product_info")

    batch = adapter.query_records(dataset, Query(filters={"itemName": "샘플"}))
    raw = adapter.call_raw(dataset, "getDurPrdlstInfoList03", {"itemName": "샘플"})

    assert batch.dataset is dataset
    assert len(batch.items) == 2
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


# test dur age taboo dataset contract metadata test scenario.
def test_dur_age_taboo_dataset_contract_metadata() -> None:
    """
    Verifies DUR age taboo dataset contract metadata.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_age_taboo.json"])

    dataset = adapter.get_dataset("dur_age_taboo")

    assert dataset.id == "datago.dur_age_taboo"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


# test dur age taboo dataset contract query and raw test scenario.
def test_dur_age_taboo_dataset_contract_query_and_raw() -> None:
    """
    Verifies DUR age taboo dataset query and raw contract.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_age_taboo.json", "success_dur_age_taboo.json"])
    dataset = adapter.get_dataset("dur_age_taboo")

    batch = adapter.query_records(dataset, Query(filters={"itemName": "샘플"}))
    raw = adapter.call_raw(dataset, "getSpcifyAgrdeTabooInfoList03", {"itemName": "샘플"})

    assert batch.dataset is dataset
    assert len(batch.items) == 2
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


# test dur dosage caution dataset contract metadata test scenario.
def test_dur_dosage_caution_dataset_contract_metadata() -> None:
    """
    Verifies DUR dosage caution dataset contract metadata.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_dosage_caution.json"])

    dataset = adapter.get_dataset("dur_dosage_caution")

    assert dataset.id == "datago.dur_dosage_caution"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


# test dur dosage caution dataset contract query and raw test scenario.
def test_dur_dosage_caution_dataset_contract_query_and_raw() -> None:
    """
    Verifies DUR dosage caution dataset query and raw contract.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(
        [
            "success_dur_dosage_caution.json",
            "success_dur_dosage_caution.json",
        ]
    )
    dataset = adapter.get_dataset("dur_dosage_caution")

    batch = adapter.query_records(dataset, Query(filters={"itemName": "샘플"}))
    raw = adapter.call_raw(dataset, "getCpctyAtentInfoList03", {"itemName": "샘플"})

    assert batch.dataset is dataset
    assert len(batch.items) == 2
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


# test dur medication period caution dataset contract metadata test scenario.
def test_dur_medication_period_caution_dataset_contract_metadata() -> None:
    """
    Verifies DUR medication period caution dataset contract metadata.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_medication_period_caution.json"])

    dataset = adapter.get_dataset("dur_medication_period_caution")

    assert dataset.id == "datago.dur_medication_period_caution"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


# test dur medication period caution dataset contract query and raw test scenario.
def test_dur_medication_period_caution_dataset_contract_query_and_raw() -> None:
    """
    Verifies DUR medication period caution dataset query and raw contract.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(
        [
            "success_dur_medication_period_caution.json",
            "success_dur_medication_period_caution.json",
        ]
    )
    dataset = adapter.get_dataset("dur_medication_period_caution")

    batch = adapter.query_records(dataset, Query(filters={"itemName": "샘플"}))
    raw = adapter.call_raw(dataset, "getMdctnPdAtentInfoList03", {"itemName": "샘플"})

    assert batch.dataset is dataset
    assert len(batch.items) == 2
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


# test dur efficacy duplication dataset contract metadata test scenario.
def test_dur_efficacy_duplication_dataset_contract_metadata() -> None:
    """
    Verifies DUR efficacy duplication dataset contract metadata.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_efficacy_duplication.json"])

    dataset = adapter.get_dataset("dur_efficacy_duplication")

    assert dataset.id == "datago.dur_efficacy_duplication"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


# test dur efficacy duplication dataset contract query and raw test scenario.
def test_dur_efficacy_duplication_dataset_contract_query_and_raw() -> None:
    """
    Verifies DUR efficacy duplication dataset query and raw contract.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(
        [
            "success_dur_efficacy_duplication.json",
            "success_dur_efficacy_duplication.json",
        ]
    )
    dataset = adapter.get_dataset("dur_efficacy_duplication")

    batch = adapter.query_records(dataset, Query(filters={"itemName": "샘플"}))
    raw = adapter.call_raw(dataset, "getEfcyDplctInfoList03", {"itemName": "샘플"})

    assert batch.dataset is dataset
    assert len(batch.items) == 2
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


# test dur er tablet split caution dataset contract metadata test scenario.
def test_dur_er_tablet_split_caution_dataset_contract_metadata() -> None:
    """
    Verifies DUR ER tablet split caution dataset contract metadata.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_er_tablet_split_caution.json"])

    dataset = adapter.get_dataset("dur_er_tablet_split_caution")

    assert dataset.id == "datago.dur_er_tablet_split_caution"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


# test dur er tablet split caution dataset contract query and raw test scenario.
def test_dur_er_tablet_split_caution_dataset_contract_query_and_raw() -> None:
    """
    Verifies DUR ER tablet split caution dataset query and raw contract.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(
        [
            "success_dur_er_tablet_split_caution.json",
            "success_dur_er_tablet_split_caution.json",
        ]
    )
    dataset = adapter.get_dataset("dur_er_tablet_split_caution")

    batch = adapter.query_records(dataset, Query(filters={"itemName": "샘플"}))
    raw = adapter.call_raw(
        dataset,
        "getSeobangjeongPartitnAtentInfoList03",
        {"itemName": "샘플"},
    )

    assert batch.dataset is dataset
    assert len(batch.items) == 2
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


# test dur pregnancy taboo dataset contract metadata test scenario.
def test_dur_pregnancy_taboo_dataset_contract_metadata() -> None:
    """
    Verifies DUR pregnancy taboo dataset contract metadata.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_dur_pregnancy_taboo.json"])

    dataset = adapter.get_dataset("dur_pregnancy_taboo")

    assert dataset.id == "datago.dur_pregnancy_taboo"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


# test dur pregnancy taboo dataset contract query and raw test scenario.
def test_dur_pregnancy_taboo_dataset_contract_query_and_raw() -> None:
    """
    Verifies DUR pregnancy taboo dataset query and raw contract.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(
        [
            "success_dur_pregnancy_taboo.json",
            "success_dur_pregnancy_taboo.json",
        ]
    )
    dataset = adapter.get_dataset("dur_pregnancy_taboo")

    batch = adapter.query_records(dataset, Query(filters={"itemName": "샘플"}))
    raw = adapter.call_raw(dataset, "getPwnmTabooInfoList03", {"itemName": "샘플"})

    assert batch.dataset is dataset
    assert len(batch.items) == 2
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


# test agri price dataset contract metadata test scenario.
def test_agri_price_dataset_contract_metadata() -> None:
    """
    Verifies agricultural price dataset contract metadata.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(["success_agri_price.json"])

    dataset = adapter.get_dataset("agri_price")

    assert dataset.id == "datago.agri_price"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


# test agri price dataset contract query and raw test scenario.
def test_agri_price_dataset_contract_query_and_raw() -> None:
    """
    Verifies agricultural price dataset query and raw contract.

    Returns:
        None: Computation result or return value from subordinate call.

    Raises:
        Exception from implementation or subordinate dependencies may propagate unchanged.

    Examples:
        Verifies expected behavior described by test name is maintained without regression.
    """
    adapter = _build_adapter(
        [
            "success_agri_price.json",
            "success_agri_price.json",
        ]
    )
    dataset = adapter.get_dataset("agri_price")

    batch = adapter.query_records(dataset, Query(filters={"cond[exmn_ymd::GTE]": "20240101"}))
    raw = adapter.call_raw(dataset, "price", {"cond[exmn_ymd::GTE]": "20240101"})

    assert batch.dataset is dataset
    assert len(batch.items) == 3
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


def test_subway_passengers_dataset_contract_metadata() -> None:
    adapter = _build_adapter(["success_subway_passengers.json"])

    dataset = adapter.get_dataset("subway_passengers")

    assert dataset.id == "datago.subway_passengers"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


def test_subway_passengers_dataset_contract_query_and_raw() -> None:
    adapter = _build_adapter(["success_subway_passengers.json", "success_subway_passengers.json"])
    dataset = adapter.get_dataset("subway_passengers")

    batch = adapter.query_records(dataset, Query(filters={"pasngYmd": "20260521"}))
    raw = adapter.call_raw(dataset, "getStnPsgr", {"pasngYmd": "20260521"})

    assert batch.dataset is dataset
    assert len(batch.items) == 2
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


def test_mid_fcst_dataset_contract_metadata() -> None:
    adapter = _build_adapter(["success_mid_fcst.json"])

    dataset = adapter.get_dataset("mid_fcst")

    assert dataset.id == "datago.mid_fcst"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


def test_mid_fcst_dataset_contract_query_and_raw() -> None:
    adapter = _build_adapter(["success_mid_fcst.json", "success_mid_fcst.json"])
    dataset = adapter.get_dataset("mid_fcst")

    batch = adapter.query_records(dataset, Query(filters={"stnId": "108", "tmFc": "2026052206"}))
    raw = adapter.call_raw(dataset, "getMidFcst", {"stnId": "108", "tmFc": "2026052206"})

    assert batch.dataset is dataset
    assert len(batch.items) == 1
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


def test_mid_land_fcst_dataset_contract_metadata() -> None:
    adapter = _build_adapter(["success_mid_land_fcst.json"])

    dataset = adapter.get_dataset("mid_land_fcst")

    assert dataset.id == "datago.mid_land_fcst"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


def test_mid_land_fcst_dataset_contract_query_and_raw() -> None:
    adapter = _build_adapter(["success_mid_land_fcst.json", "success_mid_land_fcst.json"])
    dataset = adapter.get_dataset("mid_land_fcst")

    batch = adapter.query_records(
        dataset, Query(filters={"regId": "11B00000", "tmFc": "2026052206"})
    )
    raw = adapter.call_raw(dataset, "getMidLandFcst", {"regId": "11B00000", "tmFc": "2026052206"})

    assert batch.dataset is dataset
    assert len(batch.items) == 1
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


def test_mid_ta_dataset_contract_metadata() -> None:
    adapter = _build_adapter(["success_mid_ta.json"])

    dataset = adapter.get_dataset("mid_ta")

    assert dataset.id == "datago.mid_ta"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


def test_mid_ta_dataset_contract_query_and_raw() -> None:
    adapter = _build_adapter(["success_mid_ta.json", "success_mid_ta.json"])
    dataset = adapter.get_dataset("mid_ta")

    batch = adapter.query_records(
        dataset, Query(filters={"regId": "11D20501", "tmFc": "2026052206"})
    )
    raw = adapter.call_raw(dataset, "getMidTa", {"regId": "11D20501", "tmFc": "2026052206"})

    assert batch.dataset is dataset
    assert len(batch.items) == 1
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


def test_mid_sea_fcst_dataset_contract_metadata() -> None:
    adapter = _build_adapter(["success_mid_sea_fcst.json"])

    dataset = adapter.get_dataset("mid_sea_fcst")

    assert dataset.id == "datago.mid_sea_fcst"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
    assert dataset.query_support is not None
    assert dataset.query_support.pagination is PaginationMode.OFFSET


def test_mid_sea_fcst_dataset_contract_query_and_raw() -> None:
    adapter = _build_adapter(["success_mid_sea_fcst.json", "success_mid_sea_fcst.json"])
    dataset = adapter.get_dataset("mid_sea_fcst")

    batch = adapter.query_records(
        dataset, Query(filters={"regId": "12A20000", "tmFc": "2026052206"})
    )
    raw = adapter.call_raw(dataset, "getMidSeaFcst", {"regId": "12A20000", "tmFc": "2026052206"})

    assert batch.dataset is dataset
    assert len(batch.items) == 1
    assert all(isinstance(item, dict) for item in batch.items)
    assert raw is not None


class TestDataGoBondPriceContract(ProviderAdapterContract):
    """Bond price information contract (#163)."""

    @pytest.fixture()
    def adapter(self) -> DataGoAdapter:
        return _build_adapter(["success_bond_price.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "bond_price"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: DataGoAdapter) -> DatasetRef:
        return adapter.get_dataset("bond_price")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(filters={"basDt": "20260102"})

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return ("getBondPriceInfo", {"basDt": "20260102", "page": 1, "page_size": 5})


class TestDataGoSportsFacilityContract(ProviderAdapterContract):
    """National sports facilities information contract (#166)."""

    @pytest.fixture()
    def adapter(self) -> DataGoAdapter:
        return _build_adapter(["success_sports_facility.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "sports_facility"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: DataGoAdapter) -> DatasetRef:
        return adapter.get_dataset("sports_facility")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(filters={"sidoNm": "경기도"})

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return ("TODZ_API_SFMS_FACI", {"sidoNm": "경기도", "page": 1, "page_size": 5})


class TestDataGoCultureFacilityContract(ProviderAdapterContract):
    """Cultural facility information contract (#167)."""

    @pytest.fixture()
    def adapter(self) -> DataGoAdapter:
        return _build_adapter(["success_culture_facility.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "culture_facility"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: DataGoAdapter) -> DatasetRef:
        return adapter.get_dataset("culture_facility")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(filters={"faciCl": "공연장"})

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return ("cultureartspaces/performingplace", {"page": 1, "page_size": 5})


class TestDataGoAirkoreaStationRealtimeContract(ProviderAdapterContract):
    """Air Korea real-time measurement data by station contract (#224)."""

    @pytest.fixture()
    def adapter(self) -> DataGoAdapter:
        return _build_adapter(["success_airkorea_station_realtime.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "airkorea_station_realtime"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: DataGoAdapter) -> DatasetRef:
        return adapter.get_dataset("airkorea_station_realtime")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(filters={"stationName": "강남구"})

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return (
            "getMsrstnAcctoRltmMesureDnsty",
            {"stationName": "강남구", "page": 1, "page_size": 5},
        )


class TestDataGoAirkoreaForecastContract(ProviderAdapterContract):
    """Air Korea air quality forecast contract (#224)."""

    @pytest.fixture()
    def adapter(self) -> DataGoAdapter:
        return _build_adapter(["success_airkorea_forecast.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "airkorea_forecast"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: DataGoAdapter) -> DatasetRef:
        return adapter.get_dataset("airkorea_forecast")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(filters={"informCode": "PM10"})

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return ("getMinuDustFrcstDspth", {"informCode": "PM10", "page": 1, "page_size": 5})


class TestDataGoAsosDailyContract(ProviderAdapterContract):
    """Synoptic weather observation daily data contract (#217)."""

    @pytest.fixture()
    def adapter(self) -> DataGoAdapter:
        return _build_adapter(["success_asos_daily.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "asos_daily"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: DataGoAdapter) -> DatasetRef:
        return adapter.get_dataset("asos_daily")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(
            filters={"stnIds": "108", "startDt": "20260331", "endDt": "20260401"},
            page_size=10,
        )

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return (
            "getWthrDataList",
            {
                "stnIds": "108",
                "startDt": "20260331",
                "endDt": "20260401",
                "page": 1,
                "page_size": 5,
            },
        )


class TestDataGoAsosHourlyContract(ProviderAdapterContract):
    """Synoptic weather observation hourly data contract (#217)."""

    @pytest.fixture()
    def adapter(self) -> DataGoAdapter:
        return _build_adapter(["success_asos_hourly.json"] * 5)

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        return "asos_hourly"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: DataGoAdapter) -> DatasetRef:
        return adapter.get_dataset("asos_hourly")

    @pytest.fixture()
    def sample_query(self) -> Query:
        return Query(
            filters={"stnIds": "108", "startDt": "20260401", "endDt": "20260401"},
            page_size=10,
        )

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        return (
            "getWthrDataList",
            {
                "stnIds": "108",
                "startDt": "20260401",
                "endDt": "20260401",
                "page": 1,
                "page_size": 5,
            },
        )
