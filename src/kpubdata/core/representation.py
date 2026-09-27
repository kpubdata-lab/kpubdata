"""Dataset representation types for source/form modeling."""

from __future__ import annotations

from enum import Enum


class Representation(str, Enum):
    """Describe how a dataset is provided based on source form, not access method."""

    API_JSON = "api_json"
    API_XML = "api_xml"
    FILE_CSV = "file_csv"
    FILE_EXCEL = "file_excel"
    SHEET = "sheet"
    OTHER = "other"


__all__ = ["Representation"]
