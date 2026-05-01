import httpx


_client: httpx.AsyncClient | None = None


def init_ff14_v2_client():
    global _client
    _client = httpx.AsyncClient(
        headers={"Accept": "application/json"},
        timeout=httpx.Timeout(30.0, connect=10.0),
    )


def get_ff14_v2_client() -> httpx.AsyncClient:
    if _client is None:
        raise RuntimeError("FF Logs V2 client not initialized")
    return _client


async def close_ff14_v2_client():
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
