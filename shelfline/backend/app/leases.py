"""
Lease state machine — enforces allowed transitions (Appendix E).

State machine table:
  OFFERED       → ACCEPTED        (rider accepts within offer window)
  OFFERED       → EXPIRED         (offer window passes)
  ACCEPTED      → ARRIVED_DONOR   (milestone / geofence)
  ACCEPTED      → EXPIRED         (TTL passes without sufficient progress)
  ACCEPTED      → RELEASED        (rider cancels or planner reassigns)
  ARRIVED_DONOR → PICKED_UP       (OTP confirmed — hard commit)
  PICKED_UP     → NEAR_SHELTER    (milestone / geofence)
  PICKED_UP     → REROUTED        (reroute accepted)
  NEAR_SHELTER  → DELIVERED       (shelter confirms)
  Any active    → ABORTED_UNSAFE  (safety veto)

Phase 3: TTL calc, progress ingestion, STALLED, extension, OTP, reaper, hot standby,
         self-claim, NGO claim, concurrency (state_version).
"""
from __future__ import annotations

import secrets
import string
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

from app.clock import get_clock
from app.config_loader import (
    get_grace_period, get_redispatch_reserve,
    get_lease_ttl_bounds, get_config,
)
from app.eta import get_eta_service
from app.safety_gate import SafetyReason


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------

class LeaseStatus(str, Enum):
    OFFERED        = "offered"
    ACCEPTED       = "accepted"
    ARRIVED_DONOR  = "arrived_donor"
    PICKED_UP      = "picked_up"
    NEAR_SHELTER   = "near_shelter"
    DELIVERED      = "delivered"
    EXPIRED        = "expired"
    RELEASED       = "released"
    REROUTED       = "rerouted"
    ABORTED_UNSAFE = "aborted_unsafe"


# (from, to) pairs that are legal
_ALLOWED_TRANSITIONS: Set[Tuple[LeaseStatus, LeaseStatus]] = {
    (LeaseStatus.OFFERED,       LeaseStatus.ACCEPTED),
    (LeaseStatus.OFFERED,       LeaseStatus.EXPIRED),
    (LeaseStatus.OFFERED,       LeaseStatus.RELEASED),
    (LeaseStatus.ACCEPTED,      LeaseStatus.ARRIVED_DONOR),
    (LeaseStatus.ACCEPTED,      LeaseStatus.EXPIRED),
    (LeaseStatus.ACCEPTED,      LeaseStatus.RELEASED),
    (LeaseStatus.ARRIVED_DONOR, LeaseStatus.PICKED_UP),
    (LeaseStatus.ARRIVED_DONOR, LeaseStatus.EXPIRED),
    (LeaseStatus.ARRIVED_DONOR, LeaseStatus.RELEASED),
    (LeaseStatus.PICKED_UP,     LeaseStatus.NEAR_SHELTER),
    (LeaseStatus.PICKED_UP,     LeaseStatus.REROUTED),
    (LeaseStatus.NEAR_SHELTER,  LeaseStatus.DELIVERED),
    # Safety veto from any active state
    (LeaseStatus.OFFERED,       LeaseStatus.ABORTED_UNSAFE),
    (LeaseStatus.ACCEPTED,      LeaseStatus.ABORTED_UNSAFE),
    (LeaseStatus.ARRIVED_DONOR, LeaseStatus.ABORTED_UNSAFE),
    (LeaseStatus.PICKED_UP,     LeaseStatus.ABORTED_UNSAFE),
    (LeaseStatus.NEAR_SHELTER,  LeaseStatus.ABORTED_UNSAFE),
}

_TERMINAL_STATES: Set[LeaseStatus] = {
    LeaseStatus.DELIVERED,
    LeaseStatus.EXPIRED,
    LeaseStatus.RELEASED,
    LeaseStatus.REROUTED,
    LeaseStatus.ABORTED_UNSAFE,
}

_SOFT_LEASE_STATES: Set[LeaseStatus] = {
    LeaseStatus.OFFERED,
    LeaseStatus.ACCEPTED,
    LeaseStatus.ARRIVED_DONOR,
}

_HARD_COMMIT_STATES: Set[LeaseStatus] = {
    LeaseStatus.PICKED_UP,
    LeaseStatus.NEAR_SHELTER,
}


def assert_transition(from_status: LeaseStatus, to_status: LeaseStatus) -> None:
    """Raise ValueError if the transition is not in the allowed set."""
    if (from_status, to_status) not in _ALLOWED_TRANSITIONS:
        raise ValueError(
            f"Illegal lease transition: {from_status.value} → {to_status.value}"
        )


def is_terminal(status: LeaseStatus) -> bool:
    return status in _TERMINAL_STATES


def is_soft_lease(status: LeaseStatus) -> bool:
    return status in _SOFT_LEASE_STATES


def is_hard_commit(status: LeaseStatus) -> bool:
    return status in _HARD_COMMIT_STATES


# ---------------------------------------------------------------------------
# TTL calculation  (3.2)
# ---------------------------------------------------------------------------

def calculate_lease_ttl_for_offer(
    now: datetime,
    rider_to_donor_p90: int,
    latest_pickup: datetime,
) -> int:
    """
    lease_ttl = clamp(P90(rider→donor) + grace, min_ttl, latest_pickup - now - redispatch_reserve)

    Returns TTL in minutes. Always >= min_ttl.
    """
    grace      = get_grace_period()
    redispatch = get_redispatch_reserve()
    min_ttl, max_ttl = get_lease_ttl_bounds()

    upper_bound = int((latest_pickup - now).total_seconds() / 60) - redispatch
    raw         = rider_to_donor_p90 + grace

    ttl = max(min_ttl, min(raw, upper_bound, max_ttl))
    return max(ttl, min_ttl)


# ---------------------------------------------------------------------------
# OTP generation  (3.15)
# ---------------------------------------------------------------------------
_OTP_CHARS = string.digits
_OTP_LENGTH = 6
_OTP_MAX_ATTEMPTS = 5


def generate_otp() -> str:
    """Generate a cryptographically random 6-digit OTP."""
    return "".join(secrets.choice(_OTP_CHARS) for _ in range(_OTP_LENGTH))


def verify_otp(provided: str, stored: str, attempts: int) -> Tuple[bool, str]:
    """
    Verify an OTP. Returns (ok, reason).
    Locks after _OTP_MAX_ATTEMPTS wrong attempts.
    """
    if attempts >= _OTP_MAX_ATTEMPTS:
        return False, "OTP_LOCKED"
    if provided.strip() != stored:
        return False, "OTP_WRONG"
    return True, "OK"


# ---------------------------------------------------------------------------
# Progress / stall detection  (3.4)
# ---------------------------------------------------------------------------
_STALL_THRESHOLD = 3   # non-shrinking pings before STALLED


def check_progress(
    new_lat: float,
    new_lon: float,
    last_lat: Optional[float],
    last_lon: Optional[float],
    prev_dist_to_donor: Optional[float],
    donor_lat: float,
    donor_lon: float,
    stall_count: int,
) -> Tuple[float, int, bool]:
    """
    Compute new distance to donor, update stall_count.

    Returns (new_dist_to_donor, new_stall_count, is_stalled).
    Distance shrinking = progress made.
    """
    from app.geo import haversine_km

    new_dist = haversine_km(new_lat, new_lon, donor_lat, donor_lon)

    if prev_dist_to_donor is None:
        # First ping — baseline
        return new_dist, 0, False

    if new_dist < prev_dist_to_donor * 0.995:  # 0.5 % tolerance for GPS noise
        # Moving toward donor
        new_stall_count = 0
    else:
        new_stall_count = stall_count + 1

    is_stalled = new_stall_count >= _STALL_THRESHOLD
    return new_dist, new_stall_count, is_stalled


# ---------------------------------------------------------------------------
# Lease operations (pure business logic — DB calls stay in the service layer)
# ---------------------------------------------------------------------------

@dataclass
class LeaseCreateParams:
    lot_id: int
    rider_id: Optional[int]
    shelter_id: int
    qty: int
    expires_at: datetime
    latest_pickup: datetime
    otp_pickup: str = field(default_factory=generate_otp)
    otp_delivery: str = field(default_factory=generate_otp)
    is_hot_standby: bool = False
    plan_explanation: Optional[str] = None
    claimant_type: str = "rider"


def make_lease_expiry(
    now: datetime,
    rider_to_donor_p90: int,
    latest_pickup: datetime,
) -> datetime:
    ttl = calculate_lease_ttl_for_offer(now, rider_to_donor_p90, latest_pickup)
    return now + timedelta(minutes=ttl)


def extend_lease_expiry(
    current_expiry: datetime,
    new_eta_p90: int,
    latest_pickup: datetime,
    now: datetime,
) -> datetime:
    """
    Extend lease on progress ping. Never beyond latest_pickup - redispatch_reserve.
    """
    redispatch = get_redispatch_reserve()
    hard_limit = latest_pickup - timedelta(minutes=redispatch)
    proposed   = now + timedelta(minutes=new_eta_p90 + get_grace_period())
    return min(proposed, hard_limit)
