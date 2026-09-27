"""Logging coverage tests — assert structured DEBUG records are emitted."""

from __future__ import annotations

import logging
from typing import Any

import pytest

from kpubdata.catalog import Catalog
from kpubdata.client import Client
from kpubdata.core.capability import Operation
from kpubdata.core.dataset import Dataset
from kpubdata.core.models import DatasetRef, Query, RecordBatch, SchemaDescriptor
from kpubdata.core.representation import Representation
from kpubdata.exceptions import DatasetNotFoundError, ProviderNotRegisteredError
from kpubdata.registry import ProviderRegistry
from kpubdata.transport.decode import decode_json, decode_xml, detect_content_type


class _FakeAdapter:
    """
    _FakeAdapter Class encapsulating related operations.

    This class in ``tests/unit/test_logging.py`` module manages _FakeAdapterstate and behavior.
    Key methods: __init__, list_datasets, search_datasets, get_dataset, query_records.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    name = "fake"

    def __init__(self) -> None:
        """
        Initialize internal state for the instance.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self.ref: DatasetRef = DatasetRef(
            id="fake.demo",
            provider="fake",
            dataset_key="demo",
            name="Demo Dataset",
            operations=frozenset({Operation.LIST}),
            representation=Representation.API_JSON,
        )

    def list_datasets(self) -> list[DatasetRef]:
        """
        list datasets Performs the operation.

        Returns:
            list[DatasetRef]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return [self.ref]

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """
        search datasets Performs the operation.

        Args:
            text (str): Input value provided by caller.

        Returns:
            list[DatasetRef]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return [self.ref] if text.lower() in self.ref.id else []

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """
        get dataset Performs the operation.

        Args:
            dataset_key (str): Input value provided by caller.

        Returns:
            DatasetRef: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        if dataset_key != "demo":
            raise DatasetNotFoundError(
                f"Dataset not found: fake.{dataset_key}",
                provider="fake",
                dataset_id=f"fake.{dataset_key}",
            )
        return self.ref

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """
        query records Performs the operation.

        Args:
            dataset (DatasetRef): Input value provided by caller.
            query (Query): Input value provided by caller.

        Returns:
            RecordBatch: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return RecordBatch(items=[{"id": 1}], dataset=dataset, total_count=1, raw=None)

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """
        get schema Performs the operation.

        Args:
            dataset (DatasetRef): Input value provided by caller.

        Returns:
            SchemaDescriptor | None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return None

    def call_raw(self, dataset: DatasetRef, operation: str, params: dict[str, object]) -> object:
        """
        call raw Performs the operation.

        Args:
            dataset (DatasetRef): Input value provided by caller.
            operation (str): Input value provided by caller.
            params (dict[str, object]): Input value provided by caller.

        Returns:
            object: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return {"operation": operation, "params": params}


def _records(caplog: pytest.LogCaptureFixture, name: str) -> list[logging.LogRecord]:
    """
    Helper for records processing.

    Args:
        caplog (pytest.LogCaptureFixture): Input value provided by caller.
        name (str): Input value provided by caller.

    Returns:
        list[logging.LogRecord]: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.
    """
    return [r for r in caplog.records if r.name == name]


def _by_message(records: list[logging.LogRecord], message: str) -> logging.LogRecord:
    """
    Helper for by message processing.

    Args:
        records (list[logging.LogRecord]): Input value provided by caller.
        message (str): Input value provided by caller.

    Returns:
        logging.LogRecord: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.
    """
    for record in records:
        if record.getMessage() == message:
            return record
    raise AssertionError(f"No log record with message {message!r}")


@pytest.fixture
def fake_client(caplog: pytest.LogCaptureFixture) -> Client:
    """
    fake client Performs the operation.

    Args:
        caplog (pytest.LogCaptureFixture): Input value provided by caller.

    Returns:
        Client: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.
    """
    caplog.set_level(logging.DEBUG, logger="kpubdata")
    client = Client()
    client.register_provider(_FakeAdapter())
    return client


class TestClientLogging:
    """
    TestClientLogging Class encapsulating related operations.

    This class in ``tests/unit/test_logging.py`` module manages TestClientLoggingstate and behavior.
    Key methods: test_init_emits_debug, test_close_emits_debug, test_dataset_binding_logs.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    # test init emits debug Describes scenario being tested.
    def test_init_emits_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test init emits debug Verifies scenario.

        Args:
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        caplog.set_level(logging.DEBUG, logger="kpubdata.client")
        _ = Client()
        records = _records(caplog, "kpubdata.client")
        record = _by_message(records, "Client initialized")
        assert isinstance(record.providers, list)  # type: ignore[attr-defined]
        assert "datago" in record.providers  # type: ignore[attr-defined]

    # test close emits debug Describes scenario being tested.
    def test_close_emits_debug(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test close emits debug Verifies scenario.

        Args:
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        caplog.set_level(logging.DEBUG, logger="kpubdata.client")
        client = Client()
        caplog.clear()
        client.close()
        records = _records(caplog, "kpubdata.client")
        _ = _by_message(records, "Client closing")

    # test dataset binding logs Describes scenario being tested.
    def test_dataset_binding_logs(
        self, fake_client: Client, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        test dataset binding logs Verifies scenario.

        Args:
            fake_client (Client): Input value provided by caller.
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        caplog.clear()
        caplog.set_level(logging.DEBUG, logger="kpubdata.client")
        _ = fake_client.dataset("fake.demo")
        records = _records(caplog, "kpubdata.client")
        _ = _by_message(records, "Binding dataset")
        bound = _by_message(records, "Dataset bound")
        assert bound.dataset_id == "fake.demo"  # type: ignore[attr-defined]


class TestRegistryLogging:
    """
    TestRegistryLogging Class encapsulating related operations.

    This class in ``tests/unit/test_logging.py`` module manages TestRegistryLoggingstate and behavior.
    Key methods: test_register_logs, test_lookup_failure_logs, test_lazy_register_and_materialize_logs.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    # test register logs Describes scenario being tested.
    def test_register_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test register logs Verifies scenario.

        Args:
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        caplog.set_level(logging.DEBUG, logger="kpubdata.registry")
        registry = ProviderRegistry()
        registry.register(_FakeAdapter())
        records = _records(caplog, "kpubdata.registry")
        record = _by_message(records, "Registered eager provider adapter")
        assert record.provider == "fake"  # type: ignore[attr-defined]

    # test lookup failure logs Describes scenario being tested.
    def test_lookup_failure_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test lookup failure logs Verifies scenario.

        Args:
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        caplog.set_level(logging.DEBUG, logger="kpubdata.registry")
        registry = ProviderRegistry()
        with pytest.raises(ProviderNotRegisteredError):
            registry.get("missing")
        records = _records(caplog, "kpubdata.registry")
        record = _by_message(records, "Provider lookup failed")
        assert record.provider == "missing"  # type: ignore[attr-defined]

    # test lazy register and materialize logs Describes scenario being tested.
    def test_lazy_register_and_materialize_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test lazy register and materialize logs Verifies scenario.

        Args:
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        caplog.set_level(logging.DEBUG, logger="kpubdata.registry")
        registry = ProviderRegistry()
        registry.register_lazy("fake", _FakeAdapter)
        adapter = registry.get("fake")
        assert isinstance(adapter, _FakeAdapter)
        records = _records(caplog, "kpubdata.registry")
        _ = _by_message(records, "Registered lazy provider adapter")
        _ = _by_message(records, "Materializing lazy provider adapter")
        _ = _by_message(records, "Materialized lazy provider adapter")


class TestCatalogLogging:
    """
    TestCatalogLogging Class encapsulating related operations.

    This class in ``tests/unit/test_logging.py`` module manages TestCatalogLoggingstate and behavior.
    Key methods: test_list_logs, test_search_logs, test_resolve_failure_logs, test_invalid_id_logs.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    # test list logs Describes scenario being tested.
    def test_list_logs(self, fake_client: Client, caplog: pytest.LogCaptureFixture) -> None:
        """
        test list logs Verifies scenario.

        Args:
            fake_client (Client): Input value provided by caller.
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        caplog.clear()
        caplog.set_level(logging.DEBUG, logger="kpubdata.catalog")
        result = fake_client.datasets.list()
        assert len(result) >= 1
        records = _records(caplog, "kpubdata.catalog")
        _ = _by_message(records, "Catalog list")
        _ = _by_message(records, "Catalog list result")

    # test search logs Describes scenario being tested.
    def test_search_logs(self, fake_client: Client, caplog: pytest.LogCaptureFixture) -> None:
        """
        test search logs Verifies scenario.

        Args:
            fake_client (Client): Input value provided by caller.
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        caplog.clear()
        caplog.set_level(logging.DEBUG, logger="kpubdata.catalog")
        _ = fake_client.datasets.search("fake")
        records = _records(caplog, "kpubdata.catalog")
        record = _by_message(records, "Catalog search")
        assert record.text == "fake"  # type: ignore[attr-defined]

    # test resolve failure logs Describes scenario being tested.
    def test_resolve_failure_logs(
        self, fake_client: Client, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        test resolve failure logs Verifies scenario.

        Args:
            fake_client (Client): Input value provided by caller.
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        caplog.clear()
        caplog.set_level(logging.DEBUG, logger="kpubdata.catalog")
        with pytest.raises(DatasetNotFoundError):
            _ = fake_client.dataset("fake.nope")
        records = _records(caplog, "kpubdata.catalog")
        _ = _by_message(records, "Catalog resolve failed: dataset not found")

    # test invalid id logs Describes scenario being tested.
    def test_invalid_id_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test invalid id logs Verifies scenario.

        Args:
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        caplog.set_level(logging.DEBUG, logger="kpubdata.catalog")
        registry = ProviderRegistry()
        catalog = Catalog(registry)
        with pytest.raises(DatasetNotFoundError):
            _ = catalog.resolve("invalid_id_no_dot")


class TestDatasetLogging:
    """
    TestDatasetLogging Class encapsulating related operations.

    This class in ``tests/unit/test_logging.py`` module manages TestDatasetLoggingstate and behavior.
    Key methods: test_list_logs, test_call_raw_logs, test_list_all_logs_iterations.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    # test list logs Describes scenario being tested.
    def test_list_logs(self, fake_client: Client, caplog: pytest.LogCaptureFixture) -> None:
        """
        test list logs Verifies scenario.

        Args:
            fake_client (Client): Input value provided by caller.
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ds = fake_client.dataset("fake.demo")
        caplog.clear()
        caplog.set_level(logging.DEBUG, logger="kpubdata.dataset")
        _ = ds.list(page=1, page_size=10, custom_filter="x")
        records = _records(caplog, "kpubdata.dataset")
        dispatch = _by_message(records, "Dataset.list dispatching")
        assert dispatch.page == 1  # type: ignore[attr-defined]
        assert dispatch.page_size == 10  # type: ignore[attr-defined]
        assert "custom_filter" in dispatch.filter_keys  # type: ignore[attr-defined]
        completed = _by_message(records, "Dataset.list completed")
        assert completed.item_count == 1  # type: ignore[attr-defined]

    # test call raw logs Describes scenario being tested.
    def test_call_raw_logs(self, fake_client: Client, caplog: pytest.LogCaptureFixture) -> None:
        """
        test call raw logs Verifies scenario.

        Args:
            fake_client (Client): Input value provided by caller.
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ds = fake_client.dataset("fake.demo")
        caplog.clear()
        caplog.set_level(logging.DEBUG, logger="kpubdata.dataset")
        _ = ds.call_raw("op", a=1, b=2)
        records = _records(caplog, "kpubdata.dataset")
        record = _by_message(records, "Dataset.call_raw dispatching")
        assert record.operation == "op"  # type: ignore[attr-defined]
        assert record.param_keys == ["a", "b"]  # type: ignore[attr-defined]

    # test list all logs iterations Describes scenario being tested.
    def test_list_all_logs_iterations(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test list all logs iterations Verifies scenario.

        Args:
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ref = DatasetRef(
            id="fake.demo",
            provider="fake",
            dataset_key="demo",
            name="Demo",
            operations=frozenset({Operation.LIST}),
            representation=Representation.API_JSON,
        )

        class _PagedAdapter:
            """
            _PagedAdapter Class encapsulating related operations.

            This class in ``tests/unit/test_logging.py`` module manages _PagedAdapterstate and behavior.
            Key methods: __init__, query_records, get_schema, call_raw.

            Attributes:
                Properties defined in constructor and class body are reused as shared context by methods.
            """

            name = "fake"

            def __init__(self) -> None:
                """
                Initialize internal state for the instance.

                Returns:
                    None: Returns the result or return value from downstream calls.

                Raises:
                    Propagates exceptions from implementation or dependencies.
                """
                self.calls = 0

            def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
                """
                query records Performs the operation.

                Args:
                    dataset (DatasetRef): Input value provided by caller.
                    query (Query): Input value provided by caller.

                Returns:
                    RecordBatch: Returns the result or return value from downstream calls.

                Raises:
                    Propagates exceptions from implementation or dependencies.
                """
                self.calls += 1
                next_page = 2 if self.calls == 1 else None
                return RecordBatch(
                    items=[{"i": self.calls}],
                    dataset=dataset,
                    total_count=2,
                    next_page=next_page,
                    raw=None,
                )

            def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
                """
                get schema Performs the operation.

                Args:
                    dataset (DatasetRef): Input value provided by caller.

                Returns:
                    SchemaDescriptor | None: Returns the result or return value from downstream calls.

                Raises:
                    Propagates exceptions from implementation or dependencies.
                """
                return None

            def call_raw(
                self, dataset: DatasetRef, operation: str, params: dict[str, object]
            ) -> object:
                """
                call raw Performs the operation.

                Args:
                    dataset (DatasetRef): Input value provided by caller.
                    operation (str): Input value provided by caller.
                    params (dict[str, object]): Input value provided by caller.

                Returns:
                    object: Returns the result or return value from downstream calls.

                Raises:
                    Propagates exceptions from implementation or dependencies.
                """
                return None

        adapter: Any = _PagedAdapter()
        ds = Dataset(ref=ref, adapter=adapter)
        caplog.set_level(logging.DEBUG, logger="kpubdata.dataset")
        batches = list(ds.list_all())
        assert len(batches) == 2
        records = _records(caplog, "kpubdata.dataset")
        _ = _by_message(records, "Dataset.list_all starting")
        _ = _by_message(records, "Dataset.list_all advancing")
        completed = _by_message(records, "Dataset.list_all completed")
        assert completed.iterations == 2  # type: ignore[attr-defined]


class TestDecodeLogging:
    """
    TestDecodeLogging Class encapsulating related operations.

    This class in ``tests/unit/test_logging.py`` module manages TestDecodeLoggingstate and behavior.
    Key methods: test_json_parse_failure_logs, test_xml_parse_failure_logs, test_unrecognized_content_type_logs.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    # test json parse failure logs Describes scenario being tested.
    def test_json_parse_failure_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test json parse failure logs Verifies scenario.

        Args:
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.exceptions import ParseError

        caplog.set_level(logging.DEBUG, logger="kpubdata.transport.decode")
        with pytest.raises(ParseError):
            _ = decode_json(b"{not json}")
        records = _records(caplog, "kpubdata.transport.decode")
        _ = _by_message(records, "JSON parse failed")

    # test xml parse failure logs Describes scenario being tested.
    def test_xml_parse_failure_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test xml parse failure logs Verifies scenario.

        Args:
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.exceptions import ParseError

        caplog.set_level(logging.DEBUG, logger="kpubdata.transport.decode")
        with pytest.raises(ParseError):
            _ = decode_xml(b"<broken")
        records = _records(caplog, "kpubdata.transport.decode")
        _ = _by_message(records, "XML parse failed")

    # test unrecognized content type logs Describes scenario being tested.
    def test_unrecognized_content_type_logs(self, caplog: pytest.LogCaptureFixture) -> None:
        """
        test unrecognized content type logs Verifies scenario.

        Args:
            caplog (pytest.LogCaptureFixture): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        import httpx

        caplog.set_level(logging.DEBUG, logger="kpubdata.transport.decode")
        response = httpx.Response(
            200, content=b"x", headers={"content-type": "application/octet-stream"}
        )
        assert detect_content_type(response) == "other"
        records = _records(caplog, "kpubdata.transport.decode")
        _ = _by_message(records, "Unrecognized content-type, defaulting to 'other'")
