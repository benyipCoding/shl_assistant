from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from captcha.image import ImageCaptcha
import random
import string
import uuid
from app.clients.redis_client import get_redis
from app.services.captcha import captcha_service
from app.schemas.auth import CaptchaRequest
from fastapi import Query


router = APIRouter(prefix="/captcha", tags=["Captcha"])


def generate_code(length=5):
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=length))


@router.get("")
async def get_captcha(oldCaptchaId: str = Query(None, description="旧验证码ID")):
    captcha_id, data = await captcha_service.generate_captcha(oldCaptchaId)
    return StreamingResponse(
        data, media_type="image/png", headers={"Captcha-Id": captcha_id}
    )


@router.post("/verify")
async def validate_captcha(captcha_request: CaptchaRequest):
    if await captcha_service.validate_captcha(
        captcha_request.user_input, captcha_request.captcha_id
    ):
        return {"success": True, "message": "Captcha validated successfully."}
    else:
        return {"success": False, "message": "Invalid captcha."}
