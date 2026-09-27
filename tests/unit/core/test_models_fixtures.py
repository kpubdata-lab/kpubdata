"""Test module.

This file defines test scenarios and helper objects in the
``tests/unit/core/test_models_fixtures.py`` path. Validates core flows,
exceptions, and edge cases for regression prevention and public contract
verification.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import MappingProxyType
from typing import cast

from kpubdata.core.capability import Operation, PaginationMode, QuerySupport
from kpubdata.core.models import DatasetRef, Query, RecordBatch
from kpubdata.core.representation import Representation

REPO_ROOT = Path(__file__).resolve().parents[3]
CATALOGUE_PATH = REPO_ROOT / "src/kpubdata/providers/datago/catalogue.json"
FIXTURES_DIR = REPO_ROOT / "tests/fixtures/datago"


def _load_catalogue_entries() -> tuple[dict[str, object], dict[str, object]]:
    """
    Internal helper for load_catalogue_entries operation.

    Returns:
        tuple[dict[str, object], dict[str, object]]: Result of computation or
        return value from downstream call.

    Raises:
        Implementation may propagate exceptions from downstream dependencies.
    """
    catalogue = cast(
        list[dict[str, object]],
        json.loads(CATALOGUE_PATH.read_text(encoding="utf-8")),
    )
    return catalogue[0], catalogue[1]


def _make_ref(entry: dict[str, object]) -> DatasetRef:
    """
    Internal helper for make_ref operation.

    Args:
        entry (dict[str, object]): Input value provided by caller.

    Returns:
        DatasetRef: Result of computation or return value from downstream call.

    Raises:
        Implementation may propagate exceptions from downstream dependencies.
    """
    return DatasetRef(
        id=f"datago.{entry['dataset_key']}",
        provider="datago",
        dataset_key=str(entry["dataset_key"]),
        name=str(entry["name"]),
        representation=Representation.API_JSON,
        operations=frozenset({Operation.LIST, Operation.RAW}),
        query_support=QuerySupport(
            pagination=PaginationMode.OFFSET,
            max_page_size=1000,
        ),
        raw_metadata=MappingProxyType(
            {
                "base_url": entry["base_url"],
                "default_operation": entry["default_operation"],
                "service_key_param": entry["service_key_param"],
            }
        ),
    )


def _load_fixture(name: str) -> dict[str, object]:
    """
    Internal helper for load_fixture operation.

    Args:
        name (str): Input value provided by caller.

    Returns:
        dict[str, object]: Result of computation or return value from downstream call.

    Raises:
        Implementation may propagate exceptions from downstream dependencies.
    """
    return cast(
        dict[str, object],
        json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8")),
    )


def _response_body(payload: dict[str, object]) -> dict[str, object]:
    """
    Internal helper for response_body operation.

    Args:
        payload (dict[str, object]): Input value provided by caller.

    Returns:
        dict[str, object]: Result of computation or return value from downstream call.

    Raises:
        Implementation may propagate exceptions from downstream dependencies.
    """
    response = cast(dict[str, object], payload["response"])
    return cast(dict[str, object], response["body"])


def _items_node(body: dict[str, object]) -> dict[str, object] | None:
    """
    Internal helper for items_node operation.

    Args:
        body (dict[str, object]): Input value provided by caller.

    Returns:
        dict[str, object] | None: Result of computation or return value from downstream call.

    Raises:
        Implementation may propagate exceptions from downstream dependencies.
    """
    return cast(dict[str, object] | None, body["items"])


def _items_list_from_body(body: dict[str, object]) -> list[dict[str, object]]:
    """
    Internal helper for items_list_from_body operation.

    Args:
        body (dict[str, object]): Input value provided by caller.

    Returns:
        list[dict[str, object]]: Result of computation or return value from downstream call.

    Raises:
        Implementation may propagate exceptions from downstream dependencies.
    """
    items = cast(dict[str, object], body["items"])
    return cast(list[dict[str, object]], items["item"])


class TestDatasetRefFromCatalogue:
    """
    Class encapsulating roles related to TestDatasetRefFromCatalogue.

    Manages state and behavior of TestDatasetRefFromCatalogue within the
    ``tests/unit/core/test_models_fixtures.py`` module. Key methods:
    test_first_entry_core_fields, test_second_entry_core_fields,
    test_operations_are_list_and_raw, test_query_support_offset_with_max_page_size,
    test_raw_metadata_is_mapping_proxy_with_required_keys.

    Attributes:
        Properties defined in __init__ and class body are reused as common context
        by downstream methods.
    """

    # Validates test_first_entry_core_fields scenario.
    def test_first_entry_core_fields(self) -> None:
        """
        Validates scenario described by test_first_entry_core_fields.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        first_entry, _ = _load_catalogue_entries()
        ref = _make_ref(first_entry)

        assert ref.id == f"datago.{first_entry['dataset_key']}"
        assert ref.provider == "datago"
        assert ref.dataset_key == first_entry["dataset_key"]
        assert ref.name == first_entry["name"]
        assert ref.representation == Representation.API_JSON

    # Validates test_second_entry_core_fields scenario.
    def test_second_entry_core_fields(self) -> None:
        """
        Validates scenario described by test_second_entry_core_fields.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        _, second_entry = _load_catalogue_entries()
        ref = _make_ref(second_entry)

        assert ref.id == f"datago.{second_entry['dataset_key']}"
        assert ref.provider == "datago"
        assert ref.dataset_key == second_entry["dataset_key"]
        assert ref.name == second_entry["name"]
        assert ref.representation == Representation.API_JSON

    # Validates test_operations_are_list_and_raw scenario.
    def test_operations_are_list_and_raw(self) -> None:
        """
        Validates scenario described by test_operations_are_list_and_raw.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        first_entry, _ = _load_catalogue_entries()
        ref = _make_ref(first_entry)

        assert ref.operations == frozenset({Operation.LIST, Operation.RAW})

    # Validates test_query_support_offset_with_max_page_size scenario.
    def test_query_support_offset_with_max_page_size(self) -> None:
        """
        Validates scenario described by test_query_support_offset_with_max_page_size.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        _, second_entry = _load_catalogue_entries()
        ref = _make_ref(second_entry)

        assert ref.query_support is not None
        assert ref.query_support.pagination == PaginationMode.OFFSET
        assert ref.query_support.max_page_size == 1000

    # Validates test_raw_metadata_is_mapping_proxy_with_required_keys scenario.
    def test_raw_metadata_is_mapping_proxy_with_required_keys(self) -> None:
        """
        Validates scenario described by test_raw_metadata_is_mapping_proxy_with_required_keys.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        first_entry, _ = _load_catalogue_entries()
        ref = _make_ref(first_entry)

        assert isinstance(ref.raw_metadata, MappingProxyType)
        assert "base_url" in ref.raw_metadata
        assert "default_operation" in ref.raw_metadata
        assert "service_key_param" in ref.raw_metadata

    # Validates test_supports_list_and_not_get scenario.
    def test_supports_list_and_not_get(self) -> None:
        """
        Validates scenario described by test_supports_list_and_not_get.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        first_entry, _ = _load_catalogue_entries()
        ref = _make_ref(first_entry)

        assert ref.supports(Operation.LIST) is True
        assert ref.supports(Operation.GET) is False

    # Validates test_is_frozen scenario.
    def test_is_frozen(self) -> None:
        """
        Validates scenario described by test_is_frozen.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        first_entry, _ = _load_catalogue_entries()
        ref = _make_ref(first_entry)
        attr = "id"

        try:
            setattr(ref, attr, "datago.changed")
            raise AssertionError("DatasetRef should be frozen")
        except AttributeError:
            pass


class TestRecordBatchFromFixtures:
    """
    Class encapsulating roles related to TestRecordBatchFromFixtures.

    Manages state and behavior of TestRecordBatchFromFixtures within the
    ``tests/unit/core/test_models_fixtures.py`` module. Key methods:
    test_single_page_batch_shape, test_single_item_fixture_normalized_to_list,
    test_empty_fixture_batch_is_falsey, test_string_numeric_fixture_shape_works_for_record_batch,
    test_multi_page_fixtures_can_be_combined.

    Attributes:
        Properties defined in __init__ and class body are reused as common context
        by downstream methods.
    """

    # Validates test_single_page_batch_shape scenario.
    def test_single_page_batch_shape(self) -> None:
        """
        Validates scenario described by test_single_page_batch_shape.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        first_entry, _ = _load_catalogue_entries()
        ref = _make_ref(first_entry)
        payload = _load_fixture("success_single_page.json")
        body = _response_body(payload)
        items_list = _items_list_from_body(body)
        batch = RecordBatch(items=items_list, dataset=ref, total_count=3, raw=payload)

        assert len(batch) == 3
        assert bool(batch) is True
        assert list(batch) == items_list
        assert batch.total_count == 3
        assert batch.raw is payload

    # Validates test_single_item_fixture_normalized_to_list scenario.
    def test_single_item_fixture_normalized_to_list(self) -> None:
        """
        Validates scenario described by test_single_item_fixture_normalized_to_list.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        first_entry, _ = _load_catalogue_entries()
        ref = _make_ref(first_entry)
        payload = _load_fixture("success_single_item.json")
        body = _response_body(payload)
        items = cast(dict[str, object], body["items"])
        single_item = cast(dict[str, object], items["item"])
        batch = RecordBatch(items=[single_item], dataset=ref, total_count=1, raw=payload)

        assert len(batch) == 1
        assert batch.items[0]["stationName"] == "종로구"

    # Validates test_empty_fixture_batch_is_falsey scenario.
    def test_empty_fixture_batch_is_falsey(self) -> None:
        """
        Validates scenario described by test_empty_fixture_batch_is_falsey.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        first_entry, _ = _load_catalogue_entries()
        ref = _make_ref(first_entry)
        payload = _load_fixture("success_empty.json")
        body = _response_body(payload)
        assert _items_node(body) is None

        batch = RecordBatch(items=[], dataset=ref, total_count=0)
        assert len(batch) == 0
        assert bool(batch) is False

    # Validates test_string_numeric_fixture_shape_works_for_record_batch scenario.
    def test_string_numeric_fixture_shape_works_for_record_batch(self) -> None:
        """
        Validates scenario described by test_string_numeric_fixture_shape_works_for_record_batch.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        first_entry, _ = _load_catalogue_entries()
        ref = _make_ref(first_entry)
        payload = _load_fixture("success_string_numerics.json")
        body = _response_body(payload)
        items = _items_list_from_body(body)

        batch = RecordBatch(
            items=items,
            dataset=ref,
            total_count=int(cast(str, body["totalCount"])),
            raw=payload,
        )
        assert len(batch) == 1
        assert batch.total_count == 1

    # Validates test_multi_page_fixtures_can_be_combined scenario.
    def test_multi_page_fixtures_can_be_combined(self) -> None:
        """
        Validates scenario described by test_multi_page_fixtures_can_be_combined.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        first_entry, _ = _load_catalogue_entries()
        ref = _make_ref(first_entry)
        page1_payload = _load_fixture("success_multi_page_1.json")
        page2_payload = _load_fixture("success_multi_page_2.json")
        page1_items = _items_list_from_body(_response_body(page1_payload))
        page2_items = _items_list_from_body(_response_body(page2_payload))
        all_items = [*page1_items, *page2_items]

        batch = RecordBatch(
            items=all_items,
            dataset=ref,
            total_count=3,
            raw=[page1_payload, page2_payload],
        )

        assert len(batch) == 3
        assert isinstance(batch.raw, list)


class TestQueryFromRealisticFilters:
    """
    Class encapsulating roles related to TestQueryFromRealisticFilters.

    Manages state and behavior of TestQueryFromRealisticFilters within the
    ``tests/unit/core/test_models_fixtures.py`` module. Key methods:
    test_query_with_korean_filters_preserves_exact_values, test_query_defaults.

    Attributes:
        Properties defined in __init__ and class body are reused as common context
        by downstream methods.
    """

    # Validates test_query_with_korean_filters_preserves_exact_values scenario.
    def test_query_with_korean_filters_preserves_exact_values(self) -> None:
        """
        Validates scenario described by test_query_with_korean_filters_preserves_exact_values.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        query = Query(
            filters={"stationName": "종로구", "dataTime": "2024-01-15 14:00"},
            page=1,
            page_size=10,
            extra={"returnType": "json"},
        )

        assert query.filters["stationName"] == "종로구"
        assert query.filters["dataTime"] == "2024-01-15 14:00"
        assert query.page == 1
        assert query.page_size == 10
        assert query.extra["returnType"] == "json"

    # Validates test_query_defaults scenario.
    def test_query_defaults(self) -> None:
        """
        Validates scenario described by test_query_defaults.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        query = Query()

        assert query.filters == {}
        assert query.page is None


class TestCapabilityImmutability:
    """
    Class encapsulating roles related to TestCapabilityImmutability.

    Manages state and behavior of TestCapabilityImmutability within the
    ``tests/unit/core/test_models_fixtures.py`` module. Key methods:
    test_query_support_is_frozen.

    Attributes:
        Properties defined in __init__ and class body are reused as common context
        by downstream methods.
    """

    # Validates test_query_support_is_frozen scenario.
    def test_query_support_is_frozen(self) -> None:
        """
        Validates scenario described by test_query_support_is_frozen.

        Returns:
            None: Result of computation or return value from downstream call.

        Raises:
            Implementation may propagate exceptions from downstream dependencies.

        Examples:
            Verify expected behavior maintained without regression as described by test name.
        """
        query_support = QuerySupport(pagination=PaginationMode.OFFSET, max_page_size=1000)
        attr = "pagination"

        try:
            setattr(query_support, attr, PaginationMode.CURSOR)
            raise AssertionError("QuerySupport should be frozen")
        except AttributeError:
            pass
