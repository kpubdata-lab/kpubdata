"""Dataset status vocabulary — the one canonical set and every mapping onto it (#619).

ADR 0005 is the rationale. Before it, six places named a dataset's state in six
vocabularies with no mapping between them, so a reader could not tell whether
SUPPORTED_DATA's schema-only level, ``fixture-verified`` and ``test-verified``
were the same thing.

Three kinds of name live here, and they are deliberately different types:

- ``DatasetStatus`` — **what a dataset is**. The canonical set. Every document
  that states a dataset's status uses these names or maps onto them.
- ``SpecStatus`` — what a spec file *declares* (``status:`` in the YAML). It is a
  maintainer override, not a level, so it maps onto ``DatasetStatus`` only
  partially: ``active`` means "no override, the evidence decides".
- ``ProbeStatus`` and ``DriftClassification`` — **what one call observed**. They
  are signals that move a status, never a status themselves.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import Enum
from functools import lru_cache
from importlib import resources
from types import MappingProxyType


class DatasetStatus(str, Enum):
    """Canonical dataset status. Ordered from least to most verified, then faults."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    FIXTURE_VERIFIED = "fixture_verified"
    LIVE_VERIFIED = "live_verified"
    PRODUCTION = "production"
    APPLICATION_REQUIRED = "application_required"
    UNSTABLE = "unstable"
    BROKEN = "broken"
    RETIRED = "retired"


class VerificationLevel(str, Enum):
    """How far a dataset has been checked, whatever else is true of it (#842).

    ``DatasetStatus`` answers with one name, so ``application_required`` hid whether
    the dataset behind it had been checked against fixtures or not at all. This is
    that axis alone. The values are the verification names of ``DatasetStatus``.
    """

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    FIXTURE_VERIFIED = "fixture_verified"
    LIVE_VERIFIED = "live_verified"
    PRODUCTION = "production"


class ApplicationRequirement(str, Enum):
    """Whether the provider asks for a per-dataset application before it answers (#842).

    ``UNKNOWN`` is the answer wherever nothing recorded says either way. It is not
    "none needed": most datasets have never had the question written down.
    """

    REQUIRED = "required"
    NOT_REQUIRED = "not_required"
    UNKNOWN = "unknown"


class SpecStatus(str, Enum):
    """Values of a spec's ``status:`` field. Kept in sync with ``specs/schema.json``."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    BROKEN = "broken"
    UNSTABLE = "unstable"


class ProbeStatus(str, Enum):
    """Outcome of one reachability probe call (#514). See ``kpubdata._probe``."""

    AVAILABLE = "available"
    AUTH_UNKNOWN = "auth_unknown"
    APPLICATION_REQUIRED = "application_required"
    PARAMS_INVALID = "params_invalid"
    RATE_LIMITED = "rate_limited"
    TEMPORARILY_UNAVAILABLE = "temporarily_unavailable"
    NETWORK_ERROR = "network_error"
    INSUFFICIENT_METADATA = "insufficient_metadata"
    RETIRED = "retired"


class DriftClassification(str, Enum):
    """Signal the drift state machine consumes (docs/DATASET_STATUS.md)."""

    HEALTHY = "HEALTHY"
    SCHEMA_CHANGED = "SCHEMA_CHANGED"
    PARAMETER_CHANGED = "PARAMETER_CHANGED"
    ENDPOINT_CHANGED = "ENDPOINT_CHANGED"
    RATE_LIMIT = "RATE_LIMIT"
    SERVICE_DOWN = "SERVICE_DOWN"
    UNKNOWN = "UNKNOWN"
    AUTH = "AUTH"
    APPLICATION_REQUIRED = "APPLICATION_REQUIRED"
    NO_DATA = "NO_DATA"
    RETIRED = "RETIRED"


#: Consecutive transient failures before a verified dataset becomes ``unstable``.
#: One number for both the state machine and the drift issue it files -- the
#: design documents disagreed (3 against "2+") before ADR 0005.
TRANSIENT_FAILURE_STREAK = 3

#: ``SUPPORTED_DATA.md`` first column → canonical status.
SUPPORTED_DATA_LEVELS: Mapping[str, DatasetStatus] = MappingProxyType(
    {
        "예정": DatasetStatus.PLANNED,
        "진행 중": DatasetStatus.IN_PROGRESS,
        "스키마만": DatasetStatus.FIXTURE_VERIFIED,
        "지원": DatasetStatus.LIVE_VERIFIED,
        "활용신청 대기": DatasetStatus.APPLICATION_REQUIRED,
        "폐기": DatasetStatus.RETIRED,
    }
)

#: ``docs/PRODUCTION_GRADE.md`` tiers → canonical status.
PRODUCTION_GRADE_TIERS: Mapping[str, DatasetStatus] = MappingProxyType(
    {
        "test-verified": DatasetStatus.FIXTURE_VERIFIED,
        "production-grade": DatasetStatus.PRODUCTION,
    }
)

#: Spec override → canonical status. ``None`` means "no override".
SPEC_STATUS_OVERRIDE: Mapping[SpecStatus, DatasetStatus | None] = MappingProxyType(
    {
        SpecStatus.ACTIVE: None,
        SpecStatus.UNSTABLE: DatasetStatus.UNSTABLE,
        SpecStatus.BROKEN: DatasetStatus.BROKEN,
        SpecStatus.DEPRECATED: DatasetStatus.RETIRED,
    }
)

#: Probe outcome → drift signal. ``None`` means the outcome says nothing about
#: the upstream API (a wrong probe parameter, an unparseable body) and moves no
#: status.
PROBE_TO_DRIFT: Mapping[ProbeStatus, DriftClassification | None] = MappingProxyType(
    {
        ProbeStatus.AVAILABLE: DriftClassification.HEALTHY,
        ProbeStatus.AUTH_UNKNOWN: DriftClassification.AUTH,
        ProbeStatus.APPLICATION_REQUIRED: DriftClassification.APPLICATION_REQUIRED,
        ProbeStatus.PARAMS_INVALID: None,
        ProbeStatus.RATE_LIMITED: DriftClassification.RATE_LIMIT,
        ProbeStatus.TEMPORARILY_UNAVAILABLE: DriftClassification.SERVICE_DOWN,
        ProbeStatus.NETWORK_ERROR: DriftClassification.UNKNOWN,
        ProbeStatus.INSUFFICIENT_METADATA: None,
        ProbeStatus.RETIRED: DriftClassification.RETIRED,
    }
)

#: Signals that mean user code breaks now. No streak: one is enough.
_STRUCTURAL = frozenset(
    {
        DriftClassification.SCHEMA_CHANGED,
        DriftClassification.PARAMETER_CHANGED,
        DriftClassification.ENDPOINT_CHANGED,
    }
)
#: Signals that may clear on their own. They count toward ``unstable``.
_TRANSIENT = frozenset(
    {
        DriftClassification.RATE_LIMIT,
        DriftClassification.SERVICE_DOWN,
        DriftClassification.UNKNOWN,
        DriftClassification.NO_DATA,
    }
)
_ACCESS = frozenset({DriftClassification.AUTH, DriftClassification.APPLICATION_REQUIRED})
#: Statuses the drift signal moves. The others change only by hand or by evidence.
_WATCHED = frozenset({DatasetStatus.PRODUCTION, DatasetStatus.LIVE_VERIFIED})
#: Cumulative failures that turn ``unstable`` into ``broken``.
UNSTABLE_TO_BROKEN_FAILURES = 7


def transition(
    current: DatasetStatus | str,
    classification: DriftClassification | str,
    streak: int,
    cumulative_failures: int = 0,
    previous_status: DatasetStatus | str | None = None,
) -> DatasetStatus:
    """Compute the next dataset status from a drift signal (docs/DATASET_STATUS.md).

    Args:
        current: The status now.
        classification: The latest signal.
        streak: How many times in a row ``classification`` has been seen, this one
            included.
        cumulative_failures: Failures seen while ``unstable``, for the 7-strike rule.
        previous_status: The status held before ``unstable`` or
            ``application_required``, restored when the dataset recovers.

    Returns:
        The next status. Pure: nothing is read or written.

    Raises:
        ValueError: A name outside the vocabulary, or a streak below 1.
    """
    status = DatasetStatus(current)
    signal = DriftClassification(classification)
    if streak < 1:
        raise ValueError(f"streak counts the signal just seen, so it is at least 1: {streak}")
    restore = DatasetStatus(previous_status) if previous_status else DatasetStatus.LIVE_VERIFIED
    if restore not in _WATCHED:
        # Restoring into a fault would loop; the verified level is the safe floor.
        restore = DatasetStatus.LIVE_VERIFIED
    healthy = signal is DriftClassification.HEALTHY

    if status in _WATCHED:
        if signal in _STRUCTURAL:
            return DatasetStatus.BROKEN
        if signal in _ACCESS:
            return DatasetStatus.APPLICATION_REQUIRED
        if signal in _TRANSIENT and streak >= TRANSIENT_FAILURE_STREAK:
            return DatasetStatus.UNSTABLE
        # HEALTHY, RETIRED (a person retires it) or a transient signal below the streak.
        return status
    if status is DatasetStatus.UNSTABLE:
        if healthy:
            return restore if streak >= TRANSIENT_FAILURE_STREAK else status
        if signal in _STRUCTURAL or cumulative_failures >= UNSTABLE_TO_BROKEN_FAILURES:
            return DatasetStatus.BROKEN
        return status
    if status is DatasetStatus.BROKEN:
        # The fixture must be re-recorded before the dataset counts as verified again.
        return DatasetStatus.FIXTURE_VERIFIED if healthy else status
    if status is DatasetStatus.APPLICATION_REQUIRED:
        # The application was approved: the dataset answers again.
        return restore if healthy else status
    # planned, in_progress, fixture_verified, retired: no automatic transition.
    return status


@lru_cache(maxsize=1)
def _packaged_statuses() -> Mapping[str, DatasetStatus]:
    """The dataset id → status map shipped with the package.

    ``scripts/gen_dataset_status.py`` writes it from ``dataset_metadata.json``, and a
    test fails when the two differ (#783, #842).
    """
    text = resources.files("kpubdata").joinpath("dataset_status.json").read_text(encoding="utf-8")
    return MappingProxyType({key: DatasetStatus(value) for key, value in json.loads(text).items()})


def dataset_status(dataset_id: str) -> DatasetStatus | None:
    """The status SUPPORTED_DATA.md gives ``dataset_id``, or None when it lists none.

    None means unknown — a dataset registered at run time, or an escape hatch such as
    ``datago.generic`` — never "verified".
    """
    return _packaged_statuses().get(dataset_id)


@lru_cache(maxsize=1)
def _packaged_metadata() -> Mapping[str, Mapping[str, object]]:
    """The dataset id → recorded level, verification and date shipped with the package.

    ``dataset_metadata.json`` is the source SUPPORTED_DATA.md's level columns and
    ``dataset_status.json`` are written from (``scripts/sync_supported_data.py``).
    """
    text = resources.files("kpubdata").joinpath("dataset_metadata.json").read_text(encoding="utf-8")
    return MappingProxyType(
        {key: MappingProxyType(dict(value)) for key, value in json.loads(text).items()}
    )


def dataset_verification(dataset_id: str) -> VerificationLevel | None:
    """How far ``dataset_id`` has been checked, or None when nothing records it.

    Independent of whether an application is pending: a dataset awaiting one is still
    ``fixture_verified`` when its fixtures pass.
    """
    entry = _packaged_metadata().get(dataset_id)
    if entry is None or entry["verification"] is None:
        # Unlisted, or retired: a dataset that no longer answers is not checked.
        return None
    return VerificationLevel(str(entry["verification"]))


def application_requirement(
    dataset_id: str, declared: object | None = None
) -> ApplicationRequirement:
    """Whether ``dataset_id`` needs a per-dataset application.

    Args:
        dataset_id: The dataset.
        declared: The ``application`` entry of its spec or catalogue, when it has one.
            Its ``required`` flag decides; without one, a recorded
            ``application_required`` level says an application is needed. Anything
            else is ``UNKNOWN``.
    """
    required = declared.get("required") if isinstance(declared, Mapping) else None
    if isinstance(required, bool):
        return ApplicationRequirement.REQUIRED if required else ApplicationRequirement.NOT_REQUIRED
    entry = _packaged_metadata().get(dataset_id)
    if entry is not None and entry["level"] == DatasetStatus.APPLICATION_REQUIRED.value:
        return ApplicationRequirement.REQUIRED
    return ApplicationRequirement.UNKNOWN


__all__ = [
    "PROBE_TO_DRIFT",
    "PRODUCTION_GRADE_TIERS",
    "SPEC_STATUS_OVERRIDE",
    "SUPPORTED_DATA_LEVELS",
    "TRANSIENT_FAILURE_STREAK",
    "UNSTABLE_TO_BROKEN_FAILURES",
    "ApplicationRequirement",
    "DatasetStatus",
    "DriftClassification",
    "ProbeStatus",
    "SpecStatus",
    "VerificationLevel",
    "application_requirement",
    "dataset_status",
    "dataset_verification",
    "transition",
]
