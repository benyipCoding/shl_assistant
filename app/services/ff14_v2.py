import asyncio
import time
from typing import Any, Literal, Mapping

import httpx

from app.clients.ff14 import FFLogsAPIError
from app.clients.ff14_v2 import get_ff14_v2_client
from app.core.config import settings


class FF14V2Service:
    def __init__(self):
        self._client_access_token: str | None = None
        self._client_token_expires_at: float = 0.0
        self._token_lock = asyncio.Lock()

    async def execute_query(
        self,
        query: str,
        variables: Mapping[str, Any] | None = None,
        operation_name: str | None = None,
        endpoint: Literal["client", "user"] = "client",
        access_token: str | None = None,
    ) -> Any:
        token = await self._resolve_access_token(
            endpoint=endpoint,
            access_token=access_token,
        )

        payload: dict[str, Any] = {"query": query}
        if variables is not None:
            payload["variables"] = dict(variables)
        if operation_name:
            payload["operationName"] = operation_name

        client = get_ff14_v2_client()

        try:
            response = await client.post(
                self._build_graphql_url(endpoint),
                json=payload,
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
            )
        except httpx.RequestError as exc:
            raise FFLogsAPIError(
                status_code=502,
                message="FF Logs V2 service unavailable",
                payload={"detail": str(exc)},
            ) from exc

        if response.is_error:
            raise FFLogsAPIError(
                status_code=response.status_code,
                message=self._extract_error_message(response),
                payload=self._extract_response_payload(response),
            )

        if not response.content:
            return None

        return response.json()

    async def _resolve_access_token(
        self,
        endpoint: Literal["client", "user"],
        access_token: str | None,
    ) -> str:
        if endpoint == "user":
            if not access_token:
                raise FFLogsAPIError(
                    status_code=400,
                    message="FF Logs user endpoint requires accessToken",
                    payload=None,
                )
            return access_token
        return await self._get_client_access_token()

    async def _get_client_access_token(self) -> str:
        now = time.time()
        if self._client_access_token and now < self._client_token_expires_at - 60:
            return self._client_access_token

        async with self._token_lock:
            now = time.time()
            if self._client_access_token and now < self._client_token_expires_at - 60:
                return self._client_access_token

            client = get_ff14_v2_client()

            try:
                response = await client.post(
                    settings.ff14_v2_token_url,
                    data={"grant_type": "client_credentials"},
                    auth=httpx.BasicAuth(
                        settings.ff14_v2_client_id,
                        settings.ff14_v2_secret_key,
                    ),
                    headers={"Accept": "application/json"},
                )
            except httpx.RequestError as exc:
                raise FFLogsAPIError(
                    status_code=502,
                    message="FF Logs OAuth service unavailable",
                    payload={"detail": str(exc)},
                ) from exc

            if response.is_error:
                raise FFLogsAPIError(
                    status_code=response.status_code,
                    message=self._extract_error_message(response),
                    payload=self._extract_response_payload(response),
                )

            payload = self._extract_response_payload(response)
            if not isinstance(payload, dict):
                raise FFLogsAPIError(
                    status_code=502,
                    message="FF Logs OAuth token response is invalid",
                    payload=payload,
                )

            access_token = payload.get("access_token")
            if not isinstance(access_token, str) or not access_token:
                raise FFLogsAPIError(
                    status_code=502,
                    message="FF Logs OAuth token response is missing access_token",
                    payload=payload,
                )

            expires_in = payload.get("expires_in")
            try:
                expires_in_seconds = int(expires_in) if expires_in is not None else 3600
            except (TypeError, ValueError):
                expires_in_seconds = 3600

            self._client_access_token = access_token
            self._client_token_expires_at = time.time() + max(expires_in_seconds, 60)
            return access_token

    def _build_graphql_url(self, endpoint: Literal["client", "user"]) -> str:
        if endpoint == "user":
            return settings.ff14_v2_user_base_url
        return settings.ff14_v2_client_base_url

    def _extract_error_message(self, response: httpx.Response) -> str:
        payload = self._extract_response_payload(response)
        if isinstance(payload, dict):
            message = (
                payload.get("error_description")
                or payload.get("error")
                or payload.get("message")
            )
            if isinstance(message, str) and message:
                return message
        if response.text:
            return response.text
        return "FF Logs V2 request failed"

    def _extract_response_payload(self, response: httpx.Response) -> Any:
        try:
            return response.json()
        except ValueError:
            if response.text:
                return {"detail": response.text}
            return None


ff14_v2_service = FF14V2Service()
