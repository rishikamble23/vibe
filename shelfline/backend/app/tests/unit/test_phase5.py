"""
Unit tests for Phase 5 Rerouting and Fallbacks (S05, S06, S07, fallbacks).
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.clock import SimClock, set_clock
from app.eta import ETAService
from app.safety_gate import SafetyGate
from app.reroute import RerouteService, FallbackTier


class MockLease:
    def __init__(self, id, shelter_id, actual_qty=40):
        self.id = id
        self.shelter_id = shelter_id
        self.actual_qty = actual_qty


class MockLot:
    def __init__(self, id, qty=40):
        self.id = id
        self.qty = qty


class MockBatch:
    def __init__(self, category="cooked_meal", shelf_life_min=75):
        self.category = category
        self.shelf_life_min = shelf_life_min
        self.cooked_at = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
        self.safe_until = datetime(2024, 1, 1, 9, 15, tzinfo=timezone.utc)
        self.cold_chain = False
        self.diet_tags = []
        self.allergens = []
        self.pickup_window_end = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


class MockShelter:
    def __init__(self, id, lat, lon, need=50, received=0, committed=0, intake_open=True, name=None):
        self.id = id
        self.lat = lat
        self.lon = lon
        self.need = need
        self.received = received
        self.committed = committed
        self.intake_open = intake_open
        self.name = name or f"Shelter {id}"
        self.accepts_diet_tags = []


class TestRerouteService:

    def test_compute_fallbacks_finds_tier1(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        set_clock(clock)
        eta_service = ETAService(clock=clock)
        safety_gate = SafetyGate(eta_service=eta_service, clock=clock)
        reroute_svc = RerouteService(safety_gate=safety_gate, eta_service=eta_service)

        batch = MockBatch()
        lot = MockLot(1, qty=30)

        # Shelter 1 (original, exclude), Shelter 2 (nearby, capacity 50), Shelter 3 (further)
        shelters = [
            MockShelter(1, 13.0, 77.6, need=50),
            MockShelter(2, 13.01, 77.61, need=50, name="Shelter B"),
            MockShelter(3, 13.1, 77.7, need=50, name="Shelter C"),
        ]

        fallbacks = reroute_svc.compute_fallbacks(
            rider_lat=13.0, rider_lon=77.6,
            lot=lot, batch=batch,
            shelters=shelters,
            exclude_shelter_id=1,
            now=clock.now(),
        )

        assert len(fallbacks) >= 2
        assert fallbacks[0].tier == FallbackTier.TIER_1_SHELTER
        assert fallbacks[0].destination_id == 2  # closer one

    def test_s06_shelter_closes_mid_transit_reroute(self):
        """S06 scenario: shelter closes mid-transit, reroutes to next best shelter."""
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        set_clock(clock)
        eta_service = ETAService(clock=clock)
        safety_gate = SafetyGate(eta_service=eta_service, clock=clock)
        reroute_svc = RerouteService(safety_gate=safety_gate, eta_service=eta_service)

        batch = MockBatch()
        lot = MockLot(1, qty=40)
        lease = MockLease(1, shelter_id=1, actual_qty=40)

        shelters = [
            MockShelter(1, 13.0, 77.6, need=50, intake_open=False),  # closed!
            MockShelter(2, 13.01, 77.61, need=50, intake_open=True, name="Shelter B"),
        ]

        decision = reroute_svc.decide_reroute(
            lease=lease, lot=lot, batch=batch,
            current_lat=13.0, current_lon=77.6,
            shelters=shelters,
            now=clock.now(),
        )

        assert decision.new_shelter_id == 2
        assert decision.tier == FallbackTier.TIER_1_SHELTER
        assert decision.partial_drop_qty is None

    def test_s07_shelter_reduces_need_partial_drop(self):
        """S07 scenario: shelter reduces need from 50 to 20 with 40 in transit -> partial drop."""
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        set_clock(clock)
        eta_service = ETAService(clock=clock)
        safety_gate = SafetyGate(eta_service=eta_service, clock=clock)
        reroute_svc = RerouteService(safety_gate=safety_gate, eta_service=eta_service)

        batch = MockBatch()
        lot = MockLot(1, qty=40)
        lease = MockLease(1, shelter_id=1, actual_qty=40)

        # Shelter 1 reduces capacity to 15 available; Shelter 2 has 50 available
        shelters = [
            MockShelter(1, 13.0, 77.6, need=15, received=0, committed=0, intake_open=True),
            MockShelter(2, 13.02, 77.62, need=50, intake_open=True, name="Shelter B"),
        ]

        decision = reroute_svc.decide_reroute(
            lease=lease, lot=lot, batch=batch,
            current_lat=13.0, current_lon=77.6,
            shelters=shelters,
            now=clock.now(),
        )

        # Should drop 15 at Shelter 1 (or Shelter B depending on distance)
        assert decision.new_shelter_id is not None
        assert decision.partial_drop_qty is not None
        assert decision.remainder_qty is not None
        assert decision.partial_drop_qty + decision.remainder_qty == 40
