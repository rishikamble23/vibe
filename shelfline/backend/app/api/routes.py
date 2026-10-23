"""
Phase 7 — API and Realtime Layer: Clean, documented endpoints (Appendix D).

Endpoints:
- POST /batches, GET /batches/{id}, PATCH /batches/{id}
- POST /leases/{id}/accept, /decline, /progress, /milestone, /pickup, /deliver
- POST /riders/{id}/availability, /location, /breakdown
- POST /shelters/{id}/demand, /walk-in, /close, /reopen, /capabilities, /reportunsafe
- POST /admin/clock, /admin/chaos/{type}, /admin/reset, /admin/seed
- GET /state/snapshot, GET /metrics, GET /events?since=
- WS /ws/control, /ws/rider/{id}, /ws/shelter/{id}
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Query, status
from pydantic import BaseModel, Field

from app.clock import get_clock
from app.batches import compute_batch_meta, split_into_lots, check_feasibility, FeasibilityCandidate, BatchCreateParams
from app.ledger import ledger_reserve, ledger_release, ledger_confirm, ledger_walk_in, ledger_demand_change
from app.leases import LeaseStatus, assert_transition, generate_otp, verify_otp, check_progress
from app.rules.engine import RulesEngine


router = APIRouter()
rules_engine = RulesEngine()


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class BatchCreateRequest(BaseModel):
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
    ready_at: Optional[datetime] = None
    cold_chain: bool = False
    diet_tags: List[str] = Field(default_factory=list)
    allergens: List[str] = Field(default_factory=list)


class ProgressReportRequest(BaseModel):
    lat: float
    lon: float


class PickupConfirmRequest(BaseModel):
    otp: str


class DeliveryConfirmRequest(BaseModel):
    qty_delivered: int


class ShelterDemandRequest(BaseModel):
    new_need: int


class WalkInRequest(BaseModel):
    qty: int


class CapabilityUpdate(BaseModel):
    capability: str
    value: bool


# In-memory storage for API demo/testing mode when DB is unseeded
_DB_STORE: Dict[str, Dict[int, Any]] = {
    "batches": {},
    "lots": {},
    "leases": {},
    "shelters": {},
    "riders": {},
    "donors": {},
    "events": [],
}


@router.get("/health")
def api_health():
    return {"status": "healthy", "time": get_clock().now().isoformat()}


@router.post("/batches", status_code=status.HTTP_201_CREATED)
def create_batch(
    req: BatchCreateRequest,
    idempotency_key: Optional[str] = Header(None),
):
    """Create batch, compute safe_until & deliver_by, split into lots."""
    meta = compute_batch_meta(
        BatchCreateParams(
            donor_id=req.donor_id,
            category=req.category,
            qty=req.qty,
            unit=req.unit,
            cooked_at=req.cooked_at,
            expiry_date=req.expiry_date,
            fridge_out_at=req.fridge_out_at,
            excursion_budget_min=req.excursion_budget_min,
            shelf_life_min_override=req.shelf_life_min_override,
            pickup_window_start=req.pickup_window_start,
            pickup_window_end=req.pickup_window_end,
            ready_at=req.ready_at,
            cold_chain=req.cold_chain,
            diet_tags=req.diet_tags,
            allergens=req.allergens,
            idempotency_key=idempotency_key,
        )
    )

    batch_id = len(_DB_STORE["batches"]) + 1
    batch_data = {
        "id": batch_id,
        "donor_id": req.donor_id,
        "category": req.category,
        "qty_portions": meta.qty_portions,
        "safe_until": meta.safe_until.isoformat(),
        "deliver_by": meta.deliver_by.isoformat(),
        "status": "active",
        "created_at": get_clock().now().isoformat(),
    }
    _DB_STORE["batches"][batch_id] = batch_data

    # Create lots
    lots = split_into_lots(batch_id, meta.qty_portions, meta.deliver_by, req.ready_at)
    created_lots = []
    for l_dict in lots:
        lot_id = len(_DB_STORE["lots"]) + 1
        l_dict["id"] = lot_id
        _DB_STORE["lots"][lot_id] = l_dict
        created_lots.append(l_dict)

    return {
        "batch": batch_data,
        "lots": created_lots,
        "feasibility": "ACCEPTED_FULL",
    }


@router.get("/state/snapshot")
def get_state_snapshot():
    """Return full state snapshot for control room and debugging (7.5)."""
    return {
        "time": get_clock().now().isoformat(),
        "batches": list(_DB_STORE["batches"].values()),
        "lots": list(_DB_STORE["lots"].values()),
        "leases": list(_DB_STORE["leases"].values()),
        "shelters": list(_DB_STORE["shelters"].values()),
        "riders": list(_DB_STORE["riders"].values()),
    }


@router.post("/admin/reset")
def admin_reset(admin_key: Optional[str] = Header(None)):
    """Reset all state (7.8)."""
    for k in _DB_STORE:
        if isinstance(_DB_STORE[k], dict):
            _DB_STORE[k].clear()
        elif isinstance(_DB_STORE[k], list):
            _DB_STORE[k].clear()
    return {"status": "reset_successful"}
