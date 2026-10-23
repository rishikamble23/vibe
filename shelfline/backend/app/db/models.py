"""
Domain models for Phase 2 & 3 — Entities, Batches, Lots, Leases, Shelter Ledger.

Replaces the earlier placeholder models.py with the full schema from Appendix B.
All enums, state machines and constraints live here.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    BigInteger, Boolean, Column, DateTime, Enum as SAEnum,
    Float, ForeignKey, Index, Integer, JSON, String, Text,
    UniqueConstraint, CheckConstraint, SmallInteger,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class UserRole(str, enum.Enum):
    DONOR   = "donor"
    RIDER   = "rider"
    SHELTER = "shelter"
    ADMIN   = "admin"
    NGO     = "ngo"


class VehicleType(str, enum.Enum):
    BIKE = "bike"
    CAR  = "car"
    VAN  = "van"


class BatchCategory(str, enum.Enum):
    COOKED_MEAL        = "cooked_meal"
    DRY_RATION         = "dry_ration"
    RAW_RATION_KIT     = "raw_ration_kit"
    WATER              = "water"
    MEDICINE           = "medicine"
    MEDICAL_KIT        = "medical_kit"
    INFANT_FORMULA     = "infant_formula"
    COLD_CHAIN_MEDICINE = "cold_chain_medicine"
    COLD_CHAIN_FOOD    = "cold_chain_food"


class SafeUntilStrategy(str, enum.Enum):
    COOKED_FOOD = "cooked_food"
    DATED_ITEM  = "dated_item"
    COLD_CHAIN  = "cold_chain"


class BatchStatus(str, enum.Enum):
    PENDING   = "pending"
    ACTIVE    = "active"
    PARTIAL   = "partial"
    DELIVERED = "delivered"
    EXPIRED   = "expired"
    WITHDRAWN = "withdrawn"


class LotStatus(str, enum.Enum):
    UNASSIGNED     = "unassigned"
    LEASED         = "leased"
    IN_TRANSIT     = "in_transit"
    DELIVERED      = "delivered"
    EXPIRED        = "expired"
    DISCARDED      = "discarded"
    ABORTED_UNSAFE = "aborted_unsafe"


class LeaseStatus(str, enum.Enum):
    OFFERED      = "offered"
    ACCEPTED     = "accepted"
    ARRIVED_DONOR  = "arrived_donor"
    PICKED_UP    = "picked_up"
    NEAR_SHELTER = "near_shelter"
    DELIVERED    = "delivered"
    EXPIRED      = "expired"
    RELEASED     = "released"
    REROUTED     = "rerouted"
    ABORTED_UNSAFE = "aborted_unsafe"


class ClaimantType(str, enum.Enum):
    RIDER  = "rider"
    NGO    = "ngo"
    PLANNER = "planner"


class ScheduledActionType(str, enum.Enum):
    NUDGE          = "nudge"
    ALERT_STANDBY  = "alert_standby"
    EXPIRE         = "expire"
    SMS_FALLBACK   = "sms_fallback"
    EXPIRY_SWEEP   = "expiry_sweep"


class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT    = "sent"
    FAILED  = "failed"


class EventType(str, enum.Enum):
    BATCH_CREATED       = "BATCH_CREATED"
    BATCH_REVISED       = "BATCH_REVISED"
    LOT_CREATED         = "LOT_CREATED"
    LEASE_OFFERED       = "LEASE_OFFERED"
    LEASE_ACCEPTED      = "LEASE_ACCEPTED"
    LEASE_DECLINED      = "LEASE_DECLINED"
    RIDER_PING          = "RIDER_PING"
    RIDER_MILESTONE     = "RIDER_MILESTONE"
    LEASE_STALLED       = "LEASE_STALLED"
    LEASE_EXPIRED       = "LEASE_EXPIRED"
    LEASE_RELEASED      = "LEASE_RELEASED"
    PICKUP_CONFIRMED    = "PICKUP_CONFIRMED"
    DELIVERY_CONFIRMED  = "DELIVERY_CONFIRMED"
    DEMAND_CHANGED      = "DEMAND_CHANGED"
    SHELTER_CLOSED      = "SHELTER_CLOSED"
    WALK_IN_RECEIVED    = "WALK_IN_RECEIVED"
    CAPABILITY_CHANGED  = "CAPABILITY_CHANGED"
    REROUTE_PROPOSED    = "REROUTE_PROPOSED"
    REROUTE_ACKED       = "REROUTE_ACKED"
    UNSAFE_REPORTED     = "UNSAFE_REPORTED"
    LOT_EXPIRED         = "LOT_EXPIRED"
    LOT_DISCARDED       = "LOT_DISCARDED"
    PLAN_COMMITTED      = "PLAN_COMMITTED"
    CHAOS_INJECTED      = "CHAOS_INJECTED"


# ---------------------------------------------------------------------------
# Tables
# ---------------------------------------------------------------------------

class Donor(Base):
    __tablename__ = "donors"
    id          = Column(Integer, primary_key=True)
    name        = Column(String(200), nullable=False)
    phone       = Column(String(20))
    lat         = Column(Float, nullable=False)
    lon         = Column(Float, nullable=False)
    address     = Column(Text)
    verified    = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), nullable=False)
    updated_at  = Column(DateTime(timezone=True), nullable=False)

    batches = relationship("Batch", back_populates="donor")


class Rider(Base):
    __tablename__ = "riders"
    id               = Column(Integer, primary_key=True)
    name             = Column(String(200), nullable=False)
    phone            = Column(String(20))
    lat              = Column(Float)
    lon              = Column(Float)
    vehicle_type     = Column(SAEnum(VehicleType), default=VehicleType.BIKE)
    vehicle_capacity = Column(Integer, default=20)   # portions
    insulated_box    = Column(Boolean, default=False)
    reliability_score = Column(Float, default=0.8)  # Bayesian, 0-1
    status           = Column(String(20), default="available")  # available, busy, offline
    free_at          = Column(DateTime(timezone=True))          # projected free time (G8)
    free_lat         = Column(Float)                            # projected free location
    free_lon         = Column(Float)
    join_code        = Column(String(8), unique=True)
    created_at       = Column(DateTime(timezone=True), nullable=False)
    updated_at       = Column(DateTime(timezone=True), nullable=False)

    leases = relationship("Lease", back_populates="rider")


class Shelter(Base):
    __tablename__ = "shelters"
    id              = Column(Integer, primary_key=True)
    name            = Column(String(200), nullable=False)
    phone           = Column(String(20))
    lat             = Column(Float, nullable=False)
    lon             = Column(Float, nullable=False)
    address         = Column(Text)
    need            = Column(Integer, default=0)       # portions needed
    received        = Column(Integer, default=0)       # confirmed received
    committed       = Column(Integer, default=0)       # in-transit committed
    intake_open     = Column(Boolean, default=True)
    intake_open_hour  = Column(SmallInteger, default=6)   # opening hour UTC
    intake_close_hour = Column(SmallInteger, default=22)  # closing hour UTC
    accepts_diet_tags = Column(JSON, default=list)         # ["veg","halal",...]
    state_version   = Column(Integer, default=0, nullable=False)
    created_at      = Column(DateTime(timezone=True), nullable=False)
    updated_at      = Column(DateTime(timezone=True), nullable=False)

    capabilities = relationship("ShelterCapability", back_populates="shelter")
    leases       = relationship("Lease", back_populates="shelter")

    __table_args__ = (
        CheckConstraint("need >= 0", name="shelter_need_non_negative"),
        CheckConstraint("received >= 0", name="shelter_received_non_negative"),
        CheckConstraint("committed >= 0", name="shelter_committed_non_negative"),
    )


class ShelterCapability(Base):
    __tablename__ = "shelter_capabilities"
    id          = Column(Integer, primary_key=True)
    shelter_id  = Column(Integer, ForeignKey("shelters.id"), nullable=False)
    name        = Column(String(50), nullable=False)   # "water","fridge","fuel",...
    value       = Column(Boolean, default=True)
    verified_at = Column(DateTime(timezone=True))

    shelter = relationship("Shelter", back_populates="capabilities")

    __table_args__ = (
        UniqueConstraint("shelter_id", "name", name="uq_shelter_capability"),
    )


class OverflowSink(Base):
    __tablename__ = "overflow_sinks"
    id          = Column(Integer, primary_key=True)
    name        = Column(String(200), nullable=False)
    lat         = Column(Float, nullable=False)
    lon         = Column(Float, nullable=False)
    open_hour   = Column(SmallInteger, default=0)
    close_hour  = Column(SmallInteger, default=24)
    intake_limit = Column(Integer, default=100)
    created_at  = Column(DateTime(timezone=True), nullable=False)


class Batch(Base):
    __tablename__ = "batches"
    id                  = Column(Integer, primary_key=True)
    donor_id            = Column(Integer, ForeignKey("donors.id"), nullable=False)
    category            = Column(SAEnum(BatchCategory), nullable=False)
    safe_until_strategy = Column(SAEnum(SafeUntilStrategy), nullable=False)
    qty_portions        = Column(Integer, nullable=False)
    unit_original       = Column(String(20))   # original unit ("kg","tray",...)
    qty_original        = Column(Float)        # original qty before conversion
    cooked_at           = Column(DateTime(timezone=True))
    expiry_date         = Column(DateTime(timezone=True))   # for dated_item
    fridge_out_at       = Column(DateTime(timezone=True))   # for cold_chain
    shelf_life_min      = Column(Integer)
    safe_until          = Column(DateTime(timezone=True), nullable=False)
    deliver_by          = Column(DateTime(timezone=True), nullable=False)
    pickup_window_start = Column(DateTime(timezone=True))
    pickup_window_end   = Column(DateTime(timezone=True))
    ready_at            = Column(DateTime(timezone=True))   # G22 — cannot offer before this
    cold_chain          = Column(Boolean, default=False)
    diet_tags           = Column(JSON, default=list)
    allergens           = Column(JSON, default=list)
    status              = Column(SAEnum(BatchStatus), default=BatchStatus.ACTIVE)
    idempotency_key     = Column(String(64), unique=True)   # G16 — no double-submit
    state_version       = Column(Integer, default=0, nullable=False)
    created_at          = Column(DateTime(timezone=True), nullable=False)
    updated_at          = Column(DateTime(timezone=True), nullable=False)

    donor = relationship("Donor", back_populates="batches")
    lots  = relationship("Lot", back_populates="batch")

    __table_args__ = (
        Index("ix_batches_deliver_by", "deliver_by"),
        Index("ix_batches_status", "status"),
    )


class Lot(Base):
    __tablename__ = "lots"
    id           = Column(Integer, primary_key=True)
    batch_id     = Column(Integer, ForeignKey("batches.id"), nullable=False)
    qty          = Column(Integer, nullable=False)
    status       = Column(SAEnum(LotStatus), default=LotStatus.UNASSIGNED)
    ready_at     = Column(DateTime(timezone=True))          # G22 — cannot lease before this
    deliver_by   = Column(DateTime(timezone=True), nullable=False)
    state_version = Column(Integer, default=0, nullable=False)
    created_at   = Column(DateTime(timezone=True), nullable=False)
    updated_at   = Column(DateTime(timezone=True), nullable=False)

    batch  = relationship("Batch", back_populates="lots")
    leases = relationship("Lease", back_populates="lot")

    __table_args__ = (
        Index("ix_lots_status", "status"),
        Index("ix_lots_deliver_by", "deliver_by"),
        Index("ix_lots_batch_id", "batch_id"),
        CheckConstraint("qty > 0", name="lot_qty_positive"),
    )


class Lease(Base):
    __tablename__ = "leases"
    id                = Column(Integer, primary_key=True)
    lot_id            = Column(Integer, ForeignKey("lots.id"), nullable=False)
    rider_id          = Column(Integer, ForeignKey("riders.id"))
    shelter_id        = Column(Integer, ForeignKey("shelters.id"), nullable=False)
    claimant_type     = Column(SAEnum(ClaimantType), default=ClaimantType.RIDER)
    ngo_id            = Column(Integer)                       # if NGO claim
    ngo_rider_assigned_at = Column(DateTime(timezone=True))  # G5 — NGO must assign rider
    qty               = Column(Integer, nullable=False)
    status            = Column(SAEnum(LeaseStatus), default=LeaseStatus.OFFERED)
    expires_at        = Column(DateTime(timezone=True), nullable=False)
    latest_pickup     = Column(DateTime(timezone=True))
    last_progress_at  = Column(DateTime(timezone=True))
    last_lat          = Column(Float)
    last_lon          = Column(Float)
    last_dist_to_donor = Column(Float)                        # for stall detection
    stall_count       = Column(Integer, default=0)            # non-shrinking pings
    otp_pickup        = Column(String(6))                     # single-use OTP
    otp_delivery      = Column(String(6))
    otp_attempts      = Column(Integer, default=0)
    fallbacks         = Column(JSON, default=list)            # precomputed fallback shelters
    planned_qty       = Column(Integer)                       # original planned qty
    actual_qty        = Column(Integer)                        # confirmed at pickup (G6)
    plan_explanation  = Column(Text)
    state_version     = Column(Integer, default=0, nullable=False)
    is_hot_standby    = Column(Boolean, default=False)
    created_at        = Column(DateTime(timezone=True), nullable=False)
    updated_at        = Column(DateTime(timezone=True), nullable=False)

    lot     = relationship("Lot", back_populates="leases")
    rider   = relationship("Rider", back_populates="leases")
    shelter = relationship("Shelter", back_populates="leases")

    __table_args__ = (
        Index("ix_leases_expires_at", "expires_at"),
        Index("ix_leases_status", "status"),
        Index("ix_leases_lot_id", "lot_id"),
        Index("ix_leases_rider_id", "rider_id"),
        Index("ix_leases_shelter_id", "shelter_id"),
    )


class Event(Base):
    __tablename__ = "events"
    id              = Column(BigInteger, primary_key=True, autoincrement=True)
    type            = Column(SAEnum(EventType), nullable=False)
    payload         = Column(JSON, nullable=False, default=dict)
    actor_type      = Column(String(30))
    actor_id        = Column(Integer)
    idempotency_key = Column(String(64), unique=True)
    created_at      = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_events_type", "type"),
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_actor", "actor_type", "actor_id"),
    )


class ScheduledAction(Base):
    __tablename__ = "scheduled_actions"
    id          = Column(Integer, primary_key=True)
    type        = Column(SAEnum(ScheduledActionType), nullable=False)
    run_at      = Column(DateTime(timezone=True), nullable=False)
    lease_id    = Column(Integer, ForeignKey("leases.id"))
    lot_id      = Column(Integer, ForeignKey("lots.id"))
    payload     = Column(JSON, default=dict)
    processed   = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        Index("ix_scheduled_actions_run_at", "run_at"),
        Index("ix_scheduled_actions_processed", "processed"),
    )


class NotificationOutbox(Base):
    __tablename__ = "notifications_outbox"
    id          = Column(Integer, primary_key=True)
    channel     = Column(String(20), nullable=False)   # "push","sms","call"
    recipient   = Column(String(50), nullable=False)   # phone or rider_id
    message     = Column(Text, nullable=False)
    status      = Column(SAEnum(NotificationStatus), default=NotificationStatus.PENDING)
    lease_id    = Column(Integer, ForeignKey("leases.id"))
    created_at  = Column(DateTime(timezone=True), nullable=False)
    sent_at     = Column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_notifications_status", "status"),
    )


class MetricsSnapshot(Base):
    __tablename__ = "metrics_snapshots"
    id                = Column(Integer, primary_key=True)
    portions_delivered = Column(Integer, default=0)
    portions_wasted   = Column(Integer, default=0)
    violations        = Column(Integer, default=0)
    ghost_rate        = Column(Float, default=0.0)
    mean_slack_min    = Column(Float)
    reroute_count     = Column(Integer, default=0)
    snapshot_at       = Column(DateTime(timezone=True), nullable=False)
