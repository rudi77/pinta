from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from src.core.quota_scheduler import _next_month_boundary
from src.models.models import User
from src.services.quota_service import QuotaService


class TestQuotaScheduler:
    """Scheduler is wired via main.py lifespan; this covers its invariants."""

    def test_next_month_boundary_mid_month(self):
        assert _next_month_boundary(
            datetime(2026, 4, 17, 10, 0, tzinfo=timezone.utc)
        ) == datetime(2026, 5, 1, 0, 5, tzinfo=timezone.utc)

    def test_next_month_boundary_december_rollover(self):
        assert _next_month_boundary(
            datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)
        ) == datetime(2027, 1, 1, 0, 5, tzinfo=timezone.utc)

    async def test_reset_monthly_quotas_zeroes_counter_and_stamps_reset(self, test_session):
        """Confirms reset clears the counter AND records last_quota_reset."""
        user = User(
            email="reset@example.com",
            username="reset-user",
            hashed_password="x",
            is_active=True,
            quotes_this_month=7,
            last_quota_reset=None,
        )
        test_session.add(user)
        await test_session.commit()

        before = datetime.now(timezone.utc)
        info = await QuotaService().reset_monthly_quotas(test_session)
        assert info["users_affected"] >= 1

        refreshed = (
            await test_session.execute(select(User).where(User.id == user.id))
        ).scalar_one()
        assert refreshed.quotes_this_month == 0
        assert refreshed.last_quota_reset is not None
        stamp = refreshed.last_quota_reset
        stamp_utc = stamp if stamp.tzinfo else stamp.replace(tzinfo=timezone.utc)
        assert stamp_utc >= before
