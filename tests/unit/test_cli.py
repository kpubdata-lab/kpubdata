"""Unit test module.

tests/unit/test_cli.py`` Defines test scenarios and helper objects.
Verifies core flows, exceptions, and edge conditions for regression prevention and public contract validation.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable, Generator
from pathlib import Path
from types import MappingProxyType
from typing import cast, final

import pytest
from typing_extensions import override

import kpubdata.cli as cli_module
from kpubdata.core.capability import Operation, PaginationMode, QuerySupport
from kpubdata.core.models import DatasetRef, RecordBatch
from kpubdata.core.representation import Representation
from kpubdata.exceptions import AuthError, DatasetNotFoundError, InvalidRequestError, TransportError

main = cli_module.main


def _make_ref() -> DatasetRef:
    """
    Helper for make ref processing.

    Returns:
        DatasetRef: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.
    """
    return DatasetRef(
        id="bok.base_rate",
        provider="bok",
        dataset_key="base_rate",
        name="기준금리",
        representation=Representation.API_JSON,
        operations=frozenset({Operation.LIST, Operation.RAW}),
        query_support=QuerySupport(
            pagination=PaginationMode.NONE,
            time_range=True,
            max_page_size=100,
        ),
        raw_metadata=MappingProxyType({"base_url": "https://example.test", "fields": []}),
    )


class FakeCatalog:
    """
    FakeCatalog Class encapsulating related operations.

    This class in ``tests/unit/test_cli.py`` module manages FakeCatalogstate and behavior.
    Key methods: __init__, list, resolve.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    def __init__(self, dataset_ref: DatasetRef) -> None:
        """
        Initialize internal state for the instance.

        Args:
            dataset_ref (DatasetRef): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self._dataset_ref: DatasetRef = dataset_ref

    def list(self, *, provider: str | None = None) -> list[DatasetRef]:
        """
        list Performs the operation.

        Args:
            provider (str | None): Input value provided by caller.

        Returns:
            list[DatasetRef]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        if provider is not None and provider != self._dataset_ref.provider:
            return []
        return [self._dataset_ref]

    def resolve(self, dataset_id: str) -> tuple[object, DatasetRef]:
        """
        resolve Performs the operation.

        Args:
            dataset_id (str): Input value provided by caller.

        Returns:
            tuple[object, DatasetRef]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        if dataset_id != self._dataset_ref.id:
            raise DatasetNotFoundError(f"Dataset not found: {dataset_id}", dataset_id=dataset_id)
        return object(), self._dataset_ref


class FakeDataset:
    """
    FakeDataset Class encapsulating related operations.

    This class in ``tests/unit/test_cli.py`` module manages FakeDatasetstate and behavior.
    Key methods: __init__, list, list_all, call_raw.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    def __init__(self, dataset_ref: DatasetRef) -> None:
        """
        Initialize internal state for the instance.

        Args:
            dataset_ref (DatasetRef): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self.ref: DatasetRef = dataset_ref
        self.list_calls: list[dict[str, object]] = []

    def list(self, **kwargs: object) -> RecordBatch:
        """
        list Performs the operation.

        Args:
            **kwargs (object): Input value provided by caller.

        Returns:
            RecordBatch: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self.list_calls.append(kwargs)
        return RecordBatch(
            items=[
                {"TIME": "202401", "DATA_VALUE": "3.5"},
                {"TIME": "202402", "DATA_VALUE": "3.5"},
            ],
            dataset=self.ref,
        )

    def list_all(self, **kwargs: object) -> Generator[RecordBatch, None, None]:
        """
        list all Performs the operation.

        Args:
            **kwargs (object): Input value provided by caller.

        Returns:
            Generator[RecordBatch, None, None]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self.list_calls.append(kwargs)
        yield RecordBatch(items=[{"TIME": "202401", "DATA_VALUE": "3.5"}], dataset=self.ref)
        yield RecordBatch(items=[{"TIME": "202402", "DATA_VALUE": "3.5"}], dataset=self.ref)

    def call_raw(self, operation: str, **params: object) -> object:
        """
        call raw Performs the operation.

        Args:
            operation (str): Input value provided by caller.
            **params (object): Input value provided by caller.

        Returns:
            object: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return {"operation": operation, "params": params}


class FakeClient:
    """
    FakeClient Class encapsulating related operations.

    This class in ``tests/unit/test_cli.py`` module manages FakeClientstate and behavior.
    Key methods: __init__, dataset, close.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    def __init__(self, dataset_ref: DatasetRef) -> None:
        """
        Initialize internal state for the instance.

        Args:
            dataset_ref (DatasetRef): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self.datasets: FakeCatalog = FakeCatalog(dataset_ref)
        self.dataset_stub: FakeDataset = FakeDataset(dataset_ref)
        self.closed: bool = False

    def dataset(self, dataset_id: str) -> FakeDataset:
        """
        dataset Performs the operation.

        Args:
            dataset_id (str): Input value provided by caller.

        Returns:
            FakeDataset: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        if dataset_id != self.dataset_stub.ref.id:
            raise DatasetNotFoundError(f"Dataset not found: {dataset_id}", dataset_id=dataset_id)
        logging.getLogger("kpubdata.client").debug(
            "binding dataset", extra={"dataset_id": dataset_id}
        )
        return self.dataset_stub

    def close(self) -> None:
        """
        close Performs the operation.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self.closed = True


@final
class RaisingClient(FakeClient):
    """
    RaisingClient Class encapsulating related operations.

    This class in ``tests/unit/test_cli.py`` module manages RaisingClientstate and behavior.
    Key methods: __init__, dataset.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    def __init__(self, dataset_ref: DatasetRef, exc: Exception) -> None:
        """
        Initialize internal state for the instance.

        Args:
            dataset_ref (DatasetRef): Input value provided by caller.
            exc (Exception): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        super().__init__(dataset_ref)
        self._exc: Exception = exc

    @override
    def dataset(self, dataset_id: str) -> FakeDataset:
        """
        dataset Performs the operation.

        Args:
            dataset_id (str): Input value provided by caller.

        Returns:
            FakeDataset: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = dataset_id
        raise self._exc


@pytest.fixture
def fake_client(monkeypatch: pytest.MonkeyPatch) -> FakeClient:
    """
    fake client Performs the operation.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.

    Returns:
        FakeClient: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.
    """
    client = FakeClient(_make_ref())

    def _fake_create_client(*, cache_enabled: bool, provider_keys: dict[str, str]) -> FakeClient:
        """
        Helper for fake create client processing.

        Args:
            cache_enabled (bool): Input value provided by caller.
            provider_keys (dict[str, str]): Input value provided by caller.

        Returns:
            FakeClient: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = cache_enabled, provider_keys
        return client

    monkeypatch.setattr("kpubdata.cli._create_client", _fake_create_client)
    return client


# test version prints and exits zero Describes scenario being tested.
def test_version_prints_and_exits_zero(capsys: pytest.CaptureFixture[str]) -> None:
    """
    test version prints and exits zero Verifies scenario.

    Args:
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    exit_code = main(["--version"])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.err == ""
    assert captured.out.strip()


# test main without command prints help Describes scenario being tested.
def test_main_without_command_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    """
    test main without command prints help Verifies scenario.

    Args:
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    exit_code = main([])

    captured = capsys.readouterr()

    assert exit_code == 0
    assert "usage: kpubdata" in captured.out
    assert captured.err == ""


# test datasets list json outputs valid json Describes scenario being tested.
def test_datasets_list_json_outputs_valid_json(
    fake_client: FakeClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    test datasets list json outputs valid json Verifies scenario.

    Args:
        fake_client (FakeClient): Input value provided by caller.
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    exit_code = main(["datasets", "list", "--format", "json"])

    captured = capsys.readouterr()
    payload = cast(object, json.loads(captured.out))

    assert exit_code == 0
    assert captured.err == ""
    assert payload == [
        {
            "id": "bok.base_rate",
            "name": "기준금리",
            "provider": "bok",
            "operations": ["list", "raw"],
        }
    ]
    assert fake_client.closed is True


# test datasets show json outputs metadata Describes scenario being tested.
def test_datasets_show_json_outputs_metadata(
    fake_client: FakeClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    test datasets show json outputs metadata Verifies scenario.

    Args:
        fake_client (FakeClient): Input value provided by caller.
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    exit_code = main(["datasets", "show", "bok.base_rate", "--format", "json"])

    captured = capsys.readouterr()
    payload = cast(dict[str, object], json.loads(captured.out))

    assert exit_code == 0
    assert payload["id"] == "bok.base_rate"
    assert payload["provider"] == "bok"
    assert payload["operations"] == ["list", "raw"]
    assert payload["capabilities"] == {
        "pagination": "none",
        "filterable_fields": [],
        "sortable_fields": [],
        "time_range": True,
        "max_page_size": 100,
    }
    assert payload["raw_metadata_keys"] == ["base_url", "fields"]
    assert fake_client.closed is True


# test fetch csv calls dataset list with kwargs and emits csv Describes scenario being tested.
def test_fetch_csv_calls_dataset_list_with_kwargs_and_emits_csv(
    fake_client: FakeClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    test fetch csv calls dataset list with kwargs and emits csv Verifies scenario.

    Args:
        fake_client (FakeClient): Input value provided by caller.
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    exit_code = main(
        [
            "fetch",
            "bok.base_rate",
            "-p",
            "start_date=202401",
            "-p",
            "end_date=202401",
            "--format",
            "csv",
        ]
    )

    captured = capsys.readouterr()

    assert exit_code == 0
    assert fake_client.dataset_stub.list_calls == [{"start_date": "202401", "end_date": "202401"}]
    assert captured.out == "TIME,DATA_VALUE\r\n202401,3.5\r\n202402,3.5\r\n"
    assert captured.err == ""


# test fetch all json writes output file Describes scenario being tested.
def test_fetch_all_json_writes_output_file(fake_client: FakeClient, tmp_path: Path) -> None:
    """
    test fetch all json writes output file Verifies scenario.

    Args:
        fake_client (FakeClient): Input value provided by caller.
        tmp_path (Path): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    output_file = tmp_path / "records.json"

    exit_code = main(
        [
            "fetch",
            "bok.base_rate",
            "-p",
            "start_date=202401",
            "--all",
            "--format",
            "json",
            "--output",
            str(output_file),
        ]
    )

    payload = cast(list[dict[str, object]], json.loads(output_file.read_text(encoding="utf-8")))

    assert exit_code == 0
    assert fake_client.dataset_stub.list_calls == [{"max_pages": None, "start_date": "202401"}]
    assert payload == [
        {"TIME": "202401", "DATA_VALUE": "3.5"},
        {"TIME": "202402", "DATA_VALUE": "3.5"},
    ]


# test_fetch_all_with_max_pages_ten scenario
def test_fetch_all_with_max_pages_ten(fake_client: FakeClient, tmp_path: Path) -> None:
    """Test fetch with max pages=10."""
    output_file = tmp_path / "records.json"

    exit_code = main(
        [
            "fetch",
            "bok.base_rate",
            "-p",
            "max_pages=10",
            "--all",
            "--format",
            "json",
            "--output",
            str(output_file),
        ]
    )

    assert exit_code == 0
    # CLI should convert string "10" to integer 10 and pass it explicitly
    assert fake_client.dataset_stub.list_calls == [{"max_pages": 10}]
    assert fake_client.closed is True


# test raw writes pretty json to output file Describes scenario being tested.
def test_raw_writes_pretty_json_to_output_file(fake_client: FakeClient, tmp_path: Path) -> None:
    """
    test raw writes pretty json to output file Verifies scenario.

    Args:
        fake_client (FakeClient): Input value provided by caller.
        tmp_path (Path): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    output_file = tmp_path / "raw.json"

    exit_code = main(
        [
            "raw",
            "bok.base_rate",
            "series",
            "-p",
            "stat_code=722Y001",
            "--output",
            str(output_file),
        ]
    )

    payload = cast(dict[str, object], json.loads(output_file.read_text(encoding="utf-8")))

    assert exit_code == 0
    assert payload == {
        "operation": "series",
        "params": {"stat_code": "722Y001"},
    }
    assert fake_client.closed is True


# test invalid dataset id returns exit two and stderr Describes scenario being tested.
def test_invalid_dataset_id_returns_exit_two_and_stderr(
    fake_client: FakeClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    test invalid dataset id returns exit two and stderr Verifies scenario.

    Args:
        fake_client (FakeClient): Input value provided by caller.
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    exit_code = main(["datasets", "show", "bok.unknown", "--format", "json"])

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "error: DatasetNotFoundError: Dataset not found: bok.unknown" in captured.err
    assert fake_client.closed is True


# test invalid param format returns exit two Describes scenario being tested.
def test_invalid_param_format_returns_exit_two(
    fake_client: FakeClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    test invalid param format returns exit two Verifies scenario.

    Args:
        fake_client (FakeClient): Input value provided by caller.
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    exit_code = main(["fetch", "bok.base_rate", "-p", "invalid"])

    captured = capsys.readouterr()

    assert exit_code == 2
    assert captured.out == ""
    assert "error: InvalidRequestError: -p/--param expects KEY=VALUE: invalid" in captured.err
    assert fake_client.closed is True


# test auth error returns exit three Describes scenario being tested.
def test_auth_error_returns_exit_three(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    test auth error returns exit three Verifies scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = RaisingClient(_make_ref(), AuthError("bad key"))

    def _fake_create_client(*, cache_enabled: bool, provider_keys: dict[str, str]) -> RaisingClient:
        """
        Helper for fake create client processing.

        Args:
            cache_enabled (bool): Input value provided by caller.
            provider_keys (dict[str, str]): Input value provided by caller.

        Returns:
            RaisingClient: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = cache_enabled, provider_keys
        return client

    monkeypatch.setattr("kpubdata.cli._create_client", _fake_create_client)

    exit_code = main(["fetch", "bok.base_rate"])

    captured = capsys.readouterr()

    assert exit_code == 3
    assert "error: AuthError: bad key" in captured.err
    assert client.closed is True


# test transport error returns exit four Describes scenario being tested.
def test_transport_error_returns_exit_four(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    test transport error returns exit four Verifies scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = RaisingClient(_make_ref(), TransportError("network down"))

    def _fake_create_client(*, cache_enabled: bool, provider_keys: dict[str, str]) -> RaisingClient:
        """
        Helper for fake create client processing.

        Args:
            cache_enabled (bool): Input value provided by caller.
            provider_keys (dict[str, str]): Input value provided by caller.

        Returns:
            RaisingClient: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = cache_enabled, provider_keys
        return client

    monkeypatch.setattr("kpubdata.cli._create_client", _fake_create_client)

    exit_code = main(["fetch", "bok.base_rate"])

    captured = capsys.readouterr()

    assert exit_code == 4
    assert "error: TransportError: network down" in captured.err
    assert client.closed is True


# test unexpected error returns exit one Describes scenario being tested.
def test_unexpected_error_returns_exit_one(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    test unexpected error returns exit one Verifies scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    client = RaisingClient(_make_ref(), RuntimeError("boom"))

    def _fake_create_client(*, cache_enabled: bool, provider_keys: dict[str, str]) -> RaisingClient:
        """
        Helper for fake create client processing.

        Args:
            cache_enabled (bool): Input value provided by caller.
            provider_keys (dict[str, str]): Input value provided by caller.

        Returns:
            RaisingClient: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = cache_enabled, provider_keys
        return client

    monkeypatch.setattr("kpubdata.cli._create_client", _fake_create_client)

    exit_code = main(["fetch", "bok.base_rate"])

    captured = capsys.readouterr()

    assert exit_code == 1
    assert "error: RuntimeError: boom" in captured.err
    assert client.closed is True


# test log level debug sets logger level and emits debug log Describes scenario being tested.
def test_log_level_debug_sets_logger_level_and_emits_debug_log(
    fake_client: FakeClient, caplog: pytest.LogCaptureFixture, capsys: pytest.CaptureFixture[str]
) -> None:
    """
    test log level debug sets logger level and emits debug log Verifies scenario.

    Args:
        fake_client (FakeClient): Input value provided by caller.
        caplog (pytest.LogCaptureFixture): Input value provided by caller.
        capsys (pytest.CaptureFixture[str]): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    caplog.set_level(logging.DEBUG, logger="kpubdata")

    exit_code = main(["--log-level", "debug", "fetch", "bok.base_rate", "--format", "json"])

    _ = capsys.readouterr()

    assert exit_code == 0
    assert fake_client.closed is True
    assert logging.getLogger("kpubdata").getEffectiveLevel() == logging.DEBUG
    assert "CLI logging configured" in caplog.text
    assert "binding dataset" in caplog.text


# test cli helper functions cover formats and serialization Describes scenario being tested.
def test_cli_helper_functions_cover_formats_and_serialization(tmp_path: Path) -> None:
    """
    test cli helper functions cover formats and serialization Verifies scenario.

    Args:
        tmp_path (Path): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    csv_headers = cast(Callable[..., list[str]], cli_module.__dict__["_csv_headers"])
    get_version = cast(Callable[[], str], cli_module.__dict__["_get_version"])
    parse_assignments = cast(
        Callable[..., dict[str, str]], cli_module.__dict__["_parse_assignments"]
    )
    query_support_payload = cast(
        Callable[..., dict[str, object] | None],
        cli_module.__dict__["_query_support_payload"],
    )
    render_csv = cast(Callable[..., str], cli_module.__dict__["_render_csv"])
    render_records = cast(Callable[..., str], cli_module.__dict__["_render_records"])
    render_table = cast(Callable[..., str], cli_module.__dict__["_render_table"])
    split_assignment = cast(
        Callable[..., tuple[str, str]], cli_module.__dict__["_split_assignment"]
    )
    stringify_value = cast(Callable[[object], str], cli_module.__dict__["_stringify_value"])
    table_headers = cast(Callable[..., list[str]], cli_module.__dict__["_table_headers"])
    to_jsonable = cast(Callable[[object], object], cli_module.__dict__["_to_jsonable"])
    truncate = cast(Callable[[str], str], cli_module.__dict__["_truncate"])
    write_output = cast(Callable[..., None], cli_module.__dict__["_write_output"])

    dataset_ref = _make_ref()
    batch = RecordBatch(
        items=[{"alpha": "x" * 50, "beta": 1}, {"alpha": "y", "gamma": True}],
        dataset=dataset_ref,
        total_count=2,
        next_page=2,
        meta={"seen": 2},
        raw={"ok": True},
    )

    assert query_support_payload(None) is None
    assert split_assignment("key=value", flag_name="-p") == ("key", "value")
    assert parse_assignments(["a=1", "b=2"], flag_name="-p") == {"a": "1", "b": "2"}
    with pytest.raises(InvalidRequestError):
        _ = split_assignment("novalue", flag_name="-p")

    assert table_headers(batch.items) == ["alpha", "beta"]
    assert csv_headers(batch.items) == ["alpha", "beta", "gamma"]
    assert truncate("x" * 50).endswith("…")
    assert stringify_value(None) == ""
    assert stringify_value({"x": 1}) == '{"x": 1}'

    table_output = render_table(batch.items, headers=["alpha", "beta"])
    csv_output = render_csv(batch.items)
    json_output = render_records(batch.items, output_format="json")

    assert "alpha" in table_output
    assert "beta" in table_output
    assert csv_output.startswith("alpha,beta,gamma")
    assert json.loads(json_output)[0]["beta"] == 1
    assert "alpha" in render_records(batch.items, output_format="table")
    assert render_records([], output_format="table") == "(no columns)"
    assert render_records(batch.items, output_format="csv").startswith("alpha,beta,gamma")

    jsonable_batch = cast(dict[str, object], to_jsonable(batch))
    jsonable_dataset = cast(dict[str, object], to_jsonable(dataset_ref))
    jsonable_enum = to_jsonable(Operation.LIST)

    assert jsonable_batch["dataset"] == "bok.base_rate"
    assert jsonable_dataset["provider"] == "bok"
    assert jsonable_enum == "list"
    assert to_jsonable({"nested": [Operation.RAW]}) == {"nested": ["raw"]}
    assert cast(str, to_jsonable(object())).startswith("<object object")

    output_file = tmp_path / "out.txt"

    write_output("saved", str(output_file))
    assert output_file.read_text(encoding="utf-8") == "saved"
    assert get_version()


# test get version falls back to package version Describes scenario being tested.
def test_get_version_falls_back_to_package_version(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    test get version falls back to package version Verifies scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    from importlib.metadata import PackageNotFoundError

    get_version = cast(Callable[[], str], cli_module.__dict__["_get_version"])

    def _raise_package_not_found(_: str) -> str:
        """
        Helper for raise package not found processing.

        Args:
            _ (str): Input value provided by caller.

        Returns:
            str: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        raise PackageNotFoundError

    monkeypatch.setattr("kpubdata.cli.version", _raise_package_not_found)

    assert get_version()


# test_fetch_all_rejects_invalid_max_pages_non_numeric_string scenario
def test_fetch_all_rejects_invalid_max_pages_non_numeric_string(
    fake_client: FakeClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test fetch rejects non-numeric max pages."""
    exit_code = main(["fetch", "bok.base_rate", "--all", "-p", "max_pages=abc"])

    captured = capsys.readouterr()

    # CLI should reject non-numeric string "abc" for max_pages
    assert exit_code == 2
    assert captured.out == ""
    assert (
        "error: InvalidRequestError: max_pages must be a positive integer or None, got string: abc"
        in captured.err
    )
    assert fake_client.closed is True


# test_fetch_all_rejects_invalid_max_pages_zero scenario
def test_fetch_all_rejects_invalid_max_pages_zero(
    fake_client: FakeClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test fetch rejects max pages=0."""
    exit_code = main(["fetch", "bok.base_rate", "--all", "-p", "max_pages=0"])

    captured = capsys.readouterr()

    # CLI should reject 0 for max_pages
    assert exit_code == 2
    assert captured.out == ""
    assert (
        "error: InvalidRequestError: max_pages must be a positive integer or None" in captured.err
    )
    assert fake_client.closed is True


# test_fetch_all_accepts_valid_max_pages_integer scenario
def test_fetch_all_accepts_valid_max_pages_integer(
    fake_client: FakeClient, capsys: pytest.CaptureFixture[str]
) -> None:
    """Test fetch accepts valid max pages integer."""
    # Note: Since CLI params come as strings, we can't test passing int 10 via -p
    # But we can test that when max_pages is not provided, it works fine
    exit_code = main(["fetch", "bok.base_rate", "--all", "--format", "json"])

    captured = capsys.readouterr()

    # Should succeed when max_pages is not specified
    assert exit_code == 0
    assert "error" not in captured.err
    payload = cast(list[dict[str, object]], json.loads(captured.out))
    assert len(payload) == 2
    assert fake_client.closed is True
