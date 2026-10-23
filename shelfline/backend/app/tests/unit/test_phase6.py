"""
Unit tests for Phase 6 Rules Engine and Safety Vetoes (S13, S14, S17, S18).
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.clock import SimClock, set_clock
from app.rules.engine import RulesEngine
from app.safety_gate import SafetyGate, SafetyReason


class TestRulesEngine:

    def test_rules_engine_loads_yaml(self):
        engine = RulesEngine()
        assert "raw_ration_kit" in engine.item_rules
        assert engine.item_rules["raw_ration_kit"].requires == ["clean_water", "cooking_fuel"]

    def test_compatibility_valid(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        set_clock(clock)
        engine = RulesEngine()

        capabilities = {
            "clean_water": (True, clock.now()),
            "cooking_fuel": (True, clock.now()),
        }

        ok, reasons = engine.validate_compatibility(
            batch_category="raw_ration_kit",
            batch_diet_tags=[],
            shelter_capabilities=capabilities,
            rider_equipment=[],
            now=clock.now(),
        )
        assert ok is True
        assert len(reasons) == 0

    def test_s13_shelter_lacks_water_fails_requirements(self):
        """S13 scenario: shelter lacks water for raw ration kits."""
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        set_clock(clock)
        engine = RulesEngine()

        capabilities = {
            "clean_water": (False, clock.now()),  # Lacks water!
            "cooking_fuel": (True, clock.now()),
        }

        ok, reasons = engine.validate_compatibility(
            batch_category="raw_ration_kit",
            batch_diet_tags=[],
            shelter_capabilities=capabilities,
            rider_equipment=[],
            now=clock.now(),
        )
        assert ok is False
        assert "CAPABILITY_MISSING_CLEAN_WATER" in reasons

    def test_s14_stale_capability_treated_as_unknown(self):
        """S14 scenario: capability data is stale (> 6 hours) treated as unknown/invalid."""
        clock = SimClock(datetime(2024, 1, 1, 15, 0, tzinfo=timezone.utc))
        set_clock(clock)
        engine = RulesEngine()

        stale_time = datetime(2024, 1, 1, 6, 0, tzinfo=timezone.utc)  # 9 hours ago
        capabilities = {
            "clean_water": (True, stale_time),
            "cooking_fuel": (True, clock.now()),
        }

        ok, reasons = engine.validate_compatibility(
            batch_category="raw_ration_kit",
            batch_diet_tags=[],
            shelter_capabilities=capabilities,
            rider_equipment=[],
            now=clock.now(),
        )
        assert ok is False
        assert "CAPABILITY_STALE_CLEAN_WATER" in reasons

    def test_cold_chain_requires_insulated_box(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        set_clock(clock)
        engine = RulesEngine()

        capabilities = {
            "refrigeration": (True, clock.now()),
        }

        # Rider without insulated box
        ok, reasons = engine.validate_compatibility(
            batch_category="cold_chain_medicine",
            batch_diet_tags=[],
            shelter_capabilities=capabilities,
            rider_equipment=[],  # missing insulated_box
            now=clock.now(),
        )
        assert ok is False
        assert "RIDER_EQUIPMENT_MISSING_INSULATED_BOX" in reasons

        # Rider with insulated box
        ok2, reasons2 = engine.validate_compatibility(
            batch_category="cold_chain_medicine",
            batch_diet_tags=[],
            shelter_capabilities=capabilities,
            rider_equipment=["insulated_box"],
            now=clock.now(),
        )
        assert ok2 is True
        assert len(reasons2) == 0
