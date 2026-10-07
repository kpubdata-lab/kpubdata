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


def _everyone_can_write(reviews: list[dict[str, Any]]) -> dict[str, str]:
    """A permission map in which every reviewer can push — the tests of the review
    history are about the history, so they hold the permission still (#860)."""
    return {
        review["user"]["login"]: "write"
        for review in reviews
        if isinstance(review.get("user"), dict)
    }


def _evaluate(pull: dict[str, Any], reviews: list[dict[str, Any]], *args: Any) -> Any:
    return r3.evaluate(pull, reviews, _everyone_can_write(reviews), *args)


# --- passes -----------------------------------------------------------------------


@pytest.mark.parametrize("labels", [(), ("review:R2",), ("review:R1", "epic:governance")])
def test_a_pull_request_that_is_not_r3_passes(labels: tuple[str, ...]) -> None:
    decision = _evaluate(_pull(*labels), [])
    assert decision.passed
    assert "not review:R3" in decision.reason


def test_an_r3_pull_request_approved_by_another_person_passes() -> None:
    decision = _evaluate(_pull("review:R3"), [_review("reviewer", "APPROVED")])
    assert decision.passed
    assert decision.approvers == ("reviewer",)


def test_the_owner_counts_as_a_reviewer() -> None:
    decision = _evaluate(
        _pull("review:R3"), [_review("yeongseon", "APPROVED", association="OWNER")]
    )
    assert decision.passed


def test_an_approval_on_an_older_head_still_counts() -> None:
    """Mirrors branch protection, where "dismiss stale approvals" is off."""
    decision = _evaluate(_pull("review:R3"), [_review("reviewer", "APPROVED", commit="old")])
    assert decision.passed


def test_a_later_comment_does_not_withdraw_an_approval() -> None:
    reviews = [
        _review("reviewer", "APPROVED", at="2026-10-01T00:00:00Z"),
        _review("reviewer", "COMMENTED", at="2026-10-01T01:00:00Z"),
    ]
    assert _evaluate(_pull("review:R3"), reviews).passed


def test_changes_requested_then_approved_passes() -> None:
    reviews = [
        _review("reviewer", "CHANGES_REQUESTED", at="2026-10-01T00:00:00Z"),
        _review("reviewer", "APPROVED", at="2026-10-01T01:00:00Z"),
    ]
    assert _evaluate(_pull("review:R3"), reviews).passed


def test_one_valid_approval_is_enough_among_invalid_ones() -> None:
    reviews = [
        _review(AUTHOR, "APPROVED"),
        _review("bot[bot]", "APPROVED", kind="Bot", association="NONE"),
        _review("reviewer", "APPROVED"),
    ]
    assert _evaluate(_pull("review:R3"), reviews).approvers == ("reviewer",)


# --- fails ------------------------------------------------------------------------


def test_an_r3_pull_request_with_no_review_fails() -> None:
    decision = _evaluate(_pull("review:R3"), [])
    assert not decision.passed
    assert AUTHOR in decision.reason


def test_the_authors_own_approval_does_not_count() -> None:
    decision = _evaluate(_pull("review:R3"), [_review(AUTHOR, "APPROVED", association="OWNER")])
    assert not decision.passed


def test_the_authors_approval_is_matched_without_case() -> None:
    decision = _evaluate(_pull("review:R3"), [_review(AUTHOR.upper(), "APPROVED")])
    assert not decision.passed


def test_approved_then_changes_requested_fails() -> None:
    reviews = [
        _review("reviewer", "APPROVED", at="2026-10-01T00:00:00Z"),
        _review("reviewer", "CHANGES_REQUESTED", at="2026-10-01T01:00:00Z"),
    ]
    assert not _evaluate(_pull("review:R3"), reviews).passed


def test_the_order_is_taken_from_the_timestamps_not_the_list() -> None:
    reviews = [
        _review("reviewer", "CHANGES_REQUESTED", at="2026-10-01T01:00:00Z"),
        _review("reviewer", "APPROVED", at="2026-10-01T00:00:00Z"),
    ]
    assert not _evaluate(_pull("review:R3"), reviews).passed


def test_a_dismissed_approval_fails() -> None:
    """GitHub rewrites a dismissed review's state to DISMISSED."""
    assert not _evaluate(_pull("review:R3"), [_review("reviewer", "DISMISSED")]).passed


def test_a_comment_is_not_an_approval() -> None:
    assert not _evaluate(_pull("review:R3"), [_review("reviewer", "COMMENTED")]).passed


def test_a_pending_review_is_not_an_approval() -> None:
    assert not _evaluate(_pull("review:R3"), [_review("reviewer", "PENDING")]).passed


def test_a_bot_approval_is_not_a_human_review() -> None:
    reviews = [_review("helper[bot]", "APPROVED", kind="Bot", association="COLLABORATOR")]
    assert not _evaluate(_pull("review:R3"), reviews).passed


@pytest.mark.parametrize("association", ["NONE", "CONTRIBUTOR", "FIRST_TIME_CONTRIBUTOR"])
def test_an_approval_without_write_access_does_not_count(association: str) -> None:
    reviews = [_review("passer-by", "APPROVED", association=association)]
    assert not _evaluate(_pull("review:R3"), reviews).passed


def test_a_deleted_account_is_skipped_not_crashed_on() -> None:
    reviews = [{"id": 1, "user": None, "state": "APPROVED", "author_association": "NONE"}]
    assert not _evaluate(_pull("review:R3"), reviews).passed


def test_an_unreadable_author_fails_closed() -> None:
    pull = _pull("review:R3")
    pull["user"] = None
    assert not _evaluate(pull, [_review("reviewer", "APPROVED")]).passed


# --- command line -----------------------------------------------------------------


def _write(
    tmp_path: Path,
    pull: dict[str, Any],
    reviews_text: str,
    permissions: dict[str, Any] | None = None,
) -> list[str]:
    """Arguments for the command line. ``permissions`` defaults to "the accounts these
    tests approve with can write"; pass ``{}`` for nobody."""
    (tmp_path / "pull.json").write_text(json.dumps(pull), encoding="utf-8")
    (tmp_path / "reviews").write_text(reviews_text, encoding="utf-8")
    granted = {"r": "write", "reviewer": "write"} if permissions is None else permissions
    (tmp_path / "permissions.json").write_text(json.dumps(granted), encoding="utf-8")
    return [
        "--pull",
        str(tmp_path / "pull.json"),
        "--reviews",
        str(tmp_path / "reviews"),
        "--permissions",
        str(tmp_path / "permissions.json"),
    ]


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


# --- who can write, now (#860) -----------------------------------------------------
#
# ``author_association`` says how an account is related to the repository. An
# organisation member or a collaborator can hold read or triage access only, and their
# APPROVED review used to satisfy the gate.


@pytest.mark.parametrize("permission", ["admin", "write"])
def test_an_approval_from_someone_who_can_push_counts(permission: str) -> None:
    reviews = [_review("reviewer", "APPROVED", association="MEMBER")]

    decision = r3.evaluate(_pull("review:R3"), reviews, {"reviewer": permission})

    assert decision.passed
    assert decision.approvers == ("reviewer",)


@pytest.mark.parametrize("association", ["MEMBER", "COLLABORATOR", "OWNER"])
@pytest.mark.parametrize("permission", ["read", "none", "triage", "maintain", "pull", "", "WRITE"])
def test_an_approval_from_someone_who_cannot_push_does_not_count(
    association: str, permission: str
) -> None:
    """``read`` is what GitHub reports for read and triage access. The other values are
    not ones this field takes for a writer, so none of them is taken as write."""
    reviews = [_review("reviewer", "APPROVED", association=association)]

    decision = r3.evaluate(_pull("review:R3"), reviews, {"reviewer": permission})

    assert not decision.passed
    assert decision.approvers == ()
    assert "reviewer" in decision.reason and "could not be confirmed" in decision.reason


@pytest.mark.parametrize(
    "permissions",
    [
        {},
        {"reviewer": None},
        {"someone-else": "admin"},
        {"reviewer": ["write"]},
        {"reviewer": True},
    ],
)
def test_a_permission_that_was_not_read_is_not_an_approval(permissions: dict[str, Any]) -> None:
    """The lookup failed, was never made, or came back as something else: fail closed."""
    reviews = [_review("reviewer", "APPROVED")]

    assert not r3.evaluate(_pull("review:R3"), reviews, permissions).passed


def test_write_access_does_not_make_up_for_a_missing_association() -> None:
    """Both are required: an outsider's review is not looked up at all."""
    reviews = [_review("stranger", "APPROVED", association="CONTRIBUTOR")]

    assert r3.candidates_to_look_up(_pull("review:R3"), reviews) == ()
    assert not r3.evaluate(_pull("review:R3"), reviews, {"stranger": "admin"}).passed


def test_write_access_does_not_let_the_author_or_a_bot_approve() -> None:
    reviews = [
        _review(AUTHOR, "APPROVED"),
        _review("renovate[bot]", "APPROVED", kind="Bot"),
    ]
    permissions = {AUTHOR: "admin", "renovate[bot]": "write"}

    assert r3.candidates_to_look_up(_pull("review:R3"), reviews) == ()
    assert not r3.evaluate(_pull("review:R3"), reviews, permissions).passed


def test_one_writer_among_several_approvers_is_enough_and_only_they_are_named() -> None:
    reviews = [
        _review("reader", "APPROVED", association="MEMBER"),
        _review("writer", "APPROVED", association="COLLABORATOR"),
        _review("unread", "APPROVED", association="MEMBER"),
    ]

    decision = r3.evaluate(
        _pull("review:R3"), reviews, {"reader": "read", "writer": "write", "unread": None}
    )

    assert decision.passed
    assert decision.approvers == ("writer",)


def test_the_permission_is_matched_whatever_the_case_of_the_login() -> None:
    reviews = [_review("Reviewer", "APPROVED")]

    assert r3.evaluate(_pull("review:R3"), reviews, {"reviewer": "write"}).passed


def test_losing_write_access_after_approving_stops_the_approval_counting() -> None:
    """The permission is the one held when the check runs, not when the review was made."""
    reviews = [_review("reviewer", "APPROVED", at="2026-10-01T00:00:00Z")]

    assert r3.evaluate(_pull("review:R3"), reviews, {"reviewer": "write"}).passed
    assert not r3.evaluate(_pull("review:R3"), reviews, {"reviewer": "read"}).passed


def test_a_writers_request_for_changes_still_cancels_their_approval() -> None:
    reviews = [
        _review("reviewer", "APPROVED", at="2026-10-01T00:00:00Z"),
        _review("reviewer", "CHANGES_REQUESTED", at="2026-10-01T01:00:00Z"),
    ]

    assert r3.candidates_to_look_up(_pull("review:R3"), reviews) == ()
    assert not r3.evaluate(_pull("review:R3"), reviews, {"reviewer": "admin"}).passed


def test_nobody_is_looked_up_for_a_pull_request_that_is_not_r3() -> None:
    """Every pull request runs the check; only a labelled one costs API calls."""
    reviews = [_review("reviewer", "APPROVED")]

    assert r3.candidates_to_look_up(_pull("review:R1"), reviews) == ()
    assert r3.candidates_to_look_up(_pull("review:R3"), reviews) == ("reviewer",)
    # And it passes with no permissions at all.
    assert r3.evaluate(_pull("review:R1"), reviews, {}).passed


def test_cli_lists_the_candidates_and_decides_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    lines = "\n".join(
        json.dumps(r)
        for r in [
            _review(AUTHOR, "APPROVED"),
            _review("zed", "APPROVED"),
            _review("amy", "APPROVED", association="MEMBER"),
            _review("stranger", "APPROVED", association="NONE"),
            _review("bot[bot]", "APPROVED", kind="Bot"),
        ]
    )

    assert r3.main([*_write(tmp_path, _pull("review:R3"), lines), "--candidates"]) == 0

    assert capsys.readouterr().out.splitlines() == ["amy", "zed"]


def test_cli_without_permissions_counts_nobody(tmp_path: Path) -> None:
    """Left out, the file means "nobody was confirmed", not "everybody"."""
    arguments = _write(tmp_path, _pull("review:R3"), json.dumps([_review("reviewer", "APPROVED")]))
    without = arguments[: arguments.index("--permissions")]

    assert r3.main(arguments) == 0
    assert r3.main(without) == 1


def test_cli_fails_when_the_approver_cannot_write(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    text = json.dumps([_review("reviewer", "APPROVED")])

    assert r3.main(_write(tmp_path, _pull("review:R3"), text, {"reviewer": "read"})) == 1

    assert "could not be confirmed" in capsys.readouterr().out


def test_cli_rejects_permissions_that_are_not_an_object(tmp_path: Path) -> None:
    arguments = _write(tmp_path, _pull("review:R3"), "")
    (tmp_path / "permissions.json").write_text('["reviewer"]', encoding="utf-8")

    assert r3.main(arguments) == 2


# --- the action's own step (#860) ---------------------------------------------------
#
# The rule above is only as good as what the action feeds it. This runs the step of
# ``.github/actions/r3-review/action.yml`` itself, with a ``gh`` that answers from files:
# the pull request, its reviews and each account's permission — or a failure.

ACTION = REPO_ROOT / ".github" / "actions" / "r3-review" / "action.yml"

_FAKE_GH = """#!/usr/bin/env bash
# A stand-in for `gh api`: answers from $FAKE_GH, and records what was asked.
echo "$*" >> "$FAKE_GH/calls"
for argument in "$@"; do
  case "$argument" in
    repos/*/pulls/*/reviews*) cat "$FAKE_GH/reviews.jsonl"; exit 0 ;;
    repos/*/pulls/*) cat "$FAKE_GH/pull.json"; exit 0 ;;
    repos/*/collaborators/*/permission)
      login="${argument#repos/*/collaborators/}"; login="${login%/permission}"
      if [ -f "$FAKE_GH/permission/$login" ]; then cat "$FAKE_GH/permission/$login"; exit 0; fi
      echo "gh: Not Found (HTTP 404)" >&2; exit 1 ;;
  esac
done
echo "unexpected gh call: $*" >&2
exit 3
"""


def _run_the_action_step(
    tmp_path: Path,
    pull: dict[str, Any],
    reviews: list[dict[str, Any]],
    permissions: dict[str, str],
) -> tuple[int, dict[str, str], list[str]]:
    """Run the action's step. Returns its exit status, its outputs and the ``gh`` calls.

    ``permissions`` holds the accounts whose lookup succeeds; any other lookup fails.
    """
    import shutil
    import subprocess

    import yaml

    if shutil.which("bash") is None or shutil.which("jq") is None:
        pytest.skip("the action's step needs bash and jq")
    step = yaml.safe_load(ACTION.read_text(encoding="utf-8"))["runs"]["steps"][0]
    script = step["run"].replace("${{ github.action_path }}", str(ACTION.parent))
    assert "${{" not in script, "an expression this test does not fill in"

    fake = tmp_path / "fake-gh"
    (fake / "permission").mkdir(parents=True)
    (fake / "pull.json").write_text(json.dumps(pull), encoding="utf-8")
    (fake / "reviews.jsonl").write_text(
        "".join(json.dumps(review) + "\n" for review in reviews), encoding="utf-8"
    )
    for login, permission in permissions.items():
        (fake / "permission" / login).write_text(permission + "\n", encoding="utf-8")
    (fake / "calls").write_text("", encoding="utf-8")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(_FAKE_GH, encoding="utf-8")
    (bin_dir / "gh").chmod(0o755)
    (tmp_path / "runner").mkdir()

    import os

    environment = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}",
        "FAKE_GH": str(fake),
        "RUNNER_TEMP": str(tmp_path / "runner"),
        "GITHUB_OUTPUT": str(tmp_path / "output"),
        "GITHUB_STEP_SUMMARY": str(tmp_path / "summary"),
        "REPO": "kpubdata-lab/kpubdata",
        "NUMBER": str(pull["number"]),
        "LABEL": "review:R3",
    }
    done = subprocess.run(  # noqa: S603 - the repository's own action step
        ["bash", "-c", script],  # noqa: S607
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    outputs = dict(
        line.split("=", 1)
        for line in (tmp_path / "output").read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    calls = (fake / "calls").read_text(encoding="utf-8").splitlines()
    return done.returncode, {**outputs, "stdout": done.stdout, "stderr": done.stderr}, calls


def _lookups(calls: list[str]) -> list[str]:
    return [call for call in calls if "/collaborators/" in call]


def test_the_action_passes_when_the_approver_can_push(tmp_path: Path) -> None:
    status, outputs, calls = _run_the_action_step(
        tmp_path, _pull("review:R3"), [_review("reviewer", "APPROVED")], {"reviewer": "write"}
    )

    assert status == 0, outputs["stderr"]
    assert outputs["passed"] == "true" and outputs["approvers"] == "reviewer"
    assert len(_lookups(calls)) == 1
    assert "repos/kpubdata-lab/kpubdata/collaborators/reviewer/permission" in _lookups(calls)[0]


@pytest.mark.parametrize("permission", ["read", "none"])
def test_the_action_fails_when_the_approver_can_only_read(tmp_path: Path, permission: str) -> None:
    """The case the gate let through: a member or collaborator with read or triage access."""
    status, outputs, _ = _run_the_action_step(
        tmp_path,
        _pull("review:R3"),
        [_review("reviewer", "APPROVED", association="MEMBER")],
        {"reviewer": permission},
    )

    assert status == 1
    assert outputs["passed"] == "false" and outputs["approvers"] == ""


def test_the_action_fails_closed_when_the_lookup_fails(tmp_path: Path) -> None:
    status, outputs, calls = _run_the_action_step(
        tmp_path, _pull("review:R3"), [_review("reviewer", "APPROVED")], {}
    )

    assert status == 1
    assert outputs["passed"] == "false"
    assert len(_lookups(calls)) == 1
    assert "could not read the repository permission of reviewer" in outputs["stdout"]


def test_one_failed_lookup_does_not_hide_another_approvers_review(tmp_path: Path) -> None:
    reviews = [_review("unreadable", "APPROVED"), _review("writer", "APPROVED")]

    status, outputs, calls = _run_the_action_step(
        tmp_path, _pull("review:R3"), reviews, {"writer": "admin"}
    )

    assert status == 0, outputs["stderr"]
    assert outputs["approvers"] == "writer"
    assert len(_lookups(calls)) == 2


def test_the_action_looks_nobody_up_for_a_pull_request_that_is_not_r3(tmp_path: Path) -> None:
    status, outputs, calls = _run_the_action_step(
        tmp_path, _pull("review:R1"), [_review("reviewer", "APPROVED")], {}
    )

    assert status == 0
    assert outputs["passed"] == "true"
    assert _lookups(calls) == []


def test_the_action_does_not_look_up_the_author_a_bot_or_an_outsider(tmp_path: Path) -> None:
    reviews = [
        _review(AUTHOR, "APPROVED"),
        _review("helper[bot]", "APPROVED", kind="Bot"),
        _review("passer-by", "APPROVED", association="NONE"),
    ]

    status, outputs, calls = _run_the_action_step(tmp_path, _pull("review:R3"), reviews, {})

    assert status == 1
    assert outputs["passed"] == "false"
    assert _lookups(calls) == []


def test_the_action_looks_up_an_account_whose_name_holds_an_underscore(tmp_path: Path) -> None:
    """Enterprise Managed User logins end in ``_<shortcode>``; the name check used to
    leave them out, so their approval could never count."""
    status, outputs, calls = _run_the_action_step(
        tmp_path,
        _pull("review:R3"),
        [_review("reviewer_corp", "APPROVED", association="MEMBER")],
        {"reviewer_corp": "write"},
    )

    assert status == 0, outputs["stderr"]
    assert outputs["approvers"] == "reviewer_corp"
    assert len(_lookups(calls)) == 1


@pytest.mark.parametrize("login", ["a/b", "a b", "a?x=1", "..", "a%2Fb"])
def test_the_action_puts_no_other_kind_of_name_into_a_url(tmp_path: Path, login: str) -> None:
    """Negative: a name that is not a login is refused, not looked up."""
    status, outputs, calls = _run_the_action_step(
        tmp_path, _pull("review:R3"), [_review(login, "APPROVED")], {}
    )

    assert status == 1
    assert _lookups(calls) == []
    assert "is not an account name this check looks up" in outputs["stdout"]
