from pydantic import BaseModel, EmailStr, Field, ConfigDict


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class UserSerializer(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    model_config = {"from_attributes": True}


class CaptchaRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    captcha_id: str = Field(..., alias="captchaId")
    user_input: str = Field(..., alias="userInput")
