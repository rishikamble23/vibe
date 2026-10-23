"""
Phase 2 & 3 unit tests (pure logic, no DB).

Covers:
  - compute_batch_meta (unit conv + safe_until + deliver_by)
  - split_into_lots
  - check_feasibility (ACCEPTED_FULL, PARTIAL, REJECTED_INFEASIBLE)
  - Lease state machine transitions
  - TTL calculation
  - OTP generation + verification
  - Progress / stall detection
  - Lease expiry extension
"""
import pytest
from datetime import datetime, timezone, timedelta
from typing import List

from app.clock import SimClock, set_clock
from app.batches import (
    BatchCreateParams, compute_batch_meta, split_into_lots,
    check_feasibility, FeasibilityCandidate, FeasibilityStatus,
)
from app.leases import (
    LeaseStatus, assert_transition, is_terminal, is_soft_lease, is_hard_commit,
    calculate_lease_ttl_for_offer, generate_otp, verify_otp,
    check_progress, make_lease_expiry, extend_lease_expiry,
)
from app.eta import ETAService, SpeedProfile, set_eta_service


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def make_clock(hour: int = 9) -> SimClock:
    return SimClock(datetime(2024, 1, 1, hour, 0, tzinfo=timezone.utc))


# ---------------------------------------------------------------------------
# Phase 2: Batch meta
# ---------------------------------------------------------------------------
class TestComputeBatchMeta:

    def test_basic_cooked_meal_portions(self):
        params = BatchCreateParams(
            donor_id=1,
            category="cooked_meal",
            qty=2.0,
            unit="kg",
            cooked_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        )
        meta = compute_batch_meta(params)
        assert meta.qty_portions == 10   # 2 kg × 5 portions/kg
        assert meta.shelf_life_min == 75

    def test_deliver_by_is_safe_until_minus_serve_buffer(self):
        params = BatchCreateParams(
            donor_id=1,
            category="cooked_meal",
            qty=50,
            unit="portion",
            cooked_at=datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc),
        )
        meta = compute_batch_meta(params)
        # safe_until = 8:00 + 75 = 9:15; deliver_by = 9:15 - 15 = 9:00
        assert meta.safe_until == datetime(2024, 1, 1, 9, 15, tzinfo=timezone.utc)
        assert meta.deliver_by == datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)

    def test_medicine_uses_dated_item_strategy(self):
        expiry = datetime(2024, 6, 1, tzinfo=timezone.utc)
        params = BatchCreateParams(
            donor_id=1,
            category="medicine",
            qty=100,
            unit="portion",
            expiry_date=expiry,
        )
        meta = compute_batch_meta(params)
        assert meta.strategy == "dated_item"
        assert meta.safe_until == expiry

    def test_cold_chain_strategy(self):
        fridge_out = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        params = BatchCreateParams(
            donor_id=1,
            category="cold_chain_medicine",
            qty=10,
            unit="box",
            fridge_out_at=fridge_out,
            excursion_budget_min=120,
        )
        meta = compute_batch_meta(params)
        assert meta.strategy == "cold_chain"
        assert meta.safe_until == datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Phase 2: Lot splitting
# ---------------------------------------------------------------------------
class TestSplitIntoLots:

    def test_exact_division(self):
        now = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        deliver_by = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        lots = split_into_lots(1, 100, deliver_by, None, lot_size=50, now=now)
        assert len(lots) == 2
        assert all(l["qty"] == 50 for l in lots)

    def test_remainder_lot(self):
        now = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        deliver_by = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        lots = split_into_lots(1, 180, deliver_by, None, lot_size=40, now=now)
        assert len(lots) == 5
        assert lots[-1]["qty"] == 20
        assert sum(l["qty"] for l in lots) == 180

    def test_single_lot(self):
        now = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        deliver_by = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        lots = split_into_lots(1, 30, deliver_by, None, lot_size=50, now=now)
        assert len(lots) == 1
        assert lots[0]["qty"] == 30

    def test_ready_at_propagated(self):
        now = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        deliver_by = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        ready = datetime(2024, 1, 1, 9, 30, tzinfo=timezone.utc)
        lots = split_into_lots(1, 50, deliver_by, ready, lot_size=50, now=now)
        assert lots[0]["ready_at"] == ready

    def test_total_qty_preserved(self):
        now = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        deliver_by = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        for total in [1, 7, 50, 100, 180, 299]:
            lots = split_into_lots(1, total, deliver_by, None, lot_size=40, now=now)
            assert sum(l["qty"] for l in lots) == total


# ---------------------------------------------------------------------------
# Phase 2: Feasibility check
# ---------------------------------------------------------------------------
class TestFeasibility:

    def _nearby_candidate(self) -> FeasibilityCandidate:
        return FeasibilityCandidate(
            rider_id=1,
            rider_lat=12.97, rider_lon=77.59,   # near donor
            vehicle_capacity=50,
            shelter_id=1,
            shelter_lat=13.0, shelter_lon=77.6,
            shelter_available=100,
        )

    def test_accepted_full(self):
        clock = make_clock(9)
        set_clock(clock)
        now = clock.now()
        deliver_by = now + timedelta(hours=2)

        result = check_feasibility(
            donor_lat=12.97, donor_lon=77.59,
            deliver_by=deliver_by,
            ready_at=None,
            qty_portions=30,
            candidates=[self._nearby_candidate()],
            now=now,
        )
        assert result.status == FeasibilityStatus.ACCEPTED_FULL
        assert result.placeable_portions >= 30

    def test_rejected_infeasible_no_candidates(self):
        clock = make_clock(9)
        set_clock(clock)
        now = clock.now()
        deliver_by = now + timedelta(minutes=5)  # way too tight

        result = check_feasibility(
            donor_lat=12.97, donor_lon=77.59,
            deliver_by=deliver_by,
            ready_at=None,
            qty_portions=50,
            candidates=[self._nearby_candidate()],
            now=now,
        )
        assert result.status == FeasibilityStatus.REJECTED_INFEASIBLE

    def test_rejected_when_shelter_full(self):
        clock = make_clock(9)
        set_clock(clock)
        now = clock.now()
        deliver_by = now + timedelta(hours=2)

        candidate = self._nearby_candidate()
        candidate.shelter_available = 0  # full

        result = check_feasibility(
            donor_lat=12.97, donor_lon=77.59,
            deliver_by=deliver_by,
            ready_at=None,
            qty_portions=30,
            candidates=[candidate],
            now=now,
        )
        assert result.status == FeasibilityStatus.REJECTED_INFEASIBLE

    def test_accepted_partial(self):
        clock = make_clock(9)
        set_clock(clock)
        now = clock.now()
        deliver_by = now + timedelta(hours=2)

        candidate = self._nearby_candidate()
        candidate.vehicle_capacity = 20  # can only carry 20

        result = check_feasibility(
            donor_lat=12.97, donor_lon=77.59,
            deliver_by=deliver_by,
            ready_at=None,
            qty_portions=50,  # need 50 but only 20 can be placed
            candidates=[candidate],
            now=now,
        )
        assert result.status == FeasibilityStatus.ACCEPTED_PARTIAL
        assert result.placeable_portions == 20


# ---------------------------------------------------------------------------
# Phase 3: Lease state machine
# ---------------------------------------------------------------------------
class TestLeaseStateMachine:

    def test_allowed_offered_to_accepted(self):
        assert_transition(LeaseStatus.OFFERED, LeaseStatus.ACCEPTED)  # no exception

    def test_allowed_accepted_to_arrived_donor(self):
        assert_transition(LeaseStatus.ACCEPTED, LeaseStatus.ARRIVED_DONOR)

    def test_allowed_arrived_donor_to_picked_up(self):
        assert_transition(LeaseStatus.ARRIVED_DONOR, LeaseStatus.PICKED_UP)

    def test_allowed_picked_up_to_near_shelter(self):
        assert_transition(LeaseStatus.PICKED_UP, LeaseStatus.NEAR_SHELTER)

    def test_allowed_near_shelter_to_delivered(self):
        assert_transition(LeaseStatus.NEAR_SHELTER, LeaseStatus.DELIVERED)

    def test_illegal_offered_to_delivered(self):
        with pytest.raises(ValueError):
            assert_transition(LeaseStatus.OFFERED, LeaseStatus.DELIVERED)

    def test_illegal_delivered_to_accepted(self):
        with pytest.raises(ValueError):
            assert_transition(LeaseStatus.DELIVERED, LeaseStatus.ACCEPTED)

    def test_illegal_expired_to_active(self):
        with pytest.raises(ValueError):
            assert_transition(LeaseStatus.EXPIRED, LeaseStatus.ACCEPTED)

    def test_safety_veto_from_any_active(self):
        for active in [
            LeaseStatus.OFFERED, LeaseStatus.ACCEPTED,
            LeaseStatus.ARRIVED_DONOR, LeaseStatus.PICKED_UP,
            LeaseStatus.NEAR_SHELTER,
        ]:
            assert_transition(active, LeaseStatus.ABORTED_UNSAFE)  # no exception

    def test_terminal_states(self):
        assert is_terminal(LeaseStatus.DELIVERED)
        assert is_terminal(LeaseStatus.EXPIRED)
        assert is_terminal(LeaseStatus.RELEASED)
        assert is_terminal(LeaseStatus.ABORTED_UNSAFE)
        assert not is_terminal(LeaseStatus.OFFERED)
        assert not is_terminal(LeaseStatus.ACCEPTED)

    def test_soft_vs_hard(self):
        assert is_soft_lease(LeaseStatus.OFFERED)
        assert is_soft_lease(LeaseStatus.ACCEPTED)
        assert is_soft_lease(LeaseStatus.ARRIVED_DONOR)
        assert not is_soft_lease(LeaseStatus.PICKED_UP)
        assert is_hard_commit(LeaseStatus.PICKED_UP)
        assert is_hard_commit(LeaseStatus.NEAR_SHELTER)


# ---------------------------------------------------------------------------
# Phase 3: TTL calculation
# ---------------------------------------------------------------------------
class TestLeaseTTL:

    def test_basic_ttl(self):
        now          = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        latest_pickup = datetime(2024, 1, 1, 11, 25, tzinfo=timezone.utc)
        ttl = calculate_lease_ttl_for_offer(now, 30, latest_pickup)
        # grace=10, redispatch=15: raw=40, upper=(85-15)=70, max_ttl=60 → clamp(40,3,70,60)=40
        assert ttl == 40

    def test_ttl_clamped_to_max(self):
        now          = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        latest_pickup = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        ttl = calculate_lease_ttl_for_offer(now, 55, latest_pickup)
        assert ttl == 60  # max_ttl

    def test_ttl_clamped_to_min(self):
        now          = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        latest_pickup = datetime(2024, 1, 1, 10, 10, tzinfo=timezone.utc)
        ttl = calculate_lease_ttl_for_offer(now, 5, latest_pickup)
        assert ttl == 3  # min_ttl


# ---------------------------------------------------------------------------
# Phase 3: OTP (3.15)
# ---------------------------------------------------------------------------
class TestOTP:

    def test_otp_is_6_digits(self):
        otp = generate_otp()
        assert len(otp) == 6
        assert otp.isdigit()

    def test_otp_correct(self):
        otp = generate_otp()
        ok, reason = verify_otp(otp, otp, 0)
        assert ok is True
        assert reason == "OK"

    def test_otp_wrong(self):
        ok, reason = verify_otp("000000", "111111", 0)
        assert ok is False
        assert reason == "OTP_WRONG"

    def test_otp_locked_after_5_attempts(self):
        ok, reason = verify_otp("111111", "000000", 5)
        assert ok is False
        assert reason == "OTP_LOCKED"

    def test_otp_uniqueness(self):
        otps = {generate_otp() for _ in range(100)}
        # Not all the same
        assert len(otps) > 1


# ---------------------------------------------------------------------------
# Phase 3: Progress / stall detection (3.4)
# ---------------------------------------------------------------------------
class TestProgressDetection:

    def test_first_ping_no_stall(self):
        new_dist, stall_count, stalled = check_progress(
            new_lat=12.97, new_lon=77.59,
            last_lat=None, last_lon=None,
            prev_dist_to_donor=None,
            donor_lat=13.0, donor_lon=77.6,
            stall_count=0,
        )
        assert stalled is False
        assert stall_count == 0
        assert new_dist > 0

    def test_approaching_resets_stall_count(self):
        donor_lat, donor_lon = 13.0, 77.6
        # Start far
        _, stall_count, _ = check_progress(
            12.0, 77.0, None, None, None, donor_lat, donor_lon, 2
        )
        # First ping sets baseline
        assert stall_count == 0

        # Now move closer
        from app.geo import haversine_km
        far_dist  = haversine_km(12.5, 77.3, donor_lat, donor_lon)
        near_dist = haversine_km(12.9, 77.5, donor_lat, donor_lon)
        assert near_dist < far_dist

        new_dist, new_stall, stalled = check_progress(
            12.9, 77.5,
            12.5, 77.3,
            far_dist,
            donor_lat, donor_lon,
            2,  # high stall count before
        )
        assert new_stall == 0
        assert stalled is False

    def test_not_approaching_increments_stall(self):
        donor_lat, donor_lon = 13.0, 77.6
        from app.geo import haversine_km
        prev_dist = haversine_km(12.5, 77.3, donor_lat, donor_lon)

        _, new_stall, _ = check_progress(
            12.4, 77.2,   # moved AWAY from donor
            12.5, 77.3,
            prev_dist,
            donor_lat, donor_lon,
            0,
        )
        assert new_stall == 1

    def test_stalled_after_threshold(self):
        donor_lat, donor_lon = 13.0, 77.6
        from app.geo import haversine_km
        prev_dist = haversine_km(12.0, 77.0, donor_lat, donor_lon)

        _, _, stalled = check_progress(
            12.0, 77.0,  # stayed same
            12.0, 77.0,
            prev_dist,
            donor_lat, donor_lon,
            2,   # already at threshold - 1
        )
        assert stalled is True


# ---------------------------------------------------------------------------
# Phase 3: Lease TTL extension (3.5)
# ---------------------------------------------------------------------------
class TestLeaseExtension:

    def test_extension_within_bounds(self):
        now          = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        latest_pickup = datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
        current      = datetime(2024, 1, 1, 10, 20, tzinfo=timezone.utc)

        extended = extend_lease_expiry(current, 5, latest_pickup, now)
        # proposed = now + 5 + 10(grace) = 10:15
        # hard_limit = latest_pickup - 15(redispatch) = 10:15
        # min(10:15, 10:15) = 10:15
        assert extended <= latest_pickup - timedelta(minutes=15)

    def test_extension_capped_at_hard_limit(self):
        now          = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        latest_pickup = datetime(2024, 1, 1, 10, 20, tzinfo=timezone.utc)
        current      = datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc)

        extended = extend_lease_expiry(current, 60, latest_pickup, now)
        # proposed = 10:00 + 60 + 10 = 11:10  but hard_limit = 10:20 - 15 = 10:05
        hard_limit = latest_pickup - timedelta(minutes=15)
        assert extended == hard_limit


# ---------------------------------------------------------------------------
# S21: Idempotency (pure create_event_payload)
# ---------------------------------------------------------------------------
class TestIdempotency:

    def test_create_event_payload_deterministic(self):
        from app.events import create_event_payload
        p1 = create_event_payload(batch_id=1, qty=50)
        p2 = create_event_payload(batch_id=1, qty=50)
        assert p1 == p2

    def test_create_event_payload_kwargs(self):
        from app.events import create_event_payload
        p = create_event_payload(x=1, y="hello", z=[1, 2])
        assert p == {"x": 1, "y": "hello", "z": [1, 2]}
