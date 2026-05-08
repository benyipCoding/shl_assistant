from typing import Optional

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyCookie, HTTPAuthorizationCredentials, HTTPBearer


cookie_scheme = APIKeyCookie(name="access_token", auto_error=False)
bearer_scheme = HTTPBearer(auto_error=False)


async def verify_user(
    request: Request,
    access_token_cookie: Optional[str] = Security(cookie_scheme),
    bearer_credentials: Optional[HTTPAuthorizationCredentials] = Security(
        bearer_scheme
    ),
):
    _ = access_token_cookie
    _ = bearer_credentials
    user = getattr(request.state, "user", None)
    if not user:
        # 必须通过抛出异常来中断请求
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unauthorized: User is not logged in",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: User account is inactive",
        )
    return user


async def verify_superuser(user=Depends(verify_user)):
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: Superuser access required",
        )
    return user
