from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.clients.db import get_db
from app.schemas.shl_analyze import SHLAnalyzePayload
from app.services.shl_analyze import shl_service

router = APIRouter(prefix="/shl_analyze", tags=["SHL Analyze"])


@router.post("/")
async def process_shl_analyze(
    payload: SHLAnalyzePayload, db: AsyncSession = Depends(get_db)
):

    result = shl_service.analyze(payload)
    return result
