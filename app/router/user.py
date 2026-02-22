from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.clients.db import get_db
from app.services.user import user_service

router = APIRouter(prefix="/user", tags=["User"])


@router.get("/me")
async def read_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    user = request.state.user
    if not user:
        return Response(status_code=401, content="Unauthorized")
    return {"id": user.id, "email": user.email, "username": user.username}


@router.get("/{user_id}")
async def read_user(user_id: int, db: AsyncSession = Depends(get_db)):
    user = await user_service.get_user_by_id(db, user_id)
    if not user:
        return Response(status_code=404, content="User not found")
    return {"id": user.id, "email": user.email, "username": user.username}
