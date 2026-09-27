"""Localdata provider adapter.

Uses shared data.go.kr family implementation (:mod:`kpubdata.providers._datago_family`)
directly — authentication, envelope, and pagination conventions match datago.
Previously localdata and semas each had 375-line copies; comparing by normalizing
names showed **0 lines of code difference**. That duplication caused "03"
(NODATA) handling to exist in only one, creating #470 regression.
"""

from __future__ import annotations

from kpubdata.providers._datago_family import DataGoFamilyAdapter


class LocaldataAdapter(DataGoFamilyAdapter):
    """Localdata (Local Administrative License) dataset adapter."""

    provider_name = "localdata"
    catalogue_package = "kpubdata.providers.localdata"


__all__ = ["LocaldataAdapter"]
