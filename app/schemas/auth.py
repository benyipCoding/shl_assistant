from pydantic import BaseModel, EmailStr


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class UserSerializer(BaseModel):
    id: int
    username: str
    email: EmailStr
    is_active: bool
    model_config = {"from_attributes": True}
