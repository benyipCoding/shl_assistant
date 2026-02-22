from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession
from app.clients.db import get_db
from app.schemas.response import APIResponse
from app.schemas.auth import AuthRequest, UserSerializer
from app.services.auth import auth_service
from app.core.config import settings
from app.clients.redis_client import get_redis
import redis.asyncio as redis
from fastapi import Request


router = APIRouter(prefix="/auth", tags=["Auth"])

ACCESS_TOKEN_KEY = "access_token"
REFRESH_TOKEN_KEY = "refresh_token"


@router.post("/register", response_model=APIResponse[UserSerializer])
async def register(
    payload: AuthRequest, response: Response, db: AsyncSession = Depends(get_db)
):
    # Only email & password provided by frontend. Use email local part as username.
    existing = await auth_service.get_by_email(db, payload.email)
    if existing:
        return APIResponse(code=409, message="Email already registered")

    username = payload.email.split("@")[0]
    user = await auth_service.create_user(
        db, username=username, email=payload.email, password=payload.password
    )
    return APIResponse(data=user)


@router.post("/login", response_model=APIResponse[UserSerializer])
async def login(
    payload: AuthRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis: redis.Redis = Depends(get_redis),
):
    user = await auth_service.authenticate_user(db, payload.email, payload.password)
    if not user:
        return APIResponse(code=401, message="Invalid credentials")

    data = {"sub": str(user.id), "email": user.email}
    access_token = auth_service.create_access_token(data)
    refresh_token = auth_service.create_refresh_token(data)

    await redis.set(
        f"refresh_token:{refresh_token}",
        str(user.id),
        ex=settings.jwt_refresh_token_expires_days * 24 * 3600,
    )

    response.set_cookie(
        key=ACCESS_TOKEN_KEY,
        value=access_token,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_access_token_expires_minutes * 60,
    )
    response.set_cookie(
        key=REFRESH_TOKEN_KEY,
        value=refresh_token,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_refresh_token_expires_days * 24 * 3600,
    )

    return APIResponse(data=user)


@router.post("/logout", response_model=APIResponse)
async def logout(
    request: Request, response: Response, redis: redis.Redis = Depends(get_redis)
):
    refresh_token = request.cookies.get(REFRESH_TOKEN_KEY)

    # 如果找到了 refresh_token，将其从 Redis 中作废
    if refresh_token:
        await redis.delete(f"refresh_token:{refresh_token}")

    # 清除客户端的 Cookie
    response.delete_cookie(
        key=ACCESS_TOKEN_KEY,
        secure=settings.cookie_secure,
        httponly=settings.cookie_httponly,
        samesite=settings.cookie_samesite,
    )
    response.delete_cookie(
        key=REFRESH_TOKEN_KEY,
        secure=settings.cookie_secure,
        httponly=settings.cookie_httponly,
        samesite=settings.cookie_samesite,
    )

    return APIResponse(message="Successfully logged out")


# TODO: 可以增加一个 /refresh 接口，允许用户在 access token 过期后使用 refresh token 获取新的 access token，而不需要重新登录
# 定义一个特殊的code 411用来表示 refresh token 无效或过期，前端收到这个code后可以直接跳转到登录页，而不需要显示错误信息
@router.post("/refresh", response_model=APIResponse[UserSerializer])
async def refresh_token(
    request: Request,
    response: Response,
    redis: redis.Redis = Depends(get_redis),
):
    refresh_token = request.cookies.get(REFRESH_TOKEN_KEY)

    if not refresh_token:
        return APIResponse(code=411, message="Refresh token not found")

    user_id = await redis.get(f"refresh_token:{refresh_token}")
    if not user_id:
        return APIResponse(code=411, message="Invalid refresh token")

    user = await auth_service.get_user_by_id(user_id)
    if not user:
        return APIResponse(code=404, message="User not found")

    access_token = auth_service.create_access_token(
        {"sub": str(user.id), "email": user.email}
    )
    response.set_cookie(
        key=ACCESS_TOKEN_KEY,
        value=access_token,
        httponly=settings.cookie_httponly,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        max_age=settings.jwt_access_token_expires_minutes * 60,
    )

    return APIResponse(data=user)
