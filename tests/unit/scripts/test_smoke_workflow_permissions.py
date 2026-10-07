"""The drift report job is given the permissions its script uses (#859).

``scripts/report_drift.py`` lists the smoke workflow's runs, downloads their result
artifacts and files or updates an issue. The workflow's default permission is
``contents: read`` alone, so the job has to declare the other two itself; without them
every call is refused and the report cannot say anything.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SMOKE = REPO_ROOT / ".github" / "workflows" / "smoke.yml"


def _job(name: str) -> str:
    """The text of one job: from its key to the next key at the same indentation."""
    text = SMOKE.read_text(encoding="utf-8")
    match = re.search(rf"^  {re.escape(name)}:\n(?P<body>(?:(?:    .*)?\n)+)", text, re.MULTILINE)
    assert match is not None, f"smoke.yml has no job named {name}"
    return match.group("body")


def _permissions(job: str) -> dict[str, str]:
    match = re.search(r"^    permissions:\n(?P<body>(?:      .+\n)+)", job, re.MULTILINE)
    if match is None:
        return {}
    pairs = (line.strip().split(":", 1) for line in match.group("body").splitlines())
    return {key.strip(): value.strip() for key, value in pairs}


def test_the_drift_report_job_can_read_runs_and_write_issues() -> None:
    assert _permissions(_job("drift-report")) == {
        "contents": "read",
        "actions": "read",
        "issues": "write",
    }


def test_the_job_that_calls_the_provider_keeps_the_workflow_default() -> None:
    """Negative: the wider permissions belong to the report job only."""
    assert _permissions(_job("datago-live")) == {}
    text = SMOKE.read_text(encoding="utf-8")
    assert re.search(r"^permissions:\n  contents: read\n", text, re.MULTILINE)
