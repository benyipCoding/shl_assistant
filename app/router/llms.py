from fastapi import APIRouter
from app.services.llms import llms_service
from app.clients.db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from typing import List
from app.schemas.response import APIResponse
from app.schemas.llms import LLMSerializer


router = APIRouter(prefix="/llms", tags=["LLMs"])


# GET /llms
@router.get("", response_model=APIResponse[List[LLMSerializer]])
async def list_llms(db: AsyncSession = Depends(get_db)):
    result = await llms_service.list_all(db)
    return APIResponse(data=result)


# GET /llms/{key}
@router.get("/{key}", response_model=APIResponse[LLMSerializer])
async def get_llm_by_key(key: str, db: AsyncSession = Depends(get_db)):
    llm = await llms_service.get_by_key(db, key)
    if llm is None:
        return APIResponse(code=404, message="LLM not found")
    return APIResponse(data=llm)
