"""ChannelLink resolver — maps an external channel identity to a Pinta user.

Two paths per inbound message:

1. Existing link:  ``(channel, external_id)`` → user. Update last_seen_at.
2. No link yet:    create a shadow user (``is_anonymous_shadow=True``) +
   a fresh ChannelLink. The user can later upgrade by claiming a
   linking_token from the Web Dashboard via ``/start <token>`` in Telegram.

A shadow user has:
- email = ``tg-<external_id>@<channel>.shadow``  (unique, dummy)
- username = ``<channel>-<external_id>``
- random hashed_password (never used for login)
- is_active=True, is_verified=False (so password-login is blocked but the
  agent can still operate)
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import get_password_hash
from src.models.models import ChannelLink, User

logger = logging.getLogger(__name__)


async def resolve_or_create_shadow_user(
    db: AsyncSession,
    *,
    channel: str,
    external_id: str,
    display_name: str | None = None,
) -> tuple[User, ChannelLink, bool]:
    """Return (user, link, was_created).

    On every call the link's last_seen_at is bumped.
    """
    stmt = (
        select(ChannelLink)
        .where(ChannelLink.channel == channel)
        .where(ChannelLink.external_id == external_id)
    )
    link = (await db.execute(stmt)).scalar_one_or_none()

    if link is not None:
        link.last_seen_at = datetime.utcnow()
        if display_name and not link.display_name:
            link.display_name = display_name
        await db.flush()
        await db.commit()
        user = await db.get(User, link.user_id)
        if user is None:  # link orphaned — recover by recreating below
            await db.delete(link)
            await db.flush()
        else:
            return user, link, False

    # Create shadow user + link
    safe_id = "".join(c for c in external_id if c.isalnum() or c in "_-")[:60]
    base_username = f"{channel}-{safe_id}"
    username = base_username
    suffix = 0
    while (await db.execute(
        select(User).where(User.username == username)
    )).scalar_one_or_none() is not None:
        suffix += 1
        username = f"{base_username}-{suffix}"

    user = User(
        username=username,
        email=f"tg-{safe_id}-{secrets.token_hex(4)}@{channel}.shadow",
        hashed_password=get_password_hash(secrets.token_urlsafe(32)),
        company_name=display_name or username,
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()

    link = ChannelLink(
        user_id=user.id,
        channel=channel,
        external_id=external_id,
        display_name=display_name,
        is_anonymous_shadow=True,
    )
    db.add(link)
    await db.flush()
    await db.commit()
    logger.info(
        "channel_link.shadow_user_created channel=%s external_id=%s user_id=%s",
        channel, external_id, user.id,
    )
    return user, link, True


# ── Linking-Token flow (web → bot) ────────────────────────────────────────

LINKING_TOKEN_TTL_HOURS = 24


async def issue_linking_token(
    db: AsyncSession, user: User, *, channel: str = "telegram",
) -> tuple[str, datetime]:
    """Generate a short-lived token a Web user can paste into the bot."""
    token = secrets.token_urlsafe(24)
    expires = datetime.utcnow() + timedelta(hours=LINKING_TOKEN_TTL_HOURS)

    # Park the token on a placeholder ChannelLink with external_id=""+token
    # so we can find it later without a separate table. Cleared when consumed.
    placeholder = ChannelLink(
        user_id=user.id,
        channel=channel,
        external_id=f"pending-{token}",
        linking_token=token,
        linking_token_expires_at=expires,
        is_anonymous_shadow=False,
    )
    db.add(placeholder)
    await db.flush()
    await db.commit()
    return token, expires


async def consume_linking_token(
    db: AsyncSession,
    *,
    token: str,
    channel: str,
    external_id: str,
    display_name: str | None = None,
) -> User | None:
    """Apply a linking token: move the channel identity from a shadow user
    to the real Pinta user that issued the token. Returns the real user,
    or ``None`` if the token is invalid/expired.
    """
    stmt = (
        select(ChannelLink)
        .where(ChannelLink.linking_token == token)
        .where(ChannelLink.channel == channel)
    )
    placeholder = (await db.execute(stmt)).scalar_one_or_none()
    if placeholder is None:
        return None
    if (
        placeholder.linking_token_expires_at
        and placeholder.linking_token_expires_at < datetime.utcnow()
    ):
        await db.delete(placeholder)
        await db.commit()
        return None

    real_user_id = placeholder.user_id
    real_user = await db.get(User, real_user_id)
    if real_user is None:
        await db.delete(placeholder)
        await db.commit()
        return None

    # Find the existing channel link for this external_id (typically a
    # shadow link created earlier when the bot first saw this chat).
    existing_stmt = (
        select(ChannelLink)
        .where(ChannelLink.channel == channel)
        .where(ChannelLink.external_id == external_id)
    )
    existing = (await db.execute(existing_stmt)).scalar_one_or_none()

    if existing is None:
        # Re-purpose the placeholder
        placeholder.external_id = external_id
        placeholder.display_name = display_name
        placeholder.linking_token = None
        placeholder.linking_token_expires_at = None
        placeholder.is_anonymous_shadow = False
    else:
        # Reassign existing link from shadow user to real user
        old_user_id = existing.user_id
        existing.user_id = real_user.id
        existing.is_anonymous_shadow = False
        if display_name:
            existing.display_name = display_name
        # Drop the placeholder (token used)
        await db.delete(placeholder)
        # Optional: leave the now-orphaned shadow user in DB for forensics;
        # could be reaped by a periodic job. We leave it for now.
        logger.info(
            "channel_link.relinked channel=%s external_id=%s "
            "from_user=%s to_user=%s",
            channel, external_id, old_user_id, real_user.id,
        )

    await db.flush()
    await db.commit()
    return real_user
