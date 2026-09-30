"""The production-grade criteria were prose until something evaluated them (#625).

production_grade.yaml (#463) defined what a verified dataset must satisfy, but
no gate read it. These tests pin the evaluator's decisions: the criteria gate
the tier that claims them (the verified status in SUPPORTED_DATA.md), an
unfinished row gates nothing, fixtures are found under whatever name the
recorder wrote, and — the actual CI gate — every spec dataset in this
repository passes the gating checks.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_production_grade.py"


def _load_script():
    """Load the script as a module (scripts/ is not a package)."""
    spec = importlib.util.spec_from_file_location("check_production_grade", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_production_grade"] = module
    spec.loader.exec_module(module)
    return module


cpg = _load_script()

_ROW = "| {status} | 실API 검증 | 2026-09-09 | 공공데이터포털 (`datago`) | `{key}` | 이름 | 인증 | 문서 | 비고 |"


def _document(*rows: str) -> str:
    header = [
        "# 지원 공공데이터 현황",
        "",
        "| 상태 | 검증 | 검증일 | Provider | Dataset ID | 이름 | 인증 | 문서 | 비고 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    return "\n".join(header + list(rows)) + "\n"


def _synthetic_spec(dataset_key: str):
    """A real spec renamed, so the checks run against something shaped right."""
    from kpubdata.core.spec import find_spec

    base = find_spec("datago.apt_trade")
    assert base is not None
    return dataclasses.replace(base, id=f"datago.{dataset_key}")


def test_every_spec_dataset_passes_the_gating_checks() -> None:
    """The CI gate: whatever this repository ships must meet the criteria it
    claims. A failure here means a dataset regressed below its own row."""
    results, _reports, _deferred = cpg.evaluate(REPO_ROOT)

    failures = [result for result in results if not result.passed]
    assert failures == []
    assert results, "no spec datasets were evaluated at all"


def test_only_the_verified_tier_gates_the_tier_checks(tmp_path: Path, monkeypatch) -> None:
    verified = _synthetic_spec("verified_one")
    in_progress = _synthetic_spec("unfinished_one")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "production_grade.yaml").write_text(
        (REPO_ROOT / "docs" / "production_grade.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "SUPPORTED_DATA.md").write_text(
        _document(
            _ROW.format(status="지원", key="verified_one"),
            _ROW.format(status="진행 중", key="unfinished_one"),
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cpg, "discover_specs", lambda: [verified, in_progress])

    results, _reports, _deferred = cpg.evaluate(tmp_path)

    by_dataset: dict[str, set[str]] = {}
    for result in results:
        by_dataset.setdefault(result.dataset_id, set()).add(result.check_id)
    # The verified row claims fixture and example, and neither exists here.
    assert "fixture_exists" in by_dataset["datago.verified_one"]
    assert "example_script" in by_dataset["datago.verified_one"]
    # The in-progress row already says the work is unfinished — it gates
    # nothing beyond being listed and having a source.
    assert "fixture_exists" not in by_dataset["datago.unfinished_one"]
    assert "example_script" not in by_dataset["datago.unfinished_one"]


def test_fields_declared_is_reported_not_gated(tmp_path: Path, monkeypatch) -> None:
    from kpubdata.core.spec import FieldSpec

    empty_fields = dataclasses.replace(_synthetic_spec("no_fields"), fields=())
    declared = dataclasses.replace(
        _synthetic_spec("with_fields"), fields=(FieldSpec(name="a", type="string"),)
    )
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "production_grade.yaml").write_text(
        (REPO_ROOT / "docs" / "production_grade.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    (tmp_path / "SUPPORTED_DATA.md").write_text(
        _document(
            _ROW.format(status="지원", key="no_fields"),
            _ROW.format(status="지원", key="with_fields"),
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(cpg, "discover_specs", lambda: [empty_fields, declared])

    results, reports, _deferred = cpg.evaluate(tmp_path)

    gating_failures = [
        result for result in results if not result.passed and result.check_id == "fields_declared"
    ]
    assert gating_failures == []
    reported = [report for report in reports if report.dataset_id == "datago.no_fields"]
    assert reported and not reported[0].passed


def test_supported_statuses_reads_the_backticked_rows(tmp_path: Path) -> None:
    document = tmp_path / "SUPPORTED_DATA.md"
    document.write_text(
        _document(
            _ROW.format(status="지원", key="apt_trade"),
            _ROW.format(status="진행 중", key="ocean_buoy"),
            "| 그냥 문장 | 입니다 |",
        ),
        encoding="utf-8",
    )

    statuses = cpg.supported_statuses(tmp_path)

    assert statuses[("datago", "apt_trade")] == "지원"
    assert statuses[("datago", "ocean_buoy")] == "진행 중"
    assert len(statuses) == 2


def test_a_fixture_is_found_under_whatever_name_it_was_recorded(tmp_path: Path) -> None:
    """tour_kor_area records ``seoul_restaurants.meta.json`` — the recorder
    names fixtures after the example, and the check must read it that way."""
    from kpubdata.core.spec import find_spec

    spec = find_spec("datago.tour_kor_area")
    assert spec is not None
    recorded = tmp_path / "tests" / "fixtures" / "datago" / "tour_kor_area"
    recorded.mkdir(parents=True)
    (recorded / "seoul_restaurants.meta.json").write_text("{}", encoding="utf-8")

    result = cpg._fixture_exists(spec, tmp_path, "지원")

    assert result.passed
    assert "seoul_restaurants.meta.json" in result.detail


def test_an_unlisted_dataset_fails_the_listing_check(tmp_path: Path) -> None:
    spec = _synthetic_spec("never_heard_of_it")
    (tmp_path / "SUPPORTED_DATA.md").write_text(_document(), encoding="utf-8")

    result = cpg._supported_data_listed(spec, tmp_path, "")

    assert not result.passed


def test_main_passes_on_this_repository(capsys) -> None:
    assert cpg.main([]) == 0
    assert "PASS" in capsys.readouterr().out
