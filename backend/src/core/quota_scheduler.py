"""Monthly quota reset scheduler.

Runs a single background task that sleeps until the 1st of the next month
(00:05 UTC) and then resets `User.quotes_this_month` for all users. On startup
it also runs a catch-up reset if the latest `User.last_quota_reset` is in a
prior calendar month, so a deployment or outage that straddles a month
boundary does not leave users stuck at their previous counter.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import func, select

from src.core.database import AsyncSessionLocal
from src.models.models import User
from src.services.quota_service import QuotaService

logger = logging.getLogger(__name__)

_scheduler_task: Optional[asyncio.Task] = None


def _next_month_boundary(now: datetime) -> datetime:
    """Return the 1st of the month following `now` at 00:05 UTC."""
    if now.month == 12:
        return datetime(now.year + 1, 1, 1, 0, 5, tzinfo=timezone.utc)
    return datetime(now.year, now.month + 1, 1, 0, 5, tzinfo=timezone.utc)


async def _needs_catch_up_reset() -> bool:
    """True if no user has been reset during the current UTC calendar month."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(func.max(User.last_quota_reset)))
        latest = result.scalar()

    if latest is None:
        # No user record at all, or none ever reset - still run once so the
        # scheduler has a stable baseline.
        return True

    latest_utc = latest if latest.tzinfo else latest.replace(tzinfo=timezone.utc)
    now = datetime.now(timezone.utc)
    return (latest_utc.year, latest_utc.month) < (now.year, now.month)


async def _run_reset() -> None:
    quota_service = QuotaService()
    async with AsyncSessionLocal() as db:
        info = await quota_service.reset_monthly_quotas(db)
    logger.info("Monthly quota reset executed: %s", info)


async def _scheduler_loop() -> None:
    try:
        if await _needs_catch_up_reset():
            logger.info("Catch-up monthly quota reset needed; running now")
            try:
                await _run_reset()
            except Exception:
                logger.exception("Catch-up quota reset failed; scheduler continues")
    except Exception:
        logger.exception("Could not determine catch-up state; scheduler continues")

    while True:
        now = datetime.now(timezone.utc)
        target = _next_month_boundary(now)
        delay = max((target - now).total_seconds(), 1.0)
        logger.info("Next monthly quota reset at %s (in %.0fs)", target.isoformat(), delay)
        try:
            await asyncio.sleep(delay)
        except asyncio.CancelledError:
            raise

        try:
            await _run_reset()
        except Exception:
            logger.exception("Scheduled quota reset failed; will retry next cycle")


async def start_quota_scheduler() -> None:
    """Start the monthly quota reset task. Safe to call multiple times."""
    global _scheduler_task
    if _scheduler_task and not _scheduler_task.done():
        return
    _scheduler_task = asyncio.create_task(_scheduler_loop(), name="quota_scheduler")
    logger.info("Quota scheduler started")


async def stop_quota_scheduler() -> None:
    """Cancel and await the running scheduler task."""
    global _scheduler_task
    if _scheduler_task is None:
        return
    _scheduler_task.cancel()
    try:
        await _scheduler_task
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("Error while stopping quota scheduler")
    _scheduler_task = None
    logger.info("Quota scheduler stopped")
