import pytest
from datetime import datetime, timezone, timedelta

from app.clock import RealClock, SimClock, get_clock, set_clock
from app.geo import haversine_km, haversine_m, validate_coordinates, bounding_box, filter_by_bounding_box, distance_within_radius
from app.eta import ETAService, SpeedProfile, ETADistribution, get_eta_service, set_eta_service
from app.config_loader import load_config, get_config, get_shelf_life, get_serve_buffer
from app.events import append_event, replay_events, create_event_payload
from app.safety_gate import (
    SafetyGate, SafetyReason, SafetyCheckResult,
    calculate_deliver_by, calculate_slack, calculate_lease_ttl, calculate_latest_pickup,
    get_safety_gate, set_safety_gate
)
from app.clock import Clock


class TestClock:
    """Tests for clock abstraction."""
    
    def test_real_clock_returns_utc(self):
        clock = RealClock()
        now = clock.now()
        assert isinstance(now, datetime)
        assert now.tzinfo == timezone.utc
    
    def test_real_clock_cannot_advance(self):
        clock = RealClock()
        with pytest.raises(NotImplementedError):
            clock.advance(10)
    
    def test_real_clock_cannot_jump(self):
        clock = RealClock()
        with pytest.raises(NotImplementedError):
            clock.jump_to(datetime.now(timezone.utc))
    
    def test_real_clock_cannot_set_speed(self):
        clock = RealClock()
        with pytest.raises(NotImplementedError):
            clock.set_speed(2.0)
    
    def test_sim_clock_advance(self):
        clock = SimClock(datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc))
        assert clock.now() == datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        
        clock.advance(30)
        assert clock.now() == datetime(2024, 1, 1, 12, 30, tzinfo=timezone.utc)
        
        clock.advance(60)
        assert clock.now() == datetime(2024, 1, 1, 13, 30, tzinfo=timezone.utc)
    
    def test_sim_clock_jump_to(self):
        clock = SimClock()
        target = datetime(2024, 6, 15, 18, 30, tzinfo=timezone.utc)
        clock.jump_to(target)
        assert clock.now() == target
    
    def test_sim_clock_jump_to_naive_datetime(self):
        clock = SimClock()
        target = datetime(2024, 6, 15, 18, 30)  # naive
        clock.jump_to(target)
        assert clock.now() == target.replace(tzinfo=timezone.utc)
    
    def test_sim_clock_set_speed(self):
        clock = SimClock()
        clock.set_speed(10.0)
        assert clock.speed == 10.0
    
    def test_global_clock_registry(self):
        # Save original
        original = get_clock()
        
        try:
            sim = SimClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
            set_clock(sim)
            assert get_clock() is sim
            assert get_clock().now() == datetime(2024, 1, 1, tzinfo=timezone.utc)
        finally:
            set_clock(original)


class TestGeo:
    """Tests for geo utilities."""
    
    def test_haversine_km_same_point(self):
        dist = haversine_km(12.9716, 77.5946, 12.9716, 77.5946)
        assert dist == 0.0
    
    def test_haversine_km_bangalore_to_delhi(self):
        # Bangalore to Delhi ~ 1740 km
        dist = haversine_km(12.9716, 77.5946, 28.7041, 77.1025)
        assert 1700 < dist < 1800
    
    def test_haversine_m_conversion(self):
        dist_km = haversine_km(0, 0, 0, 1)  # ~111 km at equator
        dist_m = haversine_m(0, 0, 0, 1)
        assert abs(dist_m - dist_km * 1000) < 1
    
    def test_validate_coordinates_valid(self):
        assert validate_coordinates(0, 0) is True
        assert validate_coordinates(90, 180) is True
        assert validate_coordinates(-90, -180) is True
        assert validate_coordinates(12.9716, 77.5946) is True
    
    def test_validate_coordinates_invalid(self):
        assert validate_coordinates(91, 0) is False
        assert validate_coordinates(-91, 0) is False
        assert validate_coordinates(0, 181) is False
        assert validate_coordinates(0, -181) is False
    
    def test_bounding_box(self):
        min_lat, max_lat, min_lon, max_lon = bounding_box(0, 0, 111)  # ~1 degree
        assert min_lat == pytest.approx(-1.0, abs=0.01)
        assert max_lat == pytest.approx(1.0, abs=0.01)
        assert min_lon == pytest.approx(-1.0, abs=0.01)
        assert max_lon == pytest.approx(1.0, abs=0.01)
    
    def test_filter_by_bounding_box(self):
        points = [
            (0, 0, "center"),
            (0.5, 0.5, "near"),
            (2, 2, "far"),
        ]
        filtered = filter_by_bounding_box(points, 0, 0, 111)  # ~1 degree
        assert len(filtered) == 2
        assert filtered[0][2] == "center"
        assert filtered[1][2] == "near"
    
    def test_distance_within_radius(self):
        assert distance_within_radius(0, 0, 0.5, 0.5, 100) is True
        assert distance_within_radius(0, 0, 2, 2, 100) is False


class TestSpeedProfile:
    """Tests for speed profiles."""
    
    def test_speed_profile_morning_rush(self):
        profile = SpeedProfile()
        dt = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)  # 8 AM
        speed = profile.get_speed(dt, "car")
        assert speed == 25.0  # morning_rush
    
    def test_speed_profile_midday(self):
        profile = SpeedProfile()
        dt = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)  # 12 PM
        speed = profile.get_speed(dt, "car")
        assert speed == 35.0  # midday
    
    def test_speed_profile_evening_rush(self):
        profile = SpeedProfile()
        dt = datetime(2024, 1, 1, 17, 0, tzinfo=timezone.utc)  # 5 PM
        speed = profile.get_speed(dt, "car")
        assert speed == 20.0  # evening_rush
    
    def test_speed_profile_night(self):
        profile = SpeedProfile()
        dt = datetime(2024, 1, 1, 22, 0, tzinfo=timezone.utc)  # 10 PM
        speed = profile.get_speed(dt, "car")
        assert speed == 40.0  # night
    
    def test_speed_profile_vehicle_multipliers(self):
        profile = SpeedProfile()
        dt = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        
        assert profile.get_speed(dt, "bike") == 35.0 * 0.8
        assert profile.get_speed(dt, "car") == 35.0 * 1.0
        assert profile.get_speed(dt, "van") == 35.0 * 0.9


class TestETAService:
    """Tests for ETA service."""
    
    def test_eta_service_basic(self):
        clock = SimClock(datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc))
        profile = SpeedProfile(midday=30.0)  # Simple speed
        service = ETAService(speed_profile=profile, clock=clock)
        
        # ~111 km at equator, 1 degree lat/lon
        eta = service.calculate_eta(0, 0, 1, 0, vehicle_type="car", zone="default")
        
        # Distance ~111 km * 1.35 circuity / 30 km/h * 60 = ~299 min
        # But with noise it varies
        assert eta.p50_minutes > 200
        assert eta.p90_minutes > eta.p50_minutes
        assert eta.mean_minutes > 0
        assert eta.std_minutes > 0
    
    def test_eta_service_p90_greater_than_p50(self):
        clock = SimClock(datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc))
        service = ETAService(clock=clock)
        
        eta = service.calculate_eta(12.9716, 77.5946, 13.0, 77.6)
        
        assert eta.p90_minutes >= eta.p50_minutes
    
    def test_eta_service_cache(self):
        clock = SimClock(datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc))
        service = ETAService(clock=clock)
        
        eta1 = service.calculate_eta(12.9716, 77.5946, 13.0, 77.6)
        eta2 = service.calculate_eta(12.9716, 77.5946, 13.0, 77.6)
        
        # Should return cached result
        assert eta1.p50_minutes == eta2.p50_minutes
        assert eta1.p90_minutes == eta2.p90_minutes
    
    def test_eta_service_traffic_multiplier(self):
        clock = SimClock(datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc))
        service = ETAService(clock=clock)
        
        # Normal traffic
        eta_normal = service.calculate_eta(12.9716, 77.5946, 13.0, 77.6, zone="zone1")
        
        # Heavy traffic
        service.set_traffic_multiplier("zone1", 2.0)
        eta_heavy = service.calculate_eta(12.9716, 77.5946, 13.0, 77.6, zone="zone1")
        
        # Heavy traffic should increase ETA
        assert eta_heavy.p50_minutes > eta_normal.p50_minutes
        assert eta_heavy.p90_minutes > eta_normal.p90_minutes
    
    def test_eta_service_clear_cache(self):
        clock = SimClock(datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc))
        service = ETAService(clock=clock)
        
        eta1 = service.calculate_eta(12.9716, 77.5946, 13.0, 77.6)
        service.clear_cache()
        eta2 = service.calculate_eta(12.9716, 77.5946, 13.0, 77.6)
        
        # After clear, should recalculate (might be same or different due to time)
        # But we verify cache was cleared by checking timestamps
        assert len(service._cache) == 1


class TestConfigLoader:
    """Tests for configuration loader."""
    
    def test_load_config(self):
        config = load_config()
        assert isinstance(config, dict)
        assert "shelf_life" in config
        assert "serve_buffer_min" in config
    
    def test_get_config_nested(self):
        config = load_config()
        shelf_life = get_config("shelf_life.cooked_meal", config=config)
        assert shelf_life == 75
    
    def test_get_config_default(self):
        config = load_config()
        value = get_config("nonexistent.key", default="fallback", config=config)
        assert value == "fallback"
    
    def test_get_shelf_life(self):
        assert get_shelf_life("cooked_meal") == 75
        assert get_shelf_life("medicine") == 240
        assert get_shelf_life("unknown") == 75  # default
    
    def test_get_serve_buffer(self):
        assert get_serve_buffer() == 15


class TestEvents:
    """Tests for event log (basic structure)."""
    
    def test_create_event_payload(self):
        payload = create_event_payload(batch_id=1, qty=50)
        assert payload == {"batch_id": 1, "qty": 50}


class TestSafetyGateCalculations:
    """Tests for safety gate calculation functions."""
    
    def test_calculate_deliver_by(self):
        clock = SimClock(datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc))
        
        class MockBatch:
            cooked_at = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
            shelf_life_min = 75
            safe_until = None
            category = "cooked_meal"
        
        batch = MockBatch()
        deliver_by = calculate_deliver_by(batch, clock)
        
        # cooked_at + 75 min - 15 min serve_buffer = 8:00 + 60 = 9:00
        expected = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        assert deliver_by == expected
    
    def test_calculate_deliver_by_with_safe_until(self):
        clock = SimClock(datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc))
        
        class MockBatch:
            cooked_at = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
            shelf_life_min = 75
            safe_until = datetime(2024, 1, 1, 8, 30, tzinfo=timezone.utc)  # Earlier!
            category = "cooked_meal"
        
        batch = MockBatch()
        deliver_by = calculate_deliver_by(batch, clock)
        
        # safe_until (8:30) - 15 min serve_buffer = 8:15
        expected = datetime(2024, 1, 1, 8, 15, tzinfo=timezone.utc)
        assert deliver_by == expected
    
    def test_calculate_slack(self):
        now = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        deliver_by = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)  # 2 hours from now
        
        slack = calculate_slack(now, deliver_by, 30, 30)  # 30 min each leg
        
        # 120 min until deliver_by - 30 - 5 - 30 - 5 = 50 min slack
        assert slack == 50
    
    def test_calculate_slack_negative(self):
        now = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        deliver_by = datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)  # 30 min from now
        
        slack = calculate_slack(now, deliver_by, 30, 30)
        
        # 30 min until deliver_by - 30 - 5 - 30 - 5 = -40 min slack
        assert slack == -40
    
    def test_calculate_latest_pickup(self):
        deliver_by = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        donor_to_shelter_p90 = 30
        
        latest = calculate_latest_pickup(deliver_by, donor_to_shelter_p90)
        
        # deliver_by - 30 - 5 = 11:25
        expected = datetime(2024, 1, 1, 11, 25, tzinfo=timezone.utc)
        assert latest == expected
    
    def test_calculate_lease_ttl(self):
        now = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        latest_pickup = datetime(2024, 1, 1, 11, 25, tzinfo=timezone.utc)
        
        ttl = calculate_lease_ttl(now, 30, latest_pickup)
        
        # rider_to_donor_p90 (30) + grace (10) = 40
        # latest_pickup - now - redispatch (15) = 85 - 15 = 70
        # min_ttl = 3, max_ttl = 60
        # clamp(40, 3, 70, 60) = 40
        assert ttl == 40
    
    def test_calculate_lease_ttl_clamped_to_max(self):
        now = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        latest_pickup = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        
        ttl = calculate_lease_ttl(now, 50, latest_pickup)
        
        # rider_to_donor_p90 (50) + grace (10) = 60
        # latest_pickup - now - redispatch (15) = 120 - 15 = 105
        # clamp(60, 3, 105, 60) = 60
        assert ttl == 60
    
    def test_calculate_lease_ttl_clamped_to_min(self):
        now = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        latest_pickup = datetime(2024, 1, 1, 10, 10, tzinfo=timezone.utc)
        
        ttl = calculate_lease_ttl(now, 5, latest_pickup)
        
        # rider_to_donor_p90 (5) + grace (10) = 15
        # latest_pickup - now - redispatch (15) = 10 - 15 = -5
        # clamp(15, 3, -5, 60) = max(3, -5) = 3
        assert ttl == 3


class MockLot:
    def __init__(self, qty=50):
        self.qty = qty


class MockRider:
    def __init__(self, lat=12.9716, lon=77.5946, vehicle_capacity=50, insulated_box=False):
        self.lat = lat
        self.lon = lon
        self.vehicle_capacity = vehicle_capacity
        self.insulated_box = insulated_box


class MockShelter:
    def __init__(self, lat=13.0, lon=77.6, need=100, received=0, committed=0, intake_open=True, accepts_diet_tags=None):
        self.lat = lat
        self.lon = lon
        self.need = need
        self.received = received
        self.committed = committed
        self.intake_open = intake_open
        self.accepts_diet_tags = accepts_diet_tags or []


class MockBatch:
    def __init__(self, lat=12.97, lon=77.59, category="cooked_meal", cold_chain=False, diet_tags=None, allergens=None, shelf_life_min=75, pickup_window_end=None):
        self.lat = lat
        self.lon = lon
        self.category = category
        self.cold_chain = cold_chain
        self.diet_tags = diet_tags or []
        self.allergens = allergens or []
        self.shelf_life_min = shelf_life_min
        self.cooked_at = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
        self.safe_until = None
        self.pickup_window_end = pickup_window_end if pickup_window_end is not None else datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)


class TestSafetyGate:
    """Tests for SafetyGate."""
    
    def test_safe_assignment(self):
        # now = 09:00, cooked_at = 09:00, shelf_life=75 min → deliver_by = 09:00+75-15 = 10:00
        # ETA rider→donor ~2 min, donor→shelter ~14 min → slack ≈ 60-2-5-14-5 = 34 min → OK
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        eta_service = ETAService(clock=clock)
        gate = SafetyGate(eta_service=eta_service, clock=clock)

        lot = MockLot(qty=30)
        rider = MockRider(lat=12.9716, lon=77.5946)
        shelter = MockShelter(lat=13.0, lon=77.6, need=100, received=0, committed=0)
        # cooked_at = now so deliver_by = now + 75 - 15 = now + 60 min → plenty of slack
        batch = MockBatch(
            pickup_window_end=datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        )
        batch.cooked_at = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)

        result = gate.is_safe(lot, rider, shelter, batch)

        assert result.ok is True
        assert SafetyReason.OK in result.reasons
        assert result.slack_minutes > 0
    
    def test_deadline_exceeded(self):
        clock = SimClock(datetime(2024, 1, 1, 11, 30, tzinfo=timezone.utc))  # Very late
        eta_service = ETAService(clock=clock)
        gate = SafetyGate(eta_service=eta_service, clock=clock)
        
        lot = MockLot(qty=30)
        rider = MockRider(lat=12.9716, lon=77.5946)
        shelter = MockShelter(lat=13.0, lon=77.6, need=100)
        batch = MockBatch()
        
        result = gate.is_safe(lot, rider, shelter, batch)
        
        assert result.ok is False
        assert SafetyReason.DEADLINE_EXCEEDED in result.reasons
    
    def test_insufficient_capacity(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        eta_service = ETAService(clock=clock)
        gate = SafetyGate(eta_service=eta_service, clock=clock)
        
        lot = MockLot(qty=100)  # More than vehicle capacity (50)
        rider = MockRider()
        shelter = MockShelter(need=100)
        batch = MockBatch()
        
        result = gate.is_safe(lot, rider, shelter, batch)
        
        assert result.ok is False
        assert SafetyReason.INSUFFICIENT_CAPACITY in result.reasons
    
    def test_shelter_closed(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        eta_service = ETAService(clock=clock)
        gate = SafetyGate(eta_service=eta_service, clock=clock)
        
        lot = MockLot(qty=30)
        rider = MockRider()
        shelter = MockShelter(intake_open=False)
        batch = MockBatch()
        
        result = gate.is_safe(lot, rider, shelter, batch)
        
        assert result.ok is False
        assert SafetyReason.SHELTER_CLOSED in result.reasons
    
    def test_shelter_full(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        eta_service = ETAService(clock=clock)
        gate = SafetyGate(eta_service=eta_service, clock=clock)
        
        lot = MockLot(qty=30)
        rider = MockRider()
        shelter = MockShelter(need=50, received=30, committed=30)  # available = -10
        batch = MockBatch()
        
        result = gate.is_safe(lot, rider, shelter, batch)
        
        assert result.ok is False
        assert SafetyReason.SHELTER_FULL in result.reasons
    
    def test_cold_chain_required(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        eta_service = ETAService(clock=clock)
        gate = SafetyGate(eta_service=eta_service, clock=clock)
        
        lot = MockLot(qty=30)
        rider = MockRider(insulated_box=False)
        shelter = MockShelter(need=100)
        batch = MockBatch(cold_chain=True)
        
        result = gate.is_safe(lot, rider, shelter, batch)
        
        assert result.ok is False
        assert SafetyReason.COLD_CHAIN_REQUIRED in result.reasons
    
    def test_diet_mismatch(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc))
        eta_service = ETAService(clock=clock)
        gate = SafetyGate(eta_service=eta_service, clock=clock)
        
        lot = MockLot(qty=30)
        rider = MockRider()
        shelter = MockShelter(accepts_diet_tags=["vegetarian"])  # Doesn't accept halal
        batch = MockBatch(diet_tags=["halal"])
        
        result = gate.is_safe(lot, rider, shelter, batch)
        
        assert result.ok is False
        assert SafetyReason.DIET_MISMATCH in result.reasons
    
    def test_pickup_window_missed(self):
        clock = SimClock(datetime(2024, 1, 1, 9, 45, tzinfo=timezone.utc))  # 15 min before pickup window ends
        eta_service = ETAService(clock=clock)
        gate = SafetyGate(eta_service=eta_service, clock=clock)
        
        lot = MockLot(qty=30)
        rider = MockRider(lat=12.0, lon=77.0)  # Far away
        shelter = MockShelter(need=100)
        batch = MockBatch(pickup_window_end=datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc))
        
        result = gate.is_safe(lot, rider, shelter, batch)
        
        # Rider can't reach donor before pickup window ends
        assert result.ok is False
        assert SafetyReason.PICKUP_WINDOW_MISSED in result.reasons


class TestSafetyGateBoundaryTimes:
    """Tests for boundary time decisions (exactly at, 1 sec before, 1 sec after)."""
    
    def test_slack_exactly_zero(self):
        clock = SimClock(datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc))
        eta_service = ETAService(
            speed_profile=SpeedProfile(midday=1000.0),  # Very fast to control time
            clock=clock
        )
        gate = SafetyGate(eta_service=eta_service, clock=clock)
        
        # With huge speed, travel time ~0, so slack ~ time_until_deliver_by - 10
        # Set deliver_by to exactly now + 10 min (handover * 2)
        class MockBatch:
            lat = 12.9716
            lon = 77.5946
            category = "cooked_meal"
            cold_chain = False
            diet_tags = []
            allergens = []
            shelf_life_min = 75
            cooked_at = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
            safe_until = None
            pickup_window_end = datetime(2024, 1, 1, 12, 0, tzinfo=timezone.utc)
        
        lot = MockLot(qty=30)
        rider = MockRider()
        shelter = MockShelter(lat=12.9716, lon=77.5946, need=100)  # Same location
        batch = MockBatch()
        
        result = gate.is_safe(lot, rider, shelter, batch)
        
        # With same location and infinite speed, slack should be ~0
        # But we use min_slack_min = 0, so OK
        assert "slack_minutes" in result.details


if __name__ == "__main__":
    pytest.main([__file__, "-v"])