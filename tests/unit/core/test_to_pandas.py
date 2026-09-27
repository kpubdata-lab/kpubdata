"""Tests for RecordBatch.to_pandas() optional pandas integration."""

from __future__ import annotations

from types import ModuleType
from unittest.mock import patch

import pytest

from kpubdata.core.models import DatasetRef, RecordBatch
from kpubdata.core.representation import Representation


def _dataset_ref() -> DatasetRef:
    """
    As internal helper for handles dataset ref processing.

    Returns:
        DatasetRef: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.
    """
    return DatasetRef(
        id="mock.test",
        provider="mock",
        dataset_key="test",
        name="Test",
        representation=Representation.API_JSON,
    )


class _FakeDataFrame:
    """
    Class encapsulating _FakeDataFrame role.

    This class ``tests/unit/core/test_to_pandas.py`` within module _FakeDataFramemanages its state and behavior together.
    Key methods: __init__, __len__.

    Property description:
        Properties defined in constructor and class body are reused by sub-methods in shared context.
    """

    _data: list[dict[str, object]]
    columns: list[str]

    def __init__(self, data: list[dict[str, object]]) -> None:
        """
        Initialize internal state for instance use.

        Args:
            data (list[dict[str, object]]): input value provided by caller.

        Returns:
            None: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.
        """
        self._data = list(data)
        self.columns = list(self._data[0].keys()) if self._data else []

    def __len__(self) -> int:
        """
        As internal helper for len processing.

        Returns:
            int: returns computation result or value from sub-call.

        Raises:
            can propagate exceptions from sub-dependencies as-is.
        """
        return len(self._data)


class _FakePandasModule(ModuleType):
    """
    _FakePandasModule Class encapsulating role.

    This class ``tests/unit/core/test_to_pandas.py`` within module _FakePandasModulemanages its state and behavior together.
    Key methods: none.

    Property description:
        Properties defined in constructor and class body are reused by sub-methods in shared context.
    """

    DataFrame: type[_FakeDataFrame] = _FakeDataFrame


def _fake_pandas_module() -> _FakePandasModule:
    """
    As internal helper for fake pandas module processing.

    Returns:
        _FakePandasModule: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.
    """
    module = _FakePandasModule("pandas")
    module.DataFrame = _FakeDataFrame
    return module


# test to pandas returns dataframe Explains scenario validated by test.
def test_to_pandas_returns_dataframe() -> None:
    """
    test to pandas returns dataframe Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    batch = RecordBatch(
        items=[{"name": "Alice", "age": 30}, {"name": "Bob", "age": 31}],
        dataset=_dataset_ref(),
    )

    fake_pandas = _fake_pandas_module()

    with patch.dict("sys.modules", {"pandas": fake_pandas}):
        df = batch.to_pandas()

    assert isinstance(df, fake_pandas.DataFrame)
    assert list(df.columns) == ["name", "age"]
    assert len(df) == 2


# test to pandas empty items Explains scenario validated by test.
def test_to_pandas_empty_items() -> None:
    """
    test to pandas empty items Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    batch = RecordBatch(items=[], dataset=_dataset_ref())

    fake_pandas = _fake_pandas_module()

    with patch.dict("sys.modules", {"pandas": fake_pandas}):
        df = batch.to_pandas()

    assert isinstance(df, fake_pandas.DataFrame)
    assert list(df.columns) == []
    assert len(df) == 0


# test to pandas import error Explains scenario validated by test.
def test_to_pandas_import_error() -> None:
    """
    test to pandas import error Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    batch = RecordBatch(items=[{"name": "Alice"}], dataset=_dataset_ref())

    with (
        patch.dict("sys.modules", {"pandas": None}),
        pytest.raises(ImportError, match=r"pandas is required for to_pandas\(\)"),
    ):
        _ = batch.to_pandas()


# test to pandas real pandas if available Explains scenario validated by test.
def test_to_pandas_real_pandas_if_available() -> None:
    """
    test to pandas real pandas if available Verify scenario.

    Returns:
        None: returns computation result or value from sub-call.

    Raises:
        can propagate exceptions from sub-dependencies as-is.

    Example:
        Verify expected behavior described by test name is maintained without regression.
    """
    from typing import Protocol, cast

    class _DataFrameLike(Protocol):
        """
        _DataFrameLike Class encapsulating role.

        This class ``tests/unit/core/test_to_pandas.py`` within module _DataFrameLikemanages its state and behavior together.
        Key methods: none.

        Property description:
            Properties defined in constructor and class body are reused by sub-methods in shared context.
        """

        shape: tuple[int, int]
        columns: list[str]

    class _PandasModule(Protocol):
        """
        _PandasModule Class encapsulating role.

        This class ``tests/unit/core/test_to_pandas.py`` within module _PandasModulemanages its state and behavior together.
        Key methods: none.

        Property description:
            Properties defined in constructor and class body are reused by sub-methods in shared context.
        """

        DataFrame: type[_DataFrameLike]

    pd = cast(_PandasModule, pytest.importorskip("pandas"))

    batch = RecordBatch(
        items=[
            {"name": "Alice", "age": 30},
            {"name": "Bob", "age": 31},
            {"name": "Carol", "age": 32},
        ],
        dataset=_dataset_ref(),
    )

    df = batch.to_pandas()

    assert isinstance(df, pd.DataFrame)
    assert df.shape == (3, 2)
    assert list(df.columns) == ["name", "age"]
