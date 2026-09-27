"""Unit tests for provider scaffolding tool (#61).

Verifies scaffold_provider creates a file set and result is actually
compatible with adapter contract (seed dataset registers and appears in
list_datasets).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from kpubdata.scaffold import scaffold_provider


def _shared_repo_root(tmp_path: Path) -> Path:
    """Return temp repo root with directories scaffold expects.

    Only creates src/kpubdata/providers, tests/contract, tests/fixtures.
    Does not create Python files—scaffold must create them all.
    """
    (tmp_path / "src" / "kpubdata" / "providers").mkdir(parents=True)
    (tmp_path / "tests" / "contract").mkdir(parents=True)
    (tmp_path / "tests" / "fixtures").mkdir(parents=True)
    return tmp_path


class TestScaffoldProvider:
    def test_creates_expected_file_set(self, tmp_path: Path) -> None:
        # Scaffold creates adapter / __init__ / catalogue / fixture / contract test.
        repo = _shared_repo_root(tmp_path)

        result = scaffold_provider("my_prov", repo_root=repo, dataset_key="sample")

        assert result.adapter_path.exists()
        assert result.init_path.exists()
        assert result.catalogue_path.exists()
        assert result.fixture_path.exists()
        assert result.contract_test_path.exists()
        assert set(result.created) >= {
            result.adapter_path,
            result.init_path,
            result.catalogue_path,
            result.fixture_path,
            result.contract_test_path,
        }

    def test_catalogue_seed_is_valid_json_with_dataset_key(self, tmp_path: Path) -> None:
        # Seed catalogue is parseable and contains requested dataset_key.
        repo = _shared_repo_root(tmp_path)

        result = scaffold_provider("my_prov", repo_root=repo, dataset_key="weather")

        entries = json.loads(result.catalogue_path.read_text(encoding="utf-8"))
        assert isinstance(entries, list) and entries
        assert entries[0]["dataset_key"] == "weather"
        assert "list" in entries[0]["operations"]
        assert "raw" in entries[0]["operations"]

    def test_init_exports_adapter_class_with_camel_case(self, tmp_path: Path) -> None:
        # __init__.py exports class in MyProvAdapter form.
        repo = _shared_repo_root(tmp_path)

        result = scaffold_provider("my_prov", repo_root=repo)

        init_text = result.init_path.read_text(encoding="utf-8")
        assert "MyProvAdapter" in init_text

    def test_generated_adapter_loads_and_lists_seed_dataset(self, tmp_path: Path) -> None:
        # Load generated adapter via spec_from_file_location, verify list_datasets
        # exposes seed dataset_key—ensures scaffold output satisfies adapter
        # contract discovery immediately.
        import importlib.util

        repo = _shared_repo_root(tmp_path)
        result = scaffold_provider("scaffolded_demo", repo_root=repo, dataset_key="demo_ds")

        spec = importlib.util.spec_from_file_location("_scaffold_demo_adapter", result.adapter_path)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
            adapter = module.ScaffoldedDemoAdapter()
            assert adapter.name == "scaffolded_demo"
            datasets = adapter.list_datasets()
            assert any(d.dataset_key == "demo_ds" for d in datasets)
            dataset = adapter.get_dataset("demo_ds")
            assert dataset.id == "scaffolded_demo.demo_ds"
        finally:
            sys.modules.pop("_scaffold_demo_adapter", None)

    def test_refuses_to_overwrite_existing_files_without_force(self, tmp_path: Path) -> None:
        repo = _shared_repo_root(tmp_path)
        scaffold_provider("dup_prov", repo_root=repo)

        with pytest.raises(FileExistsError, match="refusing to overwrite"):
            scaffold_provider("dup_prov", repo_root=repo)

    def test_force_replaces_existing_files(self, tmp_path: Path) -> None:
        repo = _shared_repo_root(tmp_path)
        first = scaffold_provider("dup_prov", repo_root=repo, dataset_key="first")
        # Modify catalogue, force regenerate returns to original seed.
        first.catalogue_path.write_text("[]\n", encoding="utf-8")

        second = scaffold_provider("dup_prov", repo_root=repo, dataset_key="second", overwrite=True)

        entries = json.loads(second.catalogue_path.read_text(encoding="utf-8"))
        assert entries[0]["dataset_key"] == "second"

    def test_rejects_invalid_provider_name(self, tmp_path: Path) -> None:
        # Reject names escaping workspace or not Python identifiers.
        repo = _shared_repo_root(tmp_path)

        with pytest.raises(ValueError, match="provider name must match"):
            scaffold_provider("../escape", repo_root=repo)

    def test_rejects_invalid_dataset_key(self, tmp_path: Path) -> None:
        repo = _shared_repo_root(tmp_path)

        with pytest.raises(ValueError, match="dataset_key must match"):
            scaffold_provider("ok_name", repo_root=repo, dataset_key="Bad-Key")

    def test_rejects_python_keyword_as_provider_name(self, tmp_path: Path) -> None:
        # Regex passes but Python keywords like "class" cause SyntaxError in
        # generated code import—must reject separately.
        repo = _shared_repo_root(tmp_path)

        with pytest.raises(ValueError, match="Python keyword"):
            scaffold_provider("class", repo_root=repo)

    def test_rejects_python_keyword_as_dataset_key(self, tmp_path: Path) -> None:
        repo = _shared_repo_root(tmp_path)

        with pytest.raises(ValueError, match="Python keyword"):
            scaffold_provider("ok_name", repo_root=repo, dataset_key="class")


class TestScaffoldRollback:
    def test_new_scaffold_failure_rolls_back_all_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _shared_repo_root(tmp_path)

        write_count = 0
        original_write_text = Path.write_text

        def failing_write_text(self: Path, content: str, *, encoding: str = "utf-8") -> None:
            nonlocal write_count
            write_count += 1
            if write_count == 3:
                raise OSError("Simulated disk error")
            original_write_text(self, content, encoding=encoding)

        monkeypatch.setattr(Path, "write_text", failing_write_text)

        with pytest.raises(OSError, match="Simulated disk error"):
            scaffold_provider("rollback_test", repo_root=repo, dataset_key="sample")

        for path in [
            repo / "src" / "kpubdata" / "providers" / "rollback_test" / "__init__.py",
            repo / "src" / "kpubdata" / "providers" / "rollback_test" / "adapter.py",
            repo / "src" / "kpubdata" / "providers" / "rollback_test" / "catalogue.json",
            repo / "tests" / "fixtures" / "rollback_test" / "success_sample.json",
            repo / "tests" / "contract" / "test_rollback_test.py",
        ]:
            assert not path.exists(), f"File should be rolled back: {path}"

        provider_dir = repo / "src" / "kpubdata" / "providers" / "rollback_test"
        fixture_dir = repo / "tests" / "fixtures" / "rollback_test"
        contract_test_dir = repo / "tests" / "contract"

        assert not provider_dir.exists() or not list(provider_dir.iterdir())
        assert not fixture_dir.exists() or not list(fixture_dir.iterdir())
        assert contract_test_dir.exists()

        result = scaffold_provider("rollback_test", repo_root=repo, dataset_key="sample")
        assert result.adapter_path.exists()
        assert result.contract_test_path.exists()

    def test_overwrite_failure_restores_original_files(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _shared_repo_root(tmp_path)
        original_result = scaffold_provider(
            "overwrite_rollback", repo_root=repo, dataset_key="first"
        )

        original_init_bytes = original_result.init_path.read_bytes()
        original_adapter_bytes = original_result.adapter_path.read_bytes()

        original_result.catalogue_path.write_text('["custom content"]', encoding="utf-8")
        original_result.fixture_path.write_text('{"custom": "fixture"}', encoding="utf-8")

        write_count = 0
        original_write_text = Path.write_text

        def failing_write_text(self: Path, content: str, *, encoding: str = "utf-8") -> None:
            nonlocal write_count
            write_count += 1
            if write_count == 2:
                raise OSError("Simulated overwrite error")
            original_write_text(self, content, encoding=encoding)

        monkeypatch.setattr(Path, "write_text", failing_write_text)

        with pytest.raises(OSError, match="Simulated overwrite error"):
            scaffold_provider(
                "overwrite_rollback", repo_root=repo, dataset_key="second", overwrite=True
            )

        assert original_result.init_path.exists()
        assert original_result.adapter_path.exists()
        assert original_result.catalogue_path.exists()
        assert original_result.fixture_path.exists()
        assert original_result.contract_test_path.exists()

        assert original_result.init_path.read_bytes() == original_init_bytes, (
            "First written file should be restored"
        )
        assert original_result.adapter_path.read_bytes() == original_adapter_bytes, (
            "Second file should be unchanged"
        )

        catalogue_text = original_result.catalogue_path.read_text(encoding="utf-8")
        assert catalogue_text == '["custom content"]', (
            "catalogue was not attempted, should keep user modification"
        )

        fixture_text = original_result.fixture_path.read_text(encoding="utf-8")
        assert fixture_text == '{"custom": "fixture"}', (
            "fixture was not attempted, should keep user modification"
        )

        provider_dir = repo / "src" / "kpubdata" / "providers" / "overwrite_rollback"
        fixture_dir = repo / "tests" / "fixtures" / "overwrite_rollback"

        assert provider_dir.exists()
        assert fixture_dir.exists()

    def test_rollback_failure_reports_incomplete_rollback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _shared_repo_root(tmp_path)
        scaffold_provider("rollback_fail", repo_root=repo, dataset_key="first")

        original_write_text = Path.write_text
        original_write_bytes = Path.write_bytes

        write_count = 0
        rollback_count = 0

        def failing_write_text(self: Path, content: str, *, encoding: str = "utf-8") -> None:
            nonlocal write_count
            write_count += 1
            if write_count == 2:
                raise OSError("simulated scaffold write failure")
            original_write_text(self, content, encoding=encoding)

        def failing_write_bytes(self: Path, content: bytes) -> None:
            nonlocal rollback_count
            rollback_count += 1
            if rollback_count == 1:
                raise OSError("simulated rollback failure")
            original_write_bytes(self, content)

        monkeypatch.setattr(Path, "write_text", failing_write_text)
        monkeypatch.setattr(Path, "write_bytes", failing_write_bytes)

        with pytest.raises(RuntimeError, match="rollback was incomplete") as exc_info:
            scaffold_provider("rollback_fail", repo_root=repo, dataset_key="second", overwrite=True)

        assert "simulated rollback failure" in str(exc_info.value)
        assert exc_info.value.__cause__ is not None
        assert isinstance(exc_info.value.__cause__, OSError)
        assert "simulated scaffold write failure" in str(exc_info.value.__cause__)

    def test_nonempty_provider_dir_is_not_reported_as_rollback_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        repo = _shared_repo_root(tmp_path)

        write_count = 0
        original_write_text = Path.write_text

        def failing_write_text(self: Path, content: str, *, encoding: str = "utf-8") -> None:
            nonlocal write_count
            write_count += 1
            if write_count == 2:
                (
                    repo / "src" / "kpubdata" / "providers" / "nonempty_test" / "other.txt"
                ).write_text("other file", encoding="utf-8")
                raise OSError("Simulated scaffold failure")
            original_write_text(self, content, encoding=encoding)

        monkeypatch.setattr(Path, "write_text", failing_write_text)

        with pytest.raises(OSError, match="Simulated scaffold failure"):
            scaffold_provider("nonempty_test", repo_root=repo, dataset_key="sample")

        provider_dir = repo / "src" / "kpubdata" / "providers" / "nonempty_test"
        assert provider_dir.exists()
        assert (provider_dir / "other.txt").exists()
        assert (provider_dir / "other.txt").read_text(encoding="utf-8") == "other file"

        result = scaffold_provider("nonempty_test", repo_root=repo, dataset_key="sample")
        assert result.adapter_path.exists()


class TestScaffoldCli:
    def test_cli_subcommand_creates_files(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # kpubdata scaffold provider <name> works and returns exit 0.
        from kpubdata.cli import main

        repo = _shared_repo_root(tmp_path)
        exit_code = main(
            [
                "scaffold",
                "provider",
                "cli_prov",
                "--dataset-key",
                "demo",
                "--repo-root",
                str(repo),
            ]
        )
        captured = capsys.readouterr()

        assert exit_code == 0
        assert "Scaffolded provider 'cli_prov'" in captured.out
        assert (repo / "src" / "kpubdata" / "providers" / "cli_prov" / "adapter.py").exists()

    def test_cli_reports_invalid_name_with_exit_one(
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        from kpubdata.cli import main

        repo = _shared_repo_root(tmp_path)
        exit_code = main(["scaffold", "provider", "Bad-Name", "--repo-root", str(repo)])
        captured = capsys.readouterr()

        assert exit_code == 1
        assert "scaffold failed" in captured.err
