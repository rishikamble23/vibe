"""
Shelter ledger: reserve / release / confirm with atomic conditional updates.

All updates use UPDATE ... WHERE need - received - committed >= qty
so concurrent reserves are race-safe without application-level locking.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class LedgerResult(str, Enum):
    OK       = "OK"
    FULL     = "FULL"        # committed + received >= need
    NEGATIVE = "NEGATIVE"    # would make a column negative


@dataclass
class LedgerUpdate:
    result: LedgerResult
    available_before: int
    available_after: int
    shelter_id: int


async def ledger_reserve(
    session: "AsyncSession",
    shelter_id: int,
    qty: int,
) -> LedgerUpdate:
    """
    Atomically reserve qty portions at a shelter.

    Uses conditional UPDATE:
        UPDATE shelters
        SET committed = committed + qty, state_version = state_version + 1
        WHERE id = ? AND (need - received - committed) >= qty
    Returns FULL if the update matched 0 rows.
    """
    from sqlalchemy import text
    from sqlalchemy import select
    from app.db.models import Shelter

    # Read current state for the result report (non-locking)
    row = await session.execute(
        select(Shelter.need, Shelter.received, Shelter.committed)
        .where(Shelter.id == shelter_id)
    )
    before = row.one_or_none()
    if before is None:
        raise ValueError(f"Shelter {shelter_id} not found")

    avail_before = before.need - before.received - before.committed

    result = await session.execute(
        text(
            """
            UPDATE shelters
            SET committed = committed + :qty,
                state_version = state_version + 1,
                updated_at = NOW()
            WHERE id = :sid
              AND (need - received - committed) >= :qty
            RETURNING need, received, committed
            """
        ),
        {"qty": qty, "sid": shelter_id},
    )
    row2 = result.one_or_none()

    if row2 is None:
        return LedgerUpdate(
            result=LedgerResult.FULL,
            available_before=avail_before,
            available_after=avail_before,
            shelter_id=shelter_id,
        )

    avail_after = row2.need - row2.received - row2.committed
    return LedgerUpdate(
        result=LedgerResult.OK,
        available_before=avail_before,
        available_after=avail_after,
        shelter_id=shelter_id,
    )


async def ledger_release(
    session: "AsyncSession",
    shelter_id: int,
    qty: int,
) -> LedgerUpdate:
    """Release previously committed qty back to available."""
    from sqlalchemy import text

    result = await session.execute(
        text(
            """
            UPDATE shelters
            SET committed = GREATEST(0, committed - :qty),
                state_version = state_version + 1,
                updated_at = NOW()
            WHERE id = :sid
            RETURNING need, received, committed
            """
        ),
        {"qty": qty, "sid": shelter_id},
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Shelter {shelter_id} not found")

    avail = row.need - row.received - row.committed
    return LedgerUpdate(
        result=LedgerResult.OK,
        available_before=avail + qty,
        available_after=avail,
        shelter_id=shelter_id,
    )


async def ledger_confirm(
    session: "AsyncSession",
    shelter_id: int,
    qty: int,
) -> LedgerUpdate:
    """
    Move qty from committed → received on delivery confirmation.
    committed -= qty, received += qty.
    """
    from sqlalchemy import text

    result = await session.execute(
        text(
            """
            UPDATE shelters
            SET committed = GREATEST(0, committed - :qty),
                received  = received + :qty,
                state_version = state_version + 1,
                updated_at = NOW()
            WHERE id = :sid
            RETURNING need, received, committed
            """
        ),
        {"qty": qty, "sid": shelter_id},
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Shelter {shelter_id} not found")

    avail = row.need - row.received - row.committed
    return LedgerUpdate(
        result=LedgerResult.OK,
        available_before=avail,
        available_after=avail,
        shelter_id=shelter_id,
    )


async def ledger_walk_in(
    session: "AsyncSession",
    shelter_id: int,
    qty: int,
) -> LedgerUpdate:
    """
    Record a walk-in donation: received += qty (bypasses the lease system).
    Recomputes available and triggers re-evaluation (caller handles trigger).
    """
    from sqlalchemy import text

    result = await session.execute(
        text(
            """
            UPDATE shelters
            SET received = received + :qty,
                state_version = state_version + 1,
                updated_at = NOW()
            WHERE id = :sid
            RETURNING need, received, committed
            """
        ),
        {"qty": qty, "sid": shelter_id},
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Shelter {shelter_id} not found")

    avail = row.need - row.received - row.committed
    return LedgerUpdate(
        result=LedgerResult.OK,
        available_before=avail + qty,
        available_after=avail,
        shelter_id=shelter_id,
    )


async def ledger_demand_change(
    session: "AsyncSession",
    shelter_id: int,
    new_need: int,
) -> LedgerUpdate:
    """
    Update shelter need. If new_need < committed, returns available < 0 — caller handles reroute.
    """
    from sqlalchemy import text

    result = await session.execute(
        text(
            """
            UPDATE shelters
            SET need = :new_need,
                state_version = state_version + 1,
                updated_at = NOW()
            WHERE id = :sid
            RETURNING need, received, committed
            """
        ),
        {"new_need": new_need, "sid": shelter_id},
    )
    row = result.one_or_none()
    if row is None:
        raise ValueError(f"Shelter {shelter_id} not found")

    avail = row.need - row.received - row.committed
    return LedgerUpdate(
        result=LedgerResult.OK,
        available_before=avail,
        available_after=avail,
        shelter_id=shelter_id,
    )
