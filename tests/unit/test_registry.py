"""Tests for provider registry."""

from __future__ import annotations

import pytest

from kpubdata.exceptions import ProviderNotRegisteredError
from kpubdata.registry import ProviderRegistry


class FakeAdapter:
    """Minimal adapter satisfying the protocol for testing."""

    def __init__(self, provider_name: str = "fake") -> None:
        """
        Initialize internal state for the instance.

        Args:
            provider_name (str): Input value provided by caller.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        self._name: str = provider_name

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

    def list_datasets(self) -> list[object]:
        """
        list datasets Performs the operation.

        Returns:
            list[object]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return []

    def search_datasets(self, text: str) -> list[object]:
        """
        search datasets Performs the operation.

        Args:
            text (str): Input value provided by caller.

        Returns:
            list[object]: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        _ = text
        return []

    def get_dataset(self, dataset_key: str) -> object:
        """
        get dataset Performs the operation.

        Args:
            dataset_key (str): Input value provided by caller.

        Returns:
            object: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.
        """
        return None

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


class TestProviderRegistry:
    """
    TestProviderRegistry Class encapsulating related operations.

    This class in ``tests/unit/test_registry.py`` module manages TestProviderRegistrystate and behavior.
    Key methods: test_register_and_get, test_contains, test_iter, test_duplicate_raises, test_missing_raises.

    Attributes:
        Properties defined in constructor and class body are reused as shared context by methods.
    """

    # test register and get Describes scenario being tested.
    def test_register_and_get(self) -> None:
        """
        test register and get Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        reg = ProviderRegistry()
        adapter = FakeAdapter("test")
        reg.register(adapter)
        assert reg.get("test") is adapter

    # test contains Describes scenario being tested.
    def test_contains(self) -> None:
        """
        test contains Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        reg = ProviderRegistry()
        reg.register(FakeAdapter("test"))
        assert "test" in reg
        assert "other" not in reg

    # test iter Describes scenario being tested.
    def test_iter(self) -> None:
        """
        test iter Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        reg = ProviderRegistry()
        reg.register(FakeAdapter("b"))
        reg.register(FakeAdapter("a"))
        assert list(reg) == ["a", "b"]

    # test duplicate raises Describes scenario being tested.
    def test_duplicate_raises(self) -> None:
        """
        test duplicate raises Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        reg = ProviderRegistry()
        reg.register(FakeAdapter("dup"))
        with pytest.raises(ValueError, match="already registered"):
            reg.register(FakeAdapter("dup"))

    # test missing raises Describes scenario being tested.
    def test_missing_raises(self) -> None:
        """
        test missing raises Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        reg = ProviderRegistry()
        with pytest.raises(ProviderNotRegisteredError):
            reg.get("nonexistent")

    # test lazy register Describes scenario being tested.
    def test_lazy_register(self) -> None:
        """
        test lazy register Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        reg = ProviderRegistry()
        reg.register_lazy("lazy", lambda: FakeAdapter("lazy"))
        assert "lazy" in reg
        adapter = reg.get("lazy")
        assert adapter.name == "lazy"

    # test validate rejects bad adapter Describes scenario being tested.
    def test_validate_rejects_bad_adapter(self) -> None:
        """
        test validate rejects bad adapter Verifies scenario.

        Returns:
            None: Returns the result or return value from downstream calls.

        Raises:
            Propagates exceptions from implementation or dependencies.

        Examples:
            Verifies expected behavior matches test name without regression.
        """
        reg = ProviderRegistry()
        with pytest.raises(TypeError):
            reg.register(object())  # type: ignore[arg-type]


class TestCapabilityContractValidation:
    """Registration-time capability contract verification (#231)."""

    def _ds(self, key: str, *, operations: tuple[str, ...] = ("list", "raw")) -> object:
        """Create test DatasetRef."""
        from kpubdata.core.capability import Operation
        from kpubdata.core.models import DatasetRef
        from kpubdata.core.representation import Representation

        return DatasetRef(
            id=f"fake.{key}",
            provider="fake",
            dataset_key=key,
            name=key,
            representation=Representation.API_JSON,
            operations=frozenset(Operation(op) for op in operations),
        )

    def test_registration_calls_list_datasets_and_passes_for_honest_adapter(self) -> None:
        """Passes if list_datasets non-empty and operations filled."""
        from kpubdata.registry import ProviderRegistry

        honest = FakeAdapter("honest")
        honest_datasets = [self._ds("a"), self._ds("b")]
        honest.list_datasets = lambda: honest_datasets  # type: ignore[method-assign]

        reg = ProviderRegistry()
        reg.register(honest)  # Must not raise exception.
        assert "honest" in reg

    def test_registration_rejects_adapter_whose_list_datasets_crashes(self) -> None:
        """Fails fast as CapabilityContractError if list_datasets raises."""
        from kpubdata.exceptions import CapabilityContractError
        from kpubdata.registry import ProviderRegistry

        broken = FakeAdapter("broken")

        def boom() -> list[object]:
            raise RuntimeError("catalogue not loaded")

        broken.list_datasets = boom  # type: ignore[method-assign]

        reg = ProviderRegistry()
        with pytest.raises(CapabilityContractError, match="failed to enumerate datasets"):
            reg.register(broken)
        assert "broken" not in reg

    def test_registration_rejects_dataset_with_empty_operations(self) -> None:
        """Rejects dataset with empty operations as "false support claim"."""
        from kpubdata.exceptions import CapabilityContractError
        from kpubdata.registry import ProviderRegistry

        dishonest = FakeAdapter("dishonest")
        dishonest_datasets = [self._ds("a", operations=())]
        dishonest.list_datasets = lambda: dishonest_datasets  # type: ignore[method-assign]

        reg = ProviderRegistry()
        with pytest.raises(CapabilityContractError, match="empty operations"):
            reg.register(dishonest)

    def test_registration_rejects_non_list_return_value(self) -> None:
        """Rejects if list_datasets returns non-list."""
        from kpubdata.exceptions import CapabilityContractError
        from kpubdata.registry import ProviderRegistry

        bad_shape = FakeAdapter("bad_shape")
        bad_shape.list_datasets = lambda: "not a list"  # type: ignore[method-assign,return-value]

        reg = ProviderRegistry()
        with pytest.raises(CapabilityContractError, match="must return a list"):
            reg.register(bad_shape)

    def test_registration_rejects_non_dataset_ref_entries(self) -> None:
        """Rejects if list_datasets mixes non-DatasetRef entries."""
        from kpubdata.exceptions import CapabilityContractError
        from kpubdata.registry import ProviderRegistry

        adapter = FakeAdapter("mixed")
        adapter.list_datasets = lambda: [self._ds("ok"), {"not": "a ref"}]  # type: ignore[method-assign]

        reg = ProviderRegistry()
        with pytest.raises(CapabilityContractError, match="non-DatasetRef entries"):
            reg.register(adapter)

    def test_validate_capabilities_can_be_disabled(self) -> None:
        """Skips capability validation if validate_capabilities=False (deprecation path)."""
        from kpubdata.registry import ProviderRegistry

        adapter = FakeAdapter("legacy")
        adapter.list_datasets = lambda: [self._ds("a", operations=())]  # type: ignore[method-assign]

        reg = ProviderRegistry()
        reg.register(adapter, validate_capabilities=False)  # Must not raise exception.
        assert "legacy" in reg

    def test_lazy_registration_also_validates_capabilities_on_materialization(self) -> None:
        """Lazy registration also checked at materialization."""
        from kpubdata.exceptions import CapabilityContractError
        from kpubdata.registry import ProviderRegistry

        def factory() -> FakeAdapter:
            a = FakeAdapter("lazy_bad")
            a.list_datasets = lambda: [self._ds("a", operations=())]  # type: ignore[method-assign]
            return a

        reg = ProviderRegistry()
        reg.register_lazy("lazy_bad", factory)
        with pytest.raises(CapabilityContractError):
            reg.get("lazy_bad")

    def test_duplicate_name_short_circuits_before_capability_validation(self) -> None:
        """Skips validation for already-registered names (expensive catalog load)."""
        from kpubdata.registry import ProviderRegistry

        reg = ProviderRegistry()
        reg.register(FakeAdapter("dup_provider"))

        call_count = {"n": 0}
        second = FakeAdapter("dup_provider")

        def expensive_list() -> list[object]:
            call_count["n"] += 1
            return []

        second.list_datasets = expensive_list  # type: ignore[method-assign]

        with pytest.raises(ValueError, match="already registered"):
            reg.register(second)
        # If capability check came after name collision check, list_datasets should not be called.
        assert call_count["n"] == 0


class TestLazyConcurrency:
    """Lazy materialization concurrency and durability (#262)."""

    def test_concurrent_get_materializes_once_and_all_succeed(self) -> None:
        """Concurrent get() all receive same instance—no spurious calls during materialization race."""
        import threading

        registry = ProviderRegistry()
        calls = []
        lock = threading.Lock()

        def factory():
            with lock:
                calls.append(1)
            # Simulate materialization cost—another thread may get() in between.
            import time

            time.sleep(0.01)
            return FakeAdapter("lazy-race")

        registry.register_lazy("lazy-race", factory)

        results: list[object] = []
        errors: list[BaseException] = []

        def worker():
            try:
                results.append(registry.get("lazy-race"))
            except BaseException as exc:  # noqa: BLE001 - for test collection
                errors.append(exc)

        barrier = threading.Barrier(8)

        def racer():
            barrier.wait()
            worker()

        threads = [threading.Thread(target=racer) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert errors == []
        assert len(results) == 8
        assert all(result is results[0] for result in results)
        # Second get returns already-materialized eager item.
        assert registry.get("lazy-race") is results[0]

    def test_failed_factory_keeps_lazy_entry_retryable(self) -> None:
        """Item not lost on factory failure—retryable (#262 durability)."""
        registry = ProviderRegistry()
        attempts = []

        def flaky_factory():
            attempts.append(1)
            if len(attempts) == 1:
                raise RuntimeError("transient factory failure")
            return FakeAdapter("flaky")

        registry.register_lazy("flaky", flaky_factory)

        with pytest.raises(RuntimeError):
            _ = registry.get("flaky")

        recovered = registry.get("flaky")
        assert recovered.name == "flaky"
