"""Unit test module.

tests/unit/test_catalogue_validation.py`` Defines test scenarios and helper objects.
Verifies core flows, exceptions, and edge conditions for regression prevention and public contract validation.
"""

from __future__ import annotations

import pytest

from kpubdata.exceptions import ConfigError
from kpubdata.providers._common import build_dataset_ref, load_catalogue


class _FakeCatalogueFile:
    """
    _FakeCatalogueFile Class encapsulating related operations.

    This class in ``tests/unit/test_catalogue_validation.py`` module manages _FakeCatalogueFilestate and behavior.
    Key methods: __init__, read_text.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    def __init__(self, text: str) -> None:
        """
        Initialize internal state for the instance.

        Args:
            text (str): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self._text: str = text

    def read_text(self, *, encoding: str = "utf-8") -> str:
        """
        read text Performs the operation.

        Args:
            encoding (str): Input value provided by caller.

        Returns:
            str: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        assert encoding == "utf-8"
        return self._text


class _FakePackageFiles:
    """
    _FakePackageFiles Class encapsulating related operations.

    This class in ``tests/unit/test_catalogue_validation.py`` module manages _FakePackageFilesstate and behavior.
    Key methods: __init__, joinpath.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    def __init__(self, text: str) -> None:
        """
        Initialize internal state for the instance.

        Args:
            text (str): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self._text: str = text

    def joinpath(self, path: str) -> _FakeCatalogueFile:
        """
        joinpath Performs the operation.

        Args:
            path (str): Input value provided by caller.

        Returns:
            _FakeCatalogueFile: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        assert path == "catalogue.json"
        return _FakeCatalogueFile(self._text)


# test load catalogue raises for duplicate dataset ids Describes scenario being tested.
def test_load_catalogue_raises_for_duplicate_dataset_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    test load catalogue raises for duplicate dataset ids Verifies scenario.

    Args:
        monkeypatch (pytest.MonkeyPatch): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    import kpubdata.providers._common as common_module

    def _fake_files(_package_name: str) -> _FakePackageFiles:
        """
        Helper for fake files processing.

        Args:
            _package_name (str): Input value provided by caller.

        Returns:
            _FakePackageFiles: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return _FakePackageFiles(
            """
            [
              {"dataset_key": "dup", "name": "First", "representation": "api_json"},
              {"dataset_key": "dup", "name": "Second", "representation": "api_xml"}
            ]
            """
        )

    monkeypatch.setattr(
        common_module,
        "files",
        _fake_files,
    )

    with pytest.raises(ConfigError, match=r"duplicate dataset ids: test\.dup"):
        _ = load_catalogue("fake.package", "test")


# test build dataset ref raises for invalid representation Describes scenario being tested.
def test_build_dataset_ref_raises_for_invalid_representation() -> None:
    """
    test build dataset ref raises for invalid representation Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    with pytest.raises(ConfigError, match="invalid representation"):
        _ = build_dataset_ref(
            "test",
            {
                "dataset_key": "sample",
                "name": "Sample",
                "representation": "not_real",
            },
        )


# test build dataset ref raises for invalid operation Describes scenario being tested.
def test_build_dataset_ref_raises_for_invalid_operation() -> None:
    """
    test build dataset ref raises for invalid operation Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    with pytest.raises(ConfigError, match="invalid operation"):
        _ = build_dataset_ref(
            "test",
            {
                "dataset_key": "sample",
                "name": "Sample",
                "representation": "api_json",
                "operations": ["list", "bogus"],
            },
        )


# test build dataset ref raises for invalid pagination mode Describes scenario being tested.
def test_build_dataset_ref_raises_for_invalid_pagination_mode() -> None:
    """
    test build dataset ref raises for invalid pagination mode Verifies scenario.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    with pytest.raises(ConfigError, match=r"query_support\.pagination has invalid value"):
        _ = build_dataset_ref(
            "test",
            {
                "dataset_key": "sample",
                "name": "Sample",
                "representation": "api_json",
                "query_support": {"pagination": "page_number"},
            },
        )


# test build dataset ref raises for missing required fields Describes scenario being tested.
@pytest.mark.parametrize("field_name", ["dataset_key", "name", "representation"])
def test_build_dataset_ref_raises_for_missing_required_fields(field_name: str) -> None:
    """
    test build dataset ref raises for missing required fields Verifies scenario.

    Args:
        field_name (str): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    entry: dict[str, object] = {
        "dataset_key": "sample",
        "name": "Sample",
        "representation": "api_json",
    }
    del entry[field_name]

    with pytest.raises(ConfigError, match=rf"missing non-empty string field: {field_name}"):
        _ = build_dataset_ref("test", entry)


# test valid provider catalogues pass validation Describes scenario being tested.
@pytest.mark.parametrize(
    ("package_name", "provider"),
    [
        ("kpubdata.providers.datago", "datago"),
        ("kpubdata.providers.bok", "bok"),
        ("kpubdata.providers.kosis", "kosis"),
    ],
)
def test_valid_provider_catalogues_pass_validation(package_name: str, provider: str) -> None:
    """
    test valid provider catalogues pass validation Verifies scenario.

    Args:
        package_name (str): Input value provided by caller.
        provider (str): Input value provided by caller.

    Returns:
        None: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.

    Examples:
        Verifies expected behavior matches test name without regression.
    """
    datasets = load_catalogue(package_name, provider)

    assert datasets
    assert all(dataset.provider == provider for dataset in datasets)


class TestBuildDatasetRefMetadata:
    """
    TestBuildDatasetRefMetadata Class encapsulating related operations.

    This class in ``tests/unit/test_catalogue_validation.py`` module manages TestBuildDatasetRefMetadatastate and behavior.
    Key methods: test_description_parsed, test_description_empty_string_becomes_none, test_description_absent_is_none, test_tags_parsed, test_tags_absent_is_empty.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    # test description parsed Describes scenario being tested.
    def test_description_parsed(self) -> None:
        """
        test description parsed Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ref = build_dataset_ref(
            "test",
            {
                "dataset_key": "s",
                "name": "S",
                "representation": "api_json",
                "description": "A test dataset",
            },
        )
        assert ref.description == "A test dataset"
        assert "description" not in ref.raw_metadata

    # test description empty string becomes none Describes scenario being tested.
    def test_description_empty_string_becomes_none(self) -> None:
        """
        test description empty string becomes none Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ref = build_dataset_ref(
            "test",
            {"dataset_key": "s", "name": "S", "representation": "api_json", "description": ""},
        )
        assert ref.description is None

    # test description absent is none Describes scenario being tested.
    def test_description_absent_is_none(self) -> None:
        """
        test description absent is none Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ref = build_dataset_ref(
            "test",
            {"dataset_key": "s", "name": "S", "representation": "api_json"},
        )
        assert ref.description is None

    # test tags parsed Describes scenario being tested.
    def test_tags_parsed(self) -> None:
        """
        test tags parsed Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ref = build_dataset_ref(
            "test",
            {
                "dataset_key": "s",
                "name": "S",
                "representation": "api_json",
                "tags": ["weather", "forecast"],
            },
        )
        assert ref.tags == ("weather", "forecast")
        assert "tags" not in ref.raw_metadata

    # test tags absent is empty Describes scenario being tested.
    def test_tags_absent_is_empty(self) -> None:
        """
        test tags absent is empty Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ref = build_dataset_ref(
            "test",
            {"dataset_key": "s", "name": "S", "representation": "api_json"},
        )
        assert ref.tags == ()

    # test tags filters non strings Describes scenario being tested.
    def test_tags_filters_non_strings(self) -> None:
        """
        test tags filters non strings Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ref = build_dataset_ref(
            "test",
            {
                "dataset_key": "s",
                "name": "S",
                "representation": "api_json",
                "tags": ["valid", 123, None, "also_valid"],
            },
        )
        assert ref.tags == ("valid", "also_valid")

    # test source url parsed Describes scenario being tested.
    def test_source_url_parsed(self) -> None:
        """
        test source url parsed Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ref = build_dataset_ref(
            "test",
            {
                "dataset_key": "s",
                "name": "S",
                "representation": "api_json",
                "source_url": "https://data.go.kr/example",
            },
        )
        assert ref.source_url == "https://data.go.kr/example"
        assert "source_url" not in ref.raw_metadata

    # test source url absent is none Describes scenario being tested.
    def test_source_url_absent_is_none(self) -> None:
        """
        test source url absent is none Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ref = build_dataset_ref(
            "test",
            {"dataset_key": "s", "name": "S", "representation": "api_json"},
        )
        assert ref.source_url is None

    # test existing description removed from raw metadata Describes scenario being tested.
    def test_existing_description_removed_from_raw_metadata(self) -> None:
        """
        test existing description removed from raw metadata Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        ref = build_dataset_ref(
            "test",
            {
                "dataset_key": "s",
                "name": "S",
                "representation": "api_json",
                "description": "test",
                "base_url": "http://example.com",
            },
        )
        assert "description" not in ref.raw_metadata
        assert "base_url" in ref.raw_metadata


class TestBuildSchemaConstraints:
    """
    TestBuildSchemaConstraints Class encapsulating related operations.

    This class in ``tests/unit/test_catalogue_validation.py`` module manages TestBuildSchemaConstraintsstate and behavior.
    Key methods: _make_ref_with_fields, test_no_constraints_returns_none_on_field, test_constraints_parsed, test_constraints_max_length_and_values, test_constraints_numeric.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    def _make_ref_with_fields(self, fields: list[dict[str, object]]) -> object:
        """
        Helper for make ref with fields processing.

        Args:
            fields (list[dict[str, object]]): Input value provided by caller.

        Returns:
            object: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        from kpubdata.providers._common import build_dataset_ref, build_schema_from_metadata

        raw = {
            "dataset_key": "test_ds",
            "name": "Test",
            "representation": "api_json",
            "fields": fields,
        }
        ref = build_dataset_ref("test", raw)
        return build_schema_from_metadata(ref)

    # test no constraints returns none on field Describes scenario being tested.
    def test_no_constraints_returns_none_on_field(self) -> None:
        """
        test no constraints returns none on field Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        schema = self._make_ref_with_fields([{"name": "col1", "type": "string"}])
        assert schema is not None
        assert schema.fields[0].constraints is None

    # test constraints parsed Describes scenario being tested.
    def test_constraints_parsed(self) -> None:
        """
        test constraints parsed Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        schema = self._make_ref_with_fields(
            [
                {
                    "name": "time",
                    "type": "string",
                    "constraints": {"format": "YYYYMM", "pattern": r"^\d{6}$"},
                }
            ]
        )
        assert schema is not None
        fc = schema.fields[0].constraints
        assert fc is not None
        assert fc.format == "YYYYMM"
        assert fc.pattern == r"^\d{6}$"
        assert fc.max_length is None

    # test constraints max length and values Describes scenario being tested.
    def test_constraints_max_length_and_values(self) -> None:
        """
        test constraints max length and values Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        schema = self._make_ref_with_fields(
            [
                {
                    "name": "status",
                    "type": "string",
                    "constraints": {
                        "max_length": 10,
                        "allowed_values": ["A", "B", "C"],
                    },
                }
            ]
        )
        assert schema is not None
        fc = schema.fields[0].constraints
        assert fc is not None
        assert fc.max_length == 10
        assert fc.allowed_values == ("A", "B", "C")

    # test constraints numeric Describes scenario being tested.
    def test_constraints_numeric(self) -> None:
        """
        test constraints numeric Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        schema = self._make_ref_with_fields(
            [
                {
                    "name": "score",
                    "type": "number",
                    "constraints": {"min_value": 0, "max_value": 100.5},
                }
            ]
        )
        assert schema is not None
        fc = schema.fields[0].constraints
        assert fc is not None
        assert fc.min_value == 0
        assert fc.max_value == 100.5

    # test empty constraints dict returns none Describes scenario being tested.
    def test_empty_constraints_dict_returns_none(self) -> None:
        """
        test empty constraints dict returns none Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        schema = self._make_ref_with_fields([{"name": "col", "type": "string", "constraints": {}}])
        assert schema is not None
        assert schema.fields[0].constraints is None

    # test invalid constraints type ignored Describes scenario being tested.
    def test_invalid_constraints_type_ignored(self) -> None:
        """
        test invalid constraints type ignored Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        schema = self._make_ref_with_fields(
            [{"name": "col", "type": "string", "constraints": "invalid"}]
        )
        assert schema is not None
        assert schema.fields[0].constraints is None
