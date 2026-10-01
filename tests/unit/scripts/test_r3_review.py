"""The R3 gate decides from labels and reviews, so it is tested on labels and reviews (#722).

kpubdata-builder#893 was labelled ``review:R3`` and merged with no review. The gate
that now refuses that is only as good as its reading of GitHub's review history, so
most of these tests are the ways a pull request could look approved without being so.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "r3_review.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("r3_review", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["r3_review"] = module
    spec.loader.exec_module(module)
    return module


r3 = _load_script()

AUTHOR = "agent-account"


def _pull(*labels: str, author: str = AUTHOR) -> dict[str, Any]:
    return {
        "number": 42,
        "user": {"login": author, "type": "User"},
        "labels": [{"name": name} for name in labels],
    }


_next_id = iter(range(1, 10_000))


def _review(
    login: str,
    state: str,
    *,
    at: str = "2026-10-01T00:00:00Z",
    association: str = "COLLABORATOR",
    kind: str = "User",
    commit: str = "head",
) -> dict[str, Any]:
    return {
        "id": next(_next_id),
        "user": {"login": login, "type": kind},
        "state": state,
        "submitted_at": at,
        "author_association": association,
        "commit_id": commit,
    }


# --- passes -----------------------------------------------------------------------


@pytest.mark.parametrize("labels", [(), ("review:R2",), ("review:R1", "epic:governance")])
def test_a_pull_request_that_is_not_r3_passes(labels: tuple[str, ...]) -> None:
    decision = r3.evaluate(_pull(*labels), [])
    assert decision.passed
    assert "not review:R3" in decision.reason


def test_an_r3_pull_request_approved_by_another_person_passes() -> None:
    decision = r3.evaluate(_pull("review:R3"), [_review("reviewer", "APPROVED")])
    assert decision.passed
    assert decision.approvers == ("reviewer",)


def test_the_owner_counts_as_a_reviewer() -> None:
    decision = r3.evaluate(
        _pull("review:R3"), [_review("yeongseon", "APPROVED", association="OWNER")]
    )
    assert decision.passed


def test_an_approval_on_an_older_head_still_counts() -> None:
    """Mirrors branch protection, where "dismiss stale approvals" is off."""
    decision = r3.evaluate(_pull("review:R3"), [_review("reviewer", "APPROVED", commit="old")])
    assert decision.passed


def test_a_later_comment_does_not_withdraw_an_approval() -> None:
    reviews = [
        _review("reviewer", "APPROVED", at="2026-10-01T00:00:00Z"),
        _review("reviewer", "COMMENTED", at="2026-10-01T01:00:00Z"),
    ]
    assert r3.evaluate(_pull("review:R3"), reviews).passed


def test_changes_requested_then_approved_passes() -> None:
    reviews = [
        _review("reviewer", "CHANGES_REQUESTED", at="2026-10-01T00:00:00Z"),
        _review("reviewer", "APPROVED", at="2026-10-01T01:00:00Z"),
    ]
    assert r3.evaluate(_pull("review:R3"), reviews).passed


def test_one_valid_approval_is_enough_among_invalid_ones() -> None:
    reviews = [
        _review(AUTHOR, "APPROVED"),
        _review("bot[bot]", "APPROVED", kind="Bot", association="NONE"),
        _review("reviewer", "APPROVED"),
    ]
    assert r3.evaluate(_pull("review:R3"), reviews).approvers == ("reviewer",)


# --- fails ------------------------------------------------------------------------


def test_an_r3_pull_request_with_no_review_fails() -> None:
    decision = r3.evaluate(_pull("review:R3"), [])
    assert not decision.passed
    assert AUTHOR in decision.reason


def test_the_authors_own_approval_does_not_count() -> None:
    decision = r3.evaluate(_pull("review:R3"), [_review(AUTHOR, "APPROVED", association="OWNER")])
    assert not decision.passed


def test_the_authors_approval_is_matched_without_case() -> None:
    decision = r3.evaluate(_pull("review:R3"), [_review(AUTHOR.upper(), "APPROVED")])
    assert not decision.passed


def test_approved_then_changes_requested_fails() -> None:
    reviews = [
        _review("reviewer", "APPROVED", at="2026-10-01T00:00:00Z"),
        _review("reviewer", "CHANGES_REQUESTED", at="2026-10-01T01:00:00Z"),
    ]
    assert not r3.evaluate(_pull("review:R3"), reviews).passed


def test_the_order_is_taken_from_the_timestamps_not_the_list() -> None:
    reviews = [
        _review("reviewer", "CHANGES_REQUESTED", at="2026-10-01T01:00:00Z"),
        _review("reviewer", "APPROVED", at="2026-10-01T00:00:00Z"),
    ]
    assert not r3.evaluate(_pull("review:R3"), reviews).passed


def test_a_dismissed_approval_fails() -> None:
    """GitHub rewrites a dismissed review's state to DISMISSED."""
    assert not r3.evaluate(_pull("review:R3"), [_review("reviewer", "DISMISSED")]).passed


def test_a_comment_is_not_an_approval() -> None:
    assert not r3.evaluate(_pull("review:R3"), [_review("reviewer", "COMMENTED")]).passed


def test_a_pending_review_is_not_an_approval() -> None:
    assert not r3.evaluate(_pull("review:R3"), [_review("reviewer", "PENDING")]).passed


def test_a_bot_approval_is_not_a_human_review() -> None:
    reviews = [_review("helper[bot]", "APPROVED", kind="Bot", association="COLLABORATOR")]
    assert not r3.evaluate(_pull("review:R3"), reviews).passed


@pytest.mark.parametrize("association", ["NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR"])
def test_an_approval_without_write_access_does_not_count(association: str) -> None:
    reviews = [_review("passer-by", "APPROVED", association=association)]
    assert not r3.evaluate(_pull("review:R3"), reviews).passed


def test_a_deleted_account_is_skipped_not_crashed_on() -> None:
    reviews = [{"id": 1, "user": None, "state": "APPROVED", "author_association": "NONE"}]
    assert not r3.evaluate(_pull("review:R3"), reviews).passed


def test_an_unreadable_author_fails_closed() -> None:
    pull = _pull("review:R3")
    pull["user"] = None
    assert not r3.evaluate(pull, [_review("reviewer", "APPROVED")]).passed


# --- command line -----------------------------------------------------------------


def _write(tmp_path: Path, pull: dict[str, Any], reviews_text: str) -> list[str]:
    (tmp_path / "pull.json").write_text(json.dumps(pull), encoding="utf-8")
    (tmp_path / "reviews").write_text(reviews_text, encoding="utf-8")
    return ["--pull", str(tmp_path / "pull.json"), "--reviews", str(tmp_path / "reviews")]


def test_cli_fails_an_unapproved_r3_pull_request(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert r3.main(_write(tmp_path, _pull("review:R3"), "")) == 1
    captured = capsys.readouterr()
    assert "passed=false" in captured.out
    assert "::error::" in captured.err


def test_cli_reads_one_review_per_line(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lines = "\n".join(
        json.dumps(r) for r in [_review(AUTHOR, "APPROVED"), _review("r", "APPROVED")]
    )
    assert r3.main(_write(tmp_path, _pull("review:R3"), lines + "\n")) == 0
    assert "approvers=r" in capsys.readouterr().out


def test_cli_reads_a_json_array(tmp_path: Path) -> None:
    text = json.dumps([_review("reviewer", "APPROVED")])
    assert r3.main(_write(tmp_path, _pull("review:R3"), text)) == 0


def test_cli_passes_a_pull_request_that_is_not_r3(tmp_path: Path) -> None:
    assert r3.main(_write(tmp_path, _pull("review:R1"), "")) == 0


def test_cli_rejects_unreadable_input(tmp_path: Path) -> None:
    assert r3.main(_write(tmp_path, _pull("review:R3"), "{not json")) == 2


# --- the workflow -----------------------------------------------------------------

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "r3-review.yml"


def test_the_workflow_produces_the_context_branch_protection_requires() -> None:
    """The required context is ``R3 review``; a rename or a matrix suffix would orphan it."""
    checks = importlib.util.spec_from_file_location(
        "check_required_checks", REPO_ROOT / "scripts" / "check_required_checks.py"
    )
    assert checks is not None and checks.loader is not None
    module = importlib.util.module_from_spec(checks)
    checks.loader.exec_module(module)
    assert "R3 review" in module.produced_contexts(WORKFLOW.parent)


def test_the_workflow_re_evaluates_on_every_event_that_changes_the_answer() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    for event in ("synchronize", "labeled", "unlabeled", "submitted", "dismissed"):
        assert event in text, event
    assert "pull_request_review:" in text
    assert "pull_request_target" not in text.replace("Not pull_request_target", "")


def test_the_job_is_never_skipped_by_a_condition() -> None:
    """A required check that does not run leaves the pull request BLOCKED for ever."""
    _, _, jobs = WORKFLOW.read_text(encoding="utf-8").partition("\njobs:")
    assert "\n    if:" not in jobs
