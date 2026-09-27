"""KPubData's core canonical models and capability metadata."""

from __future__ import annotations

from kpubdata.core.capability import Operation, PaginationMode, QuerySupport
from kpubdata.core.models import (
    DatasetRef,
    FieldConstraints,
    FieldDescriptor,
    Query,
    RecordBatch,
    SchemaDescriptor,
)
from kpubdata.core.representation import Representation

__all__ = [
    "DatasetRef",
    "FieldConstraints",
    "FieldDescriptor",
    "Operation",
    "PaginationMode",
    "Query",
    "QuerySupport",
    "RecordBatch",
    "Representation",
    "SchemaDescriptor",
]
