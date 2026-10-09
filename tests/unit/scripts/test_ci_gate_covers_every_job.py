"""The CI gate waits for every job, and every job has a time limit.

``CI gate`` is the one required status check that stands for ``ci.yml``; its ``needs``
list is written by hand. A job added without being listed there can fail while the gate
passes, and a job without ``timeout-minutes`` can hold a runner for GitHub's six-hour
default. Both are checked here, so the omission fails a test, not a later pull request.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

#: Jobs the gate leaves out on purpose. ``spec-changes`` writes a summary for the
#: reviewer and is not a verdict (see the comment above ``gate`` in ci.yml).
NOT_A_VERDICT = frozenset({"spec-changes"})


def _jobs(path: Path) -> dict[str, dict[str, object]]:
    workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
    jobs = workflow["jobs"]
    assert isinstance(jobs, dict)
    return jobs


def _jobs_the_gate_misses(jobs: dict[str, dict[str, object]]) -> set[str]:
    needs = jobs["gate"]["needs"]
    assert isinstance(needs, list)
    return set(jobs) - {"gate"} - NOT_A_VERDICT - set(needs)


def _jobs_without_a_timeout(jobs: dict[str, dict[str, object]]) -> set[str]:
    # A job that calls a reusable workflow (``uses``) cannot set a timeout itself.
    return {
        name for name, job in jobs.items() if "timeout-minutes" not in job and "uses" not in job
    }


def test_the_gate_needs_every_job_that_gives_a_verdict() -> None:
    assert _jobs_the_gate_misses(_jobs(WORKFLOWS / "ci.yml")) == set()


def test_a_job_the_gate_does_not_need_is_reported() -> None:
    """Negative: a new job left out of ``needs`` is found."""
    jobs = copy.deepcopy(_jobs(WORKFLOWS / "ci.yml"))
    jobs["new-check"] = {"runs-on": "ubuntu-latest", "timeout-minutes": 5}

    assert _jobs_the_gate_misses(jobs) == {"new-check"}


@pytest.mark.parametrize("path", sorted(WORKFLOWS.glob("*.y*ml")), ids=lambda path: path.name)
def test_every_job_has_a_time_limit(path: Path) -> None:
    assert _jobs_without_a_timeout(_jobs(path)) == set()


def test_a_job_without_a_time_limit_is_reported() -> None:
    """Negative: the check does not pass a job that has none."""
    jobs = copy.deepcopy(_jobs(WORKFLOWS / "ci.yml"))
    del jobs["gate"]["timeout-minutes"]

    assert _jobs_without_a_timeout(jobs) == {"gate"}
