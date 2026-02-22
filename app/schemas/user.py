from pydantic import BaseModel, EmailStr


class UserSerializer(BaseModel):
    id: int
    username: str
    email: EmailStr
    # is_active: bool
    model_config = {"from_attributes": True}
