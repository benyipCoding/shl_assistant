import asyncio
from typing import Any, Mapping, Sequence

import httpx

from app.core.config import settings


class TwelveDataAPIError(Exception):
    def __init__(
        self,
        status_code: int,
        message: str,
        payload: Any | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.message = message
        self.payload = payload


class MarketMasterService:
    IDENTIFIER_FIELDS = ("symbol", "figi", "isin", "cusip")
    MAX_WATCHLIST_SYMBOLS = 10
    WATCHLIST_CONCURRENCY = 4
    DEFAULT_KLINE_OUTPUTSIZE = 120
    DEFAULT_KLINE_TIMEZONE = "Exchange"
    DEFAULT_KLINE_ORDER = "desc"
    DEFAULT_KLINE_PREVIOUS_CLOSE = True

    async def get_latest_price(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self.get("/price", params=params, require_identifier=True)

    async def get_quote(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self.get("/quote", params=params, require_identifier=True)

    async def get_time_series(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self.get("/time_series", params=params, require_identifier=True)

    async def search_symbols(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self.get("/symbol_search", params=params)

    async def get_market_movers(
        self,
        market: str,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        return await self.get(f"/market_movers/{market}", params=params)

    async def get(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
        require_identifier: bool = False,
    ) -> Any:
        query_params = self._build_query_params(params)

        if require_identifier:
            self._ensure_identifier(query_params)

        return await self._call_twelve_data(path=path, params=query_params)

    async def get_watchlist_quotes(
        self,
        symbols: Sequence[str],
        *,
        interval: str | None = None,
        exchange: str | None = None,
        mic_code: str | None = None,
        country: str | None = None,
        asset_type: str | None = None,
        timezone: str | None = None,
        eod: bool | None = None,
        prepost: bool | None = None,
        dp: int | None = None,
    ) -> dict[str, Any]:
        normalized_symbols = self._normalize_symbols(symbols)

        if not normalized_symbols:
            raise TwelveDataAPIError(
                status_code=400,
                message="At least one symbol is required",
                payload={"field": "symbols"},
            )

        if len(normalized_symbols) > self.MAX_WATCHLIST_SYMBOLS:
            raise TwelveDataAPIError(
                status_code=400,
                message=(
                    f"Too many symbols requested. Maximum {self.MAX_WATCHLIST_SYMBOLS} symbols per request"
                ),
                payload={
                    "max_symbols": self.MAX_WATCHLIST_SYMBOLS,
                    "requested": len(normalized_symbols),
                },
            )

        base_params = {
            "interval": interval,
            "exchange": exchange,
            "mic_code": mic_code,
            "country": country,
            "type": asset_type,
            "timezone": timezone,
            "eod": eod,
            "prepost": prepost,
            "dp": dp,
        }

        semaphore = asyncio.Semaphore(self.WATCHLIST_CONCURRENCY)

        async def fetch_quote(symbol: str) -> dict[str, Any]:
            async with semaphore:
                try:
                    payload = await self.get_quote({"symbol": symbol, **base_params})
                except TwelveDataAPIError as exc:
                    return {
                        "ok": False,
                        "symbol": symbol,
                        "error": {
                            "code": exc.status_code,
                            "message": exc.message,
                            "data": exc.payload,
                        },
                    }

                return {
                    "ok": True,
                    "symbol": symbol,
                    "item": self._normalize_quote(payload),
                }

        results = await asyncio.gather(
            *(fetch_quote(symbol) for symbol in normalized_symbols)
        )

        items: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []

        for result in results:
            if result["ok"]:
                items.append(result["item"])
            else:
                errors.append(
                    {
                        "symbol": result["symbol"],
                        **result["error"],
                    }
                )

        return {
            "requested_symbols": normalized_symbols,
            "count": len(normalized_symbols),
            "succeeded": len(items),
            "failed": len(errors),
            "items": items,
            "errors": errors,
        }

    async def get_kline_defaults(
        self,
        *,
        symbol: str,
        interval: str = "1day",
        outputsize: int | None = None,
        exchange: str | None = None,
        mic_code: str | None = None,
        country: str | None = None,
        asset_type: str | None = None,
        timezone: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        adjust: str | None = None,
        prepost: bool | None = None,
        dp: int | None = None,
    ) -> dict[str, Any]:
        normalized_outputsize = outputsize or self.DEFAULT_KLINE_OUTPUTSIZE
        normalized_timezone = timezone or self.DEFAULT_KLINE_TIMEZONE
        defaults_applied = {
            "outputsize": normalized_outputsize,
            "timezone": normalized_timezone,
            "order": self.DEFAULT_KLINE_ORDER,
            "previous_close": self.DEFAULT_KLINE_PREVIOUS_CLOSE,
        }

        payload = await self.get_time_series(
            {
                "symbol": symbol,
                "interval": interval,
                "outputsize": normalized_outputsize,
                "exchange": exchange,
                "mic_code": mic_code,
                "country": country,
                "type": asset_type,
                "timezone": normalized_timezone,
                "start_date": start_date,
                "end_date": end_date,
                "adjust": adjust,
                "prepost": prepost,
                "dp": dp,
                "order": self.DEFAULT_KLINE_ORDER,
                "previous_close": self.DEFAULT_KLINE_PREVIOUS_CLOSE,
            }
        )

        return self._normalize_kline(
            payload,
            requested_symbol=symbol,
            requested_interval=interval,
            defaults_applied=defaults_applied,
        )

    async def search_unified(
        self,
        *,
        keyword: str,
        outputsize: int = 10,
        show_plan: bool = False,
    ) -> dict[str, Any]:
        payload = await self.search_symbols(
            {
                "symbol": keyword,
                "outputsize": outputsize,
                "show_plan": show_plan,
            }
        )

        raw_items = payload.get("data") if isinstance(payload, dict) else []
        if not isinstance(raw_items, list):
            raw_items = []

        items = [
            self._normalize_search_item(item)
            for item in raw_items
            if isinstance(item, Mapping)
        ]

        return {
            "keyword": keyword,
            "count": len(items),
            "items": items,
        }

    async def _call_twelve_data(
        self,
        path: str,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        headers = {
            "Accept": "application/json",
            "Authorization": f"apikey {settings.twelve_data_api_key}",
        }

        try:
            async with httpx.AsyncClient(
                base_url=settings.twelve_data_base_url.rstrip("/"),
                headers=headers,
                timeout=httpx.Timeout(30.0, connect=10.0),
            ) as client:
                response = await client.get(path, params=params)
        except httpx.RequestError as exc:
            raise TwelveDataAPIError(
                status_code=502,
                message="Twelve Data service unavailable",
                payload={"detail": str(exc)},
            ) from exc

        if response.is_error:
            raise TwelveDataAPIError(
                status_code=response.status_code,
                message=self._extract_error_message(response),
                payload=self._extract_response_payload(response),
            )

        return self._extract_response_payload(response)

    def _build_query_params(
        self,
        params: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        return {
            key: value
            for key, value in (params or {}).items()
            if value is not None and value != "" and key != "apikey"
        }

    def _ensure_identifier(self, params: Mapping[str, Any]) -> None:
        if any(params.get(field) for field in self.IDENTIFIER_FIELDS):
            return

        raise TwelveDataAPIError(
            status_code=400,
            message="One of symbol, figi, isin or cusip is required",
            payload={"required_any_of": list(self.IDENTIFIER_FIELDS)},
        )

    def _normalize_symbols(self, symbols: Sequence[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()

        for raw_symbol in symbols:
            symbol = raw_symbol.strip().upper()
            if not symbol or symbol in seen:
                continue
            normalized.append(symbol)
            seen.add(symbol)

        return normalized

    def _normalize_quote(self, payload: Any) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            return {"raw": payload}

        week_52 = payload.get("fifty_two_week")
        if not isinstance(week_52, Mapping):
            week_52 = {}

        last_price = self._to_float(payload.get("close"))

        return {
            "symbol": payload.get("symbol"),
            "name": payload.get("name"),
            "exchange": payload.get("exchange"),
            "mic_code": payload.get("mic_code"),
            "currency": payload.get("currency"),
            "datetime": payload.get("datetime"),
            "timestamp": self._to_int(payload.get("timestamp")),
            "last_quote_at": self._to_int(payload.get("last_quote_at")),
            "last_price": last_price,
            "ohlc": {
                "open": self._to_float(payload.get("open")),
                "high": self._to_float(payload.get("high")),
                "low": self._to_float(payload.get("low")),
                "close": last_price,
            },
            "change": {
                "value": self._to_float(payload.get("change")),
                "percent": self._to_float(payload.get("percent_change")),
                "previous_close": self._to_float(payload.get("previous_close")),
            },
            "volume": self._to_int(payload.get("volume")),
            "average_volume": self._to_int(payload.get("average_volume")),
            "is_market_open": payload.get("is_market_open"),
            "week_52": {
                "low": self._to_float(week_52.get("low")),
                "high": self._to_float(week_52.get("high")),
                "range": week_52.get("range"),
            },
        }

    def _normalize_search_item(self, item: Mapping[str, Any]) -> dict[str, Any]:
        symbol = self._to_str(item.get("symbol"))
        instrument_name = self._to_str(item.get("instrument_name"))
        exchange = self._to_str(item.get("exchange"))
        mic_code = self._to_str(item.get("mic_code"))
        label = instrument_name or symbol
        if symbol and instrument_name:
            label = f"{instrument_name} ({symbol})"

        return {
            "symbol": symbol,
            "name": instrument_name,
            "label": label,
            "exchange": exchange,
            "mic_code": mic_code,
            "market": " / ".join(part for part in (exchange, mic_code) if part),
            "timezone": self._to_str(item.get("exchange_timezone")),
            "asset_type": self._to_str(item.get("instrument_type")),
            "country": self._to_str(item.get("country")),
            "currency": self._to_str(item.get("currency")),
            "provider_plan": item.get("plan") or item.get("available_on"),
        }

    def _normalize_kline(
        self,
        payload: Any,
        *,
        requested_symbol: str,
        requested_interval: str,
        defaults_applied: Mapping[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            return {
                "symbol": requested_symbol,
                "interval": requested_interval,
                "count": 0,
                "defaults_applied": dict(defaults_applied),
                "meta": {},
                "candles": [],
                "raw": payload,
            }

        meta = payload.get("meta")
        values = payload.get("values")
        if not isinstance(meta, Mapping):
            meta = {}
        if not isinstance(values, list):
            values = []

        candles = [
            self._normalize_candle(item) for item in values if isinstance(item, Mapping)
        ]

        return {
            "symbol": meta.get("symbol") or requested_symbol,
            "interval": meta.get("interval") or requested_interval,
            "count": len(candles),
            "defaults_applied": dict(defaults_applied),
            "meta": {
                "symbol": meta.get("symbol") or requested_symbol,
                "interval": meta.get("interval") or requested_interval,
                "currency": meta.get("currency"),
                "exchange": meta.get("exchange"),
                "mic_code": meta.get("mic_code"),
                "exchange_timezone": meta.get("exchange_timezone"),
                "asset_type": meta.get("type"),
            },
            "candles": candles,
        }

    def _normalize_candle(self, item: Mapping[str, Any]) -> dict[str, Any]:
        return {
            "datetime": item.get("datetime"),
            "open": self._to_float(item.get("open")),
            "high": self._to_float(item.get("high")),
            "low": self._to_float(item.get("low")),
            "close": self._to_float(item.get("close")),
            "volume": self._to_int(item.get("volume")),
            "previous_close": self._to_float(item.get("previous_close")),
        }

    def _extract_response_payload(self, response: httpx.Response) -> Any:
        content_type = response.headers.get("content-type", "").lower()

        if "application/json" in content_type:
            try:
                return response.json()
            except ValueError:
                pass

        if response.text:
            return response.text

        return None

    def _extract_error_message(self, response: httpx.Response) -> str:
        payload = self._extract_response_payload(response)
        if isinstance(payload, Mapping):
            message = payload.get("message") or payload.get("error")
            if isinstance(message, str) and message:
                return message

        if isinstance(payload, str) and payload:
            return payload

        return "Twelve Data request failed"

    def _to_float(self, value: Any) -> float | None:
        if value in (None, ""):
            return None

        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_int(self, value: Any) -> int | None:
        if value in (None, ""):
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _to_str(self, value: Any) -> str | None:
        if value in (None, ""):
            return None
        return str(value)


market_master_service = MarketMasterService()
