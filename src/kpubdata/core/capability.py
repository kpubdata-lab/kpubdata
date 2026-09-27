"""Capability metadata describing the operations and queries a dataset supports."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass as _stdlib_dataclass
from enum import Enum
from typing import TypeVar

from .._typing import dataclass_transform

_T = TypeVar("_T")


@dataclass_transform()
def _dataclass(
    *,
    slots: bool = False,
    frozen: bool = False,
) -> Callable[[type[_T]], type[_T]]:
    """Return a dataclass decorator with the options already fixed."""

    def _decorate(cls: type[_T]) -> type[_T]:
        """Apply the dataclass options to the target class and return it."""
        return _stdlib_dataclass(slots=slots, frozen=frozen)(cls)  # pyright: ignore[reportCallIssue]

    return _decorate


class Operation(str, Enum):
    """The main operations a dataset can support."""

    LIST = "list"
    GET = "get"
    SCHEMA = "schema"
    RAW = "raw"
    DOWNLOAD = "download"


class PaginationMode(str, Enum):
    """How a dataset paginates."""

    OFFSET = "offset"
    INDEX = "index"
    CURSOR = "cursor"
    NONE = "none"


@_dataclass(slots=True, frozen=True)
class QuerySupport:
    """Structured metadata about the list-query features a dataset supports."""

    pagination: PaginationMode = PaginationMode.NONE
    filterable_fields: frozenset[str] = frozenset()
    sortable_fields: frozenset[str] = frozenset()
    time_range: bool = False
    max_page_size: int | None = None


__all__ = ["Operation", "PaginationMode", "QuerySupport"]
