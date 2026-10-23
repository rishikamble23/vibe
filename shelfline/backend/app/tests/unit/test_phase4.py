"""
Unit tests for Phase 4 Planner (candidate generation, scoring, greedy EDF, scenario S02).
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.clock import SimClock, set_clock
from app.eta import ETAService
from app.safety_gate import SafetyGate
from app.planner import GreedyEDFPlanner, score_candidate, CandidateTriple


class MockLot:
    def __init__(self, id, batch_id, qty, deliver_by, status="unassigned"):
        self.id = id
        self.batch_id = batch_id
        self.qty = qty
        self.deliver_by = deliver_by
        self.status = status


class MockRider:
    def __init__(self, id, lat, lon, capacity=50, reliability=0.9, status="available"):
        self.id = id
        self.lat = lat
        self.lon = lon
        self.vehicle_capacity = capacity
        self.reliability_score = reliability
        self.status = status
        self.insulated_box = True


class MockShelter:
    def __init__(self, id, lat, lon, need=100, received=0, committed=0, intake_open=True):
        self.id = id
        self.lat = lat
        self.lon = lon
        self.need = need
        self.received = received
        self.committed = committed
        self.intake_open = intake_open
        self.accepts_diet_tags = []


class MockBatch:
    def __init__(self, id, lat, lon, category="cooked_meal", shelf_life_min=75):
        self.id = id
        self.lat = lat
        self.lon = lon
        self.category = category
        self.shelf_life_min = shelf_life_min
        self.cooked_at = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        self.safe_until = datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc)
        self.cold_chain = False
        self.diet_tags = []
        self.allergens = []
        self.pickup_window_end = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)


class TestPlanner:

    def test_scoring_prefers_lower_detour_and_higher_reliability(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        rider1 = MockRider(1, 12.0, 77.0, reliability=0.95)
        rider2 = MockRider(2, 12.0, 77.0, reliability=0.5)
        lot = MockLot(1, 1, 40, datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc))
        shelter = MockShelter(1, 12.1, 77.1, need=50)
        batch = MockBatch(1, 12.05, 77.05)

        t1 = CandidateTriple(rider1, lot, shelter, batch, 5, 10, 50)
        t2 = CandidateTriple(rider2, lot, shelter, batch, 5, 10, 50)

        s1 = score_candidate(t1)
        s2 = score_candidate(t2)

        assert s1 > s2  # higher reliability scores higher

    def test_greedy_edf_planner_basic_assignment(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        set_clock(clock)
        eta_service = ETAService(clock=clock)
        safety_gate = SafetyGate(eta_service=eta_service, clock=clock)
        planner = GreedyEDFPlanner(safety_gate=safety_gate, eta_service=eta_service)

        batch = MockBatch(1, 12.97, 77.59)
        lot = MockLot(1, 1, 30, datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc))
        rider = MockRider(1, 12.97, 77.59, capacity=50)
        shelter = MockShelter(1, 13.0, 77.6, need=100)

        result = planner.plan(
            version=1,
            lots=[lot],
            riders=[rider],
            shelters=[shelter],
            batches_map={1: batch},
            now=clock.now(),
        )

        assert len(result.assignments) == 1
        assert result.assignments[0].lot_id == 1
        assert result.assignments[0].rider_id == 1
        assert result.assignments[0].shelter_id == 1
        assert result.assignments[0].qty == 30
        assert result.runtime_ms < 200

    def test_s02_split_plan(self):
        """S02 scenario: 180 meals split across multiple riders and lots."""
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        set_clock(clock)
        eta_service = ETAService(clock=clock)
        safety_gate = SafetyGate(eta_service=eta_service, clock=clock)
        planner = GreedyEDFPlanner(safety_gate=safety_gate, eta_service=eta_service)

        batch = MockBatch(1, 12.97, 77.59)
        deliver_by = datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)

        # 5 lots of 36 portions (total 180)
        lots = [MockLot(i, 1, 36, deliver_by) for i in range(1, 6)]

        # 5 riders capacity 40
        riders = [MockRider(i, 12.97, 77.59, capacity=40) for i in range(1, 6)]

        # 2 shelters need 90 each (total 180 capacity)
        shelters = [
            MockShelter(1, 13.0, 77.6, need=90),
            MockShelter(2, 13.0, 77.6, need=90),
        ]

        result = planner.plan(
            version=1,
            lots=lots,
            riders=riders,
            shelters=shelters,
            batches_map={1: batch},
            now=clock.now(),
        )

        # All 180 portions placed successfully
        assert len(result.unplaced_lots) == 0
        total_assigned = sum(a.qty for a in result.assignments)
        assert total_assigned == 180
