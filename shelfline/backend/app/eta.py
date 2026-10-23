from dataclasses import dataclass
from datetime import datetime, time
from typing import Dict, Optional
from functools import lru_cache
import random
import math

from app.geo import haversine_km, haversine_m
from app.clock import Clock, get_clock


@dataclass
class ETADistribution:
    """ETA distribution with P50 and P90 estimates."""
    p50_minutes: int
    p90_minutes: int
    mean_minutes: float
    std_minutes: float
    
    def to_dict(self) -> dict:
        return {
            "p50_minutes": self.p50_minutes,
            "p90_minutes": self.p90_minutes,
            "mean_minutes": self.mean_minutes,
            "std_minutes": self.std_minutes,
        }


@dataclass
class SpeedProfile:
    """Speed profile for different times of day and vehicle types."""
    # Base speed in km/h for different times
    morning_rush: float = 25.0    # 7-10 AM
    midday: float = 35.0          # 10 AM - 4 PM
    evening_rush: float = 20.0    # 4-7 PM
    night: float = 40.0           # 7 PM - 7 AM
    
    # Vehicle type multipliers
    bike_multiplier: float = 0.8
    car_multiplier: float = 1.0
    van_multiplier: float = 0.9
    
    def get_speed(self, dt: datetime, vehicle_type: str = "car") -> float:
        """Get speed for a given time and vehicle type."""
        hour = dt.hour
        
        if 7 <= hour < 10:
            base = self.morning_rush
        elif 10 <= hour < 16:
            base = self.midday
        elif 16 <= hour < 19:
            base = self.evening_rush
        else:
            base = self.night
        
        multipliers = {
            "bike": self.bike_multiplier,
            "car": self.car_multiplier,
            "van": self.van_multiplier,
        }
        
        return base * multipliers.get(vehicle_type, 1.0)


class ETAService:
    """
    ETA service with P50/P90 estimates.
    
    v1: Haversine × 1.35 circuity factor ÷ speed profile × traffic multiplier + noise
    v2: OSRM/OpenRouteService integration (when reachable)
    v3: Correct using observed leg times from simulation
    """
    
    CIRCUITY_FACTOR = 1.35
    DEFAULT_TRAFFIC_MULTIPLIER = 1.0
    NOISE_STD_FACTOR = 0.15  # 15% noise for distribution
    
    def __init__(
        self,
        speed_profile: Optional[SpeedProfile] = None,
        clock: Optional[Clock] = None,
    ):
        self.speed_profile = speed_profile or SpeedProfile()
        self.clock = clock or get_clock()
        self._traffic_multipliers: Dict[str, float] = {}  # zone -> multiplier
        self._cache: Dict[str, ETADistribution] = {}
        self._cache_ttl_seconds = 300  # 5 minutes
        self._cache_timestamps: Dict[str, float] = {}
    
    def set_traffic_multiplier(self, zone: str, multiplier: float) -> None:
        """Set traffic multiplier for a zone (for Chaos Console injection)."""
        self._traffic_multipliers[zone] = multiplier
        # Invalidate cache for this zone
        keys_to_remove = [k for k in self._cache if zone in k]
        for k in keys_to_remove:
            del self._cache[k]
            del self._cache_timestamps[k]
    
    def get_traffic_multiplier(self, zone: str) -> float:
        """Get traffic multiplier for a zone."""
        return self._traffic_multipliers.get(zone, self.DEFAULT_TRAFFIC_MULTIPLIER)
    
    def _make_cache_key(
        self,
        from_lat: float, from_lon: float,
        to_lat: float, to_lon: float,
        vehicle_type: str,
        zone: str,
    ) -> str:
        return f"{from_lat:.4f},{from_lon:.4f},{to_lat:.4f},{to_lon:.4f},{vehicle_type},{zone}"
    
    def _is_cache_valid(self, key: str) -> bool:
        import time
        if key not in self._cache_timestamps:
            return False
        return (time.time() - self._cache_timestamps[key]) < self._cache_ttl_seconds
    
    def calculate_eta(
        self,
        from_lat: float, from_lon: float,
        to_lat: float, to_lon: float,
        vehicle_type: str = "car",
        zone: str = "default",
        now: Optional[datetime] = None,
    ) -> ETADistribution:
        """
        Calculate ETA distribution between two points.
        
        Args:
            from_lat, from_lon: Origin coordinates
            to_lat, to_lon: Destination coordinates
            vehicle_type: "bike", "car", or "van"
            zone: Traffic zone for multipliers
            now: Time for speed profile (defaults to clock.now())
        
        Returns:
            ETADistribution with P50 and P90
        """
        cache_key = self._make_cache_key(
            from_lat, from_lon, to_lat, to_lon, vehicle_type, zone
        )
        
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]
        
        # Calculate base distance
        distance_km = haversine_km(from_lat, from_lon, to_lat, to_lon)
        
        # Apply circuity factor (real roads aren't straight lines)
        effective_distance_km = distance_km * self.CIRCUITY_FACTOR
        
        # Get speed for current time and vehicle
        now = now or self.clock.now()
        speed_kmh = self.speed_profile.get_speed(now, vehicle_type)
        
        # Apply traffic multiplier
        traffic_mult = self.get_traffic_multiplier(zone)
        effective_speed = speed_kmh / traffic_mult
        
        # Base time in minutes
        base_time_min = (effective_distance_km / effective_speed) * 60
        
        # Add noise for distribution
        # Log-normal distribution for positive skew (realistic travel times)
        noise_std = base_time_min * self.NOISE_STD_FACTOR
        
        # Generate distribution parameters
        # For log-normal: mean = exp(mu + sigma^2/2)
        # We want P50 ≈ base_time_min, so mu = ln(base_time_min)
        # sigma controls spread
        mu = math.log(max(base_time_min, 0.1))
        sigma = self.NOISE_STD_FACTOR
        
        # P50 = exp(mu)
        p50 = math.exp(mu)
        # P90 = exp(mu + sigma * 1.28)  (1.28 is 90th percentile of normal)
        p90 = math.exp(mu + sigma * 1.28)
        
        # Mean and std of log-normal
        mean = math.exp(mu + sigma**2 / 2)
        std = math.sqrt((math.exp(sigma**2) - 1) * math.exp(2*mu + sigma**2))
        
        result = ETADistribution(
            p50_minutes=int(round(p50)),
            p90_minutes=int(round(p90)),
            mean_minutes=mean,
            std_minutes=std,
        )
        
        # Cache result
        self._cache[cache_key] = result
        import time
        self._cache_timestamps[cache_key] = time.time()
        
        return result
    
    def calculate_eta_minutes(
        self,
        from_lat: float, from_lon: float,
        to_lat: float, to_lon: float,
        vehicle_type: str = "car",
        zone: str = "default",
        percentile: int = 50,
        now: Optional[datetime] = None,
    ) -> int:
        """Quick ETA calculation returning a single percentile."""
        dist = self.calculate_eta(from_lat, from_lon, to_lat, to_lon, vehicle_type, zone, now)
        if percentile <= 50:
            return dist.p50_minutes
        elif percentile <= 90:
            return dist.p90_minutes
        else:
            # Approximate higher percentiles
            return dist.p90_minutes + int((percentile - 90) * dist.std_minutes / 40)
    
    def clear_cache(self) -> None:
        """Clear the ETA cache."""
        self._cache.clear()
        self._cache_timestamps.clear()


# Global ETA service instance
_eta_service: Optional[ETAService] = None


def get_eta_service() -> ETAService:
    """Get the global ETA service instance."""
    global _eta_service
    if _eta_service is None:
        _eta_service = ETAService()
    return _eta_service


def set_eta_service(service: ETAService) -> None:
    """Set the global ETA service instance (for testing)."""
    global _eta_service
    _eta_service = service