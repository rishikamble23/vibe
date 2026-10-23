from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import Optional, List
from sqlalchemy import (
    Column, Integer, String, DateTime, ForeignKey, Enum, Float, Boolean,
    Text, Index, UniqueConstraint, BigInteger, JSON
)
from sqlalchemy.orm import relationship, declarative_base
from sqlalchemy.dialects.postgresql import UUID
import uuid


Base = declarative_base()


class LotStatus(PyEnum):
    UNASSIGNED = "UNASSIGNED"
    LEASED = "LEASED"
    IN_TRANSIT = "IN_TRANSIT"
    DELIVERED = "DELIVERED"
    EXPIRED = "EXPIRED"
    DISCARDED = "DISCARDED"
    ABORTED_UNSAFE = "ABORTED_UNSAFE"


class LeaseState(PyEnum):
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"
    ARRIVED_DONOR = "ARRIVED_DONOR"
    PICKED_UP = "PICKED_UP"
    NEAR_SHELTER = "NEAR_SHELTER"
    DELIVERED = "DELIVERED"
    EXPIRED = "EXPIRED"
    RELEASED = "RELEASED"
    REROUTED = "REROUTED"
    ABORTED_UNSAFE = "ABORTED_UNSAFE"


class EventType(PyEnum):
    BATCH_CREATED = "BATCH_CREATED"
    BATCH_REVISED = "BATCH_REVISED"
    LOT_CREATED = "LOT_CREATED"
    LEASE_OFFERED = "LEASE_OFFERED"
    LEASE_ACCEPTED = "LEASE_ACCEPTED"
    LEASE_DECLINED = "LEASE_DECLINED"
    RIDER_PING = "RIDER_PING"
    RIDER_MILESTONE = "RIDER_MILESTONE"
    LEASE_STALLED = "LEASE_STALLED"
    LEASE_EXPIRED = "LEASE_EXPIRED"
    LEASE_RELEASED = "LEASE_RELEASED"
    PICKUP_CONFIRMED = "PICKUP_CONFIRMED"
    DELIVERY_CONFIRMED = "DELIVERY_CONFIRMED"
    DEMAND_CHANGED = "DEMAND_CHANGED"
    SHELTER_CLOSED = "SHELTER_CLOSED"
    WALK_IN_RECEIVED = "WALK_IN_RECEIVED"
    CAPABILITY_CHANGED = "CAPABILITY_CHANGED"
    REROUTE_PROPOSED = "REROUTE_PROPOSED"
    REROUTE_ACKED = "REROUTE_ACKED"
    UNSAFE_REPORTED = "UNSAFE_REPORTED"
    LOT_EXPIRED = "LOT_EXPIRED"
    LOT_DISCARDED = "LOT_DISCARDED"
    PLAN_COMMITTED = "PLAN_COMMITTED"
    CHAOS_INJECTED = "CHAOS_INJECTED"


class Donor(Base):
    __tablename__ = "donors"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    contact = Column(String(255))
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    batches = relationship("Batch", back_populates="donor")


class Rider(Base):
    __tablename__ = "riders"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    phone = Column(String(50))
    vehicle_capacity = Column(Integer, default=50)
    insulated_box = Column(Boolean, default=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    status = Column(String(50), default="AVAILABLE")
    reliability_alpha = Column(Integer, default=1)
    reliability_beta = Column(Integer, default=1)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    leases = relationship("Lease", back_populates="rider")


class Shelter(Base):
    __tablename__ = "shelters"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    contact = Column(String(255))
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    need = Column(Integer, default=0)
    received = Column(Integer, default=0)
    committed = Column(Integer, default=0)
    intake_open = Column(Boolean, default=True)
    accepts_diet_tags = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    capabilities = relationship("ShelterCapability", back_populates="shelter", cascade="all, delete-orphan")
    leases = relationship("Lease", back_populates="shelter")


class ShelterCapability(Base):
    __tablename__ = "shelter_capabilities"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    shelter_id = Column(Integer, ForeignKey("shelters.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    value = Column(Boolean, default=True)
    verified_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    shelter = relationship("Shelter", back_populates="capabilities")
    
    __table_args__ = (
        UniqueConstraint("shelter_id", "name", name="uq_shelter_capability"),
    )


class OverflowSink(Base):
    __tablename__ = "overflow_sinks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    open_from = Column(String(5))
    open_to = Column(String(5))
    intake_limit = Column(Integer)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Batch(Base):
    __tablename__ = "batches"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    donor_id = Column(Integer, ForeignKey("donors.id"), nullable=False)
    category = Column(String(100), nullable=False)
    qty_portions = Column(Integer, nullable=False)
    cooked_at = Column(DateTime(timezone=True), nullable=False)
    shelf_life_min = Column(Integer, nullable=False)
    safe_until = Column(DateTime(timezone=True), nullable=False)
    pickup_window_start = Column(DateTime(timezone=True), nullable=False)
    pickup_window_end = Column(DateTime(timezone=True), nullable=False)
    cold_chain = Column(Boolean, default=False)
    allergens = Column(JSON, default=list)
    diet_tags = Column(JSON, default=list)
    status = Column(String(50), default="ACTIVE")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    donor = relationship("Donor", back_populates="batches")
    lots = relationship("Lot", back_populates="batch", cascade="all, delete-orphan")


class Lot(Base):
    __tablename__ = "lots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    batch_id = Column(Integer, ForeignKey("batches.id", ondelete="CASCADE"), nullable=False)
    qty = Column(Integer, nullable=False)
    status = Column(Enum(LotStatus), default=LotStatus.UNASSIGNED, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    batch = relationship("Batch", back_populates="lots")
    leases = relationship("Lease", back_populates="lot")


class Lease(Base):
    __tablename__ = "leases"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lot_id = Column(Integer, ForeignKey("lots.id", ondelete="CASCADE"), nullable=False)
    rider_id = Column(Integer, ForeignKey("riders.id"), nullable=False)
    shelter_id = Column(Integer, ForeignKey("shelters.id"), nullable=False)
    state = Column(Enum(LeaseState), default=LeaseState.OFFERED, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    last_progress_at = Column(DateTime(timezone=True))
    progress_pings = Column(Integer, default=0)
    fallbacks = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    lot = relationship("Lot", back_populates="leases")
    rider = relationship("Rider", back_populates="leases")
    shelter = relationship("Shelter", back_populates="leases")
    stops = relationship("LeaseStop", back_populates="lease", cascade="all, delete-orphan", order_by="LeaseStop.sequence")


class LeaseStop(Base):
    __tablename__ = "lease_stops"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    lease_id = Column(Integer, ForeignKey("leases.id", ondelete="CASCADE"), nullable=False)
    sequence = Column(Integer, nullable=False)
    location_type = Column(String(50), nullable=False)
    location_id = Column(Integer, nullable=False)
    lat = Column(Float, nullable=False)
    lon = Column(Float, nullable=False)
    eta_p50 = Column(Integer)
    eta_p90 = Column(Integer)
    arrived_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    lease = relationship("Lease", back_populates="stops")


class Event(Base):
    __tablename__ = "events"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    type = Column(Enum(EventType), nullable=False)
    payload = Column(JSON, nullable=False)
    actor_type = Column(String(50))
    actor_id = Column(Integer)
    idempotency_key = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("ix_events_created_at", "created_at"),
        Index("ix_events_actor", "actor_type", "actor_id"),
    )


class ScheduledAction(Base):
    __tablename__ = "scheduled_actions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    action_type = Column(String(50), nullable=False)
    target_type = Column(String(50))
    target_id = Column(Integer)
    payload = Column(JSON, default={})
    execute_at = Column(DateTime(timezone=True), nullable=False)
    executed_at = Column(DateTime(timezone=True))
    status = Column(String(50), default="PENDING")
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    
    __table_args__ = (
        Index("ix_scheduled_actions_execute_at", "execute_at"),
    )


class NotificationOutbox(Base):
    __tablename__ = "notifications_outbox"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    channel = Column(String(50), nullable=False)
    recipient = Column(String(255), nullable=False)
    subject = Column(String(255))
    body = Column(Text, nullable=False)
    status = Column(String(50), default="PENDING")
    attempts = Column(Integer, default=0)
    sent_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


class Plan(Base):
    __tablename__ = "plans"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(Integer, nullable=False)
    assignments = Column(JSON, default=list)
    explanations = Column(JSON, default=list)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    committed_at = Column(DateTime(timezone=True))


class MetricsSnapshot(Base):
    __tablename__ = "metrics_snapshots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    portions_delivered = Column(Integer, default=0)
    portions_wasted = Column(Integer, default=0)
    portions_wasted_expired = Column(Integer, default=0)
    portions_wasted_unsafe = Column(Integer, default=0)
    portions_wasted_capacity = Column(Integer, default=0)
    lease_violations = Column(Integer, default=0)
    ghost_rate = Column(Float, default=0.0)
    avg_reroute_time_ms = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))