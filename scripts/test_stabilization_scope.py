"""Regression tests for the stabilization scope gate.

Run: python3 scripts/test_stabilization_scope.py -v
"""

from __future__ import annotations

import unittest
from pathlib import Path

from check_stabilization_scope import (
    PullUnavailable,
    check_scope,
    content_indicators,
    current_pull,
    scope_indicators,
)

SDK = "kpubdata-lab/kpubdata"
BUILDER = "kpubdata-lab/kpubdata-builder"
STUDIO = "kpubdata-lab/kpubdata-studio"
BODY = (
    "Scope exception: YES\n"
    "Existing flow or risk: Preserve an existing user flow whose safety is broken.\n"
    "Refs #918\n"
)


class StabilizationGateTests(unittest.TestCase):
    def test_bugfix_unit_tests_and_docs_pass(self) -> None:
        for repo in (SDK, BUILDER, STUDIO):
            self.assertEqual(
                check_scope(repo, "fix: correct failure", "", set(), "M\tsrc/a.py", ""),
                (),
            )

    def test_feature_title_fails_without_exception(self) -> None:
        self.assertTrue(check_scope(SDK, "feat(api): add feature", "", set(), "", ""))

    def test_exception_requires_review_label(self) -> None:
        errors = check_scope(BUILDER, "feat(backup): fix recovery", BODY, set(), "", "")
        self.assertTrue(any("review:R3" in error for error in errors))

    def test_exception_requires_justification_and_issue(self) -> None:
        errors = check_scope(
            STUDIO, "feat(ui): new page", "Scope exception: YES", {"review:R3"}, "", ""
        )
        self.assertTrue(any("Existing flow or risk:" in error for error in errors))
        self.assertTrue(any("Refs #N" in error for error in errors))

    def test_reviewed_necessary_exception_passes(self) -> None:
        self.assertEqual(
            check_scope(BUILDER, "feat(ops): restore existing runs", BODY, {"review:R3"}, "", ""),
            (),
        )

    def test_new_dataset_spec_cannot_hide_in_fix(self) -> None:
        self.assertTrue(
            check_scope(
                SDK, "fix: adjust docs", "", set(), "A\tsrc/kpubdata/specs/datago/new.yaml", ""
            )
        )

    def test_new_provider_source_is_flagged(self) -> None:
        self.assertIn(
            "new provider source:",
            " ".join(
                scope_indicators(
                    SDK, "fix: provider", "A\tsrc/kpubdata/providers/new/adapter.py", ""
                )
            ),
        )

    def test_new_backend_route_is_flagged(self) -> None:
        patch = (
            "diff --git a/contract/builder-api.yaml b/contract/builder-api.yaml\n"
            "+++ b/contract/builder-api.yaml\n+  /new-route:\n"
        )
        self.assertTrue(
            check_scope(BUILDER, "fix: api", "", set(), "M\tcontract/builder-api.yaml", patch)
        )

    def test_new_browser_route_is_flagged(self) -> None:
        patch = "+++ b/src/app/router.tsx\n+    path: 'new-page',\n"
        self.assertTrue(
            check_scope(STUDIO, "fix: router", "", set(), "M\tsrc/app/router.tsx", patch)
        )

    def test_new_workflow_or_schedule_is_flagged(self) -> None:
        self.assertTrue(
            check_scope(SDK, "ci: monitor", "", set(), "A\t.github/workflows/new.yml", "")
        )
        patch = "+++ b/.github/workflows/old.yml\n+    - cron: '0 2 * * *'\n"
        self.assertTrue(
            check_scope(SDK, "ci: monitor", "", set(), "M\t.github/workflows/old.yml", patch)
        )

    def test_new_sdk_export_needs_exception(self) -> None:
        patch = '+++ b/src/kpubdata/__init__.py\n+    "NewExport",\n'
        self.assertTrue(
            check_scope(SDK, "fix: exports", "", set(), "M\tsrc/kpubdata/__init__.py", patch)
        )

    def test_normal_workflow_fix_still_passes(self) -> None:
        patch = "+++ b/.github/workflows/ci.yml\n+      - name: Validate changed inputs\n"
        self.assertEqual(
            check_scope(
                BUILDER, "fix(ci): pin a check", "", set(), "M\t.github/workflows/ci.yml", patch
            ),
            (),
        )

    def test_new_issue_writer_in_an_existing_workflow_requires_review(self) -> None:
        patch = '+++ b/.github/workflows/report.yml\n+        run: gh issue create --title "new"\n'
        self.assertTrue(check_scope(BUILDER, "fix(ci): alert", "", set(), "", patch))

    def test_new_python_issue_creator_requires_review(self) -> None:
        patch = '+++ b/scripts/alerts.py\n+    _gh(run, "issue", "create", title)\n'
        self.assertTrue(check_scope(SDK, "fix: alerts", "", set(), "", patch))

    def test_literal_in_a_test_fixture_does_not_trigger_issue_gate(self) -> None:
        patch = "+++ b/scripts/test_alerts.py\n+    command = 'gh issue create'\n"
        self.assertEqual(
            check_scope(SDK, "test: alerts", "", set(), "", patch),
            (),
        )

    def test_new_studio_page_requires_exception(self) -> None:
        self.assertTrue(
            check_scope(STUDIO, "fix: screen", "", set(), "A\tsrc/pages/NewPage.tsx", "")
        )


STALE = {
    "number": 7,
    "title": "fix: old title",
    "body": "old body",
    "labels": [{"name": "old"}],
    "base": {"sha": "a" * 40},
}
LIVE = {
    "number": 7,
    "title": "feat: new title",
    "body": "new body",
    "labels": [{"name": "review:R3"}],
    "base": {"sha": "b" * 40},
}


class CurrentPullTests(unittest.TestCase):
    def test_the_live_pull_request_replaces_a_stale_event_payload(self) -> None:
        pull = current_pull(STALE, "kpubdata-lab/kpubdata", lambda repo, number: LIVE)
        self.assertEqual(pull["title"], "feat: new title")
        self.assertEqual(pull["labels"], [{"name": "review:R3"}])

    def test_the_lookup_gets_the_repository_and_number(self) -> None:
        calls: list[tuple[str, int]] = []

        def fetch(repo: str, number: int) -> dict[str, object]:
            calls.append((repo, number))
            return LIVE

        current_pull(STALE, "kpubdata-lab/kpubdata", fetch)
        self.assertEqual(calls, [("kpubdata-lab/kpubdata", 7)])

    def test_an_unavailable_api_falls_back_to_the_event(self) -> None:
        def fetch(repo: str, number: int) -> dict[str, object]:
            raise PullUnavailable("no network")

        self.assertEqual(current_pull(STALE, "kpubdata-lab/kpubdata", fetch), STALE)

    def test_an_event_without_a_number_uses_the_event(self) -> None:
        def fetch(repo: str, number: int) -> dict[str, object]:
            raise AssertionError("must not be called")

        event = {key: value for key, value in STALE.items() if key != "number"}
        self.assertEqual(current_pull(event, "kpubdata-lab/kpubdata", fetch), event)

    def test_a_live_payload_without_a_title_is_not_trusted(self) -> None:
        pull = current_pull(STALE, "kpubdata-lab/kpubdata", lambda repo, number: {"number": 7})
        self.assertEqual(pull, STALE)


class MainBaseTests(unittest.TestCase):
    def test_the_diff_base_is_the_events_not_the_live_one(self) -> None:
        """A re-run keeps its old merge commit; the live base would misattribute main."""
        import json
        import os
        import tempfile
        from unittest import mock

        import check_stabilization_scope as scope

        with tempfile.TemporaryDirectory() as tmp:
            event = Path(tmp) / "event.json"
            event.write_text(json.dumps({"pull_request": STALE}), encoding="utf-8")
            calls: list[list[str]] = []

            def fake_git(args: list[str]) -> str:
                calls.append(args)
                return ""

            env = {"GITHUB_EVENT_PATH": str(event), "GITHUB_REPOSITORY": "kpubdata-lab/kpubdata"}
            with (
                mock.patch.dict(os.environ, env),
                mock.patch.object(scope, "current_pull", lambda pull, repo: LIVE),
                mock.patch.object(scope, "_git", fake_git),
            ):
                scope.main()

        diffs = [args for args in calls if args[0] == "diff"]
        self.assertTrue(diffs)
        self.assertTrue(all("a" * 40 in args and "b" * 40 not in args for args in diffs))


INIT = "src/kpubdata/__init__.py"
CATALOGUE = "src/kpubdata/providers/datago/catalogue.json"
BASE_INIT = '__all__ = [\n    "Client",\n    "Query",\n]\n'


def _contents(
    name_status: str, base: dict[str, str], head: dict[str, str], repository: str = SDK
) -> list[str]:
    return content_indicators(repository, name_status, base.get, head.get)


class PublicExportContentTests(unittest.TestCase):
    """New exports are found by comparing the parsed ``__all__``, not patch lines."""

    def _added(self, head_source: str) -> list[str]:
        return _contents(f"M\t{INIT}", {INIT: BASE_INIT}, {INIT: head_source})

    def test_an_export_with_a_trailing_comment_is_flagged(self) -> None:
        head = '__all__ = [\n    "Client",\n    "Query",\n    "NewThing",  # new\n]\n'
        self.assertEqual(self._added(head), ["new SDK public export: NewThing"])

    def test_an_append_is_flagged(self) -> None:
        head = BASE_INIT + '__all__.append("NewThing")\n'
        self.assertEqual(self._added(head), ["new SDK public export: NewThing"])

    def test_an_augmented_assignment_is_flagged(self) -> None:
        head = BASE_INIT + '__all__ += ["NewThing"]\n'
        self.assertEqual(self._added(head), ["new SDK public export: NewThing"])

    def test_an_extend_is_flagged(self) -> None:
        head = BASE_INIT + '__all__.extend(("NewThing",))\n'
        self.assertEqual(self._added(head), ["new SDK public export: NewThing"])

    def test_two_exports_on_one_line_are_flagged(self) -> None:
        head = '__all__ = [\n    "Client",\n    "Query",\n    "A", "B",\n]\n'
        self.assertEqual(
            self._added(head), ["new SDK public export: A", "new SDK public export: B"]
        )

    def test_a_reordered_or_shrunk_list_is_not_flagged(self) -> None:
        self.assertEqual(self._added('__all__ = ["Query", "Client"]\n'), [])
        self.assertEqual(self._added('__all__ = ["Client"]\n'), [])

    def test_a_computed_export_list_is_flagged(self) -> None:
        head = BASE_INIT + "__all__ += _names()\n"
        self.assertEqual(self._added(head), ["SDK public exports not a literal list: " + INIT])

    def test_an_unparseable_module_is_flagged(self) -> None:
        self.assertEqual(
            self._added("__all__ = [\n"), ["SDK public exports not a literal list: " + INIT]
        )

    def test_an_unchanged_init_is_not_read(self) -> None:
        def explode(path: str) -> str | None:
            raise AssertionError(f"must not read {path}")

        self.assertEqual(content_indicators(SDK, "M\tsrc/a.py", explode, explode), [])

    def test_other_repositories_are_not_read(self) -> None:
        head = BASE_INIT + '__all__.append("NewThing")\n'
        self.assertEqual(
            _contents(f"M\t{INIT}", {INIT: BASE_INIT}, {INIT: head}, repository=BUILDER), []
        )

    def test_a_flagged_export_still_takes_the_documented_exception(self) -> None:
        head = BASE_INIT + '__all__.append("NewThing")\n'
        contents = self._added(head)
        self.assertTrue(check_scope(SDK, "fix: exports", "", set(), "", "", contents))
        self.assertEqual(
            check_scope(SDK, "fix: exports", BODY, {"review:R3"}, "", "", contents), ()
        )


class CatalogueKeyContentTests(unittest.TestCase):
    """A provider catalogue that gains a dataset_key is a new dataset."""

    BASE = '[{"dataset_key": "a", "name": "A"}]'

    def test_an_added_dataset_key_is_flagged(self) -> None:
        head = '[{"dataset_key": "a", "name": "A"}, {"dataset_key": "brand_new"}]'
        self.assertEqual(
            _contents(f"M\t{CATALOGUE}", {CATALOGUE: self.BASE}, {CATALOGUE: head}),
            ["new catalogue dataset: datago.brand_new"],
        )

    def test_a_new_catalogue_file_flags_every_key(self) -> None:
        path = "src/kpubdata/providers/newprov/catalogue.json"
        self.assertEqual(
            _contents(f"A\t{path}", {}, {path: '[{"dataset_key": "x"}]'}),
            ["new catalogue dataset: newprov.x"],
        )

    def test_an_edited_or_shrunk_catalogue_is_not_flagged(self) -> None:
        edited = '[{"dataset_key": "a", "name": "renamed"}]'
        self.assertEqual(
            _contents(f"M\t{CATALOGUE}", {CATALOGUE: self.BASE}, {CATALOGUE: edited}), []
        )
        self.assertEqual(
            _contents(f"M\t{CATALOGUE}", {CATALOGUE: self.BASE}, {CATALOGUE: "[]"}), []
        )

    def test_an_unreadable_catalogue_is_flagged(self) -> None:
        self.assertEqual(
            _contents(f"M\t{CATALOGUE}", {CATALOGUE: self.BASE}, {CATALOGUE: "{"}),
            ["catalogue not readable: " + CATALOGUE],
        )

    def test_a_changed_file_missing_at_head_fails(self) -> None:
        with self.assertRaises(ValueError):
            _contents(f"M\t{CATALOGUE}", {CATALOGUE: self.BASE}, {})


class MainContentTests(unittest.TestCase):
    """``main`` reads both sides from git: a real temporary repository, no network."""

    def test_an_export_and_a_catalogue_key_fail_the_gate(self) -> None:
        import json
        import os
        import subprocess
        import tempfile
        from unittest import mock

        import check_stabilization_scope as scope

        def git(cwd: str, *args: str) -> str:
            return subprocess.run(
                [
                    "git",
                    "-c",
                    "user.name=test",
                    "-c",
                    "user.email=test@example.invalid",
                    "-c",
                    "commit.gpgsign=false",
                    *args,
                ],
                cwd=cwd,
                check=True,
                text=True,
                capture_output=True,
            ).stdout

        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            (repo / "src/kpubdata/providers/datago").mkdir(parents=True)
            (repo / INIT).write_text(BASE_INIT, encoding="utf-8")
            (repo / CATALOGUE).write_text('[{"dataset_key": "a"}]', encoding="utf-8")
            git(str(repo), "init", "-q")
            git(str(repo), "add", "-A")
            git(str(repo), "commit", "-q", "-m", "base")
            base = git(str(repo), "rev-parse", "HEAD").strip()
            (repo / INIT).write_text(
                '__all__ = [\n    "Client",\n    "Query",\n    "NewThing",  # new\n]\n',
                encoding="utf-8",
            )
            (repo / CATALOGUE).write_text(
                '[{"dataset_key": "a"}, {"dataset_key": "b"}]', encoding="utf-8"
            )
            git(str(repo), "commit", "-q", "-am", "head")

            pull = {
                "number": 7,
                "title": "fix: tidy",
                "body": "",
                "labels": [],
                "base": {"sha": base},
            }
            event = Path(tmp) / "event.json"
            event.write_text(json.dumps({"pull_request": pull}), encoding="utf-8")

            def offline_git(args: list[str]) -> str:
                if args[0] == "fetch":
                    return ""
                return git(str(repo), *args)

            env = {"GITHUB_EVENT_PATH": str(event), "GITHUB_REPOSITORY": SDK}
            with (
                mock.patch.dict(os.environ, env),
                mock.patch.object(scope, "current_pull", lambda pull, repo: pull),
                mock.patch.object(scope, "_git", offline_git),
                mock.patch("sys.stdout") as stdout,
            ):
                code = scope.main()

        printed = "".join(call.args[0] for call in stdout.write.call_args_list)
        self.assertEqual(code, 1)
        self.assertIn("new SDK public export: NewThing", printed)
        self.assertIn("new catalogue dataset: datago.b", printed)


if __name__ == "__main__":
    unittest.main()
