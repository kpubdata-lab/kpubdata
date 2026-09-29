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

from collections.abc import Mapping
from enum import Enum
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


__all__ = [
    "PROBE_TO_DRIFT",
    "PRODUCTION_GRADE_TIERS",
    "SPEC_STATUS_OVERRIDE",
    "SUPPORTED_DATA_LEVELS",
    "TRANSIENT_FAILURE_STREAK",
    "UNSTABLE_TO_BROKEN_FAILURES",
    "DatasetStatus",
    "DriftClassification",
    "ProbeStatus",
    "SpecStatus",
    "transition",
]
