import jwt
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from app.core.config import settings
from app.clients import db
from app.services.user import user_service
from app.models.user import User


class UserAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 默认 None，表示未登录或无效 Token
        request.state.user = None

        # 1. 尝试从 Cookie 获取 Token
        token = request.cookies.get("access_token")

        # 2. 如果 Cookie 中没有，尝试从 Authorization Header 获取
        if not token:
            auth_header = request.headers.get("Authorization")
            if auth_header:
                parts = auth_header.split()
                if len(parts) == 2 and parts[0].lower() == "bearer":
                    token = parts[1]

        if not token:
            return await call_next(request)

        try:
            # 3. 解码 JWT
            payload = jwt.decode(
                token,
                settings.jwt_secret_key,
                algorithms=[settings.jwt_algorithm],
            )

            # 校验 token 类型是否为 access
            if payload.get("type") != "access":
                return await call_next(request)

            user_id: str = payload.get("sub")
            if user_id is None:
                return await call_next(request)

            # 4. 查询数据库获取用户
            # 注意：此处需要拿到 Session，db.async_session 在 lifespan 中初始化
            if db.async_session:
                async with db.async_session() as session:
                    user: Optional[User] = await user_service.get_user_by_id(
                        session, int(user_id)
                    )
                    if user:
                        request.state.user = user

        except (jwt.PyJWTError, ValueError):
            # Token 无效或过期，这里不做处理，request.state.user 保持 None
            pass

        return await call_next(request)
