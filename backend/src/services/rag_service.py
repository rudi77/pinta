"""RAG service for grounding quote generation in real material prices.

Uses OpenAI embeddings + in-process cosine similarity. This is intentionally
database-agnostic (works on SQLite & PostgreSQL without pgvector) so it's
usable in dev, tests, and small-scale production. For larger datasets the
similarity step should move to pgvector — the stored JSON embeddings can be
reused directly.
"""
from __future__ import annotations

import json
import logging
import math
from typing import List, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.settings import settings
from src.models.models import MaterialPrice
from src.services.ai_service import AIService

logger = logging.getLogger(__name__)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


class RagService:
    """Retrieve relevant materials from the knowledge base for a given query."""

    def __init__(self, ai_service: Optional[AIService] = None):
        self.ai_service = ai_service or AIService()

    @staticmethod
    def build_embedding_text(material: MaterialPrice) -> str:
        parts = [material.name]
        if material.manufacturer:
            parts.append(material.manufacturer)
        if material.category:
            parts.append(material.category)
        if material.description:
            parts.append(material.description)
        return " | ".join(parts)

    async def embed_material(self, material: MaterialPrice) -> str:
        """Compute and serialize the embedding for a material row."""
        text = self.build_embedding_text(material)
        vector = await self.ai_service.create_embedding(text)
        return json.dumps(vector)

    async def retrieve_materials(
        self,
        db: AsyncSession,
        query: str,
        region: Optional[str] = None,
        top_k: int = 5,
    ) -> List[MaterialPrice]:
        """Return the top-k materials most relevant to ``query``.

        If no embeddings are available (e.g. seeded without AI or fallback
        mock), falls back to a simple substring match on the name/description
        so the endpoint stays useful offline.
        """
        if not settings.rag_materials_enabled:
            return []

        stmt = select(MaterialPrice)
        if region:
            stmt = stmt.where(
                (MaterialPrice.region == region) | (MaterialPrice.region.is_(None))
            )
        result = await db.execute(stmt)
        all_materials: List[MaterialPrice] = list(result.scalars().all())
        if not all_materials:
            return []

        query_vector = await self.ai_service.create_embedding(query)
        has_query_embedding = any(abs(v) > 1e-9 for v in query_vector)

        scored: List[tuple[float, MaterialPrice]] = []
        for m in all_materials:
            score = 0.0
            if has_query_embedding and m.embedding:
                try:
                    vec = json.loads(m.embedding)
                    score = _cosine(query_vector, vec)
                except (json.JSONDecodeError, TypeError):
                    logger.warning("Invalid embedding on material id=%s", m.id)
            if score == 0.0:
                # Degraded substring fallback — keeps RAG useful without API key
                q = query.lower()
                haystack = " ".join(
                    filter(None, [m.name, m.manufacturer, m.category, m.description])
                ).lower()
                score = 1.0 if q and q in haystack else 0.0
            scored.append((score, m))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [m for score, m in scored[:top_k] if score > 0.0]

    @staticmethod
    def materials_to_prompt_context(materials: Sequence[MaterialPrice]) -> List[dict]:
        """Serialize retrieved materials for injection into the LLM system prompt."""
        return [
            {
                "name": m.name,
                "manufacturer": m.manufacturer,
                "category": m.category,
                "unit": m.unit,
                "price_net": m.price_net,
                "region": m.region,
            }
            for m in materials
        ]
