"""Tests for Dataset binding and capability checks."""

from __future__ import annotations

import pytest

from kpubdata.core.capability import Operation
from kpubdata.core.dataset import Dataset
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.core.representation import Representation
from kpubdata.exceptions import InvalidRequestError, UnsupportedCapabilityError


class MockAdapter:
    """Adapter that records calls for assertion."""

    def __init__(self) -> None:
        self.last_query: Query | None = None
        self.last_raw_op: str | None = None
        self.batches: list[RecordBatch] = []

    @property
    def name(self) -> str:
        return "mock"

    def list_datasets(self) -> list[DatasetRef]:
        return []

    def search_datasets(self, text: str) -> list[DatasetRef]:
        _ = text
        return []

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        _ = dataset_key
        return _ref()

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """
        Perform query_records operation.

        Args:
            dataset (DatasetRef): Input value provided by caller.
            query (Query): Input value provided by caller.

        Returns:
            RecordBatch: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.
        """
        self.last_query = query
        if self.batches:
            return self.batches.pop(0)
        return RecordBatch(items=[{"k": "v"}], dataset=dataset)

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        _ = dataset
        return None

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        _ = dataset, params
        self.last_raw_op = operation
        return {"raw": True}


def _ref(ops: frozenset[Operation] | None = None) -> DatasetRef:
    return DatasetRef(
        id="mock.test",
        provider="mock",
        dataset_key="test",
        name="Test",
        representation=Representation.API_JSON,
        operations=ops or frozenset({Operation.LIST, Operation.RAW}),
    )


class TestDataset:
    """Tests for Dataset binding and capability checks."""

    def test_list(self) -> None:
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(), adapter=adapter)
        result = ds.list(code="11680")
        assert len(result) == 1
        assert adapter.last_query is not None
        assert adapter.last_query.filters["code"] == "11680"

    def test_list_unsupported(self) -> None:
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(frozenset({Operation.RAW})), adapter=adapter)
        with pytest.raises(UnsupportedCapabilityError, match="list"):
            _ = ds.list()

    def test_list_all_unsupported(self) -> None:
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(frozenset({Operation.RAW})), adapter=adapter)
        with pytest.raises(UnsupportedCapabilityError, match="list"):
            _ = list(ds.list_all())

    def test_call_raw(self) -> None:
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(), adapter=adapter)
        result = ds.call_raw("list", param="value")
        assert result == {"raw": True}
        assert adapter.last_raw_op == "list"

    def test_repr(self) -> None:
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(), adapter=adapter)
        assert "mock.test" in repr(ds)

    def test_list_separates_canonical_query_fields(self) -> None:
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(), adapter=adapter)

        _ = ds.list(
            start_date="202401",
            end_date="202412",
            page=2,
            page_size=50,
            region="서울",
        )

        assert adapter.last_query is not None
        assert adapter.last_query.start_date == "202401"
        assert adapter.last_query.end_date == "202412"
        assert adapter.last_query.page == 2
        assert adapter.last_query.page_size == 50
        assert adapter.last_query.filters == {"region": "서울"}

    def test_list_canonical_fields_not_in_filters(self) -> None:
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(), adapter=adapter)

        _ = ds.list(cursor="abc", fields=["name", "age"], sort=["name"])

        assert adapter.last_query is not None
        assert adapter.last_query.cursor == "abc"
        assert adapter.last_query.fields == ["name", "age"]
        assert adapter.last_query.sort == ["name"]
        assert adapter.last_query.filters == {}

    def test_list_only_filters_no_canonical(self) -> None:
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(), adapter=adapter)

        _ = ds.list(lawd_code="11680", deal_ym="202503")

        assert adapter.last_query is not None
        assert adapter.last_query.page is None
        assert adapter.last_query.start_date is None
        assert adapter.last_query.filters == {"lawd_code": "11680", "deal_ym": "202503"}

    def test_list_all_yields_multiple_batches(self) -> None:
        adapter = MockAdapter()
        dataset_ref = _ref()
        adapter.batches = [
            RecordBatch(items=[{"page": 1}], dataset=dataset_ref, next_page=2),
            RecordBatch(items=[{"page": 2}], dataset=dataset_ref, next_page=3),
            RecordBatch(items=[{"page": 3}], dataset=dataset_ref, next_page=None),
        ]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        batches = list(ds.list_all(region="서울"))

        assert [batch.items[0]["page"] for batch in batches] == [1, 2, 3]

    def test_list_all_stops_when_next_page_is_none(self) -> None:
        adapter = MockAdapter()
        dataset_ref = _ref()
        adapter.batches = [
            RecordBatch(items=[{"page": 1}], dataset=dataset_ref, next_page=2),
            RecordBatch(items=[{"page": 2}], dataset=dataset_ref, next_page=None),
        ]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        batches = list(ds.list_all(code="11680"))

        assert len(batches) == 2
        assert adapter.last_query is not None
        assert adapter.last_query.page == 2
        assert adapter.last_query.filters == {"code": "11680"}

    def test_list_all_single_page(self) -> None:
        adapter = MockAdapter()
        dataset_ref = _ref()
        adapter.batches = [RecordBatch(items=[{"page": 1}], dataset=dataset_ref, next_page=None)]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        batches = list(ds.list_all())

        assert len(batches) == 1
        assert batches[0].items == [{"page": 1}]

    def test_list_all_cursor_pagination(self) -> None:
        adapter = MockAdapter()
        dataset_ref = _ref()
        adapter.batches = [
            RecordBatch(items=[{"cursor": "a"}], dataset=dataset_ref, next_cursor="abc"),
            RecordBatch(items=[{"cursor": "b"}], dataset=dataset_ref, next_cursor="def"),
            RecordBatch(items=[{"cursor": "c"}], dataset=dataset_ref, next_cursor=None),
        ]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        batches = list(ds.list_all(region="서울"))

        assert [batch.items[0]["cursor"] for batch in batches] == ["a", "b", "c"]
        assert adapter.last_query is not None
        assert adapter.last_query.cursor == "def"
        assert adapter.last_query.page is None
        assert adapter.last_query.filters == {"region": "서울"}

    def test_list_all_cursor_single_page(self) -> None:
        adapter = MockAdapter()
        dataset_ref = _ref()
        adapter.batches = [
            RecordBatch(items=[{"cursor": "a"}], dataset=dataset_ref, next_cursor=None)
        ]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        batches = list(ds.list_all())

        assert len(batches) == 1
        assert batches[0].items == [{"cursor": "a"}]

    # Validates test_list_all_respects_max_pages_parameter scenario.
    def test_list_all_respects_max_pages_parameter(self) -> None:
        """
        Validates scenario described by test_list_all_respects_max_pages_parameter.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        # Create 5 pages of data
        adapter.batches = [
            RecordBatch(items=[{"page": 1}], dataset=dataset_ref, next_page=2),
            RecordBatch(items=[{"page": 2}], dataset=dataset_ref, next_page=3),
            RecordBatch(items=[{"page": 3}], dataset=dataset_ref, next_page=4),
            RecordBatch(items=[{"page": 4}], dataset=dataset_ref, next_page=5),
            RecordBatch(items=[{"page": 5}], dataset=dataset_ref, next_page=None),
        ]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # Should complete normally with 5 pages when max_pages=10
        batches = list(ds.list_all(max_pages=10))
        assert len(batches) == 5

    # Validates test_list_all_raises_when_max_pages_exceeded scenario.
    def test_list_all_raises_when_max_pages_exceeded(self) -> None:
        """
        Validates scenario described by test_list_all_raises_when_max_pages_exceeded.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        # Create many pages to exceed the limit
        adapter.batches = [
            RecordBatch(items=[{"page": i}], dataset=dataset_ref, next_page=i + 1)
            for i in range(1, 15)
        ]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # Should raise when exceeding max_pages=10
        with pytest.raises(InvalidRequestError, match="Pagination limit exceeded"):
            _ = list(ds.list_all(max_pages=10))

    # Validates test_list_all_detects_page_cycle scenario.
    def test_list_all_detects_page_cycle(self) -> None:
        """
        Validates scenario described by test_list_all_detects_page_cycle.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        # Create a cycle: page 1 -> 2 -> 3 -> 2 -> 3 ...
        adapter.batches = [
            RecordBatch(items=[{"page": 1}], dataset=dataset_ref, next_page=2),
            RecordBatch(items=[{"page": 2}], dataset=dataset_ref, next_page=3),
            RecordBatch(items=[{"page": 3}], dataset=dataset_ref, next_page=2),  # cycle back to 2
        ]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # Should detect the cycle when trying to fetch page 2 again
        with pytest.raises(InvalidRequestError, match="pagination cycle"):
            _ = list(ds.list_all())

    # Validates test_list_all_detects_cursor_cycle scenario.
    def test_list_all_detects_cursor_cycle(self) -> None:
        """
        Validates scenario described by test_list_all_detects_cursor_cycle.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        # Create a cycle with cursors
        adapter.batches = [
            RecordBatch(items=[{"cursor": "a"}], dataset=dataset_ref, next_cursor="abc"),
            RecordBatch(items=[{"cursor": "b"}], dataset=dataset_ref, next_cursor="def"),
            RecordBatch(items=[{"cursor": "c"}], dataset=dataset_ref, next_cursor="abc"),  # cycle
        ]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # Should detect the cycle when trying to use cursor "abc" again
        with pytest.raises(InvalidRequestError, match="pagination cycle"):
            _ = list(ds.list_all())

    # Validates test_list_all_raises_on_consecutive_empty_batches scenario.
    def test_list_all_raises_on_consecutive_empty_batches(self) -> None:
        """
        Validates scenario described by test_list_all_raises_on_consecutive_empty_batches.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        # Provider keeps returning empty batches but with next_page
        adapter.batches = [
            RecordBatch(items=[], dataset=dataset_ref, next_page=2),
            RecordBatch(items=[], dataset=dataset_ref, next_page=3),
            RecordBatch(items=[], dataset=dataset_ref, next_page=4),
        ]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # Should raise after 3 consecutive empty batches
        with pytest.raises(InvalidRequestError, match="consecutive empty batches"):
            _ = list(ds.list_all())

    # Validates test_list_all_allows_single_empty_batch scenario.
    def test_list_all_allows_single_empty_batch(self) -> None:
        """
        Validates scenario described by test_list_all_allows_single_empty_batch.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        # A single empty batch is allowed (might be legitimate)
        adapter.batches = [RecordBatch(items=[], dataset=dataset_ref, next_page=None)]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # Should complete normally
        batches = list(ds.list_all())
        assert len(batches) == 1
        assert batches[0].items == []

    # Validates test_list_all_handles_mixed_empty_and_non_empty_batches scenario.
    def test_list_all_handles_mixed_empty_and_non_empty_batches(self) -> None:
        """
        Validates scenario described by test_list_all_handles_mixed_empty_and_non_empty_batches.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        # Mix of empty and non-empty batches should be fine
        adapter.batches = [
            RecordBatch(items=[{"page": 1}], dataset=dataset_ref, next_page=2),
            RecordBatch(items=[], dataset=dataset_ref, next_page=3),  # empty but has next
            RecordBatch(items=[{"page": 3}], dataset=dataset_ref, next_page=None),
        ]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # Should complete normally
        batches = list(ds.list_all())
        assert len(batches) == 3
        assert [batch.items[0].get("page") if batch.items else None for batch in batches] == [
            1,
            None,
            3,
        ]

    # Validates test_list_all_uses_default_max_pages_when_not_specified scenario.
    def test_list_all_uses_default_max_pages_when_not_specified(self) -> None:
        """
        Validates scenario described by test_list_all_uses_default_max_pages_when_not_specified.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        # Create a reasonable number of pages (should be under default limit)
        adapter.batches = [
            RecordBatch(items=[{"page": i}], dataset=dataset_ref, next_page=i + 1)
            for i in range(1, 10)
        ]
        adapter.batches.append(
            RecordBatch(items=[{"page": 10}], dataset=dataset_ref, next_page=None)
        )
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # Should work with default max_pages
        batches = list(ds.list_all())
        assert len(batches) == 10

    # Validates test_list_all_detects_immediate_cycle_from_first_page scenario.
    def test_list_all_detects_immediate_cycle_from_first_page(self) -> None:
        """
        Validates scenario described by test_list_all_detects_immediate_cycle_from_first_page.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        # First batch immediately returns to page 1 (cycle to itself)
        adapter.batches = [RecordBatch(items=[{"page": 1}], dataset=dataset_ref, next_page=1)]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # Should detect cycle when trying to fetch page 1 again
        with pytest.raises(InvalidRequestError, match="pagination cycle"):
            _ = list(ds.list_all())

    # Validates test_list_all_passes_through_filters_with_max_pages scenario.
    def test_list_all_passes_through_filters_with_max_pages(self) -> None:
        """
        Validates scenario described by test_list_all_passes_through_filters_with_max_pages.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        adapter.batches = [RecordBatch(items=[{"page": 1}], dataset=dataset_ref, next_page=None)]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        _ = list(ds.list_all(max_pages=5, region="서울", code="11680"))

        assert adapter.last_query is not None
        assert adapter.last_query.filters == {"region": "서울", "code": "11680"}

    # Validates test_list_all_with_max_pages_none_uses_default scenario.
    def test_list_all_with_max_pages_none_uses_default(self) -> None:
        """
        Validates scenario described by test_list_all_with_max_pages_none_uses_default.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may also propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        adapter.batches = [RecordBatch(items=[{"page": 1}], dataset=dataset_ref, next_page=None)]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # max_pages=None should use default (1000)
        batches = list(ds.list_all(max_pages=None))
        assert len(batches) == 1

    # Validates test_list_all_with_max_pages_one scenario.
    def test_list_all_with_max_pages_one(self) -> None:
        """
        Validates scenario described by test_list_all_with_max_pages_one.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may also propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        adapter.batches = [RecordBatch(items=[{"page": 1}], dataset=dataset_ref, next_page=None)]
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # max_pages=1 should work
        batches = list(ds.list_all(max_pages=1))
        assert len(batches) == 1

    # Validates test_list_all_rejects_max_pages_zero scenario.
    def test_list_all_rejects_max_pages_zero(self) -> None:
        """
        Validates scenario described by test_list_all_rejects_max_pages_zero.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may also propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # max_pages=0 should raise InvalidRequestError
        with pytest.raises(InvalidRequestError, match="must be None or a positive integer"):
            _ = list(ds.list_all(max_pages=0))

    # Validates test_list_all_rejects_max_pages_negative scenario.
    def test_list_all_rejects_max_pages_negative(self) -> None:
        """
        Validates scenario described by test_list_all_rejects_max_pages_negative.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may also propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # max_pages=-1 should raise InvalidRequestError
        with pytest.raises(InvalidRequestError, match="must be None or a positive integer"):
            _ = list(ds.list_all(max_pages=-1))

    # Validates test_list_all_rejects_max_pages_true scenario.
    def test_list_all_rejects_max_pages_true(self) -> None:
        """
        Validates scenario described by test_list_all_rejects_max_pages_true.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may also propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # max_pages=True should raise InvalidRequestError
        with pytest.raises(
            InvalidRequestError, match="must be None or a positive integer.*got bool"
        ):
            _ = list(ds.list_all(max_pages=True))

    # Validates test_list_all_rejects_max_pages_string scenario.
    def test_list_all_rejects_max_pages_string(self) -> None:
        """
        Validates scenario described by test_list_all_rejects_max_pages_string.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may also propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        adapter = MockAdapter()
        dataset_ref = _ref()
        ds = Dataset(ref=dataset_ref, adapter=adapter)

        # max_pages="10" should raise InvalidRequestError
        with pytest.raises(
            InvalidRequestError, match="must be None or a positive integer.*got str"
        ):
            _ = list(ds.list_all(max_pages="10"))


class TestDatasetQueryValidation:
    """Tests for Dataset.list() canonical query validation."""

    @pytest.mark.parametrize(
        "kwargs,expected_match",
        [
            ({"page": "1"}, "page"),
            ({"page": 0}, "page"),
            ({"page": -1}, "page"),
            ({"page_size": 0}, "page_size"),
            ({"page_size": -1}, "page_size"),
            ({"cursor": 123}, "cursor"),
            ({"cursor": ""}, "cursor"),
            ({"start_date": 20240101}, "start_date"),
            ({"start_date": ""}, "start_date"),
            ({"start_date": "   "}, "start_date"),
            ({"end_date": 20240101}, "end_date"),
            ({"end_date": ""}, "end_date"),
            ({"fields": "name"}, "fields"),
            ({"sort": "date"}, "sort"),
        ],
    )
    def test_invalid_canonical_params_rejected(self, kwargs: dict, expected_match: str) -> None:
        """Invalid canonical parameters raise InvalidRequestError before adapter call."""
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(), adapter=adapter)

        with pytest.raises(InvalidRequestError, match=expected_match):
            ds.list(**kwargs)

        assert adapter.last_query is None

    def test_valid_query_passes_through(self) -> None:
        """Valid canonical query reaches adapter with correct fields."""
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(), adapter=adapter)

        result = ds.list(
            page=1,
            page_size=100,
            start_date="202401",
            end_date="202412",
            fields=["name"],
            sort=["date"],
        )

        assert adapter.last_query is not None
        assert adapter.last_query.page == 1
        assert adapter.last_query.page_size == 100
        assert adapter.last_query.start_date == "202401"
        assert adapter.last_query.end_date == "202412"
        assert adapter.last_query.fields == ["name"]
        assert adapter.last_query.sort == ["date"]
        assert len(result) == 1

    def test_provider_specific_filter_passes_through(self) -> None:
        """Provider-specific filters are passed through unchanged."""
        adapter = MockAdapter()
        ds = Dataset(ref=_ref(), adapter=adapter)

        result = ds.list(region="11", custom_param="value")

        assert adapter.last_query is not None
        assert adapter.last_query.filters == {"region": "11", "custom_param": "value"}
        assert len(result) == 1
