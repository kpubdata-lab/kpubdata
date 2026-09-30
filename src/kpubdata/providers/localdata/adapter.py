"""Localdata provider adapter.

Uses shared data.go.kr family implementation (:mod:`kpubdata.providers._datago_family`)
directly — authentication, envelope, and pagination conventions match datago.
Previously localdata and semas each had 375-line copies; comparing by normalizing
names showed **0 lines of code difference**. That duplication caused "03"
(NODATA) handling to exist in only one, creating #470 regression.

The original localdata.go.kr closed on 2026-04-16, but the data was **migrated
to data.go.kr** (`apis.data.go.kr/1741000/...`). Three datasets (bakery,
general_restaurant, rest_cafe) pass live-API verification as of 2026-09-09.
The remaining 56 need activation on data.go.kr — they return 403,
not because the endpoint is dead but because the key lacks permission (#618).
"""

from __future__ import annotations

from kpubdata.providers._datago_family import DataGoFamilyAdapter


class LocaldataAdapter(DataGoFamilyAdapter):
    """Localdata (Local Administrative License) dataset adapter.

    Data was migrated from localdata.go.kr to data.go.kr. The API is alive;
    datasets without activation return 403 (application required, not retired).
    """

    provider_name = "localdata"
    catalogue_package = "kpubdata.providers.localdata"


__all__ = ["LocaldataAdapter"]
