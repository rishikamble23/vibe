from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml
from functools import lru_cache


@lru_cache(maxsize=1)
def load_config(config_path: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    
    Args:
        config_path: Path to config file. Defaults to app/config.yaml
    
    Returns:
        Configuration dictionary
    """
    if config_path is None:
        config_path = Path(__file__).parent / "config.yaml"
    elif isinstance(config_path, str):
        config_path = Path(config_path)
    
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def get_config(key: str, default: Any = None, config: Optional[Dict] = None) -> Any:
    """
    Get a nested config value using dot notation.
    
    Args:
        key: Dot-separated path (e.g., "shelf_life.cooked_meal")
        default: Default value if key not found
        config: Config dict to use (loads default if None)
    
    Returns:
        Config value or default
    """
    if config is None:
        config = load_config()
    
    parts = key.split(".")
    value = config
    for part in parts:
        if isinstance(value, dict) and part in value:
            value = value[part]
        else:
            return default
    return value


# Convenience functions for common configs
def get_shelf_life(category: str) -> int:
    """Get shelf life in minutes for a category."""
    return get_config(f"shelf_life.{category}", get_config("shelf_life.default", 75))


def get_serve_buffer() -> int:
    """Get serve buffer in minutes."""
    return get_config("serve_buffer_min", 15)


def get_handover_time() -> int:
    """Get handover time in minutes."""
    return get_config("handover_time_min", 5)


def get_grace_period() -> int:
    """Get grace period in minutes."""
    return get_config("grace_period_min", 10)


def get_redispatch_reserve() -> int:
    """Get redispatch reserve in minutes."""
    return get_config("redispatch_reserve_min", 15)


def get_lease_ttl_bounds() -> tuple[int, int]:
    """Get (min_ttl, max_ttl) in minutes."""
    return (
        get_config("lease_ttl_min_min", 3),
        get_config("lease_ttl_max_min", 60),
    )


def get_planner_timebox() -> int:
    """Get planner timebox in milliseconds."""
    return get_config("planner_timebox_ms", 200)


def get_scoring_weights() -> Dict[str, float]:
    """Get planner scoring weights."""
    return get_config("scoring", {
        "urgency_weight": 1.0,
        "detour_weight": 0.5,
        "late_probability_weight": 2.0,
        "reliability_weight": 1.5,
    })


def get_vehicle_capacity(vehicle_type: str) -> int:
    """Get vehicle capacity in portions."""
    return get_config(f"vehicle_capacity.{vehicle_type}", 50)


def get_safety_gate_config() -> Dict[str, Any]:
    """Get safety gate configuration."""
    return get_config("safety_gate", {"use_p90": True, "min_slack_min": 0})


def get_reaper_config() -> Dict[str, Any]:
    """Get reaper configuration."""
    return get_config("reaper", {"interval_seconds": 5, "batch_size": 50})