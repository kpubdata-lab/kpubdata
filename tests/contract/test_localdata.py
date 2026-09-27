"""Test module.

This file defines test scenarios and helper objects in the
``tests/contract/test_localdata.py`` path. It verifies core flows, exceptions,
and edge conditions for regression prevention and public contract validation.
"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import Protocol, cast

import pytest

from kpubdata.config import KPubDataConfig
from kpubdata.core.models import DatasetRef, Query
from kpubdata.core.protocol import ProviderAdapter
from kpubdata.transport.http import HttpTransport
from tests.contract.provider_adapter import ProviderAdapterContract


def _fixture_path(name: str) -> Path:
    """
    Internal helper that handles fixture path resolution.

    Args:
        name (str): The input value provided by the caller.

    Returns:
        Path: The computed result or the return value from downstream calls.

    Raises:
        Exception from internal implementation or downstream dependencies
        can be raised as-is.
    """
    return Path(__file__).resolve().parents[1] / "fixtures" / "localdata" / name


def _load_fixture_bytes(name: str) -> bytes:
    """
    Internal helper that handles loading fixture bytes.

    Args:
        name (str): The input value provided by the caller.

    Returns:
        bytes: The computed result or the return value from downstream calls.

    Raises:
        Exception from internal implementation or downstream dependencies
        can be raised as-is.
    """
    return _fixture_path(name).read_bytes()


class _FakeResponse:
    """
    Class that encapsulates roles related to _FakeResponse.

    This class manages state and behavior of _FakeResponse within the
    ``tests/contract/test_localdata.py`` module.
    Key method: __init__.

    Attribute description:
        Properties defined in the constructor and class body are reused
        as shared context by downstream methods.
    """

    def __init__(self, data: bytes, content_type: str = "application/json") -> None:
        """
        Initialize instance state for internal use.

        Args:
            data (bytes): The input value provided by the caller.
            content_type (str): The input value provided by the caller.

        Returns:
            None: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        self.headers: dict[str, str] = {"content-type": content_type}
        self.content: bytes = data
        self.text: str = data.decode("utf-8")


class _FixtureTransport:
    """
    Class that encapsulates roles related to _FixtureTransport.

    This class manages state and behavior of _FixtureTransport within the
    ``tests/contract/test_localdata.py`` module.
    Key methods: __init__, request.

    Attribute description:
        Properties defined in the constructor and class body are reused
        as shared context by downstream methods.
    """

    def __init__(self, fixture_names: list[str]) -> None:
        """
        Initialize instance state for internal use.

        Args:
            fixture_names (list[str]): The input value provided by the caller.

        Returns:
            None: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        self._responses: list[_FakeResponse] = [
            _FakeResponse(_load_fixture_bytes(name)) for name in fixture_names
        ]
        self.calls: list[dict[str, object]] = []

    def request(self, method: str, url: str, **kwargs: object) -> _FakeResponse:
        """
        Perform request operation.

        Args:
            method (str): The input value provided by the caller.
            url (str): The input value provided by the caller.
            **kwargs (object): The input value provided by the caller.

        Returns:
            _FakeResponse: The computed result or the return value from
            downstream calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        self.calls.append({"method": method, "url": url, **kwargs})
        if not self._responses:
            raise AssertionError("No fixture responses remaining")
        return self._responses.pop(0)


class _AdapterFactory(Protocol):
    """
    Class that encapsulates roles related to _AdapterFactory.

    This class manages state and behavior of _AdapterFactory within the
    ``tests/contract/test_localdata.py`` module.
    Key method: __call__.

    Attribute description:
        Properties defined in the constructor and class body are reused
        as shared context by downstream methods.
    """

    def __call__(
        self,
        *,
        config: KPubDataConfig | None = None,
        transport: HttpTransport | None = None,
    ) -> ProviderAdapter: ...


def _build_adapter(fixture_names: list[str]) -> ProviderAdapter:
    """
    Internal helper that handles adapter building.

    Args:
        fixture_names (list[str]): The input value provided by the caller.

    Returns:
        ProviderAdapter: The computed result or the return value from
        downstream calls.

    Raises:
        Exception from internal implementation or downstream dependencies
        can be raised as-is.
    """
    transport = _FixtureTransport(fixture_names)
    config = KPubDataConfig(provider_keys={"datago": "test-key"})
    adapter_module = import_module("kpubdata.providers.localdata.adapter")
    adapter_class_obj = cast(object, adapter_module.LocaldataAdapter)
    if not isinstance(adapter_class_obj, type):
        raise AssertionError("LocaldataAdapter is not a class")
    adapter_class = cast(_AdapterFactory, adapter_class_obj)
    adapter_obj = adapter_class(
        config=config,
        transport=cast(HttpTransport, cast(object, transport)),
    )
    return adapter_obj


class TestLocaldataAdapterContract(ProviderAdapterContract):
    """
    Class that encapsulates roles related to TestLocaldataAdapterContract.

    This class manages state and behavior of TestLocaldataAdapterContract
    within the ``tests/contract/test_localdata.py`` module.
    Key methods: adapter, valid_dataset_key, invalid_dataset_key,
    sample_dataset, sample_query.

    Attribute description:
        Properties defined in the constructor and class body are reused
        as shared context by downstream methods.
    """

    @pytest.fixture()
    def adapter(self) -> ProviderAdapter:
        """
        Perform adapter operation.

        Returns:
            ProviderAdapter: The computed result or the return value from
            downstream calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return _build_adapter(
            [
                "general_restaurant_success.json",
                "rest_cafe_success.json",
                "bakery_success.json",
                "hospital_success.json",
                "clinic_success.json",
                "pharmacy_success.json",
                "animal_hospital_success.json",
                "optical_shop_success.json",
                "public_bath_success.json",
                "laundry_success.json",
                "barber_shop_success.json",
                "beauty_salon_success.json",
                "pet_grooming_success.json",
                "dance_academy_success.json",
                "karaoke_success.json",
                "singing_bar_success.json",
                "billiard_hall_success.json",
                "performance_hall_success.json",
                "movie_theater_success.json",
                "swimming_pool_success.json",
                "fitness_center_success.json",
                "ice_rink_success.json",
                "golf_course_success.json",
                "golf_practice_range_success.json",
                "horse_riding_success.json",
                "ski_resort_success.json",
                "affiliated_medical_institution_success.json",
                "postpartum_care_success.json",
                "safe_over_the_counter_drug_store_success.json",
                "emergency_patient_transport_success.json",
                "medical_foundation_success.json",
                "quasi_medical_business_success.json",
                "medical_device_repair_success.json",
                "dental_lab_success.json",
                "medical_device_sales_success.json",
                "animal_breeding_success.json",
                "animal_import_success.json",
                "animal_care_service_success.json",
                "animal_transport_success.json",
                "animal_funeral_success.json",
                "animal_exhibition_success.json",
                "animal_sales_success.json",
                "animal_crematorium_success.json",
                "animal_training_success.json",
                "companion_animal_related_business_success.json",
                "livestock_farming_success.json",
                "livestock_artificial_insemination_center_success.json",
                "slaughterhouse_success.json",
                "hatchery_success.json",
                "feed_manufacturing_success.json",
                "breeding_stock_success.json",
                "game_distribution_success.json",
                "game_manufacturing_success.json",
                "game_provider_success.json",
                "composite_game_provider_success.json",
                "internet_computer_game_facility_success.json",
                "youth_game_provider_success.json",
                "electronic_distribution_success.json",
                "tourist_performance_hall_success.json",
                "tourist_theater_entertainment_success.json",
                "tourist_track_success.json",
                "tourism_business_success.json",
                "tourist_excursion_boat_success.json",
                "tourism_convenience_facility_success.json",
                "international_conference_facility_success.json",
                "foreign_tourist_city_homestay_success.json",
                "amusement_facility_success.json",
                "general_amusement_facility_success.json",
                "comprehensive_amusement_facility_success.json",
                "comprehensive_resort_business_success.json",
                "specialized_resort_business_success.json",
                "hanok_experience_success.json",
                "tourism_duty_free_success.json",
                "international_conference_planning_success.json",
                "popular_culture_arts_planning_success.json",
                "culture_industry_company_success.json",
                "video_viewing_room_success.json",
                "video_distribution_success.json",
                "video_small_theater_success.json",
                "video_viewing_service_success.json",
                "video_production_success.json",
                "tourist_accommodation_success.json",
                "tourist_pension_success.json",
                "rural_guesthouse_success.json",
                "small_hotel_success.json",
                "foreign_tourist_city_homestay_lodging_success.json",
                "general_lodging_success.json",
                "hanok_experience_lodging_success.json",
                "residential_accommodation_success.json",
                "domestic_travel_success.json",
                "domestic_international_travel_success.json",
                "comprehensive_travel_success.json",
                "movie_distribution_success.json",
                "movie_screening_success.json",
                "movie_import_success.json",
                "movie_production_success.json",
                "online_music_service_success.json",
                "record_distribution_success.json",
                "record_production_success.json",
                "music_video_distribution_success.json",
                "music_video_production_success.json",
                "medical_linen_processing_success.json",
                "multilevel_sales_success.json",
                "large_store_success.json",
                "door_to_door_sales_success.json",
                "prepaid_installment_trade_success.json",
                "ecommerce_success.json",
                "mail_order_sales_success.json",
                "dance_hall_success.json",
                "yacht_marina_success.json",
                "motor_racing_course_success.json",
                "comprehensive_sports_facility_success.json",
                "martial_arts_gym_success.json",
                "boxing_gym_success.json",
                "contract_foodservice_success.json",
                "group_cafeteria_success.json",
                "health_functional_food_retail_success.json",
                "health_functional_food_specialty_success.json",
                "health_functional_food_distributor_success.json",
                "food_cold_storage_success.json",
                "food_repackaging_success.json",
                "food_transportation_success.json",
                "food_vending_machine_success.json",
                "food_manufacturing_success.json",
                "food_additive_manufacturing_success.json",
                "edible_ice_sales_success.json",
                "onggi_manufacturing_success.json",
                "distribution_specialized_sales_success.json",
                "instant_food_manufacturing_success.json",
                "milk_collection_success.json",
                "livestock_processing_success.json",
                "livestock_storage_success.json",
                "livestock_transportation_success.json",
                "livestock_sales_success.json",
                "imported_livestock_sales_success.json",
                "container_packaging_manufacturing_success.json",
                "other_food_sales_success.json",
                "imported_food_sales_success.json",
                "entertainment_bar_success.json",
                "tourist_restaurant_success.json",
                "foreigner_exclusive_entertainment_restaurant_success.json",
                "tourist_entertainment_restaurant_success.json",
                "timber_import_distribution_success.json",
                "log_production_success.json",
                "sawmill_success.json",
                "meter_repair_success.json",
                "high_pressure_gas_success.json",
                "petroleum_sales_success.json",
                "petroleum_import_export_success.json",
                "energy_saving_company_success.json",
                "lpg_charging_success.json",
                "lpg_collective_supply_success.json",
                "lpg_sales_success.json",
                "electrical_construction_success.json",
                "electrical_safety_management_agency_success.json",
                "electricity_sales_success.json",
                "city_gas_success.json",
                "gas_appliance_manufacturing_success.json",
                "groundwater_construction_success.json",
                "groundwater_impact_assessment_success.json",
                "groundwater_purification_success.json",
                "building_sanitation_management_success.json",
                "water_tank_cleaning_success.json",
                "disinfection_business_success.json",
                "sanitary_product_manufacturing_success.json",
                "sanitation_treatment_success.json",
                "waste_treatment_success.json",
                "waste_collection_transportation_success.json",
                "night_soil_collection_transportation_success.json",
                "environmental_measurement_agency_success.json",
                "environmental_impact_assessment_success.json",
                "air_pollution_prevention_facility_success.json",
                "water_pollution_prevention_facility_success.json",
                "soil_remediation_success.json",
                "noise_vibration_prevention_facility_success.json",
                "waste_recycling_success.json",
                "medical_waste_treatment_success.json",
                "marine_environment_management_success.json",
                "environmental_consulting_success.json",
                "outdoor_advertising_success.json",
                "printing_house_success.json",
                "publisher_success.json",
                "tobacco_wholesale_success.json",
                "tobacco_retail_success.json",
                "tobacco_import_sales_success.json",
                "international_freight_forwarding_success.json",
                "logistics_warehouse_success.json",
                "civil_defense_water_supply_success.json",
                "funeral_service_success.json",
                "elevator_maintenance_success.json",
                "elevator_manufacturing_import_success.json",
                "caregiver_training_institution_success.json",
                "funeral_director_training_institution_success.json",
                "free_job_placement_success.json",
                "paid_job_placement_success.json",
            ]
        )

    @pytest.fixture()
    def valid_dataset_key(self) -> str:
        """
        Perform valid dataset key operation.

        Returns:
            str: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return "general_restaurant"

    @pytest.fixture()
    def invalid_dataset_key(self) -> str:
        """
        Perform invalid dataset key operation.

        Returns:
            str: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return "nonexistent_dataset_key_xyz"

    @pytest.fixture()
    def sample_dataset(self, adapter: ProviderAdapter) -> DatasetRef:
        """
        Perform sample dataset operation.

        Args:
            adapter (ProviderAdapter): The input value provided by the caller.

        Returns:
            DatasetRef: The computed result or the return value from
            downstream calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return adapter.get_dataset("general_restaurant")

    @pytest.fixture()
    def sample_query(self) -> Query:
        """
        Perform sample query operation.

        Returns:
            Query: The computed result or the return value from downstream
            calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return Query()

    @pytest.fixture()
    def raw_operation(self) -> tuple[str, dict[str, object]]:
        """
        Perform raw operation operation.

        Returns:
            tuple[str, dict[str, object]]: The computed result or the return
            value from downstream calls.

        Raises:
            Exception from internal implementation or downstream dependencies
            can be raised as-is.
        """
        return ("info", {"pageNo": "1", "numOfRows": "10"})
