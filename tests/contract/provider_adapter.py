"""Test module.

This file defines test scenarios and helper objects at ``tests/contract/provider_adapter.py``.
It verifies core flows, exceptions, and edge cases for regression prevention and
public contract validation.
"""

from __future__ import annotations

import pytest

from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.exceptions import DatasetNotFoundError


class ProviderAdapterContract:
    """
    Class that encapsulates roles related to ProviderAdapterContract.

    This class manages state and behavior of ProviderAdapterContract
    within the ``tests/contract/provider_adapter.py`` module.
    Key methods: test_isinstance_provider_adapter, test_name_is_nonempty_string,
    test_list_datasets_returns_list_of_dataset_ref, test_list_datasets_nonempty,
    test_search_datasets_returns_list_of_dataset_ref.

    Attribute descriptions:
        Properties defined in constructor and class body are reused by
        subordinate methods as common context.
    """

    # Describes scenario validated by test isinstance provider adapter.
    def test_isinstance_provider_adapter(self, adapter: ProviderAdapter) -> None:
        """
        Verifies test isinstance provider adapter scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        assert isinstance(adapter, ProviderAdapter)

    # Describes scenario validated by test name is nonempty string.
    def test_name_is_nonempty_string(self, adapter: ProviderAdapter) -> None:
        """
        Verifies test name is nonempty string scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        name = adapter.name
        assert isinstance(name, str)
        assert len(name) > 0

    # Describes scenario validated by test list datasets returns list of dataset ref.
    def test_list_datasets_returns_list_of_dataset_ref(self, adapter: ProviderAdapter) -> None:
        """
        Verifies test list datasets returns list of dataset ref scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        datasets = adapter.list_datasets()
        assert isinstance(datasets, list)
        assert all(isinstance(ds, DatasetRef) for ds in datasets)

    # Describes scenario validated by test list datasets nonempty.
    def test_list_datasets_nonempty(self, adapter: ProviderAdapter) -> None:
        """
        Verifies test list datasets nonempty scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        datasets = adapter.list_datasets()
        assert len(datasets) > 0

    # Describes scenario validated by test search datasets returns list of dataset ref.
    def test_search_datasets_returns_list_of_dataset_ref(self, adapter: ProviderAdapter) -> None:
        """
        Verifies test search datasets returns list of dataset ref scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        result = adapter.search_datasets("test")
        assert isinstance(result, list)
        assert all(isinstance(ds, DatasetRef) for ds in result)

    # Describes scenario validated by test get dataset valid key.
    def test_get_dataset_valid_key(self, adapter: ProviderAdapter, valid_dataset_key: str) -> None:
        """
        Verifies test get dataset valid key scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.
            valid_dataset_key (str): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        dataset = adapter.get_dataset(valid_dataset_key)
        assert isinstance(dataset, DatasetRef)
        assert dataset.dataset_key == valid_dataset_key

    # Describes scenario validated by test get dataset invalid key raises.
    def test_get_dataset_invalid_key_raises(
        self, adapter: ProviderAdapter, invalid_dataset_key: str
    ) -> None:
        """
        Verifies test get dataset invalid key raises scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.
            invalid_dataset_key (str): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        with pytest.raises(DatasetNotFoundError):
            _ = adapter.get_dataset(invalid_dataset_key)

    # Describes scenario validated by test query records returns record batch.
    def test_query_records_returns_record_batch(
        self, adapter: ProviderAdapter, sample_dataset: DatasetRef, sample_query: Query
    ) -> None:
        """
        Verifies test query records returns record batch scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.
            sample_dataset (DatasetRef): Input value provided by caller.
            sample_query (Query): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        batch = adapter.query_records(sample_dataset, sample_query)
        assert isinstance(batch, RecordBatch)
        assert isinstance(batch.items, list)
        assert batch.dataset is sample_dataset

    # Describes scenario validated by test query records items are dicts.
    def test_query_records_items_are_dicts(
        self, adapter: ProviderAdapter, sample_dataset: DatasetRef, sample_query: Query
    ) -> None:
        """
        Verifies test query records items are dicts scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.
            sample_dataset (DatasetRef): Input value provided by caller.
            sample_query (Query): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        batch = adapter.query_records(sample_dataset, sample_query)
        for item in batch.items:
            assert isinstance(item, dict)

    # Describes scenario validated by test get schema returns descriptor or none.
    def test_get_schema_returns_descriptor_or_none(
        self, adapter: ProviderAdapter, sample_dataset: DatasetRef
    ) -> None:
        """
        Verifies test get schema returns descriptor or none scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.
            sample_dataset (DatasetRef): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        schema = adapter.get_schema(sample_dataset)
        assert schema is None or isinstance(schema, SchemaDescriptor)

    # Describes scenario validated by test call raw returns object.
    def test_call_raw_returns_object(
        self,
        adapter: ProviderAdapter,
        sample_dataset: DatasetRef,
        raw_operation: tuple[str, dict[str, object]],
    ) -> None:
        """
        Verifies test call raw returns object scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.
            sample_dataset (DatasetRef): Input value provided by caller.
            raw_operation (tuple[str, dict[str, object]]): Input value
                provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        operation, params = raw_operation
        result = adapter.call_raw(sample_dataset, operation, params)
        assert result is not None

    # Describes scenario validated by test all datasets have provider set.
    def test_all_datasets_have_provider_set(self, adapter: ProviderAdapter) -> None:
        """
        Verifies test all datasets have provider set scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        for dataset in adapter.list_datasets():
            assert dataset.provider == adapter.name

    # Describes scenario validated by test all dataset ids prefixed with provider.
    def test_all_dataset_ids_prefixed_with_provider(self, adapter: ProviderAdapter) -> None:
        """
        Verifies test all dataset ids prefixed with provider scenario.

        Args:
            adapter (ProviderAdapter): Input value provided by caller.

        Returns:
            None: Computation result or return value from subordinate call.

        Raises:
            Exception from implementation or subordinate dependencies may
            propagate unchanged.

        Examples:
            Verifies that expected behavior described by test name is
            maintained without regression.
        """
        for dataset in adapter.list_datasets():
            assert dataset.id.startswith(f"{adapter.name}.")
