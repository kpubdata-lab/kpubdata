"""Scaffolding tooling for new provider adapters (#61).

This module generates the minimal bundle of files needed to add a new
provider adapter. The point is an honest skeleton that follows the rules in
PROVIDER_ADAPTER_CONTRACT.md / AGENTS.md — a working placeholder adapter,
catalogue, fixture and contract test produced in one shot — removing the
startup cost of writing the first PR.

Main functions:
    - scaffold_provider: write a provider skeleton to disk under the given
      name.
"""

from __future__ import annotations

import errno
import json
import keyword
import re
from dataclasses import dataclass
from pathlib import Path

_PROVIDER_NAME_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")
_DATASET_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass(frozen=True)
class ScaffoldResult:
    """Result object carrying the paths the scaffolding created.

    Attributes:
        provider_dir: The src/kpubdata/providers/<name>/ directory.
        adapter_path: Path of the provider adapter module.
        init_path: Path of the provider package __init__.py.
        catalogue_path: Path of catalogue.json.
        fixture_dir: The tests/fixtures/<name>/ directory.
        fixture_path: Path of the sample fixture JSON.
        contract_test_path: Path of tests/contract/test_<name>.py.
        created: Paths of the newly created files.
    """

    provider_dir: Path
    adapter_path: Path
    init_path: Path
    catalogue_path: Path
    fixture_dir: Path
    fixture_path: Path
    contract_test_path: Path
    created: tuple[Path, ...]


def _validate_provider_name(name: str) -> None:
    """Reject names that could escape the workspace or are not identifiers.

    Python keywords (``class``, ``import``, ...) are rejected separately
    from the regex because they would raise SyntaxError in import/from
    statements regardless of pattern compliance.
    """
    if not _PROVIDER_NAME_PATTERN.match(name):
        raise ValueError(
            f"provider name must match {_PROVIDER_NAME_PATTERN.pattern!r}, got {name!r}. "
            "Use lowercase ASCII letters, digits, underscore; start with a letter."
        )
    if keyword.iskeyword(name) or keyword.issoftkeyword(name):
        raise ValueError(
            f"provider name must not be a Python keyword, got {name!r}. "
            "Generated `from kpubdata.providers.<name>` would fail to parse."
        )


def _validate_dataset_key(key: str) -> None:
    """Reject non-ASCII or non-identifier dataset keys.

    dataset_key can also be reused as part of a test function name
    (``test_<provider>_seed_dataset_*``), so Python keywords are rejected
    explicitly.
    """
    if not _DATASET_KEY_PATTERN.match(key):
        raise ValueError(
            f"dataset_key must match {_DATASET_KEY_PATTERN.pattern!r}, got {key!r}. "
            "Use lowercase ASCII letters, digits, underscore; start with a letter."
        )
    if keyword.iskeyword(key) or keyword.issoftkeyword(key):
        raise ValueError(f"dataset_key must not be a Python keyword, got {key!r}.")


def _adapter_module(provider_name: str, dataset_key: str) -> str:
    """Return the provider adapter module body as a string."""
    class_name = "".join(part.capitalize() for part in provider_name.split("_")) + "Adapter"
    return f'''"""{provider_name} provider adapter (TODO: one-line summary).

A skeleton following PROVIDER_ADAPTER_CONTRACT.md. The real backend calls still
need writing (e.g. HTTP transport calls, turning native responses into RecordBatch).
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

from kpubdata.core.models import (
    DatasetRef,
    Query,
    RecordBatch,
    SchemaDescriptor,
)
from kpubdata.exceptions import DatasetNotFoundError, InvalidRequestError
from kpubdata.providers._common import build_dataset_ref, load_catalogue


_CATALOGUE_PATH = Path(__file__).parent / "catalogue.json"


def _load_default_catalogue() -> tuple[DatasetRef, ...]:
    """Load this provider package's catalogue.json as a tuple of DatasetRef.

    An installed package uses ``load_catalogue`` over ``importlib.resources`` (which
    also works from a zipped wheel). When that fails -- right after scaffolding,
    before the package is importable, or when loaded standalone through
    spec_from_file_location -- it falls back to reading the file next to ``__file__``.
    """
    try:
        return load_catalogue("kpubdata.providers.{provider_name}", "{provider_name}")
    except (ModuleNotFoundError, FileNotFoundError):
        raw = json.loads(_CATALOGUE_PATH.read_text(encoding="utf-8"))
        return tuple(build_dataset_ref("{provider_name}", entry) for entry in raw)


class {class_name}:
    """{provider_name} provider adapter.

    Only dataset discovery works in this skeleton. The fetch logic --
    query_records, call_raw -- has to be written against the backend's spec.
    """

    requires_api_key: bool = True  # TODO: set to False if the backend needs no key.

    def __init__(self, *, catalogue: Sequence[DatasetRef] | None = None) -> None:
        """Load the provider catalogue (tests may inject one)."""
        self._datasets: tuple[DatasetRef, ...] = (
            tuple(catalogue) if catalogue is not None else _load_default_catalogue()
        )
        self._datasets_by_key: dict[str, DatasetRef] = {{
            d.dataset_key: d for d in self._datasets
        }}

    @property
    def name(self) -> str:
        """Canonical provider key."""
        return "{provider_name}"

    def list_datasets(self) -> list[DatasetRef]:
        """Datasets discoverable from this provider."""
        return list(self._datasets)

    def search_datasets(self, text: str) -> list[DatasetRef]:
        """Search datasets by text (casefolded match on name and id)."""
        needle = text.casefold()
        return [
            d for d in self._datasets
            if needle in d.id.casefold() or needle in d.name.casefold()
        ]

    def get_dataset(self, dataset_key: str) -> DatasetRef:
        """Resolve a provider-local dataset_key to a DatasetRef."""
        dataset = self._datasets_by_key.get(dataset_key)
        if dataset is not None:
            return dataset
        raise DatasetNotFoundError(
            f"Dataset not found: {provider_name}.{{dataset_key}}",
            provider="{provider_name}",
            dataset_id=f"{provider_name}.{{dataset_key}}",
        )

    def query_records(self, dataset: DatasetRef, query: Query) -> RecordBatch:
        """Canonical list/query call. TODO: implement the backend call."""
        raise InvalidRequestError(
            "query_records is not implemented yet — fill in backend logic.",
            provider="{provider_name}",
            dataset_id=dataset.id,
        )

    def get_schema(self, dataset: DatasetRef) -> SchemaDescriptor | None:
        """Optional schema metadata (None when unsupported)."""
        return None

    def call_raw(
        self, dataset: DatasetRef, operation: str, params: dict[str, object]
    ) -> object:
        """Raw escape hatch. TODO: return the backend's original response as-is."""
        raise InvalidRequestError(
            "call_raw is not implemented yet — fill in backend logic.",
            provider="{provider_name}",
            dataset_id=dataset.id,
        )


__all__ = ["{class_name}"]
'''


def _init_module(provider_name: str) -> str:
    """Body of the provider package __init__.py."""
    class_name = "".join(part.capitalize() for part in provider_name.split("_")) + "Adapter"
    return (
        f'"""{provider_name} provider adapter package."""\n\n'
        f"from __future__ import annotations\n\n"
        f"from .adapter import {class_name}\n\n"
        f'__all__ = ["{class_name}"]\n'
    )


def _catalogue_seed(provider_name: str, dataset_key: str) -> str:
    """Initial catalogue.json body (one sample dataset)."""
    entry = {
        "dataset_key": dataset_key,
        "name": f"{provider_name} {dataset_key} sample (TODO: replace with the real name)",
        "base_url": "https://example.invalid/api",
        "default_operation": "list",
        "representation": "api_json",
        "service_key_param": "serviceKey",
        "format_param": "type",
        "description": "TODO: describe the backend dataset.",
        "tags": [provider_name],
        "source_url": "https://example.invalid/dataset",
        "operations": ["list", "raw"],
        "query_support": {"pagination": "offset", "max_page_size": 100},
    }
    return json.dumps([entry], indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def _fixture_seed(dataset_key: str) -> str:
    """Sample success fixture (synthetic placeholder)."""
    payload = {
        "response": {
            "header": {"resultCode": "00", "resultMsg": "NORMAL SERVICE."},
            "body": {
                "items": {
                    "item": [
                        {"id": "1", "name": f"sample {dataset_key} record"},
                    ],
                },
                "numOfRows": 1,
                "pageNo": 1,
                "totalCount": 1,
            },
        },
    }
    return json.dumps(payload, indent=2, ensure_ascii=False) + "\n"


def _contract_test(provider_name: str, dataset_key: str) -> str:
    """tests/contract/test_<name>.py skeleton — covers discovery only."""
    class_name = "".join(part.capitalize() for part in provider_name.split("_")) + "Adapter"
    return f'''"""{provider_name} provider contract test (skeleton).

Add scenario tests once query_records and the other backend calls are implemented.
"""

from __future__ import annotations

from kpubdata.core.capability import Operation
from kpubdata.providers.{provider_name} import {class_name}


def _adapter() -> {class_name}:
    """Create an adapter instance for the tests."""
    return {class_name}()


def test_{provider_name}_adapter_name() -> None:
    """The provider name matches the canonical key."""
    assert _adapter().name == "{provider_name}"


def test_{provider_name}_lists_seed_dataset() -> None:
    """The seed dataset in catalogue.json appears in list_datasets."""
    datasets = _adapter().list_datasets()
    assert any(d.dataset_key == "{dataset_key}" for d in datasets)


def test_{provider_name}_seed_dataset_metadata() -> None:
    """The seed dataset declares the list and raw operations."""
    dataset = _adapter().get_dataset("{dataset_key}")
    assert dataset.id == "{provider_name}.{dataset_key}"
    assert Operation.LIST in dataset.operations
    assert Operation.RAW in dataset.operations
'''


def _cleanup_empty_directories(dirs: list[Path]) -> list[str]:
    """Remove empty directories deepest-first.

    Helper for cleaning up leaf directories created by this call.
    Directories that existed before the call, or that still hold files,
    are not deleted.

    Silently ignored conditions:
        - the directory no longer exists (FileNotFoundError)
        - the directory is not empty (errno.ENOTEMPTY)

    Returns:
        Error messages for deletions that genuinely failed.
    """
    errors: list[str] = []
    for directory in reversed(dirs):
        try:
            directory.rmdir()
        except FileNotFoundError:
            pass
        except OSError as exc:
            if exc.errno == errno.ENOTEMPTY:
                pass
            else:
                errors.append(f"{directory}: {type(exc).__name__}: {exc}")
    return errors


def scaffold_provider(
    name: str,
    *,
    repo_root: Path,
    dataset_key: str = "sample",
    overwrite: bool = False,
) -> ScaffoldResult:
    """Create the minimal file bundle for a new provider adapter.

    Args:
        name: Provider name (a Python package name, e.g. ``my_provider``).
        repo_root: Root of the kpubdata repository (parent of ``src/`` and
            ``tests/``).
        dataset_key: dataset_key of the seed catalogue entry.
        overwrite: Whether to overwrite existing files. Defaults to
            False — existing files raise ``FileExistsError``.

    Returns:
        ScaffoldResult: The bundle of created paths.

    Raises:
        ValueError: The name or dataset_key breaks the rules.
        FileExistsError: Files already exist and ``overwrite=False``.
    """
    _validate_provider_name(name)
    _validate_dataset_key(dataset_key)

    provider_dir = repo_root / "src" / "kpubdata" / "providers" / name
    adapter_path = provider_dir / "adapter.py"
    init_path = provider_dir / "__init__.py"
    catalogue_path = provider_dir / "catalogue.json"
    fixture_dir = repo_root / "tests" / "fixtures" / name
    fixture_path = fixture_dir / "success_sample.json"
    contract_test_path = repo_root / "tests" / "contract" / f"test_{name}.py"

    files: dict[Path, str] = {
        init_path: _init_module(name),
        adapter_path: _adapter_module(name, dataset_key),
        catalogue_path: _catalogue_seed(name, dataset_key),
        fixture_path: _fixture_seed(dataset_key),
        contract_test_path: _contract_test(name, dataset_key),
    }

    if not overwrite:
        existing = [p for p in files if p.exists()]
        if existing:
            paths = ", ".join(str(p) for p in existing)
            raise FileExistsError(
                f"refusing to overwrite existing scaffold files: {paths}. "
                "Pass overwrite=True (or --force) to replace."
            )

    provider_dir_existed = provider_dir.exists()
    fixture_dir_existed = fixture_dir.exists()
    contract_test_parent_existed = contract_test_path.parent.exists()

    provider_dir.mkdir(parents=True, exist_ok=True)
    fixture_dir.mkdir(parents=True, exist_ok=True)
    contract_test_path.parent.mkdir(parents=True, exist_ok=True)

    created_directories: list[Path] = []
    if not provider_dir_existed:
        created_directories.append(provider_dir)
    if not fixture_dir_existed:
        created_directories.append(fixture_dir)
    if not contract_test_parent_existed:
        created_directories.append(contract_test_path.parent)

    existing_contents: dict[Path, bytes] = {}
    new_files: set[Path] = set()
    attempted: list[Path] = []

    for path in files:
        if path.exists():
            existing_contents[path] = path.read_bytes()
        else:
            new_files.add(path)

    try:
        for path, content in files.items():
            attempted.append(path)
            path.write_text(content, encoding="utf-8")
    except Exception as original_exc:
        rollback_errors: list[str] = []

        for path in reversed(attempted):
            if path in existing_contents:
                try:
                    path.write_bytes(existing_contents[path])
                except OSError as exc:
                    rollback_errors.append(f"{path}: {type(exc).__name__}: {exc}")
            else:
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    rollback_errors.append(f"{path}: {type(exc).__name__}: {exc}")

        dir_errors = _cleanup_empty_directories(created_directories)
        rollback_errors.extend(dir_errors)

        if rollback_errors:
            details = "; ".join(rollback_errors)
            raise RuntimeError(
                f"scaffold failed and rollback was incomplete: {details}"
            ) from original_exc

        raise

    return ScaffoldResult(
        provider_dir=provider_dir,
        adapter_path=adapter_path,
        init_path=init_path,
        catalogue_path=catalogue_path,
        fixture_dir=fixture_dir,
        fixture_path=fixture_path,
        contract_test_path=contract_test_path,
        created=tuple(files.keys()),
    )


__all__ = ["ScaffoldResult", "scaffold_provider"]
