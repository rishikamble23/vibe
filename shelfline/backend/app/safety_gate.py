from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from app.clock import Clock, get_clock
from app.eta import ETAService, get_eta_service
from app.geo import haversine_km
from app.config_loader import (
    get_shelf_life, get_serve_buffer, get_handover_time,
    get_grace_period, get_redispatch_reserve, get_vehicle_capacity,
    get_lease_ttl_bounds, get_safety_gate_config
)


class SafetyReason(str, Enum):
    """Reasons why a lot assignment is not safe."""
    OK = "OK"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"          # P90 arrival > deliver_by
    INSUFFICIENT_CAPACITY = "INSUFFICIENT_CAPACITY"  # Lot qty > vehicle capacity
    NO_RIDER_AVAILABLE = "NO_RIDER_AVAILABLE"        # No rider can reach in time
    SHELTER_CLOSED = "SHELTER_CLOSED"                # Shelter not accepting
    SHELTER_FULL = "SHELTER_FULL"                    # Shelter need already committed
    COLD_CHAIN_REQUIRED = "COLD_CHAIN_REQUIRED"      # Batch needs cold chain, rider doesn't have
    DIET_MISMATCH = "DIET_MISMATCH"                  # Shelter doesn't accept diet tags
    ALLERGEN_CONFLICT = "ALLERGEN_CONFLICT"          # Shelter can't handle allergens
    CAPABILITY_MISSING = "CAPABILITY_MISSING"        # Shelter missing required capability
    RULE_VETO = "RULE_VETO"                          # Rules engine vetoed
    PICKUP_WINDOW_MISSED = "PICKUP_WINDOW_MISSED"    # Can't reach donor before pickup window ends


@dataclass
class SafetyCheckResult:
    """Result of a safety check."""
    ok: bool
    reasons: List[SafetyReason]
    slack_minutes: int
    p90_arrival_minutes: int
    deliver_by: datetime
    details: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "reasons": [r.value for r in self.reasons],
            "slack_minutes": self.slack_minutes,
            "p90_arrival_minutes": self.p90_arrival_minutes,
            "deliver_by": self.deliver_by.isoformat() if self.deliver_by else None,
            "details": self.details,
        }


def calculate_deliver_by(batch: Any, clock: Clock) -> datetime:
    """
    Calculate the hard delivery deadline for a batch.
    
    deliver_by = min(cooked_at + shelf_life, donor_declared_safe_until) - serve_buffer
    """
    serve_buffer = get_serve_buffer()
    
    # Calculate from cooked_at + shelf_life
    shelf_life_min = getattr(batch, 'shelf_life_min', None)
    if shelf_life_min is None:
        category = getattr(batch, 'category', 'default')
        shelf_life_min = get_shelf_life(category)
    
    cooked_at = getattr(batch, 'cooked_at', clock.now())
    if cooked_at.tzinfo is None:
        cooked_at = cooked_at.replace(tzinfo=timezone.utc)
    
    from datetime import timedelta
    safe_until_cooked = cooked_at + timedelta(minutes=shelf_life_min)
    
    # Donor declared safe_until (if provided)
    donor_safe_until = getattr(batch, 'safe_until', None)
    if donor_safe_until and donor_safe_until.tzinfo is None:
        donor_safe_until = donor_safe_until.replace(tzinfo=timezone.utc)
    
    # Use the earlier of the two
    if donor_safe_until:
        hard_deadline = min(safe_until_cooked, donor_safe_until)
    else:
        hard_deadline = safe_until_cooked
    
    # Subtract serve buffer
    deliver_by = hard_deadline - timedelta(minutes=serve_buffer)
    
    return deliver_by


def calculate_slack(
    now: datetime,
    deliver_by: datetime,
    rider_to_donor_p90: int,
    donor_to_shelter_p90: int,
) -> int:
    """
    Calculate slack in minutes.
    
    slack = deliver_by - now - P90(rider->donor) - handover - P90(donor->shelter) - handover
    """
    handover = get_handover_time()
    
    total_travel = rider_to_donor_p90 + donor_to_shelter_p90 + 2 * handover
    
    from datetime import timedelta
    time_until_deliver_by = int((deliver_by - now).total_seconds() / 60)
    
    slack = time_until_deliver_by - total_travel
    
    return slack


def calculate_lease_ttl(
    now: datetime,
    rider_to_donor_p90: int,
    latest_pickup: datetime,
) -> int:
    """
    Calculate lease TTL in minutes.
    
    lease_ttl = clamp(P90(rider->donor) + grace, min_ttl, latest_pickup - now - redispatch_reserve)
    """
    grace = get_grace_period()
    redispatch = get_redispatch_reserve()
    min_ttl, max_ttl = get_lease_ttl_bounds()
    
    # Calculate latest_pickup - now - redispatch_reserve in minutes
    from datetime import timedelta
    max_allowed = int((latest_pickup - now).total_seconds() / 60) - redispatch
    
    # Base TTL
    ttl = rider_to_donor_p90 + grace
    
    # Clamp
    ttl = max(min_ttl, min(ttl, max_allowed, max_ttl))
    
    return max(ttl, min_ttl)  # Ensure at least min_ttl


def calculate_latest_pickup(deliver_by: datetime, donor_to_shelter_p90: int) -> datetime:
    """Calculate latest pickup time."""
    handover = get_handover_time()
    from datetime import timedelta
    return deliver_by - timedelta(minutes=donor_to_shelter_p90 + handover)


class SafetyGate:
    """
    Safety Gate - vetoes assignments that could finish late or violate constraints.
    
    Uses P90 (pessimistic) travel times, not averages.
    A late or incompatible delivery is not a bad option, it is an illegal one.
    """
    
    def __init__(
        self,
        eta_service: Optional[ETAService] = None,
        clock: Optional[Clock] = None,
        rules_engine: Optional[Any] = None,  # Phase 6
    ):
        self.eta_service = eta_service or get_eta_service()
        self.clock = clock or get_clock()
        self.rules_engine = rules_engine
        self.config = get_safety_gate_config()
    
    def is_safe(
        self,
        lot: Any,
        rider: Any,
        shelter: Any,
        batch: Any,
        now: Optional[datetime] = None,
    ) -> SafetyCheckResult:
        """
        Check if assigning this lot to this rider for this shelter is safe.
        
        Returns SafetyCheckResult with ok=True/False and list of reasons.
        """
        now = now or self.clock.now()
        reasons: List[SafetyReason] = []
        details: Dict[str, Any] = {}
        
        # 1. Check deliver_by deadline
        deliver_by = calculate_deliver_by(batch, self.clock)
        details["deliver_by"] = deliver_by.isoformat()
        
        # 2. Calculate ETAs
        rider_to_donor = self.eta_service.calculate_eta(
            rider.lat, rider.lon,
            getattr(batch, 'lat', 0), getattr(batch, 'lon', 0),
            vehicle_type="car",  # Could be from rider.vehicle_type
            zone="default",
            now=now,
        )
        donor_to_shelter = self.eta_service.calculate_eta(
            getattr(batch, 'lat', 0), getattr(batch, 'lon', 0),
            shelter.lat, shelter.lon,
            vehicle_type="car",
            zone="default",
            now=now,
        )
        
        p90_rider_to_donor = rider_to_donor.p90_minutes
        p90_donor_to_shelter = donor_to_shelter.p90_minutes
        
        details["rider_to_donor_p90"] = p90_rider_to_donor
        details["donor_to_shelter_p90"] = p90_donor_to_shelter
        
        # 3. Calculate slack
        slack = calculate_slack(now, deliver_by, p90_rider_to_donor, p90_donor_to_shelter)
        details["slack_minutes"] = slack
        
        min_slack = self.config.get("min_slack_min", 0)
        if slack < min_slack:
            reasons.append(SafetyReason.DEADLINE_EXCEEDED)
        
        # 4. Check vehicle capacity
        lot_qty = getattr(lot, 'qty', 0)
        vehicle_cap = get_vehicle_capacity("car")  # Could be rider.vehicle_capacity
        if lot_qty > vehicle_cap:
            reasons.append(SafetyReason.INSUFFICIENT_CAPACITY)
        details["vehicle_capacity"] = vehicle_cap
        details["lot_qty"] = lot_qty
        
        # 5. Check shelter intake
        if not getattr(shelter, 'intake_open', True):
            reasons.append(SafetyReason.SHELTER_CLOSED)
        
        # 6. Check shelter capacity (need - received - committed)
        need = getattr(shelter, 'need', 0)
        received = getattr(shelter, 'received', 0)
        committed = getattr(shelter, 'committed', 0)
        available = need - received - committed
        
        details["shelter_need"] = need
        details["shelter_received"] = received
        details["shelter_committed"] = committed
        details["shelter_available"] = available
        
        if available <= 0:
            reasons.append(SafetyReason.SHELTER_FULL)
        elif lot_qty > available:
            # Could partially fill - for now reject if can't take full lot
            reasons.append(SafetyReason.SHELTER_FULL)
        
        # 7. Check pickup window
        pickup_window_end = getattr(batch, 'pickup_window_end', None)
        if pickup_window_end:
            if pickup_window_end.tzinfo is None:
                pickup_window_end = pickup_window_end.replace(tzinfo=timezone.utc)
            
            from datetime import timedelta
            latest_arrival_donor = now + timedelta(minutes=p90_rider_to_donor)
            if latest_arrival_donor > pickup_window_end:
                reasons.append(SafetyReason.PICKUP_WINDOW_MISSED)
            details["pickup_window_end"] = pickup_window_end.isoformat()
            details["latest_arrival_donor"] = latest_arrival_donor.isoformat()
        
        # 8. Cold chain check
        if getattr(batch, 'cold_chain', False) and not getattr(rider, 'insulated_box', False):
            reasons.append(SafetyReason.COLD_CHAIN_REQUIRED)
        details["cold_chain_required"] = getattr(batch, 'cold_chain', False)
        details["rider_insulated_box"] = getattr(rider, 'insulated_box', False)
        
        # 9. Diet/allergen tags (simplified)
        batch_diet = set(getattr(batch, 'diet_tags', []) or [])
        shelter_accepts = set(getattr(shelter, 'accepts_diet_tags', []) or [])
        if batch_diet and not batch_diet.issubset(shelter_accepts):
            reasons.append(SafetyReason.DIET_MISMATCH)
        details["batch_diet_tags"] = list(batch_diet)
        details["shelter_accepts"] = list(shelter_accepts)
        
        batch_allergens = set(getattr(batch, 'allergens', []) or [])
        # For now just record - would need shelter allergen handling config
        details["batch_allergens"] = list(batch_allergens)
        
        # 10. Capabilities (placeholder for Phase 6 rules engine)
        if self.rules_engine:
            # Would call rules engine here
            pass
        
        # Final result
        ok = len(reasons) == 0
        if ok:
            reasons = [SafetyReason.OK]
        
        p90_arrival = now
        from datetime import timedelta
        p90_arrival = now + timedelta(
            minutes=p90_rider_to_donor + get_handover_time() + p90_donor_to_shelter + get_handover_time()
        )
        
        return SafetyCheckResult(
            ok=ok,
            reasons=reasons,
            slack_minutes=slack,
            p90_arrival_minutes=int((p90_arrival - now).total_seconds() / 60),
            deliver_by=deliver_by,
            details=details,
        )


# Global safety gate instance
_safety_gate: Optional[SafetyGate] = None


def get_safety_gate() -> SafetyGate:
    """Get the global safety gate instance."""
    global _safety_gate
    if _safety_gate is None:
        _safety_gate = SafetyGate()
    return _safety_gate


def set_safety_gate(gate: SafetyGate) -> None:
    """Set the global safety gate instance (for testing)."""
    global _safety_gate
    _safety_gate = gate