from fastapi import APIRouter, Depends, Query, Path, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.db import get_db
from app.schemas.response import APIResponse
from app.schemas.shl_solver import (
    SHLSolverHistorySerializer,
    SHLSolverHistoryListResponse,
)
from app.services.shl_solver import shl_solver_service
from app.depends.jwt_guard import verify_user

router = APIRouter(
    prefix="/shl_history",
    tags=["SHL Solver History"],
    dependencies=[Depends(verify_user)],
)


@router.get("", response_model=APIResponse[SHLSolverHistoryListResponse])
async def list_shl_history(
    page: int = Query(1, ge=1, description="Page number"),
    size: int = Query(10, ge=1, le=100, description="Page size"),
    db: AsyncSession = Depends(get_db),
):
    """
    Batch retrieve SHL solver history.
    """
    items, total = await shl_solver_service.get_history_list(db, page, size)

    return APIResponse(
        data=SHLSolverHistoryListResponse(
            items=items, total=total, page=page, size=size
        )
    )


@router.get("/{id}", response_model=APIResponse[SHLSolverHistorySerializer])
async def get_shl_history_detail(
    id: int = Path(..., description="History ID"), db: AsyncSession = Depends(get_db)
):
    """
    Get a single SHL solver history record.
    """
    item = await shl_solver_service.get_history_detail(db, id)

    if not item:
        return APIResponse(code=404, message="SHL Solver History not found")

    return APIResponse(data=item)
