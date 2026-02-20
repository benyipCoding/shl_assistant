from pydantic import BaseModel


class ImageData(BaseModel):
    mimeType: str
    data: str


class SHLAnalyzePayload(BaseModel):
    images_data: list[ImageData]
    llmKey: str
