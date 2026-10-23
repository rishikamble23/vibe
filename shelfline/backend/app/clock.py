"""
Clock abstraction: RealClock, SimClock.

All application code MUST call clock.now() — never datetime.now() or datetime.utcnow().
A lint/grep test enforces this.

Audit v2 additions (1.9, 1.10, 1.11):
  - Clock.speed multiplier for Judge Mode (1 sim-min ≈ 6 real-seconds at 10x)
  - advance_to(t): steps through scheduled actions in timestamp order (never skips a deadline)
  - Seeded randomness support
"""
from __future__ import annotations

import secrets
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Callable, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Global clock registry
# ---------------------------------------------------------------------------
_clock: Optional["Clock"] = None


def get_clock() -> "Clock":
    global _clock
    if _clock is None:
        _clock = RealClock()
    return _clock


def set_clock(clock: "Clock") -> None:
    global _clock
    _clock = clock


# ---------------------------------------------------------------------------
# Abstract interface
# ---------------------------------------------------------------------------
class Clock(ABC):
    """All code must use clock.now() instead of datetime.now()."""

    @abstractmethod
    def now(self) -> datetime:
        """Return the current UTC datetime."""
        ...

    def advance(self, minutes: float) -> None:
        """Advance the clock by N minutes (sim only)."""
        raise NotImplementedError("Only SimClock supports advance()")

    def jump_to(self, dt: datetime) -> None:
        """Jump the clock to a specific time (sim only)."""
        raise NotImplementedError("Only SimClock supports jump_to()")

    def set_speed(self, speed: float) -> None:
        """Set the time-scale multiplier (sim only)."""
        raise NotImplementedError("Only SimClock supports set_speed()")

    def advance_to(
        self,
        target: datetime,
        scheduled_actions: Optional[List[Tuple[datetime, Callable[[], None]]]] = None,
    ) -> None:
        """
        Step from now() to target, executing scheduled_actions in timestamp order.
        Never jumps over a deadline (G11 fix).
        """
        raise NotImplementedError("Only SimClock supports advance_to()")


# ---------------------------------------------------------------------------
# Real clock
# ---------------------------------------------------------------------------
class RealClock(Clock):
    """Production clock — returns actual wall time in UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Simulated clock
# ---------------------------------------------------------------------------
class SimClock(Clock):
    """
    Deterministic clock for tests and Judge Mode.

    - advance(n): move forward N minutes instantly
    - jump_to(t): teleport to t
    - set_speed(s): real-time speed multiplier (10 = 10× faster)
    - advance_to(t, actions): step through actions in order, emit events with sim timestamps
    """

    def __init__(
        self,
        start: Optional[datetime] = None,
        speed: float = 1.0,
    ) -> None:
        if start is None:
            start = datetime.now(timezone.utc)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        self._now = start
        self.speed = speed

    # ------------------------------------------------------------------
    def now(self) -> datetime:
        return self._now

    def advance(self, minutes: float) -> None:
        self._now += timedelta(minutes=minutes)

    def jump_to(self, dt: datetime) -> None:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        self._now = dt

    def set_speed(self, speed: float) -> None:
        """
        Set time-scale multiplier.
        Judge Mode default: speed=10 (1 sim-minute ≈ 6 real seconds).
        Every UI countdown derives from server time and speed.
        """
        self.speed = speed

    def advance_to(
        self,
        target: datetime,
        scheduled_actions: Optional[List[Tuple[datetime, Callable[[], None]]]] = None,
    ) -> None:
        """
        Step from now() to target executing each scheduled action in timestamp order.
        If no actions are provided, jumps directly.

        This ensures advancing 40 minutes produces the same result as
        40 one-minute steps (G11 — clock-jump test requirement).
        """
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)

        if scheduled_actions:
            # Sort by scheduled time, only those between now and target
            pending = sorted(
                [(t, fn) for t, fn in scheduled_actions if self._now < t <= target],
                key=lambda x: x[0],
            )
            for ts, fn in pending:
                self._now = ts
                fn()

        self._now = target


# ---------------------------------------------------------------------------
# FixedClock (useful for property tests where time must never move)
# ---------------------------------------------------------------------------
class FixedClock(Clock):
    """Clock frozen at a specific point. Advance/jump raise errors."""

    def __init__(self, fixed: datetime) -> None:
        if fixed.tzinfo is None:
            fixed = fixed.replace(tzinfo=timezone.utc)
        self._fixed = fixed

    def now(self) -> datetime:
        return self._fixed
