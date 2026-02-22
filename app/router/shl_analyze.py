from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.clients.db import get_db
from app.schemas.shl_analyze import SHLAnalyzePayload
from app.services.shl_analyze import shl_service
from app.schemas.response import APIResponse
from app.schemas.shl_analyze import SHLAnalyzeResult
from fastapi_limiter.depends import RateLimiter
from fastapi import Request
from app.services.llms import llms_service
from app.depends.jwt_guard import verify_user


router = APIRouter(
    prefix="/shl_analyze", tags=["SHL Analyze"], dependencies=[Depends(verify_user)]
)


async def ai_rate_limit_key(request: Request):
    user = getattr(request.state, "user", None)
    if user:
        return f"user:{user.id}"
    return f"ip:{request.client.host}"


@router.post(
    "",
    response_model=APIResponse[SHLAnalyzeResult],
    dependencies=[
        Depends(RateLimiter(times=3, seconds=60, identifier=ai_rate_limit_key)),
    ],
)
async def process_shl_analyze(
    request: Request,
    payload: SHLAnalyzePayload,
    db: AsyncSession = Depends(get_db),
):
    client_ip = request.client.host
    try:
        llm = await llms_service.get_by_id(db, payload.llmId)
        if not llm or not llm.enabled:
            return APIResponse(message="LLM not found or disabled", code=404)

        result = await shl_service.analyze(payload, db, client_ip, llm.key)
        return APIResponse(data=result)
    except Exception as e:
        return APIResponse(message=str(e), code=500)
