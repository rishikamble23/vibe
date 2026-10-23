"""
Batch intake logic: validate, compute safe_until / deliver_by,
split into lots, feasibility check, revision handling.

Phase 2 deliverables: 2.1–2.8
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.config_loader import (
    get_serve_buffer, get_handover_time, get_vehicle_capacity, get_config,
)
from app.eta import get_eta_service
from app.geo import haversine_km
from app.safety_gate import calculate_deliver_by as _calc_deliver_by
from app.units import compute_safe_until, to_portions


# ---------------------------------------------------------------------------
# Feasibility response (2.4)
# ---------------------------------------------------------------------------

class FeasibilityStatus(str, Enum):
    ACCEPTED_FULL     = "ACCEPTED_FULL"
    ACCEPTED_PARTIAL  = "ACCEPTED_PARTIAL"
    REJECTED_INFEASIBLE = "REJECTED_INFEASIBLE"


@dataclass
class FeasibilityResult:
    status: FeasibilityStatus
    placeable_portions: int
    reason: Optional[str] = None
    alternative: Optional[str] = None
    earliest_feasible_pickup: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Batch creation params
# ---------------------------------------------------------------------------

@dataclass
class BatchCreateParams:
    donor_id: int
    category: str
    qty: float
    unit: str = "portion"
    cooked_at: Optional[datetime] = None
    expiry_date: Optional[datetime] = None
    fridge_out_at: Optional[datetime] = None
    excursion_budget_min: Optional[int] = None
    shelf_life_min_override: Optional[int] = None
    pickup_window_start: Optional[datetime] = None
    pickup_window_end: Optional[datetime] = None
    ready_at: Optional[datetime] = None    # G22
    cold_chain: bool = False
    diet_tags: List[str] = field(default_factory=list)
    allergens: List[str] = field(default_factory=list)
    idempotency_key: Optional[str] = None


@dataclass
class ComputedBatchMeta:
    qty_portions: int
    safe_until: datetime
    deliver_by: datetime
    shelf_life_min: int
    strategy: str


def compute_batch_meta(params: BatchCreateParams) -> ComputedBatchMeta:
    """
    Pure function: convert units, compute safe_until and deliver_by.
    No DB calls.
    """
    qty_portions = to_portions(params.qty, params.unit, params.category)

    result = compute_safe_until(
        category=params.category,
        cooked_at=params.cooked_at,
        expiry_date=params.expiry_date,
        fridge_out_at=params.fridge_out_at,
        excursion_budget_min=params.excursion_budget_min,
        shelf_life_min_override=params.shelf_life_min_override,
    )

    serve_buffer = get_serve_buffer()
    deliver_by = result.safe_until - timedelta(minutes=serve_buffer)

    return ComputedBatchMeta(
        qty_portions=qty_portions,
        safe_until=result.safe_until,
        deliver_by=deliver_by,
        shelf_life_min=result.shelf_life_min,
        strategy=result.strategy.value,
    )


# ---------------------------------------------------------------------------
# Lot splitting (2.3)
# ---------------------------------------------------------------------------

def split_into_lots(
    batch_id: int,
    qty_portions: int,
    deliver_by: datetime,
    ready_at: Optional[datetime],
    lot_size: Optional[int] = None,
    now: Optional[datetime] = None,
) -> List[Dict[str, Any]]:
    """
    Split batch into lots. Default lot_size = largest vehicle capacity.
    Returns list of dicts ready to insert into the lots table.
    """
    if now is None:
        now = get_clock().now()

    if lot_size is None:
        lot_size = max(
            get_vehicle_capacity("bike"),
            get_vehicle_capacity("car"),
            get_vehicle_capacity("van"),
        )
        lot_size = get_config("vehicle_capacity.van", lot_size)

    lots = []
    remaining = qty_portions
    while remaining > 0:
        this_qty = min(lot_size, remaining)
        lots.append({
            "batch_id":   batch_id,
            "qty":        this_qty,
            "status":     "unassigned",
            "deliver_by": deliver_by,
            "ready_at":   ready_at,
            "created_at": now,
            "updated_at": now,
            "state_version": 0,
        })
        remaining -= this_qty

    return lots


# ---------------------------------------------------------------------------
# Quick feasibility check (2.4) — pure, no DB
# ---------------------------------------------------------------------------

@dataclass
class FeasibilityCandidate:
    rider_id: int
    rider_lat: float
    rider_lon: float
    vehicle_capacity: int
    shelter_id: int
    shelter_lat: float
    shelter_lon: float
    shelter_available: int


def check_feasibility(
    donor_lat: float,
    donor_lon: float,
    deliver_by: datetime,
    ready_at: Optional[datetime],
    qty_portions: int,
    candidates: List[FeasibilityCandidate],
    now: Optional[datetime] = None,
) -> FeasibilityResult:
    """
    Check if ANY (rider, shelter) pair can feasibly deliver this batch.

    Returns ACCEPTED_FULL, ACCEPTED_PARTIAL(n), or REJECTED_INFEASIBLE.
    Uses P90 ETAs.
    """
    if now is None:
        now = get_clock().now()

    eta_svc = get_eta_service()
    serve_buf = get_serve_buffer()
    handover  = get_handover_time()

    # If ready_at is in the future, feasibility starts from ready_at
    effective_now = max(now, ready_at) if ready_at else now

    placeable = 0
    best_alternative: Optional[str] = None
    earliest_feasible: Optional[datetime] = None

    for c in candidates:
        # ETA rider→donor
        r2d = eta_svc.calculate_eta(
            c.rider_lat, c.rider_lon,
            donor_lat, donor_lon,
        )
        # ETA donor→shelter
        d2s = eta_svc.calculate_eta(
            donor_lat, donor_lon,
            c.shelter_lat, c.shelter_lon,
        )

        p90_total = r2d.p90_minutes + handover + d2s.p90_minutes + handover
        arrival   = effective_now + timedelta(minutes=p90_total)

        if arrival <= deliver_by and c.shelter_available > 0:
            can_carry   = min(c.vehicle_capacity, c.shelter_available or 0, qty_portions)
            placeable   = max(placeable, can_carry)
            if earliest_feasible is None or arrival < earliest_feasible:
                earliest_feasible = arrival
        else:
            # Compute earliest feasible pickup time for the alternative hint
            slack_needed = p90_total
            slack_available = int((deliver_by - effective_now).total_seconds() / 60)
            if slack_available < slack_needed:
                feasible_start = deliver_by - timedelta(minutes=slack_needed)
                if best_alternative is None:
                    best_alternative = (
                        f"feasible if pickup starts by "
                        f"{feasible_start.strftime('%H:%M UTC')}"
                    )

    if placeable >= qty_portions:
        return FeasibilityResult(
            status=FeasibilityStatus.ACCEPTED_FULL,
            placeable_portions=placeable,
        )
    elif placeable > 0:
        return FeasibilityResult(
            status=FeasibilityStatus.ACCEPTED_PARTIAL,
            placeable_portions=placeable,
            reason=f"Only {placeable} of {qty_portions} portions can be placed in time",
            alternative=best_alternative,
            earliest_feasible_pickup=earliest_feasible,
        )
    else:
        return FeasibilityResult(
            status=FeasibilityStatus.REJECTED_INFEASIBLE,
            placeable_portions=0,
            reason="No rider can reach the donor and deliver within the safety window",
            alternative=best_alternative,
        )
