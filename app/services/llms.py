from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.llms import LLMs


class LLMsService:
    """Minimal service for querying LLM records.

    Methods are async and expect an `AsyncSession` from `app.db.get_db`.
    """

    async def get_by_key(self, db: AsyncSession, key: str) -> Optional[LLMs]:
        """Return the first `LLMs` record matching `key`, or `None`."""
        stmt = select(LLMs).where(LLMs.key == key)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def list_all(self, db: AsyncSession) -> List[LLMs]:
        """Return all `LLMs` records ordered by `id`."""
        stmt = select(LLMs).order_by(LLMs.id)
        result = await db.execute(stmt)
        return result.scalars().all()


# export a module-level instance for convenience
llms_service = LLMsService()
