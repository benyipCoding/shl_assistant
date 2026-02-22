import base64
from fastapi import Request


def base64_to_bytes(b64: str) -> bytes:
    # 如果有 data:image/...;base64, 前缀，先去掉
    if "," in b64:
        b64 = b64.split(",", 1)[1]
    return base64.b64decode(b64)


async def ai_rate_limit_key(request: Request):
    user = getattr(request.state, "user", None)
    if user:
        return f"user:{user.id}"
    return f"ip:{request.client.host}"
