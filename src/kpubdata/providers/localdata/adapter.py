"""Localdata provider adapter — RETIRED (#527).

The localdata upstream closed on 2026-04-16. All 59 datasets are retired.
Calls emit a DeprecationWarning and will fail against the dead endpoints.

Uses shared data.go.kr family implementation (:mod:`kpubdata.providers._datago_family`)
directly — authentication, envelope, and pagination conventions match datago.
Previously localdata and semas each had 375-line copies; comparing by normalizing
names showed **0 lines of code difference**. That duplication caused "03"
(NODATA) handling to exist in only one, creating #470 regression.
"""

from __future__ import annotations

import warnings

from kpubdata.core.models import DatasetRef, Query, RecordBatch
from kpubdata.providers._datago_family import DataGoFamilyAdapter

_RETIRED_MSG = (
    "localdata upstream closed on 2026-04-16. All 59 datasets are retired (#527). "
    "Calls will fail. Check data.go.kr Localdata 2.0 for replacements."
)


class LocaldataAdapter(DataGoFamilyAdapter):
    """Localdata (Local Administrative License) dataset adapter — retired.

    The upstream API shut down on 2026-04-16. Every call emits a
    DeprecationWarning naming the retirement, then attempts the request
    (which will fail with a transport error against the dead endpoints).
    """

    provider_name = "localdata"
    catalogue_package = "kpubdata.providers.localdata"

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """Emit retirement warning, then attempt the (failing) query."""
        warnings.warn(_RETIRED_MSG, DeprecationWarning, stacklevel=2)
        return super().query_records(dataset, query)


__all__ = ["LocaldataAdapter"]
