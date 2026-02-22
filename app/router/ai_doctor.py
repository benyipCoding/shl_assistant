from fastapi import APIRouter
from app.schemas.ai_doctor import AnalyzePayload

from app.schemas.response import APIResponse
from app.schemas.ai_doctor import AnalyzeResponse
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from app.clients.db import get_db
from fastapi_limiter.depends import RateLimiter
from fastapi import Request
from app.utils.helpers import ai_rate_limit_key
from app.depends.jwt_guard import verify_user
from app.services.ai_doctor import ai_doctor_service
from app.services.llms import llms_service


router = APIRouter(
    prefix="/ai_doctor", tags=["AI Doctor"], dependencies=[Depends(verify_user)]
)


@router.post(
    "/analyze",
    response_model=APIResponse[AnalyzeResponse],
    dependencies=[
        Depends(RateLimiter(times=3, seconds=60, identifier=ai_rate_limit_key)),
    ],
)
async def process_analyze(
    request: Request, payload: AnalyzePayload, db: AsyncSession = Depends(get_db)
):
    llm = await llms_service.get_by_key(db, payload.llmKey)
    if not llm or not llm.enabled:
        return APIResponse(message="LLM not found or disabled", code=404)

    result = await ai_doctor_service.analyze(request, payload, db)
    return APIResponse(data=result)
