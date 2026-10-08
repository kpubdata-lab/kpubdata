"""Structure checks for the CI workflow's cancellation and timeout policy (#871).

A workflow file is code this repository ships: its cancellation rule and its
timeouts decide whether a main run leaves a usable result behind. These checks
hold that policy in place the same way the other workflow structure tests do.
"""

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/ci.yml")


def _load() -> dict:
    return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))


def test_only_a_pull_requests_own_run_is_cancelled() -> None:
    doc = _load()
    concurrency = doc["concurrency"]
    assert concurrency["group"] == "ci-${{ github.ref }}"
    # A merge to main must finish and keep its result; only a pull request's
    # newer push replaces that pull request's earlier run.
    assert concurrency["cancel-in-progress"] == "${{ github.event_name == 'pull_request' }}"


def test_every_job_declares_a_timeout() -> None:
    doc = _load()
    missing = [name for name, job in doc["jobs"].items() if "timeout-minutes" not in job]
    assert missing == [], f"jobs without timeout-minutes: {missing}"
