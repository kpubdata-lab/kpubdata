"""Integration tests for features added in recent sessions.

Tests license field, ocean_buoy spec, CI verify, repositioning changes,
and other multi-PR features to ensure they integrate correctly.
"""

from __future__ import annotations

from kpubdata import Client
from kpubdata.core.spec import LicenseSpec, discover_specs, find_spec


class TestLicenseFieldIntegration:
    """Verify license field works throughout pipeline."""

    def test_spec_with_license_loads(self) -> None:
        """Spec with license loads correctly."""
        spec = find_spec("datago.apt_trade")
        assert spec is not None
        assert isinstance(spec.license, LicenseSpec)
        assert spec.license.type == "공공누리_1유형"
        assert spec.license.commercial_use is True
        assert spec.license.attribution_required is True

    def test_spec_without_license_loads(self) -> None:
        """Spec without license loads as None (synthetic — all real specs now have one)."""
        from kpubdata.core.spec import from_mapping

        spec = from_mapping(
            {
                "id": "test.no_license",
                "provider": "test",
                "title": "No licence",
                "endpoint": {"base_url": "https://example.test/api", "operation": "list"},
                "auth": {"type": "none"},
                "response": {
                    "format": "json",
                    "envelope": "datago_standard",
                    "error": {
                        "style": "header_result_code",
                        "code_path": "response.header.resultCode",
                    },
                },
                "pagination": {"type": "none"},
            }
        )
        assert spec.license is None

    def test_all_specs_valid_license_or_none(self) -> None:
        """All specs have license as LicenseSpec or None."""
        for spec in discover_specs():
            if spec.license is not None:
                assert isinstance(spec.license, LicenseSpec), f"{spec.id}: invalid license type"

    def test_license_preserved_across_four_datago_specs(self) -> None:
        """4 datago specs from PR #443 retain license."""
        for ds_id in (
            "datago.apt_trade",
            "datago.apt_rent",
            "datago.air_quality",
            "datago.village_fcst",
        ):
            spec = find_spec(ds_id)
            assert spec is not None, f"{ds_id} not found"
            assert spec.license is not None, f"{ds_id} has no license"
            assert spec.license.type == "공공누리_1유형"


class TestOceanBuoyIntegration:
    """Verify ocean_buoy spec integrates correctly."""

    def test_spec_discoverable(self) -> None:
        """ocean_buoy included in discover_specs."""
        specs = discover_specs()
        ids = [s.id for s in specs]
        assert "datago.ocean_buoy" in ids

    def test_spec_fields(self) -> None:
        """ocean_buoy spec has correct core fields."""
        spec = find_spec("datago.ocean_buoy")
        assert spec is not None
        assert spec.title.startswith("해양관측부이")
        assert spec.endpoint.operation == "GetTWRecentApiService"
        assert spec.status == "unstable"

        param_names = {p.name for p in spec.params}
        assert "obsCode" in param_names

        field_names = {f.name for f in spec.fields}
        assert "wvhgt" in field_names  # Wind direction
        assert "wspd" in field_names  # Wind speed
        assert "wtem" in field_names  # Water temperature

    def test_client_resolves_ocean_buoy(self) -> None:
        """Client resolves ocean_buoy correctly."""
        client = Client()
        ds_list = client.datasets.list(provider="datago")
        ocean_ids = [d.id for d in ds_list if "ocean" in d.id]
        assert "datago.ocean_buoy" in ocean_ids


class TestKrxLicenseNotice:
    """Verify KRX license warnings preserved in catalog."""

    def test_license_note_in_raw_metadata(self) -> None:
        """3 KRX datasets have license_note."""
        client = Client()
        for ds_id in ("krx.kospi_index", "krx.investor_flow", "krx.market_valuation"):
            ds_ref = next(d for d in client.datasets.list(provider="krx") if d.id == ds_id)
            note = ds_ref.raw_metadata.get("license_note")
            assert note is not None, f"{ds_id}: license_note missing"
            assert "KRX" in note or "재배포" in note


class TestSpecSchemaValidation:
    """Verify license field added to spec schema passes validation."""

    def test_validate_all_specs_pass(self) -> None:
        """All specs pass schema validation."""
        import subprocess
        import sys

        result = subprocess.run(
            [sys.executable, "scripts/validate_spec.py"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        assert result.returncode == 0, f"spec validation failed:\n{result.stdout}\n{result.stderr}"
        assert "실패" not in result.stdout or "0개 실패" in result.stdout


class TestClientIntegrationSmoke:
    """Client-level smoke test for basic operations."""

    def test_datasets_list_includes_all_providers(self) -> None:
        """Client.datasets.list() includes major providers."""
        client = Client()
        all_ds = client.datasets.list()
        providers = {d.provider for d in all_ds}
        # Check providers modified this session still registered
        assert "datago" in providers
        assert "krx" in providers
        assert "bok" in providers

    def test_search_finds_ocean_buoy(self) -> None:
        """ocean_buoy found via search."""
        client = Client()
        results = client.datasets.search("해양")
        ids = [d.id for d in results]
        assert "datago.ocean_buoy" in ids

    def test_spec_count_increased(self) -> None:
        """23+ spec datasets after ocean_buoy addition."""
        specs = discover_specs()
        assert len(specs) >= 23
