"""Common catalogue and schema utilities for provider adapters."""

from __future__ import annotations

import json
from collections.abc import Mapping
from importlib.resources import files
from types import MappingProxyType
from typing import cast

from kpubdata.core.capability import Operation, PaginationMode, QuerySupport
from kpubdata.core.models import (
    DatasetRef,
    FieldConstraints,
    FieldDescriptor,
    SchemaDescriptor,
)
from kpubdata.core.representation import Representation
from kpubdata.exceptions import ConfigError

_CATALOGUE_CANONICAL_KEYS = frozenset(
    {
        "dataset_key",
        "name",
        "representation",
        "operations",
        "query_support",
        "description",
        "tags",
        "source_url",
    }
)


def load_catalogue(package_name: str, provider: str) -> tuple[DatasetRef, ...]:
    """Load and parse the provider package's catalogue.json."""
    package_files = files(package_name)
    catalogue_text = package_files.joinpath("catalogue.json").read_text(encoding="utf-8")
    parsed_catalogue = cast(object, json.loads(catalogue_text))
    if not isinstance(parsed_catalogue, list):
        msg = f"{provider} catalogue.json must contain a top-level JSON array"
        raise ConfigError(msg, provider=provider)

    catalogue_entries = cast(list[object], parsed_catalogue)
    datasets: list[DatasetRef] = []
    for entry_object in catalogue_entries:
        if not isinstance(entry_object, dict):
            msg = f"{provider} catalogue entries must be JSON objects"
            raise ConfigError(msg, provider=provider)
        typed_entry_object = cast(dict[object, object], entry_object)
        entry: dict[str, object] = {}
        for key, value in typed_entry_object.items():
            if not isinstance(key, str):
                msg = f"{provider} catalogue entry keys must be strings"
                raise ConfigError(msg, provider=provider)
            entry[key] = value
        datasets.append(build_dataset_ref(provider, entry))

    dataset_ids = [dataset.id for dataset in datasets]
    duplicate_ids = sorted(
        {dataset_id for dataset_id in dataset_ids if dataset_ids.count(dataset_id) > 1}
    )
    if duplicate_ids:
        duplicates = ", ".join(duplicate_ids)
        msg = f"{provider} catalogue contains duplicate dataset ids: {duplicates}"
        raise ConfigError(msg, provider=provider)

    return tuple(datasets)


def build_dataset_ref(provider: str, entry: dict[str, object]) -> DatasetRef:
    """Build a DatasetRef from a raw catalogue entry dict."""
    dataset_key = require_string_field(entry, "dataset_key", provider)
    name = require_string_field(entry, "name", provider)
    representation_value = require_string_field(entry, "representation", provider)
    dataset_id = f"{provider}.{dataset_key}"
    try:
        representation = Representation(representation_value)
    except ValueError as exc:
        msg = f"{provider} catalogue entry has invalid representation: {representation_value}"
        raise ConfigError(msg, provider=provider, dataset_id=dataset_id) from exc

    ops_raw_obj = entry.get("operations", [])
    ops_raw = cast(list[object], ops_raw_obj) if isinstance(ops_raw_obj, list) else []
    operations: set[Operation] = set()
    for op_raw in ops_raw:
        if not isinstance(op_raw, str):
            msg = f"{provider} catalogue entry has non-string operation value: {op_raw!r}"
            raise ConfigError(msg, provider=provider, dataset_id=dataset_id)
        try:
            operations.add(Operation(op_raw))
        except ValueError as exc:
            msg = f"{provider} catalogue entry has invalid operation: {op_raw}"
            raise ConfigError(msg, provider=provider, dataset_id=dataset_id) from exc

    query_support = _parse_query_support(entry, provider)

    description_raw = entry.get("description")
    description = description_raw if isinstance(description_raw, str) and description_raw else None

    tags_raw = entry.get("tags")
    tags: tuple[str, ...] = ()
    if isinstance(tags_raw, list):
        tags = tuple(t for t in cast(list[object], tags_raw) if isinstance(t, str))

    source_url_raw = entry.get("source_url")
    source_url = source_url_raw if isinstance(source_url_raw, str) and source_url_raw else None

    raw_metadata = MappingProxyType(
        {key: value for key, value in entry.items() if key not in _CATALOGUE_CANONICAL_KEYS}
    )

    return DatasetRef(
        id=dataset_id,
        provider=provider,
        dataset_key=dataset_key,
        name=name,
        representation=representation,
        description=description,
        tags=tags,
        source_url=source_url,
        operations=frozenset(operations),
        query_support=query_support,
        raw_metadata=raw_metadata,
    )


def _parse_query_support(entry: dict[str, object], provider: str) -> QuerySupport | None:
    """Parse query_support from a catalogue entry."""
    qs_raw_obj = entry.get("query_support")
    if not isinstance(qs_raw_obj, dict):
        return None

    qs_raw = cast(dict[str, object], qs_raw_obj)
    pagination_raw = qs_raw.get("pagination", "none")
    valid_pagination = {member.value for member in PaginationMode}
    if isinstance(pagination_raw, str):
        if pagination_raw not in valid_pagination:
            msg = f"{provider} query_support.pagination has invalid value: {pagination_raw}"
            raise ConfigError(msg, provider=provider)
        pagination = PaginationMode(pagination_raw)
    else:
        pagination = PaginationMode.NONE

    max_page_size = None
    if "max_page_size" in qs_raw:
        max_page_size_raw = qs_raw["max_page_size"]
        if isinstance(max_page_size_raw, int):
            max_page_size = max_page_size_raw
        elif isinstance(max_page_size_raw, str):
            max_page_size = int(max_page_size_raw)
        else:
            msg = f"{provider} query_support.max_page_size must be int-like"
            raise ConfigError(msg, provider=provider)

    return QuerySupport(pagination=pagination, max_page_size=max_page_size)


def _parse_field_constraints(entry: dict[str, object]) -> FieldConstraints | None:
    """Parse and return field constraints."""
    constraints_raw = entry.get("constraints")
    if not isinstance(constraints_raw, dict):
        return None
    c = cast(dict[str, object], constraints_raw)

    max_length = c.get("max_length")
    if not isinstance(max_length, int):
        max_length = None

    min_value = c.get("min_value")
    if not isinstance(min_value, (int, float)):
        min_value = None

    max_value = c.get("max_value")
    if not isinstance(max_value, (int, float)):
        max_value = None

    pattern = c.get("pattern")
    if not isinstance(pattern, str):
        pattern = None

    allowed_values_raw = c.get("allowed_values")
    allowed_values: tuple[str, ...] | None = None
    if isinstance(allowed_values_raw, list) and all(isinstance(v, str) for v in allowed_values_raw):
        allowed_values = tuple(allowed_values_raw)

    fmt = c.get("format")
    if not isinstance(fmt, str):
        fmt = None

    if all(v is None for v in (max_length, min_value, max_value, pattern, allowed_values, fmt)):
        return None

    return FieldConstraints(
        max_length=max_length,
        min_value=min_value,
        max_value=max_value,
        pattern=pattern,
        allowed_values=allowed_values,
        format=fmt,
    )


def build_schema_from_metadata(dataset: DatasetRef) -> SchemaDescriptor | None:
    """Build SchemaDescriptor from catalogue metadata fields."""
    fields_raw = dataset.raw_metadata.get("fields")
    if not isinstance(fields_raw, list) or not fields_raw:
        return None

    entries = cast(list[object], fields_raw)
    field_descriptors: list[FieldDescriptor] = []
    for entry_obj in entries:
        if not isinstance(entry_obj, dict):
            continue
        entry = cast(dict[str, object], entry_obj)
        name_raw = entry.get("name")
        if not isinstance(name_raw, str) or not name_raw:
            continue
        title_raw = entry.get("title")
        type_raw = entry.get("type")
        desc_raw = entry.get("description")
        nullable_raw = entry.get("nullable")
        constraints = _parse_field_constraints(entry)
        field_descriptors.append(
            FieldDescriptor(
                name=name_raw,
                title=title_raw if isinstance(title_raw, str) else None,
                type=type_raw if isinstance(type_raw, str) else None,
                description=desc_raw if isinstance(desc_raw, str) else None,
                nullable=nullable_raw if isinstance(nullable_raw, bool) else None,
                constraints=constraints,
                raw=MappingProxyType({k: v for k, v in entry.items() if k != "name"}),
            )
        )

    if not field_descriptors:
        return None

    return SchemaDescriptor(
        dataset=dataset,
        fields=field_descriptors,
        raw=MappingProxyType({"source": "catalogue"}),
    )


def coerce_int(value: object, default: int) -> int:
    """Coerce value to int; return default on failure."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def require_string_field(entry: Mapping[str, object], field_name: str, provider: str) -> str:
    """Extract required non-empty string field from catalogue entry."""
    value = entry.get(field_name)
    if isinstance(value, str) and value:
        return value
    raise ConfigError(
        f"{provider} catalogue entry missing non-empty string field: {field_name}",
        provider=provider,
    )


__all__ = [
    "build_dataset_ref",
    "build_schema_from_metadata",
    "coerce_int",
    "load_catalogue",
    "require_string_field",
]
