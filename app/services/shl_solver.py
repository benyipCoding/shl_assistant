from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, Tuple, List

from app.models.shl_solver import SHLSolverHistory
from app.models.user import User


class SHLSolverService:
    async def get_history_list(
        self, db: AsyncSession, page: int, size: int, user_id: Optional[int] = None
    ) -> Tuple[List[dict], int]:
        """
        Get paginated list of SHL solver history.
        """
        offset = (page - 1) * size

        # Base query to select SHLSolverHistory and User.username
        stmt = (
            select(SHLSolverHistory, User.username)
            .join(User, SHLSolverHistory.user_id == User.id)
            .order_by(desc(SHLSolverHistory.created_at))
        )

        if user_id:
            stmt = stmt.where(SHLSolverHistory.user_id == user_id)

        # Calculate total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = await db.scalar(count_stmt) or 0

        # Apply pagination
        stmt = stmt.offset(offset).limit(size)
        result = await db.execute(stmt)

        # Process results to match schema expectation (flat dict or object with joined fields)
        items = []
        for history, username in result:
            # Create a dict or modify object to include username
            # Pydantic's from_attributes can handle objects if they have the attribute,
            # but SHLSolverHistory doesn't have username.
            # So we construct a dict representation or a wrapper.
            item_dict = history.__dict__.copy()
            item_dict["username"] = username
            items.append(item_dict)

        return items, total

    async def get_history_detail(
        self, db: AsyncSession, history_id: int
    ) -> Optional[dict]:
        """
        Get a single SHL solver history record by ID.
        """
        stmt = (
            select(SHLSolverHistory, User.username)
            .join(User, SHLSolverHistory.user_id == User.id)
            .where(SHLSolverHistory.id == history_id)
        )

        result = await db.execute(stmt)
        row = result.first()

        if row:
            history, username = row
            item_dict = history.__dict__.copy()
            item_dict["username"] = username
            return item_dict

        return None


shl_solver_service = SHLSolverService()
