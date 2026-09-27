"""Contract tests applied uniformly to every provider adapter (#455).

Parametrizes, in one place, the parts of `PROVIDER_ADAPTER_CONTRACT.md` §2
that **do not vary per adapter**. Per-adapter test files keep only the
dialect differences (envelope shapes, parameter-name mapping, provider
error codes).

Why bundle them this way: with 14 adapters each rewriting the same
contract, every new adapter duplicates the whole test set (at issue time
test code was 2.8x the source). Adding one line here applies immediately
to all 14, and a new adapter inherits the entire contract by adding a
single line to ``_ADAPTERS``.

**This is a regression tripwire, not a coverage metric** — the machine
checks the spots one tends to skip as "surely this works" when wiring up
a new provider.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.capability import Operation
from kpubdata.core.models import DatasetRef
from kpubdata.exceptions import DatasetNotFoundError

# (module name, class name). Adding a new adapter means adding one line here.
_ADAPTER_SPECS: list[tuple[str, str]] = [
    ("bok", "BokAdapter"),
    ("datago", "DataGoAdapter"),
    ("fds", "FdsAdapter"),
    ("kipris", "KiprisAdapter"),
    ("korean", "KoreanAdapter"),
    ("kosis", "KosisAdapter"),
    ("krx", "KrxAdapter"),
    ("law", "LawAdapter"),
    ("localdata", "LocaldataAdapter"),
    ("lofin", "LofinAdapter"),
    ("neis", "NeisAdapter"),
    ("semas", "SemasAdapter"),
    ("seoul", "SeoulAdapter"),
    ("sgis", "SgisAdapter"),
]


def _load(module_name: str, class_name: str) -> Any:
    module = importlib.import_module(f"kpubdata.providers.{module_name}.adapter")
    return getattr(module, class_name)


def _adapter(module_name: str, class_name: str) -> Any:
    """Build the adapter with no key — catalogue lookup must not demand credentials."""
    return _load(module_name, class_name)(config=KPubDataConfig(provider_keys={}))


_PARAMS = [pytest.param(m, c, id=m) for m, c in _ADAPTER_SPECS]


def _adapter_params(func: Any) -> Any:
    return pytest.mark.parametrize(("module_name", "class_name"), _PARAMS)(func)


# --- Basic surface ---------------------------------------------------------


@_adapter_params
def test_adapter_exposes_the_required_surface(module_name: str, class_name: str) -> None:
    """Every method the Client calls must exist (contract §2)."""
    cls = _load(module_name, class_name)
    for attribute in (
        "name",
        "list_datasets",
        "search_datasets",
        "get_dataset",
        "get_schema",
        "query_records",
        "call_raw",
    ):
        assert hasattr(cls, attribute), f"{class_name} is missing {attribute}"


@_adapter_params
def test_adapter_declares_whether_it_needs_a_key(module_name: str, class_name: str) -> None:
    """``requires_api_key`` must be a bool — the Client branches on it."""
    cls = _load(module_name, class_name)
    assert isinstance(cls.requires_api_key, bool)


@_adapter_params
def test_provider_name_matches_the_module(module_name: str, class_name: str) -> None:
    assert _adapter(module_name, class_name).name == module_name


@_adapter_params
def test_catalogue_loads_without_any_credential(module_name: str, class_name: str) -> None:
    """Discovery must work without a key — if listing needs a key, discoverability dies."""
    datasets = _adapter(module_name, class_name).list_datasets()
    assert datasets, f"{module_name} has an empty catalogue"
    assert all(isinstance(d, DatasetRef) for d in datasets)


# --- Catalogue integrity ---------------------------------------------------


@_adapter_params
def test_dataset_keys_are_unique(module_name: str, class_name: str) -> None:
    """With duplicate keys, which one ``get_dataset`` returns is undefined."""
    keys = [d.dataset_key for d in _adapter(module_name, class_name).list_datasets()]
    duplicates = {k for k in keys if keys.count(k) > 1}
    assert not duplicates, f"{module_name} has duplicate dataset keys: {sorted(duplicates)}"


@_adapter_params
def test_dataset_ids_are_provider_qualified(module_name: str, class_name: str) -> None:
    """``id`` must be provider-qualified so cross-provider results do not mix."""
    for dataset in _adapter(module_name, class_name).list_datasets():
        assert dataset.provider == module_name
        assert dataset.id.startswith(f"{module_name}."), dataset.id


@_adapter_params
def test_every_dataset_declares_at_least_one_operation(module_name: str, class_name: str) -> None:
    """Empty operations means "can do nothing" — enforce honest declarations (contract §2)."""
    for dataset in _adapter(module_name, class_name).list_datasets():
        assert dataset.operations, f"{dataset.id} declares no operations"
        assert all(isinstance(op, Operation) for op in dataset.operations)


@_adapter_params
def test_declared_operations_match_supports(module_name: str, class_name: str) -> None:
    for dataset in _adapter(module_name, class_name).list_datasets():
        for operation in dataset.operations:
            assert dataset.supports(operation)


@_adapter_params
def test_datasets_have_human_readable_names(module_name: str, class_name: str) -> None:
    for dataset in _adapter(module_name, class_name).list_datasets():
        assert dataset.name.strip(), f"{dataset.id} has a blank name"


# --- Lookup ----------------------------------------------------------------


@_adapter_params
def test_get_dataset_returns_the_catalogue_entry(module_name: str, class_name: str) -> None:
    adapter = _adapter(module_name, class_name)
    for dataset in adapter.list_datasets():
        assert adapter.get_dataset(dataset.dataset_key) is dataset


@_adapter_params
def test_unknown_dataset_key_raises_not_found(module_name: str, class_name: str) -> None:
    """Returning None silently leaves callers unable to tell an empty result from a typo."""
    adapter = _adapter(module_name, class_name)
    with pytest.raises(DatasetNotFoundError) as exc:
        adapter.get_dataset("no-such-dataset-key-xyz")
    assert exc.value.provider == module_name
    # The error must carry the provider-qualified id so the user knows what to fix.
    assert "no-such-dataset-key-xyz" in str(exc.value)


@_adapter_params
def test_search_finds_a_known_dataset(module_name: str, class_name: str) -> None:
    adapter = _adapter(module_name, class_name)
    sample = adapter.list_datasets()[0]
    assert sample in adapter.search_datasets(sample.dataset_key)


@_adapter_params
def test_search_is_case_insensitive(module_name: str, class_name: str) -> None:
    adapter = _adapter(module_name, class_name)
    sample = adapter.list_datasets()[0]
    assert sample in adapter.search_datasets(sample.dataset_key.upper())


@_adapter_params
def test_search_with_no_match_returns_empty(module_name: str, class_name: str) -> None:
    assert _adapter(module_name, class_name).search_datasets("존재하지-않는-키워드-zzz") == []


@_adapter_params
def test_list_datasets_returns_a_fresh_list(module_name: str, class_name: str) -> None:
    """Mutating the list a caller receives must not pollute the adapter's internal catalogue."""
    adapter = _adapter(module_name, class_name)
    first = adapter.list_datasets()
    first.clear()
    assert adapter.list_datasets(), f"{module_name} leaked its internal catalogue list"


# --- Schema declarations ---------------------------------------------------


@_adapter_params
def test_get_schema_is_honest_about_what_it_knows(module_name: str, class_name: str) -> None:
    """Unknown schema means ``None`` — never invent an empty schema (contract §2)."""
    adapter = _adapter(module_name, class_name)
    for dataset in adapter.list_datasets():
        schema = adapter.get_schema(dataset)
        if schema is None:
            continue
        assert schema.fields, f"{dataset.id} returned an empty schema instead of None"
