from starlette.middleware.base import BaseHTTPMiddleware


class RealIPMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # 获取 X-Forwarded-For 头部
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        # x_real_ip = request.headers.get("X-Real-IP")

        if x_forwarded_for:
            # X-Forwarded-For 可能包含多个 IP，取第一个（客户端的真实 IP）
            real_ip = x_forwarded_for.split(",")[0].strip()
            setattr(request.state, "real_ip", real_ip)

        return await call_next(request)
