"""Mandatory onboarding for new users.

After register + email-verify, the frontend gates the dashboard behind
`GET /onboarding/status.completed`. The user fills out three steps:
company info → cost params → optional logo, then `POST /complete` flips
`User.onboarding_completed_at`.
"""
from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import get_current_user
from src.models.models import User
from src.schemas.schemas import (
    OnboardingPayload,
    OnboardingStatus,
    UserResponse,
)

router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])

_ALLOWED_LOGO_MIMES = {"image/png", "image/jpeg", "image/webp", "image/svg+xml"}
_LOGO_MAX_BYTES = 1 * 1024 * 1024  # 1 MB
_LOGO_DIR = Path("uploads/logos")
_FILENAME_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def _missing_fields(user: User) -> List[str]:
    missing: List[str] = []
    if not user.company_name:
        missing.append("company_name")
    if not user.address:
        missing.append("address")
    if user.hourly_rate is None:
        missing.append("hourly_rate")
    if user.material_cost_markup is None:
        missing.append("material_cost_markup")
    return missing


@router.get("/status", response_model=OnboardingStatus)
async def get_onboarding_status(
    current_user: User = Depends(get_current_user),
):
    return OnboardingStatus(
        completed=current_user.onboarding_completed_at is not None,
        missing=_missing_fields(current_user),
        user=UserResponse.model_validate(current_user),
    )


@router.post("/complete", response_model=UserResponse)
async def complete_onboarding(
    payload: OnboardingPayload,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Idempotent: re-running overwrites existing values and re-stamps."""
    current_user.company_name = payload.company_name
    current_user.address = payload.address
    current_user.vat_id = payload.vat_id
    current_user.hourly_rate = payload.hourly_rate
    current_user.material_cost_markup = payload.material_cost_markup
    current_user.onboarding_completed_at = datetime.utcnow()
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/logo", response_model=UserResponse)
async def upload_logo(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in _ALLOWED_LOGO_MIMES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Logo muss PNG, JPEG, WebP oder SVG sein (got {file.content_type}).",
        )

    contents = await file.read()
    if len(contents) > _LOGO_MAX_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Logo darf max. {_LOGO_MAX_BYTES // 1024} KB groß sein.",
        )

    user_dir = _LOGO_DIR / str(current_user.id)
    user_dir.mkdir(parents=True, exist_ok=True)

    raw_name = file.filename or "logo"
    safe = _FILENAME_SAFE.sub("_", raw_name)[:80] or "logo"
    final_name = f"{uuid.uuid4().hex[:8]}_{safe}"
    target = (user_dir / final_name).resolve()

    # Defence-in-depth: refuse anything that escapes the user's logo dir,
    # even though the filename was already sanitised above.
    user_dir_resolved = user_dir.resolve()
    if not str(target).startswith(str(user_dir_resolved)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungültiger Dateiname.",
        )

    target.write_bytes(contents)

    # Store path relative to the uploads root so the value survives container
    # mount-point changes and doesn't leak the host filesystem layout.
    current_user.logo_path = str(target.relative_to(_LOGO_DIR.resolve()).as_posix())
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.delete("/logo", response_model=UserResponse)
async def delete_logo(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Forget the logo path. The file on disk is left in place — it's
    user-uploaded content and a separate cleanup job can reap orphans
    later. No-op if no logo is set."""
    current_user.logo_path = None
    db.add(current_user)
    await db.commit()
    await db.refresh(current_user)
    return current_user
