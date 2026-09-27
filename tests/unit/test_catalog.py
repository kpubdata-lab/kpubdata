"""Tests for catalog discovery."""

from __future__ import annotations

import pytest

from kpubdata.catalog import Catalog
from kpubdata.core.capability import Operation
from kpubdata.core.models import DatasetRef
from kpubdata.core.representation import Representation
from kpubdata.exceptions import DatasetNotFoundError
from kpubdata.registry import ProviderRegistry


class StubAdapter:
    """Adapter returning predetermined datasets for testing."""

    def __init__(self, provider_name: str, datasets: list[DatasetRef]) -> None:
        """
        Initialize internal state for the instance.

        Args:
            provider_name (str): Input value provided by caller.
            datasets (list[DatasetRef]): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self._name = provider_name
        self._datasets = datasets

    @property
    def name(self) -> str:
        """
        name Performs the operation.

        Returns:
            str: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return self._name

    def list_datasets(self) -> list[DatasetRef]:
        """
        list datasets Performs the operation.

        Returns:
            list[DatasetRef]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return list(self._datasets)

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
        needle = text.casefold()
        return [d for d in self._datasets if needle in d.name.casefold()]

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
        for d in self._datasets:
            if d.dataset_key == dataset_key:
                return d
        raise DatasetNotFoundError(f"Not found: {dataset_key}")

    def query_records(self, dataset: object, query: object) -> object:
        """
        query records Performs the operation.

        Args:
            dataset (object): Input value provided by caller.
            query (object): Input value provided by caller.

        Returns:
            object: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return None

    def get_schema(self, dataset: object) -> object:
        """
        get schema Performs the operation.

        Args:
            dataset (object): Input value provided by caller.

        Returns:
            object: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return None

    def call_raw(self, dataset: object, operation: str, params: dict[str, object]) -> object:
        """
        call raw Performs the operation.

        Args:
            dataset (object): Input value provided by caller.
            operation (str): Input value provided by caller.
            params (dict[str, object]): Input value provided by caller.

        Returns:
            object: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = dataset, operation, params
        return None


def _make_ref(provider: str, key: str, name: str) -> DatasetRef:
    """
    Helper handling make ref processing.

    Args:
        provider (str): Input value provided by caller.
        key (str): Input value provided by caller.
        name (str): Input value provided by caller.

    Returns:
        DatasetRef: Returns the result or return value from downstream calls.

    Raises:
        Propagates exceptions from implementation or dependencies.
    """
    return DatasetRef(
        id=f"{provider}.{key}",
        provider=provider,
        dataset_key=key,
        name=name,
        representation=Representation.API_JSON,
        operations=frozenset({Operation.LIST, Operation.RAW}),
    )


class TestCatalog:
    """
    TestCatalog Class encapsulating related operations.

    This class in ``tests/unit/test_catalog.py`` module manages TestCatalogstate and behavior.
    Key methods: _build, test_list_all, test_list_filtered, test_search, test_search_case_insensitive.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    def _build(self) -> Catalog:
        """
        Helper handling build processing.

        Returns:
            Catalog: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        reg = ProviderRegistry()
        reg.register(
            StubAdapter(
                "alpha",
                [
                    _make_ref("alpha", "ds1", "Alpha Dataset One"),
                    _make_ref("alpha", "ds2", "Alpha Dataset Two"),
                ],
            )
        )
        reg.register(
            StubAdapter(
                "beta",
                [
                    _make_ref("beta", "subway", "Beta Subway Data"),
                ],
            )
        )
        return Catalog(reg)

    # test list all Test scenario summary.
    def test_list_all(self) -> None:
        """
        test list all Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build()
        result = catalog.list()
        assert len(result) == 3

    # test list filtered Test scenario summary.
    def test_list_filtered(self) -> None:
        """
        test list filtered Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build()
        result = catalog.list(provider="alpha")
        assert len(result) == 2

    # test search Test scenario summary.
    def test_search(self) -> None:
        """
        test search Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build()
        result = catalog.search("subway")
        assert len(result) == 1
        assert result[0].name == "Beta Subway Data"

    # test search case insensitive Test scenario summary.
    def test_search_case_insensitive(self) -> None:
        """
        test search case insensitive Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build()
        result = catalog.search("ALPHA")
        assert len(result) == 2

    # test search with provider filter Test scenario summary.
    def test_search_with_provider_filter(self) -> None:
        """
        test search with provider filter Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build()
        result = catalog.search("dataset", provider="alpha")
        assert len(result) == 2
        assert all(r.provider == "alpha" for r in result)

    # test search delegates to adapter Test scenario summary.
    def test_search_delegates_to_adapter(self) -> None:
        """
        test search delegates to adapter Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build()
        result = catalog.search("subway")
        assert len(result) == 1
        assert result[0].name == "Beta Subway Data"

    # test search no match returns empty Test scenario summary.
    def test_search_no_match_returns_empty(self) -> None:
        """
        test search no match returns empty Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build()
        result = catalog.search("nonexistent_xyz")
        assert result == []

    # test resolve Test scenario summary.
    def test_resolve(self) -> None:
        """
        test resolve Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build()
        adapter, ref = catalog.resolve("beta.subway")
        assert ref.dataset_key == "subway"
        assert adapter.name == "beta"

    # test resolve invalid format Test scenario summary.
    def test_resolve_invalid_format(self) -> None:
        """
        test resolve invalid format Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build()
        with pytest.raises(DatasetNotFoundError, match="Invalid dataset id"):
            _ = catalog.resolve("nodot")

    # test resolve not found Test scenario summary.
    def test_resolve_not_found(self) -> None:
        """
        test resolve not found Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build()
        with pytest.raises(DatasetNotFoundError):
            _ = catalog.resolve("alpha.nonexistent")


class TestCatalogFuzzySearch:
    """Tests for catalog-level fuzzy search across name, description, tags, and id."""

    @staticmethod
    def _make_rich_ref(
        provider: str,
        key: str,
        name: str,
        *,
        description: str | None = None,
        tags: tuple[str, ...] = (),
    ) -> DatasetRef:
        """
        Helper for make rich ref processing.

        Args:
            provider (str): Input value provided by caller.
            key (str): Input value provided by caller.
            name (str): Input value provided by caller.
            description (str | None): Input value provided by caller.
            tags (tuple[str, ...]): Input value provided by caller.

        Returns:
            DatasetRef: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return DatasetRef(
            id=f"{provider}.{key}",
            provider=provider,
            dataset_key=key,
            name=name,
            representation=Representation.API_JSON,
            operations=frozenset({Operation.LIST}),
            description=description,
            tags=tags,
        )

    def _build_rich(self) -> Catalog:
        """
        Helper for build rich processing.

        Returns:
            Catalog: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        reg = ProviderRegistry()
        reg.register(
            StubAdapter(
                "weather",
                [
                    self._make_rich_ref(
                        "weather",
                        "village_fcst",
                        "동네예보",
                        description="기상청 단기예보 조회 서비스",
                        tags=("weather", "forecast", "기상"),
                    ),
                    self._make_rich_ref(
                        "weather",
                        "air_quality",
                        "대기오염정보",
                        description="한국환경공단 대기질 정보",
                        tags=("air", "pollution", "환경"),
                    ),
                ],
            )
        )
        reg.register(
            StubAdapter(
                "finance",
                [
                    self._make_rich_ref(
                        "finance",
                        "base_rate",
                        "기준금리",
                        description="한국은행 기준금리 조회",
                        tags=("economy", "interest-rate", "금리"),
                    ),
                ],
            )
        )
        return Catalog(reg)

    # test search by description Test scenario summary.
    def test_search_by_description(self) -> None:
        """
        test search by description Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build_rich()
        result = catalog.search("기상청")
        assert len(result) == 1
        assert result[0].dataset_key == "village_fcst"

    # test search by tag Test scenario summary.
    def test_search_by_tag(self) -> None:
        """
        test search by tag Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build_rich()
        result = catalog.search("pollution")
        assert len(result) == 1
        assert result[0].dataset_key == "air_quality"

    # test search by korean tag Test scenario summary.
    def test_search_by_korean_tag(self) -> None:
        """
        test search by korean tag Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build_rich()
        result = catalog.search("금리")
        assert len(result) == 1
        assert result[0].dataset_key == "base_rate"

    # test search by id substring Test scenario summary.
    def test_search_by_id_substring(self) -> None:
        """
        test search by id substring Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build_rich()
        result = catalog.search("base_rate")
        assert len(result) >= 1
        assert result[0].dataset_key == "base_rate"

    # test search partial name Test scenario summary.
    def test_search_partial_name(self) -> None:
        """
        test search partial name Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build_rich()
        result = catalog.search("예보")
        assert len(result) == 1
        assert result[0].dataset_key == "village_fcst"

    # test search sorted by relevance Test scenario summary.
    def test_search_sorted_by_relevance(self) -> None:
        """
        test search sorted by relevance Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build_rich()
        result = catalog.search("대기")
        assert len(result) >= 1
        assert result[0].dataset_key == "air_quality"

    # test search custom threshold Test scenario summary.
    def test_search_custom_threshold(self) -> None:
        """
        test search custom threshold Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build_rich()
        strict = catalog.search("weathr", threshold=0.9)
        lenient = catalog.search("weathr", threshold=0.1)
        assert len(lenient) >= len(strict)

    # test search empty string Test scenario summary.
    def test_search_empty_string(self) -> None:
        """
        test search empty string Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build_rich()
        result = catalog.search("")
        assert len(result) == 3

    # test search provider filter with fuzzy Test scenario summary.
    def test_search_provider_filter_with_fuzzy(self) -> None:
        """
        test search provider filter with fuzzy Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        catalog = self._build_rich()
        result = catalog.search("정보", provider="weather")
        assert all(r.provider == "weather" for r in result)


class TestScoreDataset:
    """Direct unit tests for the _score_dataset helper."""

    @staticmethod
    def _ref(name: str, **kwargs: object) -> DatasetRef:
        """
        Helper for ref processing.

        Args:
            name (str): Input value provided by caller.
            **kwargs (object): Input value provided by caller.

        Returns:
            DatasetRef: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return DatasetRef(
            id="test.ds",
            provider="test",
            dataset_key="ds",
            name=name,
            representation=Representation.API_JSON,
            **kwargs,  # type: ignore[arg-type]
        )

    # test exact substring returns one Test scenario summary.
    def test_exact_substring_returns_one(self) -> None:
        """
        test exact substring returns one Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _score_dataset

        ref = self._ref("Hello World")
        assert _score_dataset("hello", ref) == 1.0

    # test no match returns low Test scenario summary.
    def test_no_match_returns_low(self) -> None:
        """
        test no match returns low Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _score_dataset

        ref = self._ref("Hello World")
        score = _score_dataset("zzzzzzzzz", ref)
        assert score < 0.2

    # test description match Test scenario summary.
    def test_description_match(self) -> None:
        """
        test description match Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _score_dataset

        ref = self._ref("Short Name", description="A detailed description with keywords")
        assert _score_dataset("keywords", ref) == 1.0

    # test tag match Test scenario summary.
    def test_tag_match(self) -> None:
        """
        test tag match Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _score_dataset

        ref = self._ref("Name", tags=("weather", "forecast"))
        assert _score_dataset("forecast", ref) == 1.0

    # test case insensitive Test scenario summary.
    def test_case_insensitive(self) -> None:
        """
        test case insensitive Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _score_dataset

        ref = self._ref("Base Rate")
        assert _score_dataset("BASE RATE", ref) == 1.0

    # test whitespace only returns one Test scenario summary.
    def test_whitespace_only_returns_one(self) -> None:
        """
        test whitespace only returns one Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _score_dataset

        ref = self._ref("Anything")
        assert _score_dataset("   ", ref) == 1.0

    def test_search_does_not_call_adapter_search_datasets(self) -> None:
        """Catalog.search uses catalog-level scoring, not adapter delegation."""
        from unittest.mock import MagicMock

        adapter = StubAdapter("mock", [_make_ref("mock", "ds", "Mock Data")])
        adapter.search_datasets = MagicMock(side_effect=AssertionError("should not be called"))  # type: ignore[method-assign]

        reg = ProviderRegistry()
        reg.register(adapter)
        catalog = Catalog(reg)

        result = catalog.search("Mock")
        assert len(result) == 1
        adapter.search_datasets.assert_not_called()


class TestCatalogIndexedScorer:
    """Tests for the indexed scorer introduced in the catalog search refactor."""

    @staticmethod
    def _make_ref(
        provider: str,
        key: str,
        name: str,
        *,
        description: str | None = None,
        tags: tuple[str, ...] = (),
    ) -> DatasetRef:
        """
        Helper handling make ref processing.

        Args:
            provider (str): Input value provided by caller.
            key (str): Input value provided by caller.
            name (str): Input value provided by caller.
            description (str | None): Input value provided by caller.
            tags (tuple[str, ...]): Input value provided by caller.

        Returns:
            DatasetRef: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return DatasetRef(
            id=f"{provider}.{key}",
            provider=provider,
            dataset_key=key,
            name=name,
            representation=Representation.API_JSON,
            operations=frozenset({Operation.LIST}),
            description=description,
            tags=tags,
        )

    def _build_catalog(self) -> Catalog:
        """
        Helper for build catalog processing.

        Returns:
            Catalog: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        reg = ProviderRegistry()
        reg.register(
            StubAdapter(
                "weather",
                [
                    self._make_ref(
                        "weather",
                        "village_fcst",
                        "동네예보",
                        description="기상청 단기예보 조회 서비스",
                        tags=("weather", "forecast", "기상"),
                    ),
                    self._make_ref(
                        "weather",
                        "marine_fcst",
                        "해양예보",
                        description="기상청 해양예보 서비스",
                        tags=("weather", "marine"),
                    ),
                ],
            )
        )
        reg.register(
            StubAdapter(
                "finance",
                [
                    self._make_ref(
                        "finance",
                        "base_rate",
                        "기준금리",
                        description="한국은행 기준금리",
                        tags=("economy", "rate"),
                    ),
                ],
            )
        )
        return Catalog(reg)

    def test_token_overlap_ranks_full_match_above_partial(self) -> None:
        """A dataset matching both query tokens outranks one matching only one."""
        catalog = self._build_catalog()
        # 'marine weather' is not a contiguous substring of any field, so both
        # datasets fall through the substring layer. marine_fcst tags contain
        # both 'marine' and 'weather' (2/2 → ceil score), while village_fcst
        # tags contain only 'weather' (1/2 → mid-band score).
        result = catalog.search("marine weather", threshold=0.6)
        keys = [ref.dataset_key for ref in result]
        assert "marine_fcst" in keys and "village_fcst" in keys
        assert keys.index("marine_fcst") < keys.index("village_fcst")

    def test_provider_name_is_searchable(self) -> None:
        """Searching by provider name returns that provider's datasets."""
        catalog = self._build_catalog()
        result = catalog.search("finance")
        assert len(result) == 1
        assert result[0].provider == "finance"

    def test_dataset_key_is_searchable_as_single_token(self) -> None:
        """Identifier-style dataset_key remains a single token (no underscore split)."""
        catalog = self._build_catalog()
        # threshold=0.9 filters out fuzzy noise from sibling keys that share
        # the '_fcst' suffix; only the exact substring hit on village_fcst
        # (score 1.0) qualifies.
        result = catalog.search("village_fcst", threshold=0.9)
        assert len(result) == 1
        assert result[0].dataset_key == "village_fcst"

    def test_substring_outranks_token_overlap(self) -> None:
        """An exact substring hit (score 1.0) always sorts above token-overlap hits."""
        catalog = self._build_catalog()
        # 'forecast' appears as a substring in the 'forecast' tag on village_fcst
        # (score 1.0) and is also a query token. marine_fcst lacks the
        # 'forecast' tag, so it can only earn a token-overlap or fuzzy score.
        result = catalog.search("forecast", threshold=0.5)
        assert result, "expected at least one result"
        assert result[0].dataset_key == "village_fcst"

    def test_no_result_for_long_meaningless_query(self) -> None:
        """A long random query stays below threshold (no spurious fuzzy hits)."""
        catalog = self._build_catalog()
        result = catalog.search("qzxvbnmqzxvbnmqzxvbnm_no_such_dataset_anywhere")
        assert result == []

    def test_case_insensitive_token_match(self) -> None:
        """Token overlap is computed on casefolded text."""
        catalog = self._build_catalog()
        # 'MARINE' is uppercase but should match 'marine' tag (substring path).
        result = catalog.search("MARINE")
        assert len(result) == 1
        assert result[0].dataset_key == "marine_fcst"

    def test_mixed_korean_and_ascii_tokenization(self) -> None:
        """Korean and ASCII tokens coexist in a single query."""
        catalog = self._build_catalog()
        # 'Korean forecast' substring search test (dataset has Korean description)
        # village_fcst; 'forecast' substring hits its tag. Both pass via the
        # substring layer; result is non-empty and stably ordered.
        result = catalog.search("기상청 forecast", threshold=0.5)
        assert any(r.dataset_key == "village_fcst" for r in result)

    def test_provider_filter_applies_before_indexing(self) -> None:
        """Provider filter narrows candidates; cross-provider matches are excluded."""
        catalog = self._build_catalog()
        # 'Korean bank' appears only in finance dataset (search test with Korean);
        # provider='weather' the candidate pool excludes finance entirely.
        result = catalog.search("한국은행", provider="weather")
        assert result == []

    def test_empty_query_returns_all_candidates(self) -> None:
        """An empty query yields score 1.0 for every dataset (existing contract)."""
        catalog = self._build_catalog()
        result = catalog.search("")
        assert len(result) == 3

    def test_threshold_above_one_returns_empty(self) -> None:
        """Threshold > 1.0 excludes everything (token overlap caps below 1.0)."""
        catalog = self._build_catalog()
        # A query that hits only via token overlap (no substring): pick a query
        # token that appears only as a token (e.g. provider name as a token).
        # With threshold=1.01 nothing can pass.
        result = catalog.search("forecast", threshold=1.01)
        assert result == []


class TestIndexedScorerHelpers:
    """Direct tests for the indexed scorer building blocks."""

    @staticmethod
    def _ref(
        name: str,
        *,
        description: str | None = None,
        tags: tuple[str, ...] = (),
    ) -> DatasetRef:
        """
        Helper for ref processing.

        Args:
            name (str): Input value provided by caller.
            description (str | None): Input value provided by caller.
            tags (tuple[str, ...]): Input value provided by caller.

        Returns:
            DatasetRef: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return DatasetRef(
            id="prov.key",
            provider="prov",
            dataset_key="key",
            name=name,
            representation=Representation.API_JSON,
            operations=frozenset({Operation.LIST}),
            description=description,
            tags=tags,
        )

    # test tokenize splits on non word chars Test scenario summary.
    def test_tokenize_splits_on_non_word_chars(self) -> None:
        """
        test tokenize splits on non word chars Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _tokenize

        assert _tokenize("Hello, World!") == frozenset({"hello", "world"})

    # test tokenize keeps underscore identifier intact Test scenario summary.
    def test_tokenize_keeps_underscore_identifier_intact(self) -> None:
        """
        test tokenize keeps underscore identifier intact Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _tokenize

        assert _tokenize("village_fcst") == frozenset({"village_fcst"})

    # test tokenize korean word Test scenario summary.
    def test_tokenize_korean_word(self) -> None:
        """
        test tokenize korean word Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _tokenize

        assert _tokenize("기상청 예보") == frozenset({"기상청", "예보"})

    # test tokenize empty returns empty set Test scenario summary.
    def test_tokenize_empty_returns_empty_set(self) -> None:
        """
        test tokenize empty returns empty set Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _tokenize

        assert _tokenize("") == frozenset()
        assert _tokenize("   ") == frozenset()

    # test build index includes provider and dataset key Test scenario summary.
    def test_build_index_includes_provider_and_dataset_key(self) -> None:
        """
        test build index includes provider and dataset key Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _build_index

        ref = self._ref("Name", tags=("alpha",), description="desc")
        index = _build_index([ref])
        assert len(index) == 1
        item = index[0]
        assert "prov" in item.tokens
        assert "key" in item.tokens
        assert "name" in item.tokens
        assert "alpha" in item.tokens
        assert "desc" in item.tokens

    # test score indexed substring returns one Test scenario summary.
    def test_score_indexed_substring_returns_one(self) -> None:
        """
        test score indexed substring returns one Verifies the scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        from kpubdata.catalog import _build_index, _score_indexed, _tokenize

        ref = self._ref("Hello World")
        item = _build_index([ref])[0]
        score = _score_indexed("hello", _tokenize("hello"), item)
        assert score == 1.0

    def test_score_indexed_token_overlap_band(self) -> None:
        """Token overlap score stays strictly below 1.0 and within the band."""
        from kpubdata.catalog import (
            _TOKEN_OVERLAP_CEIL,
            _TOKEN_OVERLAP_FLOOR,
            _build_index,
            _score_indexed,
            _tokenize,
        )

        ref = self._ref("Apple Banana", description="fruit basket")
        item = _build_index([ref])[0]
        # Query token 'apple' is a substring of 'apple banana' → returns 1.0.
        # To force the token-overlap branch we need a query whose tokens match
        # item tokens exactly but whose normalized form is NOT a substring of
        # any field. 'banana apple' has both tokens; ' apple banana' contains
        # both as a substring. Use a query that is not contiguous in any field.
        query = "banana zzz"
        score = _score_indexed(query, _tokenize(query), item)
        # 1/2 of query tokens matched ('banana') → expect floor + 0.5 * (ceil-floor)
        expected = _TOKEN_OVERLAP_FLOOR + 0.5 * (_TOKEN_OVERLAP_CEIL - _TOKEN_OVERLAP_FLOOR)
        assert score == pytest.approx(expected)
        assert score < 1.0
        assert _TOKEN_OVERLAP_FLOOR <= score <= _TOKEN_OVERLAP_CEIL

    def test_score_indexed_full_token_overlap_below_substring_score(self) -> None:
        """Even 100% token overlap stays below substring score (1.0)."""
        from kpubdata.catalog import (
            _TOKEN_OVERLAP_CEIL,
            _build_index,
            _score_indexed,
            _tokenize,
        )

        ref = self._ref("Apple Banana")
        item = _build_index([ref])[0]
        # 'banana apple' tokens fully overlap but the literal string is not a
        # contiguous substring of 'apple banana'.
        query = "banana apple"
        score = _score_indexed(query, _tokenize(query), item)
        assert score == pytest.approx(_TOKEN_OVERLAP_CEIL)
        assert score < 1.0


class TestSearchIndexCache:
    """catalog.search index reuse (#279)."""

    def test_repeated_searches_reuse_built_index(self, monkeypatch) -> None:
        """_build_index runs once for identical catalog setup."""
        import kpubdata.catalog as catalog_module

        calls: list[int] = []
        original = catalog_module._build_index

        def counting_build(datasets):
            calls.append(1)
            return original(datasets)

        monkeypatch.setattr(catalog_module, "_build_index", counting_build)

        catalog = None
        if catalog is None:
            from kpubdata.registry import ProviderRegistry

            class _StubAdapter:
                def __init__(self) -> None:
                    self.datasets = [
                        _make_ref("cached", "alpha", "캐시 검증용"),
                        _make_ref("cached", "beta", "두번째 항목"),
                    ]

                @property
                def name(self) -> str:
                    return "stub"

                def list_datasets(self):
                    return self.datasets

                def search_datasets(self, *args, **kwargs):  # pragma: no cover
                    return self.datasets

                def get_dataset(self, *args, **kwargs):  # pragma: no cover
                    raise KeyError(args)

                def query_records(self, *args, **kwargs):  # pragma: no cover
                    raise NotImplementedError

                def get_schema(self, *args, **kwargs):  # pragma: no cover
                    return None

                def call_raw(self, *args, **kwargs):  # pragma: no cover
                    raise NotImplementedError

            registry = ProviderRegistry()
            registry.register(_StubAdapter(), validate_capabilities=False)
            catalog = catalog_module.Catalog(registry)

        first = catalog.search("캐시")
        second = catalog.search("캐시")
        third = catalog.search("두번째")

        assert first and second and third
        assert len(calls) == 1

    def test_registry_change_rebuilds_index(self, monkeypatch) -> None:
        """Index rebuilt when catalog setup changes (cache invalidation)."""
        import kpubdata.catalog as catalog_module

        calls: list[int] = []
        original = catalog_module._build_index

        def counting_build(datasets):
            calls.append(1)
            return original(datasets)

        monkeypatch.setattr(catalog_module, "_build_index", counting_build)

        from kpubdata.registry import ProviderRegistry

        class _StubAdapter:
            def __init__(self, suffix: str) -> None:
                self._suffix = suffix

            @property
            def name(self) -> str:
                return f"stub{self._suffix}"

            def list_datasets(self):
                return [_make_ref(f"set{self._suffix}", "one", f"항목 {self._suffix}")]

            def search_datasets(self, *args, **kwargs):  # pragma: no cover
                return self.list_datasets()

            def get_dataset(self, *args, **kwargs):  # pragma: no cover
                raise KeyError(args)

            def query_records(self, *args, **kwargs):  # pragma: no cover
                raise NotImplementedError

            def get_schema(self, *args, **kwargs):  # pragma: no cover
                return None

            def call_raw(self, *args, **kwargs):  # pragma: no cover
                raise NotImplementedError

        registry = ProviderRegistry()
        registry.register(_StubAdapter("a"), validate_capabilities=False)
        catalog = catalog_module.Catalog(registry)
        assert catalog.search("항목")

        registry.register(_StubAdapter("b"), validate_capabilities=False)
        assert catalog.search("항목")

        assert len(calls) == 2
