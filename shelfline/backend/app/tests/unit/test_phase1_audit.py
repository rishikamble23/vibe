"""
Phase 1 audit v2 tests (1.9, 1.10, 1.12, 1.13)
"""
import pytest
from datetime import datetime, timezone, timedelta

from app.clock import SimClock, FixedClock, set_clock, get_clock
from app.units import to_portions, compute_safe_until, SafeUntilStrategy, get_strategy


class TestClockAudit:
    """Tests for audit v2 additions to clock (1.9, 1.10)."""

    def test_sim_clock_speed_attribute(self):
        clock = SimClock(speed=10.0)
        assert clock.speed == 10.0

    def test_sim_clock_set_speed(self):
        clock = SimClock()
        clock.set_speed(10.0)
        assert clock.speed == 10.0

    def test_advance_to_no_actions(self):
        start = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        clock = SimClock(start)
        target = datetime(2024, 1, 1, 10, 40, tzinfo=timezone.utc)
        clock.advance_to(target)
        assert clock.now() == target

    def test_advance_to_executes_actions_in_order(self):
        start  = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        clock  = SimClock(start)
        events = []

        t1 = datetime(2024, 1, 1, 10, 15, tzinfo=timezone.utc)
        t2 = datetime(2024, 1, 1, 10, 25, tzinfo=timezone.utc)
        t3 = datetime(2024, 1, 1, 10, 35, tzinfo=timezone.utc)

        # Pass them out of order — should still execute in time order
        clock.advance_to(
            datetime(2024, 1, 1, 10, 40, tzinfo=timezone.utc),
            scheduled_actions=[
                (t3, lambda: events.append(("t3", clock.now()))),
                (t1, lambda: events.append(("t1", clock.now()))),
                (t2, lambda: events.append(("t2", clock.now()))),
            ],
        )
        assert [e[0] for e in events] == ["t1", "t2", "t3"]
        assert events[0][1] == t1
        assert events[1][1] == t2
        assert events[2][1] == t3

    def test_advance_to_skips_past_actions(self):
        """Actions before now() are not re-fired."""
        start = datetime(2024, 1, 1, 10, 30, tzinfo=timezone.utc)
        clock = SimClock(start)
        events = []

        past   = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)   # already past
        future = datetime(2024, 1, 1, 10, 45, tzinfo=timezone.utc)

        clock.advance_to(
            datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc),
            scheduled_actions=[
                (past,   lambda: events.append("past")),
                (future, lambda: events.append("future")),
            ],
        )
        assert events == ["future"]

    def test_advance_to_40min_same_as_40_steps(self):
        """G11: advance_to(+40min) == 40 one-minute steps."""
        hits_batch  = []
        hits_steps  = []

        deadlines = [10, 20, 35]  # minutes

        # Batch advance
        start = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        clock = SimClock(start)
        actions = [
            (start + timedelta(minutes=m), lambda m=m: hits_batch.append(m))
            for m in deadlines
        ]
        clock.advance_to(start + timedelta(minutes=40), scheduled_actions=actions)

        # Step advance
        clock2 = SimClock(start)
        for i in range(1, 41):
            clock2.advance(1)
            t = clock2.now()
            for m in deadlines:
                if t == start + timedelta(minutes=m):
                    hits_steps.append(m)

        assert sorted(hits_batch) == sorted(hits_steps)

    def test_fixed_clock_raises_on_advance(self):
        clock = FixedClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
        with pytest.raises(NotImplementedError):
            clock.advance(5)

    def test_fixed_clock_raises_on_jump(self):
        clock = FixedClock(datetime(2024, 1, 1, tzinfo=timezone.utc))
        with pytest.raises(NotImplementedError):
            clock.jump_to(datetime(2024, 1, 2, tzinfo=timezone.utc))


class TestUnitConversion:
    """Tests for unit conversion table (1.12)."""

    def test_portions_passthrough(self):
        assert to_portions(50, "portion", "cooked_meal") == 50

    def test_kg_to_portions_cooked_meal(self):
        # 2 kg cooked meal @ 5 portions/kg = 10
        assert to_portions(2, "kg", "cooked_meal") == 10

    def test_tray_to_portions_cooked_meal(self):
        assert to_portions(1, "tray", "cooked_meal") == 12

    def test_box_to_portions_generic(self):
        assert to_portions(1, "box", "dry_ration") == 20

    def test_litre_water(self):
        assert to_portions(5, "litre", "water") == 5

    def test_unknown_unit_fallback(self):
        # unknown unit defaults to 1.0 factor
        assert to_portions(7, "unknown_unit", "cooked_meal") == 7

    def test_kg_medicine(self):
        # medicine kg = 1 portion/kg (not by weight)
        assert to_portions(1, "kg", "medicine") == 1

    def test_rounding(self):
        # 1.3 kg cooked_meal @ 5 = 6.5 → int conversion truncates/rounds
        assert to_portions(1.3, "kg", "cooked_meal") in (6, 7)


class TestSafeUntilStrategies:
    """Tests for safe_until strategies (1.13)."""

    def test_cooked_food_strategy(self):
        cooked_at = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
        result = compute_safe_until("cooked_meal", cooked_at=cooked_at)
        assert result.strategy == SafeUntilStrategy.COOKED_FOOD
        # shelf_life = 75 min → safe_until = 8:00 + 75 min = 9:15
        assert result.safe_until == datetime(2024, 1, 1, 9, 15, tzinfo=timezone.utc)

    def test_dated_item_uses_expiry_date(self):
        expiry = datetime(2024, 3, 1, 0, 0, tzinfo=timezone.utc)
        result = compute_safe_until("medicine", expiry_date=expiry)
        assert result.strategy == SafeUntilStrategy.DATED_ITEM
        assert result.safe_until == expiry

    def test_dated_item_fallback_to_cooked(self):
        """dated_item without expiry_date falls back to cooked_food calc."""
        cooked_at = datetime(2024, 1, 1, 10, 0, tzinfo=timezone.utc)
        result = compute_safe_until("medicine", cooked_at=cooked_at)
        assert result.strategy == SafeUntilStrategy.DATED_ITEM
        # should produce a safe_until based on cooked_at + shelf_life
        assert result.safe_until > cooked_at

    def test_cold_chain_uses_excursion_budget(self):
        fridge_out = datetime(2024, 1, 1, 9, 0, tzinfo=timezone.utc)
        result = compute_safe_until(
            "cold_chain_medicine",
            fridge_out_at=fridge_out,
            excursion_budget_min=120,
        )
        assert result.strategy == SafeUntilStrategy.COLD_CHAIN
        assert result.safe_until == datetime(2024, 1, 1, 11, 0, tzinfo=timezone.utc)

    def test_shelf_life_override(self):
        cooked_at = datetime(2024, 1, 1, 8, 0, tzinfo=timezone.utc)
        result = compute_safe_until("cooked_meal", cooked_at=cooked_at, shelf_life_min_override=30)
        assert result.shelf_life_min == 30
        assert result.safe_until == datetime(2024, 1, 1, 8, 30, tzinfo=timezone.utc)

    def test_get_strategy_default(self):
        assert get_strategy("unknown_category") == SafeUntilStrategy.COOKED_FOOD

    def test_naive_datetime_treated_as_utc(self):
        cooked_at = datetime(2024, 1, 1, 8, 0)  # naive
        result = compute_safe_until("cooked_meal", cooked_at=cooked_at)
        assert result.safe_until.tzinfo == timezone.utc
