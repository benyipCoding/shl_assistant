from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from sqlalchemy import select


class UserService:
    async def get_user_by_id(self, db: AsyncSession, user_id: int) -> Optional[User]:
        stmt = select(User).where(User.id == user_id)
        result = await db.execute(stmt)
        return result.scalars().first()

    async def get_user_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        result = await db.execute(stmt)
        return result.scalars().first()


user_service = UserService()
