from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class FF14V2GraphQLRequest(BaseModel):
    query: str = Field(min_length=1)
    variables: dict[str, Any] | None = None
    operation_name: str | None = Field(default=None, alias="operationName")
    scope: Literal["client", "user"] = "client"
    access_token: str | None = Field(default=None, alias="accessToken")

    model_config = ConfigDict(populate_by_name=True, extra="forbid")
