from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.clients.ff14 import FFLogsAPIError
from app.schemas.ff14_v2 import FF14V2GraphQLRequest
from app.schemas.response import APIResponse
from app.services.ff14_v2 import ff14_v2_service


router = APIRouter(
    prefix="/ff14_logs/v2",
    tags=["FF14 Logs V2"],
)


async def _proxy_graphql(payload: FF14V2GraphQLRequest):
    try:
        result = await ff14_v2_service.execute_query(
            query=payload.query,
            variables=payload.variables,
            operation_name=payload.operation_name,
            endpoint=payload.scope,
            access_token=payload.access_token,
        )
    except FFLogsAPIError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": exc.message,
                "data": exc.payload,
            },
        )
    return APIResponse(data=result)


@router.post("/graphql", response_model=APIResponse[Any])
async def proxy_graphql(payload: FF14V2GraphQLRequest):
    return await _proxy_graphql(payload)
