"""Dataset spec validation CLI — performs schema contract, id rules, duplicate checks.

Usage:
    uv run python scripts/validate_spec.py              # validate all specs
    uv run python scripts/validate_spec.py --spec datago.apt_trade
    uv run python scripts/validate_spec.py --specs-dir PATH --schema PATH

Checks:
1. YAML parsing
2. Violations of ``specs/schema.json`` (JSON Schema draft 2020-12)
3. id == "{provider}.{file stem}" and the file path ({provider}/) match
4. Duplicate ids across all specs
5. Duplicate examples[].names (within a dataset)
6. When a catalogue.json entry with the same key exists, prints a
   coexistence NOTICE (not a failure — pilot coexistence design)

CI (ci.yml) runs this after dependency install; any failure returns
exit 1.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

import jsonschema
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SPECS_DIR = REPO_ROOT / "src" / "kpubdata" / "specs"
DEFAULT_SCHEMA_PATH = DEFAULT_SPECS_DIR / "schema.json"
PROVIDERS_DIR = REPO_ROOT / "src" / "kpubdata" / "providers"


@dataclass
class SpecCheckResult:
    """Single spec check result."""

    spec_id: str
    path: Path
    errors: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        """Return True if no errors."""
        return not self.errors


@dataclass
class ValidationReport:
    """Complete validation report."""

    results: list[SpecCheckResult] = field(default_factory=list)

    @property
    def passed_count(self) -> int:
        """Return count of passed specs."""
        return sum(1 for result in self.results if result.passed)

    @property
    def failed_count(self) -> int:
        """Return count of failed specs."""
        return sum(1 for result in self.results if not result.passed)

    @property
    def ok(self) -> bool:
        """Return whether all passed."""
        return bool(self.results) and self.failed_count == 0


def _load_schema(schema_path: Path) -> dict[str, object]:
    """Read schema file and return as dict."""
    import json

    data = json.loads(schema_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"스키마 파일이 객체가 아닙니다: {schema_path}"
        raise ValueError(msg)
    return data


def _catalogue_dataset_keys(provider: str) -> set[str]:
    """Return set of catalogue.json dataset keys for provider (empty if none)."""
    catalogue_path = PROVIDERS_DIR / provider / "catalogue.json"
    if not catalogue_path.is_file():
        return set()
    import json

    entries = json.loads(catalogue_path.read_text(encoding="utf-8"))
    if not isinstance(entries, list):
        return set()
    keys: set[str] = set()
    for entry in entries:
        if isinstance(entry, dict) and isinstance(entry.get("dataset_key"), str):
            keys.add(entry["dataset_key"])
    return keys


def validate_spec_file(
    path: Path,
    schema: dict[str, object],
    seen_ids: dict[str, Path],
) -> SpecCheckResult:
    """Check one spec file against schema and id rules."""
    spec_id = path.stem
    result = SpecCheckResult(spec_id=spec_id, path=path)
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        result.errors.append(f"YAML 파싱 실패: {exc}")
        return result

    if not isinstance(data, dict):
        result.errors.append("spec 루트는 매핑이어야 합니다.")
        return result

    declared_id = data.get("id")
    declared_id = declared_id if isinstance(declared_id, str) else ""
    provider = data.get("provider")
    provider = provider if isinstance(provider, str) else ""

    # jsonschema check — abbreviate error messages to human-readable form.
    validator_cls = jsonschema.Draft202012Validator
    validator = validator_cls(schema)
    for error in sorted(validator.iter_errors(data), key=lambda item: list(item.absolute_path)):
        location = ".".join(str(part) for part in error.absolute_path) or "(루트)"
        result.errors.append(f"스키마 위반 [{location}]: {error.message}")

    # Meaning vs storage contradictions (ADR 0006, #651) and KOGL type vs licence flags
    # (#719, #725) — same rules as the loader.
    from kpubdata.core.spec import field_conflicts, licence_conflicts

    fields = data.get("fields")
    if isinstance(fields, list):
        for item in fields:
            if isinstance(item, dict):
                result.errors.extend(field_conflicts(dict(item)))
    licence = data.get("license")
    if isinstance(licence, dict):
        result.errors.extend(licence_conflicts(licence))

    # id ↔ filename/directory rules
    if declared_id and declared_id != f"{provider}.{path.stem}":
        result.errors.append(
            f"id({declared_id!r})는 '{{provider}}.{{파일명}}' 규칙과 불일치합니다 "
            f"(기대: {provider}.{path.stem!r})"
        )
    expected_dir = path.parent.name
    if provider and expected_dir != provider:
        result.errors.append(
            f"파일이 {expected_dir!r} 디렉터리에 있지만 provider는 {provider!r}입니다."
        )

    # Global duplicate ids
    if declared_id:
        existing = seen_ids.get(declared_id)
        if existing is not None and existing != path:
            result.errors.append(
                f"id 중복: {declared_id!r}이(가) {existing}에도 정의되어 있습니다."
            )
        else:
            seen_ids[declared_id] = path

    # examples[].name duplicates
    examples = data.get("examples")
    if isinstance(examples, list):
        names: list[str] = [
            ex.get("name")
            for ex in examples
            if isinstance(ex, dict) and isinstance(ex.get("name"), str)
        ]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            result.errors.append(f"examples[].name 중복: {', '.join(duplicated)}")

    # catalogue coexistence NOTICE (not a failure)
    dataset_key = path.stem
    if dataset_key in _catalogue_dataset_keys(provider):
        result.notices.append(
            f"공존: {provider} catalogue.json에도 {dataset_key!r}이(가) 있습니다 "
            "(파일럿 병존 설계 — 전환 완료 시 catalogue 항목 제거)"
        )

    return result


def validate_specs(specs_dir: Path, schema_path: Path) -> ValidationReport:
    """Validate entire specs directory and return report."""
    schema = _load_schema(schema_path)
    report = ValidationReport()
    seen_ids: dict[str, Path] = {}
    for path in sorted(specs_dir.rglob("*.yaml")) + sorted(specs_dir.rglob("*.yml")):
        if path.name == "schema.json":
            continue
        report.results.append(validate_spec_file(path, schema, seen_ids))
    return report


def format_report(report: ValidationReport) -> str:
    """Convert report to human-readable summary string."""
    lines: list[str] = []
    for result in report.results:
        status = "통과" if result.passed else "실패"
        shown_path = (
            result.path.relative_to(REPO_ROOT)
            if result.path.is_relative_to(REPO_ROOT)
            else result.path
        )
        lines.append(f"[{status}] {shown_path}")
        for notice in result.notices:
            lines.append(f"  참고: {notice}")
        for error in result.errors:
            lines.append(f"  오류: {error}")
    lines.append(f"검증 결과: {report.passed_count}개 통과, {report.failed_count}개 실패")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point — run validation and return exit code."""
    parser = argparse.ArgumentParser(description="데이터셋 spec 검증")
    parser.add_argument("--spec", help="이 id의 spec만 검증 (예: datago.apt_trade)")
    parser.add_argument("--specs-dir", type=Path, default=DEFAULT_SPECS_DIR, help="specs 디렉터리")
    parser.add_argument("--schema", type=Path, default=DEFAULT_SCHEMA_PATH, help="스키마 경로")
    args = parser.parse_args(argv)

    if not args.specs_dir.is_dir():
        print(f"오류: specs 디렉터리가 없습니다: {args.specs_dir}")
        return 1

    report = validate_specs(args.specs_dir, args.schema)
    if args.spec:
        # Match allows both full id "provider.filename" or filename (stem).
        report.results = [
            result
            for result in report.results
            if args.spec in (result.spec_id, f"{result.path.parent.name}.{result.spec_id}")
        ]
        if not report.results:
            print(f"오류: spec을 찾을 수 없습니다: {args.spec}")
            return 1

    print(format_report(report))
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
