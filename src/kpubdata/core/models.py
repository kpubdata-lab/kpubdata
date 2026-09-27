"""Canonical domain models shared across providers and adapters."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import field
from importlib import import_module
from types import MappingProxyType

from kpubdata.core.capability import Operation, QuerySupport, _dataclass
from kpubdata.core.representation import Representation
from kpubdata.exceptions import InvalidRequestError


def _empty_proxy() -> MappingProxyType[str, object]:
    """Return empty immutable string-key mapping proxy."""
    return MappingProxyType({})


def _empty_object_proxy() -> MappingProxyType[str, object]:
    """Return empty immutable object-value mapping proxy."""
    return MappingProxyType({})


@_dataclass(slots=True, frozen=True)
class DatasetRef:
    """Canonical immutable reference to a provider dataset.

    Attributes:
        description: Human-readable string describing what this dataset provides.
        tags: Exploration classification tags (e.g., ``("weather", "forecast")``).
        source_url: URL to original API docs or data portal page.
        query_support: Structured list-query capability metadata, if known.
        raw_metadata: Provider-specific exploration metadata for debugging.
    """

    id: str
    provider: str
    dataset_key: str
    name: str
    representation: Representation
    operations: frozenset[Operation] = frozenset()
    query_support: QuerySupport | None = None
    raw_metadata: MappingProxyType[str, object] = field(default_factory=_empty_proxy)
    description: str | None = None
    tags: tuple[str, ...] = ()
    source_url: str | None = None

    def supports(self, op: Operation) -> bool:
        """Return whether this dataset supports the requested operation."""

        return op in self.operations

    def __repr__(self) -> str:
        """Return developer-friendly concise representation."""
        ops = ", ".join(sorted(operation.value for operation in self.operations))
        return f"DatasetRef(id={self.id!r}, provider={self.provider!r}, ops=[{ops}])"


@_dataclass(slots=True)
class Query:
    """Provider-agnostic query object for record list retrieval.

    Attributes:
        filters: Provider-specific filter payload merged into query conversion.
        extra: Additional provider-specific parameters not covered by canonical fields.
    """

    filters: dict[str, object] = field(default_factory=dict)
    page: int | None = None
    page_size: int | None = None
    cursor: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    fields: list[str] | None = None
    sort: list[str] | None = None
    extra: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Perform canonical-level type validation on Query creation."""
        self._validate_page()
        self._validate_page_size()
        self._validate_cursor()
        self._validate_dates()
        self._validate_fields()
        self._validate_sort()
        self._validate_dict_type(self.filters, "filters")
        self._validate_dict_type(self.extra, "extra")

    def _validate_page(self) -> None:
        """Validate that page field is a valid integer."""
        if self.page is None:
            return
        if isinstance(self.page, bool):
            raise InvalidRequestError("page must be an integer, not bool")
        if not isinstance(self.page, int):
            raise InvalidRequestError(
                f"page must be an integer or None, got {type(self.page).__name__}"
            )
        if self.page < 1:
            raise InvalidRequestError("page must be a positive integer (>= 1)")

    def _validate_page_size(self) -> None:
        """Validate that page_size field is a valid integer."""
        if self.page_size is None:
            return
        if isinstance(self.page_size, bool):
            raise InvalidRequestError("page_size must be an integer, not bool")
        if not isinstance(self.page_size, int):
            raise InvalidRequestError(
                f"page_size must be an integer or None, got {type(self.page_size).__name__}"
            )
        if self.page_size < 1:
            raise InvalidRequestError("page_size must be a positive integer (>= 1)")

    def _validate_cursor(self) -> None:
        """Validate that cursor field is a string."""
        if self.cursor is None:
            return
        if not isinstance(self.cursor, str):
            raise InvalidRequestError(
                f"cursor must be a string or None, got {type(self.cursor).__name__}"
            )
        if self.cursor == "":
            raise InvalidRequestError("cursor must be a non-empty string")

    def _validate_dates(self) -> None:
        """Validate that date fields are non-empty strings."""
        for field_name, value in (("start_date", self.start_date), ("end_date", self.end_date)):
            if value is None:
                continue
            if not isinstance(value, str):
                raise InvalidRequestError(
                    f"{field_name} must be a string or None, got {type(value).__name__}"
                )
            if value == "" or value.isspace():
                raise InvalidRequestError(f"{field_name} must be a non-empty string")

    def _validate_fields(self) -> None:
        """Validate that fields field is a list of strings."""
        if self.fields is None:
            return
        if not isinstance(self.fields, list):
            raise InvalidRequestError(
                f"fields must be a list of strings or None, got {type(self.fields).__name__}"
            )
        for i, item in enumerate(self.fields):
            if not isinstance(item, str):
                raise InvalidRequestError(
                    f"fields must contain only strings, got {type(item).__name__} at index {i}"
                )

    def _validate_sort(self) -> None:
        """Validate that sort field is a list of strings."""
        if self.sort is None:
            return
        if not isinstance(self.sort, list):
            raise InvalidRequestError(
                f"sort must be a list of strings or None, got {type(self.sort).__name__}"
            )
        for i, item in enumerate(self.sort):
            if not isinstance(item, str):
                raise InvalidRequestError(
                    f"sort must contain only strings, got {type(item).__name__} at index {i}"
                )

    def _validate_dict_type(self, value: dict[str, object], field_name: str) -> None:
        """Validate that dict field keys are strings."""
        if not isinstance(value, dict):
            raise InvalidRequestError(f"{field_name} must be a dict, got {type(value).__name__}")
        for key in value:
            if not isinstance(key, str):
                raise InvalidRequestError(
                    f"{field_name} keys must be strings, got {type(key).__name__}"
                )


@_dataclass(slots=True, frozen=True)
class FieldIssue:
    """One disagreement between a spec's ``fields[]`` and the data that arrived.

    Casting is per column and only when every value succeeds: the apartment-trade
    ``aptDong`` is mostly ``"105"`` but some rows carry a neighbourhood name, and
    casting row by row would leave int and str in one column. That policy is right and
    unchanged — what was wrong is that it happened silently, so a spec could disagree
    with reality for months without anyone learning.

    Attributes:
        field: The declared field name.
        declared_type: The type the spec declares.
        kind: ``uncastable`` when values do not fit the declared type, ``missing``
            when the response omits the field, ``undeclared`` when the response
            carries a key the spec does not mention. The last one is drift: the
            provider added something.
        failed_count: How many values were affected. Counting means walking the whole
            column rather than stopping at the first failure.
        sample_values: Up to three offending values, so a reader can see what the data
            actually looks like without fetching it again.
    """

    field: str
    declared_type: str
    kind: str
    failed_count: int
    sample_values: tuple[object, ...] = ()


@_dataclass(slots=True)
class ValidationReport:
    """What normalisation found while applying a spec to a response.

    Always produced, never raised on its own. The default stays lenient — a
    mismatch does not fail a query — but it stops being invisible.

    Attributes:
        checked_fields: How many declared fields were examined.
        issues: Every disagreement found, in declaration order.
    """

    checked_fields: int = 0
    issues: list[FieldIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        """Whether the data matched the spec in every respect."""
        return not self.issues

    def issues_of(self, kind: str) -> list[FieldIssue]:
        """The issues of one kind, so callers do not filter by hand."""
        return [issue for issue in self.issues if issue.kind == kind]

    def __repr__(self) -> str:
        """Summarise rather than dump every issue."""
        if self.ok:
            return f"ValidationReport(ok=True, checked_fields={self.checked_fields})"
        counts: dict[str, int] = {}
        for issue in self.issues:
            counts[issue.kind] = counts.get(issue.kind, 0) + 1
        detail = ", ".join(f"{kind}={count}" for kind, count in sorted(counts.items()))
        return f"ValidationReport(ok=False, checked_fields={self.checked_fields}, {detail})"


@_dataclass(slots=True)
class RecordBatch:
    """Normalized record batch returned from dataset query.

    Attributes:
        next_page: Next page number for offset-based pagination.
        next_cursor: Opaque cursor token for cursor-based pagination.
        raw: Provider-specific response payload used to derive this batch.
        meta: Additional adapter metadata not fitting canonical fields.
        validation: What normalisation found while applying the spec, or None for a
            batch that did not go through the spec executor — the hand-written
            adapters do not, so None means "not examined", never "no problems".
    """

    items: list[dict[str, object]]
    dataset: DatasetRef
    total_count: int | None = None
    next_page: int | None = None
    next_cursor: str | None = None
    raw: object | None = None
    meta: dict[str, object] = field(default_factory=dict)
    validation: ValidationReport | None = None

    def __len__(self) -> int:
        """Return the number of records in the batch."""
        return len(self.items)

    def __iter__(self) -> Iterator[dict[str, object]]:
        """Return an iterator over batch records."""
        return iter(self.items)

    def __bool__(self) -> bool:
        """Return True if batch has any records."""
        return bool(self.items)

    def to_pandas(self) -> object:
        """Convert items to pandas ``DataFrame``."""
        try:
            pd = import_module("pandas")
        except ImportError:
            raise ImportError(
                "pandas is required for to_pandas(). Install with: pip install kpubdata[pandas]"
            ) from None
        return pd.DataFrame(self.items)


@_dataclass(slots=True)
class FieldConstraints:
    """Structured constraints for a dataset field.

    All attributes are optional. Only populate values actually declared by the provider catalog.

    Attributes:
        max_length: Maximum character length (for string fields).
        min_value: Minimum numeric value (for numeric fields).
        max_value: Maximum numeric value (for numeric fields).
        pattern: Regex pattern that values must match (e.g., ``"^\\\\d{6}$"``).
        allowed_values: Closed set of permitted values.
        format: Semantic format hint (e.g., ``"YYYYMM"``, ``"date"``, ``"url"``).
    """

    max_length: int | None = None
    min_value: float | None = None
    max_value: float | None = None
    pattern: str | None = None
    allowed_values: tuple[str, ...] | None = None
    format: str | None = None


@_dataclass(slots=True)
class FieldDescriptor:
    """Describe a single field in a dataset schema.

    Attributes:
        constraints: Optional structured constraints for the field.
        raw: Provider-specific field metadata preserved for advanced use.
    """

    name: str
    title: str | None = None
    type: str | None = None
    description: str | None = None
    nullable: bool | None = None
    raw: MappingProxyType[str, object] = field(default_factory=_empty_object_proxy)
    constraints: FieldConstraints | None = None


@_dataclass(slots=True)
class SchemaDescriptor:
    """Describe schema metadata exposed for a dataset.

    Attributes:
        raw: Provider-specific schema metadata preserved without normalization.
    """

    dataset: DatasetRef
    fields: list[FieldDescriptor]
    raw: MappingProxyType[str, object] = field(default_factory=_empty_object_proxy)


__all__ = [
    "DatasetRef",
    "FieldConstraints",
    "FieldDescriptor",
    "Query",
    "RecordBatch",
    "SchemaDescriptor",
]
