from datetime import datetime, timezone
from typing import Any, Callable, TypeVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.models import Event, EventType
from app.clock import Clock, get_clock


T = TypeVar('T')


async def append_event(
    session: AsyncSession,
    event_type: EventType,
    payload: dict[str, Any],
    actor_type: str | None = None,
    actor_id: int | None = None,
    idempotency_key: str | None = None,
    clock: Clock | None = None,
) -> Event:
    """
    Append an event to the event log with idempotency guarantee.
    
    If an event with the same idempotency_key already exists, returns the existing event.
    """
    if idempotency_key is None:
        import uuid
        idempotency_key = str(uuid.uuid4())
    
    clock = clock or get_clock()
    now = clock.now()
    
    # Use PostgreSQL ON CONFLICT for idempotency
    stmt = pg_insert(Event).values(
        type=event_type,
        payload=payload,
        actor_type=actor_type,
        actor_id=actor_id,
        idempotency_key=idempotency_key,
        created_at=now,
    ).on_conflict_do_nothing(
        index_elements=['idempotency_key'],
    ).returning(Event)
    
    result = await session.execute(stmt)
    event = result.scalar_one_or_none()
    
    if event is None:
        # Event already exists, fetch it
        stmt = select(Event).where(Event.idempotency_key == idempotency_key)
        result = await session.execute(stmt)
        event = result.scalar_one()
    
    return event


# State reconstruction function type
StateReducer = Callable[[T, Event], T]


async def replay_events(
    session: AsyncSession,
    initial_state: T,
    reducer: StateReducer,
    since_id: int | None = None,
    actor_type: str | None = None,
    actor_id: int | None = None,
) -> T:
    """
    Rebuild state by replaying events through a reducer function.
    
    Args:
        session: Database session
        initial_state: Initial state to start from
        reducer: Function (state, event) -> new_state
        since_id: Only replay events after this ID
        actor_type: Filter by actor type
        actor_id: Filter by actor ID
    
    Returns:
        Final state after applying all events
    """
    stmt = select(Event).order_by(Event.id)
    
    if since_id is not None:
        stmt = stmt.where(Event.id > since_id)
    if actor_type is not None:
        stmt = stmt.where(Event.actor_type == actor_type)
    if actor_id is not None:
        stmt = stmt.where(Event.actor_id == actor_id)
    
    result = await session.execute(stmt)
    events = result.scalars().all()
    
    state = initial_state
    for event in events:
        state = reducer(state, event)
    
    return state


def create_event_payload(**kwargs: Any) -> dict[str, Any]:
    """Helper to create event payload with consistent structure."""
    return kwargs