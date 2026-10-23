from datetime import datetime, timezone
from abc import ABC, abstractmethod
from typing import Optional


class Clock(ABC):
    """Abstract clock interface. All code must use this instead of datetime.now()."""
    
    @abstractmethod
    def now(self) -> datetime:
        """Return current UTC time."""
        pass
    
    @abstractmethod
    def advance(self, minutes: int) -> None:
        """Advance clock by N minutes (simulation only)."""
        pass
    
    @abstractmethod
    def jump_to(self, target: datetime) -> None:
        """Jump to a specific time (simulation only)."""
        pass
    
    @abstractmethod
    def set_speed(self, multiplier: float) -> None:
        """Set speed multiplier (simulation only)."""
        pass


class RealClock(Clock):
    """Real-time clock using system time."""
    
    def now(self) -> datetime:
        return datetime.now(timezone.utc)
    
    def advance(self, minutes: int) -> None:
        raise NotImplementedError("Cannot advance real clock")
    
    def jump_to(self, target: datetime) -> None:
        raise NotImplementedError("Cannot jump real clock")
    
    def set_speed(self, multiplier: float) -> None:
        raise NotImplementedError("Cannot set speed on real clock")


class SimClock(Clock):
    """Simulation clock for testing and demos."""
    
    def __init__(self, start: Optional[datetime] = None):
        self._time = start or datetime.now(timezone.utc)
        self._speed = 1.0
    
    def now(self) -> datetime:
        return self._time
    
    def advance(self, minutes: int) -> None:
        from datetime import timedelta
        self._time += timedelta(minutes=minutes)
    
    def jump_to(self, target: datetime) -> None:
        if target.tzinfo is None:
            target = target.replace(tzinfo=timezone.utc)
        self._time = target
    
    def set_speed(self, multiplier: float) -> None:
        self._speed = multiplier
    
    @property
    def speed(self) -> float:
        return self._speed


# Global clock instance
_clock: Optional[Clock] = None


def get_clock() -> Clock:
    """Get the global clock instance, defaulting to RealClock."""
    global _clock
    if _clock is None:
        _clock = RealClock()
    return _clock


def set_clock(clock: Clock) -> None:
    """Set the global clock instance (for testing)."""
    global _clock
    _clock = clock