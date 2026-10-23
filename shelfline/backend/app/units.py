"""
Unit conversion table and safe_until strategies (audit v2, 1.12 + 1.13).

Converts kg / trays / boxes → portions at intake.
Implements per-category safe_until strategies:
  cooked_food  : cooked_at + shelf_life_min
  dated_item   : expiry_date field (best-before / expiry)
  cold_chain   : excursion_budget_min minutes allowed out of the fridge
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional

from app.config_loader import get_config, get_shelf_life


# ---------------------------------------------------------------------------
# Unit conversion (1.12)
# ---------------------------------------------------------------------------
# Maps (unit, category) → portions.
# Units: "kg", "tray", "box", "portion", "litre", "packet"
# For categories that don't map cleanly, we fall back to the default for the unit.

_UNIT_TO_PORTIONS: Dict[str, float] = {
    # cooking / ration
    "kg": 4.0,       # ~250 g per portion
    "tray": 10.0,    # standard food service tray
    "box": 20.0,     # standard ration box
    "packet": 5.0,   # mid-size food packet
    "portion": 1.0,  # already in portions
    "litre": 4.0,    # ~250 ml per portion for liquids
    "unit": 1.0,     # generic unit
}

# Category-specific overrides (higher specificity wins)
_CATEGORY_UNIT_OVERRIDES: Dict[str, Dict[str, float]] = {
    "cooked_meal": {
        "kg": 5.0,    # 200 g per meal
        "tray": 12.0,
    },
    "medicine": {
        "box": 30.0,   # strip packs
        "packet": 10.0,
        "kg": 1.0,     # medicines aren't counted by weight normally
    },
    "water": {
        "litre": 1.0,  # 1L = 1 portion
        "kg": 1.0,
    },
    "infant_formula": {
        "box": 60.0,
        "kg": 60.0,
    },
}


def to_portions(qty: float, unit: str, category: str) -> int:
    """
    Convert quantity in the given unit to integer portions.

    >>> to_portions(2, "kg", "cooked_meal")
    10
    >>> to_portions(1, "tray", "cooked_meal")
    12
    >>> to_portions(50, "portion", "medicine")
    50
    """
    unit = unit.lower().strip()
    category = category.lower().strip()

    factor = (
        _CATEGORY_UNIT_OVERRIDES.get(category, {}).get(unit)
        or _UNIT_TO_PORTIONS.get(unit, 1.0)
    )
    return max(1, int(round(qty * factor)))


# ---------------------------------------------------------------------------
# Safe-until strategies (1.13)
# ---------------------------------------------------------------------------

class SafeUntilStrategy(str, Enum):
    COOKED_FOOD = "cooked_food"   # cooked_at + shelf_life_min from config
    DATED_ITEM  = "dated_item"    # expiry_date / best-before from donor input
    COLD_CHAIN  = "cold_chain"    # total excursion budget in minutes out of fridge


# Per-category declared strategy (lives alongside config.yaml values)
_CATEGORY_STRATEGY: Dict[str, SafeUntilStrategy] = {
    "cooked_meal":        SafeUntilStrategy.COOKED_FOOD,
    "cooked_food":        SafeUntilStrategy.COOKED_FOOD,
    "dry_ration":         SafeUntilStrategy.DATED_ITEM,
    "raw_ration_kit":     SafeUntilStrategy.DATED_ITEM,
    "water":              SafeUntilStrategy.DATED_ITEM,
    "infant_formula":     SafeUntilStrategy.DATED_ITEM,
    "medicine":           SafeUntilStrategy.DATED_ITEM,
    "medical_kit":        SafeUntilStrategy.DATED_ITEM,
    "cold_chain_medicine":SafeUntilStrategy.COLD_CHAIN,
    "cold_chain_food":    SafeUntilStrategy.COLD_CHAIN,
    "default":            SafeUntilStrategy.COOKED_FOOD,
}


def get_strategy(category: str) -> SafeUntilStrategy:
    return _CATEGORY_STRATEGY.get(category.lower(), SafeUntilStrategy.COOKED_FOOD)


@dataclass
class SafeUntilResult:
    safe_until: datetime
    strategy: SafeUntilStrategy
    shelf_life_min: int


def compute_safe_until(
    category: str,
    cooked_at: Optional[datetime] = None,
    expiry_date: Optional[datetime] = None,
    fridge_out_at: Optional[datetime] = None,
    excursion_budget_min: Optional[int] = None,
    shelf_life_min_override: Optional[int] = None,
) -> SafeUntilResult:
    """
    Compute safe_until for a batch using the per-category strategy.

    cooked_food  → cooked_at + shelf_life (config per category)
    dated_item   → expiry_date (from donor input; falls back to cooked_food if absent)
    cold_chain   → fridge_out_at + excursion_budget_min (config default if not given)

    All datetimes returned in UTC.
    """
    strategy = get_strategy(category)
    shelf_life_min = shelf_life_min_override or get_shelf_life(category)

    def _ensure_utc(dt: datetime) -> datetime:
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt

    now_fallback = datetime.now(timezone.utc)

    if strategy == SafeUntilStrategy.COOKED_FOOD:
        base = _ensure_utc(cooked_at) if cooked_at else now_fallback
        safe_until = base + timedelta(minutes=shelf_life_min)

    elif strategy == SafeUntilStrategy.DATED_ITEM:
        if expiry_date:
            safe_until = _ensure_utc(expiry_date)
        else:
            # Fall back: treat like cooked_food
            base = _ensure_utc(cooked_at) if cooked_at else now_fallback
            safe_until = base + timedelta(minutes=shelf_life_min)

    else:  # COLD_CHAIN
        budget = excursion_budget_min or get_config("shelf_life.cold_chain_excursion_budget_min", 120)
        base = _ensure_utc(fridge_out_at) if fridge_out_at else now_fallback
        safe_until = base + timedelta(minutes=budget)

    return SafeUntilResult(
        safe_until=safe_until,
        strategy=strategy,
        shelf_life_min=shelf_life_min,
    )
