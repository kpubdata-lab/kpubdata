"""Gate for ADR 0005 — documents and code use one dataset status vocabulary (#619).

Before the ADR, six places named a dataset's state in six vocabularies and two
design documents contradicted each other and the code. Each test below pins one
place to ``kpubdata.core.status`` so a new name, or a stale one, fails here.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from kpubdata import _probe
from kpubdata.core import spec as spec_module
from kpubdata.core.status import (
    PROBE_TO_DRIFT,
    SPEC_STATUS_OVERRIDE,
    SUPPORTED_DATA_LEVELS,
    DatasetStatus,
    DriftClassification,
    ProbeStatus,
    SpecStatus,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
DOCS = REPO_ROOT / "docs"
BACKTICKED = re.compile(r"`([A-Za-z_]+)`")
DATASET_STATUSES = {status.value for status in DatasetStatus}
DRIFT_NAMES = {name.value for name in DriftClassification}


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _section(text: str, heading: str) -> str:
    """Body of the ``## heading`` section, up to the next ``## ``."""
    start = text.index(f"## {heading}")
    end = text.find("\n## ", start + 1)
    return text[start : end if end != -1 else len(text)]


def _table_rows(section: str) -> list[list[str]]:
    rows = []
    for line in section.splitlines():
        if not line.startswith("|") or set(line) <= set("|-: "):
            continue
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return rows[1:]  # drop the header


def test_spec_statuses_match_schema_json() -> None:
    schema = json.loads(_read(REPO_ROOT / "src/kpubdata/specs/schema.json"))
    assert set(schema["properties"]["status"]["enum"]) == {s.value for s in SpecStatus}
    assert {s.value for s in SpecStatus} == spec_module._STATUSES
    assert set(SPEC_STATUS_OVERRIDE) == set(SpecStatus)


def test_probe_statuses_come_from_the_enum() -> None:
    assert tuple(s.value for s in ProbeStatus) == _probe.PROBE_STATUSES
    assert set(PROBE_TO_DRIFT) == set(ProbeStatus)
    assert set(_probe._CODE_STATUS.values()) <= {s.value for s in ProbeStatus}


def test_supported_data_levels_are_all_mapped() -> None:
    levels = set()
    for line in _read(REPO_ROOT / "SUPPORTED_DATA.md").splitlines():
        # Dataset rows carry a backticked provider in a later cell; the
        # escape-hatch table puts it first and has no level column.
        cells = line.split("|")
        if line.startswith("| ") and "(`" in line and "`" not in cells[1]:
            levels.add(cells[1].strip())
    assert levels, "no dataset rows found in SUPPORTED_DATA.md"
    assert levels <= set(SUPPORTED_DATA_LEVELS), levels - set(SUPPORTED_DATA_LEVELS)


def test_adr_canonical_table_matches_enum() -> None:
    adr = _read(DOCS / "adrs/0005-dataset-status-vocabulary.md")
    table = _section(adr, "결정").split("### 2.")[0]
    names = {BACKTICKED.match(row[0]).group(1) for row in _table_rows(table)}  # type: ignore[union-attr]
    assert names == DATASET_STATUSES


def test_dataset_status_transition_table_uses_canonical_names() -> None:
    rows = _table_rows(_section(_read(DOCS / "DATASET_STATUS.md"), "Transition Rules"))
    assert rows
    for current, classification, _streak, nxt in rows:
        for name in BACKTICKED.findall(current) + BACKTICKED.findall(nxt):
            assert name in DATASET_STATUSES | {"previous_status"}, name
        for name in BACKTICKED.findall(classification):
            assert name in DRIFT_NAMES, name


def test_dataset_status_names_no_missing_module() -> None:
    text = _read(DOCS / "DATASET_STATUS.md")
    for path in re.findall(r"`(src/[\w/]+\.py)`", text):
        assert (REPO_ROOT / path).exists(), path
    for name in re.findall(r"\b[A-Z]+(?:_[A-Z]+)+\b", text):
        if name.endswith("_CHANGED"):
            assert name in DRIFT_NAMES, name


def test_live_probe_classification_matches_probe_codes() -> None:
    rows = _table_rows(_section(_read(DOCS / "LIVE_PROBE.md"), "Failure Classification"))
    documented = set()
    for status_cell, _http, codes, _e2e, drift in rows:
        status = ProbeStatus(BACKTICKED.match(status_cell).group(1))  # type: ignore[union-attr]
        documented.add(status)
        for code in re.findall(r"\d\d", codes):
            if code != "00":  # success carries no error code to map
                assert _probe._CODE_STATUS.get(code) == status.value, (code, status)
        expected = PROBE_TO_DRIFT[status]
        assert BACKTICKED.findall(drift) == ([expected.value] if expected else []), status
    assert documented == set(ProbeStatus)


def test_live_probe_example_uses_real_names() -> None:
    text = _read(DOCS / "LIVE_PROBE.md")
    example = json.loads(re.search(r"```json\n(.*?)```", text, re.S).group(1))  # type: ignore[union-attr]
    for result in example["results"]:
        assert ProbeStatus(result["status"])
        assert DriftClassification(result["classification"])
        assert spec_module.find_spec(result["dataset_id"]) is not None, result["dataset_id"]


@pytest.mark.parametrize("provider", ["neis", "fds"])
def test_live_probe_secrets_match_adapter_key_lookup(provider: str) -> None:
    text = _read(DOCS / "LIVE_PROBE.md")
    shared = next(line for line in text.splitlines() if "KPUBDATA_DATAGO_API_KEY" in line)
    adapter = _read(REPO_ROOT / f"src/kpubdata/providers/{provider}/adapter.py")
    reads_own_key = f'require_provider_key("{provider}")' in adapter
    assert reads_own_key == (provider not in shared)
