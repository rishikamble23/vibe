"""
Phase 5 — Rerouting and Fallbacks: cargo in motion is never stranded.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from app.clock import get_clock
from app.eta import get_eta_service
from app.safety_gate import SafetyGate, get_safety_gate, SafetyReason


class FallbackTier(str, Enum):
    TIER_1_SHELTER     = "tier_1_shelter"
    TIER_2_OVERFLOW    = "tier_2_overflow"
    TIER_3_FLASH_OFFER = "tier_3_flash_offer"
    TIER_4_DISCARD     = "tier_4_discard"


@dataclass
class FallbackDestination:
    tier: FallbackTier
    destination_id: int
    name: str
    lat: float
    lon: float
    p90_eta_minutes: int
    available_capacity: int
    reason: str


@dataclass
class RerouteDecision:
    lease_id: int
    original_shelter_id: int
    new_shelter_id: Optional[int]
    tier: FallbackTier
    partial_drop_qty: Optional[int]
    remainder_qty: Optional[int]
    reason: str


class RerouteService:
    """Computes precomputed fallbacks and handles mid-transit reroutes."""

    def __init__(
        self,
        safety_gate: Optional[SafetyGate] = None,
        eta_service: Optional[Any] = None,
    ):
        self.safety_gate = safety_gate or get_safety_gate()
        self.eta_service = eta_service or get_eta_service()

    def compute_fallbacks(
        self,
        rider_lat: float,
        rider_lon: float,
        lot: Any,
        batch: Any,
        shelters: List[Any],
        overflow_sinks: Optional[List[Any]] = None,
        exclude_shelter_id: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> List[FallbackDestination]:
        now = now or get_clock().now()
        fallbacks: List[FallbackDestination] = []

        class DummyRider:
            lat = rider_lat
            lon = rider_lon
            vehicle_capacity = 100
            insulated_box = True

        dummy_rider = DummyRider()

        for shelter in shelters:
            if shelter.id == exclude_shelter_id:
                continue
            if not getattr(shelter, "intake_open", True):
                continue

            avail = shelter.need - shelter.received - shelter.committed
            if avail <= 0:
                continue

            res = self.safety_gate.is_safe(lot, dummy_rider, shelter, batch, now=now)
            if res.ok or SafetyReason.SHELTER_FULL in res.reasons or SafetyReason.DEADLINE_EXCEEDED in res.reasons:
                eta_res = self.eta_service.calculate_eta(
                    rider_lat, rider_lon, shelter.lat, shelter.lon, now=now
                )
                p90 = eta_res.p90_minutes

                fallbacks.append(
                    FallbackDestination(
                        tier=FallbackTier.TIER_1_SHELTER,
                        destination_id=shelter.id,
                        name=getattr(shelter, "name", f"Shelter {shelter.id}"),
                        lat=shelter.lat,
                        lon=shelter.lon,
                        p90_eta_minutes=p90,
                        available_capacity=avail,
                        reason=f"Tier 1 shelter with {avail} capacity, P90 ETA {p90} min",
                    )
                )

        fallbacks.sort(key=lambda f: f.p90_eta_minutes)

        if overflow_sinks:
            for sink in overflow_sinks:
                eta_res = self.eta_service.calculate_eta(
                    rider_lat, rider_lon, sink.lat, sink.lon, now=now
                )
                p90 = eta_res.p90_minutes
                fallbacks.append(
                    FallbackDestination(
                        tier=FallbackTier.TIER_2_OVERFLOW,
                        destination_id=sink.id,
                        name=getattr(sink, "name", f"Sink {sink.id}"),
                        lat=sink.lat,
                        lon=sink.lon,
                        p90_eta_minutes=p90,
                        available_capacity=getattr(sink, "intake_limit", 100),
                        reason=f"Tier 2 overflow sink, P90 ETA {p90} min",
                    )
                )

        return fallbacks[:3]

    def decide_reroute(
        self,
        lease: Any,
        lot: Any,
        batch: Any,
        current_lat: float,
        current_lon: float,
        shelters: List[Any],
        overflow_sinks: Optional[List[Any]] = None,
        now: Optional[datetime] = None,
    ) -> RerouteDecision:
        now = now or get_clock().now()
        qty_carrying = getattr(lease, "actual_qty", lot.qty)

        # First check if original shelter can still take a partial drop
        orig_shelter = next((s for s in shelters if s.id == lease.shelter_id), None)
        if orig_shelter and getattr(orig_shelter, "intake_open", True):
            orig_avail = orig_shelter.need - orig_shelter.received - orig_shelter.committed
            if 0 < orig_avail < qty_carrying:
                remainder = qty_carrying - orig_avail
                return RerouteDecision(
                    lease_id=lease.id,
                    original_shelter_id=lease.shelter_id,
                    new_shelter_id=orig_shelter.id,
                    tier=FallbackTier.TIER_1_SHELTER,
                    partial_drop_qty=orig_avail,
                    remainder_qty=remainder,
                    reason=f"Partial drop: {orig_avail} at original shelter, {remainder} remainder needs reroute",
                )

        fallbacks = self.compute_fallbacks(
            current_lat, current_lon, lot, batch,
            shelters, overflow_sinks,
            exclude_shelter_id=lease.shelter_id,
            now=now,
        )

        if fallbacks:
            best = fallbacks[0]
            if best.available_capacity < qty_carrying:
                drop_qty = best.available_capacity
                remainder = qty_carrying - drop_qty
                return RerouteDecision(
                    lease_id=lease.id,
                    original_shelter_id=lease.shelter_id,
                    new_shelter_id=best.destination_id,
                    tier=best.tier,
                    partial_drop_qty=drop_qty,
                    remainder_qty=remainder,
                    reason=f"Partial drop: {drop_qty} at {best.name}, {remainder} remainder",
                )
            else:
                return RerouteDecision(
                    lease_id=lease.id,
                    original_shelter_id=lease.shelter_id,
                    new_shelter_id=best.destination_id,
                    tier=best.tier,
                    partial_drop_qty=None,
                    remainder_qty=None,
                    reason=f"Full reroute to {best.name} ({best.tier.value})",
                )

        return RerouteDecision(
            lease_id=lease.id,
            original_shelter_id=lease.shelter_id,
            new_shelter_id=None,
            tier=FallbackTier.TIER_4_DISCARD,
            partial_drop_qty=None,
            remainder_qty=None,
            reason="No viable destinations available; escalated to Tier 4 safe discard.",
        )
