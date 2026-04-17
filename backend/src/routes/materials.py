"""Material knowledge-base admin + search endpoints (Phase 2 RAG).

Superuser-only for writes so the price catalog stays curated. Search is
available to every authenticated user because contractors will eventually want
to browse/pick materials directly in the quote builder.
"""
from __future__ import annotations

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import get_current_user
from src.models.models import MaterialPrice, User
from src.schemas.schemas import (
    MaterialPriceCreate,
    MaterialPriceResponse,
    MaterialPriceUpdate,
    MaterialSearchResponse,
)
from src.services.ai_service import AIService
from src.services.rag_service import RagService

router = APIRouter(prefix="/api/v1/materials", tags=["materials"])
logger = logging.getLogger(__name__)

ai_service = AIService()
rag_service = RagService(ai_service=ai_service)


def _require_superuser(user: User) -> None:
    if not user.is_superuser:
        raise HTTPException(status_code=403, detail="Superuser access required.")


@router.post("", response_model=MaterialPriceResponse, status_code=201)
async def create_material(
    payload: MaterialPriceCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new material and compute its embedding on write."""
    _require_superuser(current_user)

    material = MaterialPrice(**payload.model_dump())
    material.embedding = await rag_service.embed_material(material)
    db.add(material)
    await db.commit()
    await db.refresh(material)
    logger.info("Material created id=%s name=%s", material.id, material.name)
    return material


@router.get("", response_model=List[MaterialPriceResponse])
async def list_materials(
    category: Optional[str] = None,
    region: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List materials with optional category/region filter."""
    stmt = select(MaterialPrice)
    if category:
        stmt = stmt.where(MaterialPrice.category == category)
    if region:
        stmt = stmt.where(MaterialPrice.region == region)
    stmt = stmt.limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("/search", response_model=MaterialSearchResponse)
async def search_materials(
    q: str = Query(..., min_length=2, description="Natural-language query"),
    region: Optional[str] = None,
    top_k: int = Query(default=5, ge=1, le=20),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Semantic search over the material catalog (RAG retrieval)."""
    materials = await rag_service.retrieve_materials(
        db=db, query=q, region=region, top_k=top_k,
    )
    return MaterialSearchResponse(
        query=q,
        results=materials,
        count=len(materials),
    )


@router.get("/{material_id}", response_model=MaterialPriceResponse)
async def get_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    material = await db.get(MaterialPrice, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    return material


@router.patch("/{material_id}", response_model=MaterialPriceResponse)
async def update_material(
    material_id: int,
    payload: MaterialPriceUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a material. Re-computes the embedding if any semantic field changed."""
    _require_superuser(current_user)

    material = await db.get(MaterialPrice, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")

    update_data = payload.model_dump(exclude_unset=True)
    semantic_fields = {"name", "manufacturer", "category", "description"}
    needs_reembed = any(field in update_data for field in semantic_fields)

    for field, value in update_data.items():
        setattr(material, field, value)

    if needs_reembed:
        material.embedding = await rag_service.embed_material(material)

    await db.commit()
    await db.refresh(material)
    return material


@router.delete("/{material_id}", status_code=204)
async def delete_material(
    material_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    _require_superuser(current_user)

    material = await db.get(MaterialPrice, material_id)
    if not material:
        raise HTTPException(status_code=404, detail="Material not found")
    await db.delete(material)
    await db.commit()
