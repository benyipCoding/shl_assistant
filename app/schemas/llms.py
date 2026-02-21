# app/schemas/llms.py
from pydantic import BaseModel


class LLMSerializer(BaseModel):
    id: int
    key: str
    name: str
    tag: str
    desc: str
    enabled: bool

    model_config = {"from_attributes": True}  # ⭐ Pydantic v2 关键
