from math import radians, sin, cos, sqrt, atan2
from typing import Tuple, List, Optional


EARTH_RADIUS_KM = 6371.0
EARTH_RADIUS_M = 6371000.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points in kilometers.
    
    Args:
        lat1, lon1: Latitude and longitude of first point (degrees)
        lat2, lon2: Latitude and longitude of second point (degrees)
    
    Returns:
        Distance in kilometers
    """
    # Convert to radians
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    
    return EARTH_RADIUS_KM * c


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate distance in meters."""
    return haversine_km(lat1, lon1, lat2, lon2) * 1000


def validate_coordinates(lat: float, lon: float) -> bool:
    """Validate that coordinates are within valid ranges."""
    return -90 <= lat <= 90 and -180 <= lon <= 180


def bounding_box(
    lat: float, 
    lon: float, 
    radius_km: float
) -> Tuple[float, float, float, float]:
    """
    Calculate bounding box around a point.
    
    Returns:
        (min_lat, max_lat, min_lon, max_lon)
    """
    # 1 degree latitude ≈ 111 km
    # 1 degree longitude ≈ 111 km * cos(latitude)
    lat_delta = radius_km / 111.0
    lon_delta = radius_km / (111.0 * cos(radians(lat)))
    
    return (
        lat - lat_delta,
        lat + lat_delta,
        lon - lon_delta,
        lon + lon_delta,
    )


def filter_by_bounding_box(
    points: List[Tuple[float, float, object]],  # (lat, lon, data)
    center_lat: float,
    center_lon: float,
    radius_km: float
) -> List[Tuple[float, float, object]]:
    """
    Filter points within a bounding box (fast pre-filter before haversine).
    
    Args:
        points: List of (lat, lon, data) tuples
        center_lat, center_lon: Center point
        radius_km: Radius in kilometers
    
    Returns:
        Filtered list of points within bounding box
    """
    min_lat, max_lat, min_lon, max_lon = bounding_box(center_lat, center_lon, radius_km)
    
    return [
        (lat, lon, data) 
        for lat, lon, data in points
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon
    ]


def distance_within_radius(
    lat1: float, lon1: float, 
    lat2: float, lon2: float, 
    radius_km: float
) -> bool:
    """Fast check if two points are within radius (uses bounding box first)."""
    # Quick bounding box check
    min_lat, max_lat, min_lon, max_lon = bounding_box(lat1, lon1, radius_km)
    
    if not (min_lat <= lat2 <= max_lat and min_lon <= lon2 <= max_lon):
        return False
    
    # Precise haversine check
    return haversine_km(lat1, lon1, lat2, lon2) <= radius_km