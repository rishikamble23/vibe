"""
Reaper: persisted scheduled_actions executed every 2-5 s.

Uses FOR UPDATE SKIP LOCKED so multiple workers never double-process.
Handles: NUDGE, ALERT_STANDBY, EXPIRE, SMS_FALLBACK, EXPIRY_SWEEP.

Phase 3: 3.8, 3.9 — escalation ladder driven by DB deadlines.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

from app.clock import get_clock
from app.config_loader import get_reaper_config

log = logging.getLogger(__name__)


async def process_scheduled_actions(session: "AsyncSession") -> int:
    """
    Process all scheduled_actions where run_at <= now() and processed = false.
    Uses SKIP LOCKED to be safe with multiple workers.

    Returns number of actions processed.
    """
    from sqlalchemy import text

    now = get_clock().now()
    config = get_reaper_config()
    batch_size = config.get("batch_size", 50)

    # Fetch and lock a batch
    rows = await session.execute(
        text(
            """
            SELECT id, type, lease_id, lot_id, payload
            FROM scheduled_actions
            WHERE processed = false
              AND run_at <= :now
            ORDER BY run_at
            LIMIT :batch_size
            FOR UPDATE SKIP LOCKED
            """
        ),
        {"now": now, "batch_size": batch_size},
    )
    actions = rows.fetchall()
    processed = 0

    for action in actions:
        try:
            await _dispatch_action(session, action)
            await session.execute(
                text(
                    "UPDATE scheduled_actions SET processed = true WHERE id = :id"
                ),
                {"id": action.id},
            )
            processed += 1
        except Exception as exc:
            log.error("Reaper action %d failed: %s", action.id, exc, exc_info=True)

    return processed


async def expire_overdue_lots(session: "AsyncSession") -> int:
    """
    Expiry sweep (2.8): lots past deliver_by with status UNASSIGNED become EXPIRED.
    Returns count of lots expired.
    """
    from sqlalchemy import text

    now = get_clock().now()
    result = await session.execute(
        text(
            """
            UPDATE lots
            SET status = 'expired', updated_at = :now
            WHERE status = 'unassigned'
              AND deliver_by < :now
            RETURNING id
            """
        ),
        {"now": now},
    )
    rows = result.fetchall()
    count = len(rows)
    if count:
        log.info("Reaper expired %d lots", count)
    return count


async def expire_overdue_leases(session: "AsyncSession") -> int:
    """
    Expire soft leases past expires_at.
    Returns count of leases expired.
    Also marks the underlying lot back to UNASSIGNED for reassignment.
    """
    from sqlalchemy import text

    now = get_clock().now()
    result = await session.execute(
        text(
            """
            UPDATE leases
            SET status = 'expired', updated_at = :now
            WHERE status IN ('offered', 'accepted', 'arrived_donor')
              AND expires_at < :now
            RETURNING id, lot_id, shelter_id, qty
            """
        ),
        {"now": now},
    )
    rows = result.fetchall()
    count = len(rows)

    for row in rows:
        # Release shelter reservation
        await session.execute(
            text(
                """
                UPDATE shelters
                SET committed = GREATEST(0, committed - :qty),
                    state_version = state_version + 1,
                    updated_at = :now
                WHERE id = :sid
                """
            ),
            {"qty": row.qty, "sid": row.shelter_id, "now": now},
        )
        # Return lot to UNASSIGNED
        await session.execute(
            text(
                """
                UPDATE lots
                SET status = 'unassigned', updated_at = :now
                WHERE id = :lot_id
                  AND status = 'leased'
                """
            ),
            {"lot_id": row.lot_id, "now": now},
        )
        log.info("Reaper expired lease %d, lot %d returned to pool", row.id, row.lot_id)

    return count


async def _dispatch_action(session: "AsyncSession", action: object) -> None:
    """Route a scheduled action to the right handler."""
    action_type = action.type  # type: ignore[attr-defined]

    if action_type == "nudge":
        await _handle_nudge(session, action)
    elif action_type == "alert_standby":
        await _handle_alert_standby(session, action)
    elif action_type == "expire":
        await _handle_expire(session, action)
    elif action_type == "sms_fallback":
        await _handle_sms_fallback(session, action)
    elif action_type == "expiry_sweep":
        await expire_overdue_lots(session)
    else:
        log.warning("Unknown scheduled action type: %s", action_type)


async def _handle_nudge(session: "AsyncSession", action: object) -> None:
    from sqlalchemy import text

    lease_id = action.lease_id  # type: ignore[attr-defined]
    now = get_clock().now()

    # Insert notification outbox entry
    await session.execute(
        text(
            """
            INSERT INTO notifications_outbox (channel, recipient, message, lease_id, created_at, status)
            SELECT 'push', r.phone, 'Your pickup window is closing soon. Please confirm progress.', :lid, :now, 'pending'
            FROM leases l
            JOIN riders r ON r.id = l.rider_id
            WHERE l.id = :lid AND l.status IN ('offered', 'accepted', 'arrived_donor')
            """
        ),
        {"lid": lease_id, "now": now},
    )
    log.info("Nudge sent for lease %d", lease_id)


async def _handle_alert_standby(session: "AsyncSession", action: object) -> None:
    log.info("Standby alert for lease %d", action.lease_id)  # type: ignore[attr-defined]
    # Full hot-standby logic wired in Phase 3 service layer


async def _handle_expire(session: "AsyncSession", action: object) -> None:
    from sqlalchemy import text
    now = get_clock().now()
    lease_id = action.lease_id  # type: ignore[attr-defined]

    await session.execute(
        text(
            """
            UPDATE leases
            SET status = 'expired', updated_at = :now
            WHERE id = :lid
              AND status IN ('offered', 'accepted', 'arrived_donor')
            """
        ),
        {"lid": lease_id, "now": now},
    )
    log.info("Forced expiry lease %d", lease_id)


async def _handle_sms_fallback(session: "AsyncSession", action: object) -> None:
    from sqlalchemy import text
    lease_id = action.lease_id  # type: ignore[attr-defined]
    now = get_clock().now()

    await session.execute(
        text(
            """
            INSERT INTO notifications_outbox (channel, recipient, message, lease_id, created_at, status)
            SELECT 'sms', r.phone, 'SHELFLINE: Your batch pickup window is closing. Reply YES to confirm or the lot will be reassigned.', :lid, :now, 'pending'
            FROM leases l
            JOIN riders r ON r.id = l.rider_id
            WHERE l.id = :lid
            """
        ),
        {"lid": lease_id, "now": now},
    )
    log.info("SMS fallback for lease %d", lease_id)


class Reaper:
    """
    Background reaper loop. Runs every `interval_seconds`.
    Uses SimClock so tests can fast-forward time.
    """

    def __init__(self, engine: "AsyncEngine", interval_seconds: Optional[float] = None) -> None:
        self.engine = engine
        config = get_reaper_config()
        self.interval = interval_seconds or config.get("interval_seconds", 5)
        self._running = False
        self._task: Optional[asyncio.Task] = None  # type: ignore[type-arg]

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._loop())
        log.info("Reaper started (interval=%.1fs)", self.interval)

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        log.info("Reaper stopped")

    async def _loop(self) -> None:
        from sqlalchemy.ext.asyncio import AsyncSession

        while self._running:
            try:
                async with AsyncSession(self.engine) as session:
                    async with session.begin():
                        await expire_overdue_leases(session)
                        await expire_overdue_lots(session)
                        await process_scheduled_actions(session)
            except Exception as exc:
                log.error("Reaper loop error: %s", exc, exc_info=True)

            await asyncio.sleep(self.interval)
