"""Raising the Python floor must preserve public enum string formatting."""

import json
from enum import Enum

import pytest

from kpubdata.core.capability import Operation, PaginationMode
from kpubdata.core.representation import Representation
from kpubdata.core.status import (
    ApplicationRequirement,
    DatasetStatus,
    DriftClassification,
    ProbeStatus,
    SpecStatus,
    VerificationLevel,
)


@pytest.mark.parametrize(
    "enum_type",
    [
        Operation,
        PaginationMode,
        Representation,
        DatasetStatus,
        VerificationLevel,
        ApplicationRequirement,
        SpecStatus,
        ProbeStatus,
        DriftClassification,
    ],
)
def test_public_string_enums_keep_formatting_and_wire_values(enum_type: type[Enum]) -> None:
    for member in enum_type:
        assert str(member) == f"{enum_type.__name__}.{member.name}"
        assert f"{member}" == str(member)
        assert json.loads(json.dumps(member)) == member.value
