"""Unit tests for core/spec.py — validate fixture samples and bundled golden specs."""

from pathlib import Path

import pytest

from kpubdata.core.spec import (
    LicenseSpec,
    discover_specs,
    find_spec,
    from_mapping,
    load_spec_file,
    spec_index,
)
from kpubdata.exceptions import InvalidRequestError

FIXTURES_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "specs"


# ----------------------------------------------------------------------
# from_mapping / load_spec_file
# ----------------------------------------------------------------------


def test_from_mapping_minimal() -> None:
    """Load succeeds with minimal required fields only."""
    spec = load_spec_file(FIXTURES_DIR / "valid_minimal.yaml")
    assert spec.id == "test.minimal"
    assert spec.provider == "test"
    assert spec.dataset_key == "minimal"
    assert spec.auth.type == "none"
    assert spec.pagination.type == "none"
    assert spec.params == ()
    assert spec.fields == ()
    assert spec.examples == ()


def test_from_mapping_full_sections() -> None:
    """All schema sections are correctly interpreted."""
    spec = load_spec_file(FIXTURES_DIR / "valid_full.yaml")
    assert spec.endpoint.format_param is not None
    assert spec.endpoint.format_param.name == "_type"
    assert spec.endpoint.format_param.values == {"json": "json", "xml": "xml"}
    assert spec.auth.param_name == "serviceKey"
    assert spec.auth.provider_key == "datago"

    param = spec.params[0]
    assert param.name == "LAWD_CD"
    assert param.alias == "region_code"
    assert param.exposed_name == "region_code"
    assert param.required is True

    assert spec.response.format == "xml"
    assert spec.response.total_count_path == "response.body.totalCount"
    assert spec.response.error.ok_values == ("00", "000", 0)

    assert spec.pagination.type == "page_no_rows"
    assert spec.pagination.max_size == 1000

    field = spec.fields[0]
    assert field.source_name == "거래금액"
    assert field.transform == "strip_comma"

    example = spec.examples[0]
    assert example.params == {"region_code": "11110"}
    assert example.format == "xml"

    assert spec.last_verified is not None
    assert spec.source is not None and spec.source.doc_version == "v1.2"

    # Undeclared keys are preserved in raw_metadata (backward compat).
    assert spec.raw_metadata.get("custom_future_field") == "보존되어야 하는 미선언 키"


def test_from_mapping_license_parsed() -> None:
    """license section correctly converts to LicenseSpec."""
    data: dict[str, object] = {
        "id": "test.lic",
        "provider": "test",
        "title": "라이선스 테스트",
        "endpoint": {"base_url": "https://example.test/api", "operation": "op", "method": "GET"},
        "auth": {"type": "none"},
        "response": {
            "format": "json",
            "envelope": "datago_standard",
            "error": {"style": "http_status"},
        },
        "pagination": {"type": "none"},
        "status": "active",
        "license": {
            "type": "공공누리_1유형",
            "commercial_use": True,
            "attribution_required": True,
            "modification_allowed": True,
            "note": "자유이용",
        },
    }
    spec = from_mapping(data)
    assert isinstance(spec.license, LicenseSpec)
    assert spec.license.type == "공공누리_1유형"
    assert spec.license.commercial_use is True
    assert spec.license.attribution_required is True
    assert spec.license.modification_allowed is True
    assert spec.license.note == "자유이용"


def test_from_mapping_license_bad_type_is_rejected() -> None:
    """Invalid license field type fails spec load.

    Previously only logged problems and put None, but that log was
    created after ``if problems: raise`` so was discarded entirely.
    Distinguishing "bad declaration" from "no declaration" is needed
    for redistribution possibility judgment not to change silently.
    """
    data: dict[str, object] = {
        "id": "test.lic2",
        "provider": "test",
        "title": "타입 오류",
        "endpoint": {"base_url": "https://example.test/api", "operation": "op", "method": "GET"},
        "auth": {"type": "none"},
        "response": {
            "format": "json",
            "envelope": "datago_standard",
            "error": {"style": "http_status"},
        },
        "pagination": {"type": "none"},
        "status": "active",
        "license": {
            "type": "공공누리_1유형",
            "commercial_use": "true",  # String instead of bool
        },
    }
    with pytest.raises(InvalidRequestError) as exc:
        from_mapping(data)

    assert "license.commercial_use" in str(exc.value)


def _licensed_spec(license_block: dict[str, object]) -> dict[str, object]:
    return {
        "id": "test.kogl",
        "provider": "test",
        "title": "KOGL",
        "endpoint": {"base_url": "https://example.test/api", "operation": "op", "method": "GET"},
        "auth": {"type": "none"},
        "response": {
            "format": "json",
            "envelope": "datago_standard",
            "error": {"style": "http_status"},
        },
        "pagination": {"type": "none"},
        "status": "active",
        "license": license_block,
    }


@pytest.mark.parametrize(
    ("license_block", "field"),
    [
        ({"type": "공공누리_3유형", "modification_allowed": True}, "license.modification_allowed"),
        ({"type": "공공누리_4유형", "modification_allowed": True}, "license.modification_allowed"),
        ({"type": "공공누리_2유형", "commercial_use": True}, "license.commercial_use"),
        ({"type": "공공누리_4유형", "commercial_use": True}, "license.commercial_use"),
    ],
)
def test_kogl_type_contradicting_its_flags_is_rejected(
    license_block: dict[str, object], field: str
) -> None:
    """A KOGL type and a flag that says the opposite cannot both be published (#719)."""
    with pytest.raises(InvalidRequestError) as exc:
        from_mapping(_licensed_spec(license_block))

    assert field in str(exc.value)


@pytest.mark.parametrize(
    "kogl_type", ["공공누리_1유형", "공공누리_2유형", "공공누리_3유형", "공공누리_4유형"]
)
def test_kogl_type_waiving_attribution_is_rejected(kogl_type: str) -> None:
    """Every KOGL type requires attribution, so none may declare it waived (#725)."""
    with pytest.raises(InvalidRequestError) as exc:
        from_mapping(_licensed_spec({"type": kogl_type, "attribution_required": False}))

    assert "license.attribution_required" in str(exc.value)


def test_non_kogl_licence_may_waive_attribution() -> None:
    spec = from_mapping(_licensed_spec({"type": "자유이용", "attribution_required": False}))

    assert spec.license is not None
    assert spec.license.attribution_required is False


@pytest.mark.parametrize(
    "license_block",
    [
        {"type": "공공누리_1유형", "commercial_use": True, "modification_allowed": True},
        {"type": "공공누리_3유형", "commercial_use": True, "modification_allowed": False},
        {"type": "공공누리_4유형", "commercial_use": False, "modification_allowed": False},
        {"type": "공공누리_3유형"},
        {"type": "공공누리_1유형", "attribution_required": True},
        {"type": "KRX_별도계약", "commercial_use": True, "modification_allowed": True},
    ],
)
def test_consistent_or_undeclared_kogl_terms_load(license_block: dict[str, object]) -> None:
    spec = from_mapping(_licensed_spec(license_block))

    assert spec.license is not None
    assert spec.license.type == license_block["type"]


def test_bundled_specs_have_no_kogl_contradiction() -> None:
    """Every bundled spec loads under the KOGL check; air_quality is type 3 (#719)."""
    specs = {spec.id: spec for spec in discover_specs()}
    air = specs["datago.air_quality"].license

    assert air is not None
    assert air.type == "공공누리_3유형"
    assert air.modification_allowed is False
    assert air.redistribution == "forbidden"


def test_from_mapping_license_none_when_absent() -> None:
    """license section is None when absent."""
    data: dict[str, object] = {
        "id": "test.nolic",
        "provider": "test",
        "title": "없음",
        "endpoint": {"base_url": "https://example.test/api", "operation": "op", "method": "GET"},
        "auth": {"type": "none"},
        "response": {
            "format": "json",
            "envelope": "datago_standard",
            "error": {"style": "http_status"},
        },
        "pagination": {"type": "none"},
        "status": "active",
    }
    spec = from_mapping(data)
    assert spec.license is None


def test_from_mapping_invalid_id_format() -> None:
    """ID not in provider.dataset format fails with all problems."""
    with pytest.raises(InvalidRequestError) as exc_info:
        load_spec_file(FIXTURES_DIR / "invalid_bad_id.yaml")
    assert "형식이어야 합니다" in str(exc_info.value)


def test_from_mapping_invalid_enum_lists_all_problems() -> None:
    """Multiple enum violations are listed in a single message."""
    with pytest.raises(InvalidRequestError) as exc_info:
        load_spec_file(FIXTURES_DIR / "invalid_bad_enum.yaml")
    message = str(exc_info.value)
    assert "auth.type" in message
    assert "response.format" in message
    assert "pagination.type" in message
    assert "status" in message


def test_from_mapping_missing_required() -> None:
    """endpoint·response·pagination omissions are each reported."""
    with pytest.raises(InvalidRequestError) as exc_info:
        load_spec_file(FIXTURES_DIR / "invalid_missing_required.yaml")
    message = str(exc_info.value)
    assert "endpoint" in message
    assert "response" in message
    assert "pagination" in message


def test_from_mapping_id_provider_mismatch() -> None:
    """Mismatch between id prefix and provider is reported."""
    with pytest.raises(InvalidRequestError, match="불일치"):
        load_spec_file(FIXTURES_DIR / "invalid_id_mismatch.yaml")


# ----------------------------------------------------------------------
# discover_specs / find_spec / spec_index
# ----------------------------------------------------------------------


def test_discover_specs_valid_only_root(tmp_path: Path) -> None:
    """Directory with valid specs only loads all (excludes invalid_* validation)."""
    valid_dir = tmp_path / "valid"
    valid_dir.mkdir()
    for name in ("valid_minimal.yaml", "valid_full.yaml"):
        target = valid_dir / name
        target.write_text((FIXTURES_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    specs = discover_specs(valid_dir)
    assert {spec.id for spec in specs} == {"test.minimal", "test.full"}


def test_discover_specs_invalid_fixture_raises() -> None:
    """Directory scan including invalid specs propagates schema validation exception."""
    with pytest.raises(InvalidRequestError):
        discover_specs(FIXTURES_DIR)


def test_discover_bundled_golden_specs() -> None:
    """Three bundled golden examples are discovered."""
    specs = discover_specs()
    ids = {spec.id for spec in specs}
    assert {
        "datago.apt_trade",
        "datago.hospital_info",
        "datago.village_fcst",
    } <= ids


def test_spec_index_and_find_spec_lookup() -> None:
    """Full id·bare key·provider-scoped lookup all work."""
    index = spec_index()
    assert "datago.apt_trade" in index

    by_full = find_spec("datago.apt_trade")
    assert by_full is not None and by_full.id == "datago.apt_trade"

    by_bare = find_spec("village_fcst", provider="datago")
    assert by_bare is not None and by_bare.id == "datago.village_fcst"

    assert find_spec("no.such_dataset") is None


def _base_spec_data(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "id": "test.dates",
        "provider": "test",
        "title": "날짜 검증",
        "endpoint": {"base_url": "https://example.test/api", "operation": "op", "method": "GET"},
        "auth": {"type": "none"},
        "response": {
            "format": "json",
            "envelope": "datago_standard",
            "error": {"style": "http_status"},
        },
        "pagination": {"type": "none"},
        "status": "active",
    }
    data.update(overrides)
    return data


def test_invalid_last_verified_is_rejected_not_silently_dropped() -> None:
    """Invalid value like ``2026-13-45`` does not silently become None.

    Spec without verification date must be distinguished from spec with
    bad verification date, or SUPPORTED_DATA's "real API verified"
    claim will pass without evidence.
    """
    with pytest.raises(InvalidRequestError) as exc:
        from_mapping(_base_spec_data(last_verified="2026-13-45"))

    assert "last_verified" in str(exc.value)


def test_invalid_source_verified_at_is_rejected() -> None:
    with pytest.raises(InvalidRequestError) as exc:
        from_mapping(_base_spec_data(source={"verified_at": "not-a-date"}))

    assert "source.verified_at" in str(exc.value)


def test_a_valid_last_verified_still_parses() -> None:
    spec = from_mapping(_base_spec_data(last_verified="2026-09-24"))

    assert spec.last_verified is not None
    assert spec.last_verified.isoformat() == "2026-09-24"


def test_absent_dates_stay_none() -> None:
    spec = from_mapping(_base_spec_data())

    assert spec.last_verified is None
