from typing import List, Optional
from pydantic import BaseModel, Field


class AnalyzePayload(BaseModel):
    mimeType: str
    data: str
    explanationStyle: str
    llmKey: str


class Abnormality(BaseModel):
    name: str
    value: str
    reference: Optional[str] = None
    status: str
    explanation: str
    possibleCauses: Optional[str] = None
    consequence: Optional[str] = None
    advice: Optional[str] = None


class AnalyzeResponse(BaseModel):
    reportType: Optional[str] = None
    patientName: Optional[str] = None
    healthScore: Optional[int] = Field(None, ge=0, le=100)
    summary: Optional[str] = None
    abnormalities: List[Abnormality] = []
    normalCount: Optional[int] = 0
    disclaimer: Optional[str] = None
    # 当图片无法识别或不是化验单时，返回该字段说明错误原因
    error: Optional[str] = None
    model_config = {"from_attributes": True}  # ⭐ Pydantic v2 关键
