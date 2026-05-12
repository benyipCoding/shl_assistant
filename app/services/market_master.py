import asyncio
from datetime import date, datetime
from typing import Any, Mapping, Sequence
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

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
    DEFAULT_FILTER_NON_TRADING = True
    ALWAYS_OPEN_ASSET_TYPES = {"digital currency"}
    HOLIDAY_LIKE_STALE_MIN_CANDLES = 3

    async def get_latest_price(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self.get("/price", params=params, require_identifier=True)

    async def get_quote(self, params: Mapping[str, Any] | None = None) -> Any:
        return await self.get("/quote", params=params, require_identifier=True)

    async def get_time_series(
        self,
        params: Mapping[str, Any] | None = None,
        *,
        filter_non_trading: bool = False,
    ) -> Any:
        payload, _ = await self._get_time_series_payload(
            params,
            filter_non_trading=filter_non_trading,
        )
        return payload

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
        filter_non_trading: bool = DEFAULT_FILTER_NON_TRADING,
    ) -> dict[str, Any]:
        normalized_outputsize = outputsize or self.DEFAULT_KLINE_OUTPUTSIZE
        normalized_timezone = timezone or self.DEFAULT_KLINE_TIMEZONE
        defaults_applied = {
            "outputsize": normalized_outputsize,
            "timezone": normalized_timezone,
            "order": self.DEFAULT_KLINE_ORDER,
            "previous_close": self.DEFAULT_KLINE_PREVIOUS_CLOSE,
        }

        payload, filter_info = await self._get_time_series_payload(
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
            },
            filter_non_trading=filter_non_trading,
        )

        return self._normalize_kline(
            payload,
            requested_symbol=symbol,
            requested_interval=interval,
            defaults_applied=defaults_applied,
            filter_info=filter_info,
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

    async def _get_time_series_payload(
        self,
        params: Mapping[str, Any] | None,
        *,
        filter_non_trading: bool,
    ) -> tuple[Any, dict[str, Any]]:
        payload = await self.get("/time_series", params=params, require_identifier=True)

        if not filter_non_trading:
            return payload, self._build_filter_info(
                requested=False,
                applied=False,
                original_count=self._extract_values_count(payload),
                filtered_count=self._extract_values_count(payload),
                reason="disabled",
            )

        return self._filter_time_series_payload(payload, params=params)

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
        filter_info: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            return {
                "symbol": requested_symbol,
                "interval": requested_interval,
                "count": 0,
                "defaults_applied": dict(defaults_applied),
                "filtering": dict(filter_info or {}),
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
            "filtering": dict(filter_info or {}),
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

    def _filter_time_series_payload(
        self,
        payload: Any,
        *,
        params: Mapping[str, Any] | None,
    ) -> tuple[Any, dict[str, Any]]:
        original_count = self._extract_values_count(payload)
        base_info = self._build_filter_info(
            requested=True,
            applied=False,
            original_count=original_count,
            filtered_count=original_count,
            reason=None,
        )

        if not isinstance(payload, Mapping):
            return payload, self._with_filter_reason(base_info, "payload_not_mapping")

        raw_meta = payload.get("meta")
        raw_values = payload.get("values")
        meta = raw_meta if isinstance(raw_meta, Mapping) else {}
        values = raw_values if isinstance(raw_values, list) else []

        interval = self._to_str(meta.get("interval")) or self._to_str(
            (params or {}).get("interval")
        )
        asset_type = self._normalize_asset_type(
            self._to_str(meta.get("type")) or self._to_str((params or {}).get("type"))
        )

        if not self._is_intraday_interval(interval):
            return payload, self._with_filter_reason(base_info, "non_intraday_interval")

        if asset_type in self.ALWAYS_OPEN_ASSET_TYPES:
            return payload, self._with_filter_reason(base_info, "always_open_asset")

        entries = self._build_candle_entries(values, meta=meta, params=params)
        if not entries:
            return payload, self._with_filter_reason(base_info, "datetime_parse_failed")

        holiday_like_dates = self._detect_holiday_like_dates(entries)
        filtered_values: list[Mapping[str, Any]] = []
        dropped_weekend = 0
        dropped_holiday_like = 0

        for entry in entries:
            is_weekend_stale = (
                entry["is_stale"]
                and entry["exchange_date"] is not None
                and entry["exchange_date"].weekday() >= 5
            )
            is_holiday_like = entry["exchange_date"] in holiday_like_dates

            if is_weekend_stale:
                dropped_weekend += 1
                continue

            if is_holiday_like:
                dropped_holiday_like += 1
                continue

            filtered_values.append(entry["item"])

        filtered_count = len(filtered_values)
        dropped_count = original_count - filtered_count
        filter_info = self._build_filter_info(
            requested=True,
            applied=dropped_count > 0,
            original_count=original_count,
            filtered_count=filtered_count,
            dropped_weekend=dropped_weekend,
            dropped_holiday_like=dropped_holiday_like,
            reason=(
                "filtered_closed_session_candles"
                if dropped_count > 0
                else "no_closed_session_candles_detected"
            ),
        )

        if dropped_count == 0:
            return payload, filter_info

        filtered_payload = dict(payload)
        filtered_payload["values"] = filtered_values
        return filtered_payload, filter_info

    def _build_candle_entries(
        self,
        values: Sequence[Any],
        *,
        meta: Mapping[str, Any],
        params: Mapping[str, Any] | None,
    ) -> list[dict[str, Any]]:
        response_timezone = self._resolve_response_timezone_name(
            interval=self._to_str(meta.get("interval"))
            or self._to_str((params or {}).get("interval")),
            request_timezone=self._to_str((params or {}).get("timezone")),
            exchange_timezone=self._to_str(meta.get("exchange_timezone")),
        )
        exchange_timezone = self._to_str(meta.get("exchange_timezone"))

        entries: list[dict[str, Any]] = []
        for item in values:
            if not isinstance(item, Mapping):
                continue

            raw_datetime = self._to_str(item.get("datetime"))
            parsed_datetime = self._parse_candle_datetime(raw_datetime)
            if raw_datetime is None or parsed_datetime is None:
                return []

            exchange_datetime = self._to_exchange_datetime(
                parsed_datetime,
                response_timezone=response_timezone,
                exchange_timezone=exchange_timezone,
            )
            entries.append(
                {
                    "item": item,
                    "raw_datetime": raw_datetime,
                    "sort_key": raw_datetime,
                    "exchange_date": exchange_datetime.date(),
                    "is_stale": False,
                }
            )

        previous_close: float | None = None
        sorted_entries = sorted(entries, key=lambda item: item["sort_key"])
        for index, entry in enumerate(sorted_entries):
            close_price = self._to_float(entry["item"].get("close"))
            explicit_previous_close = self._to_float(
                entry["item"].get("previous_close")
            )
            next_close = None
            if index + 1 < len(sorted_entries):
                next_close = self._to_float(
                    sorted_entries[index + 1]["item"].get("close")
                )

            entry["is_stale"] = self._is_stale_candle(
                entry["item"],
                previous_close=(
                    explicit_previous_close
                    if explicit_previous_close is not None
                    else previous_close
                ),
                next_close=next_close,
            )
            if close_price is not None:
                previous_close = close_price

        return entries

    def _detect_holiday_like_dates(
        self,
        entries: Sequence[Mapping[str, Any]],
    ) -> set[date]:
        grouped: dict[date, list[Mapping[str, Any]]] = {}

        for entry in entries:
            exchange_date = entry.get("exchange_date")
            if not isinstance(exchange_date, date):
                continue
            grouped.setdefault(exchange_date, []).append(entry)

        holiday_like_dates: set[date] = set()
        for exchange_date, grouped_entries in grouped.items():
            if exchange_date.weekday() >= 5:
                continue
            if len(grouped_entries) < self.HOLIDAY_LIKE_STALE_MIN_CANDLES:
                continue
            if all(entry.get("is_stale") for entry in grouped_entries):
                holiday_like_dates.add(exchange_date)

        return holiday_like_dates

    def _is_stale_candle(
        self,
        item: Mapping[str, Any],
        *,
        previous_close: float | None,
        next_close: float | None,
    ) -> bool:
        open_price = self._to_float(item.get("open"))
        high_price = self._to_float(item.get("high"))
        low_price = self._to_float(item.get("low"))
        close_price = self._to_float(item.get("close"))
        volume = self._to_int(item.get("volume"))

        if None in (open_price, high_price, low_price, close_price):
            return False

        if (
            open_price != high_price
            or high_price != low_price
            or low_price != close_price
        ):
            return False

        if previous_close is not None and close_price == previous_close:
            return volume in (None, 0)

        if next_close is not None and close_price == next_close:
            return volume in (None, 0)

        return False

    def _resolve_response_timezone_name(
        self,
        *,
        interval: str | None,
        request_timezone: str | None,
        exchange_timezone: str | None,
    ) -> str | None:
        if not self._is_intraday_interval(interval):
            return exchange_timezone

        if request_timezone is None or request_timezone.casefold() == "exchange":
            return exchange_timezone

        return request_timezone

    def _to_exchange_datetime(
        self,
        parsed_datetime: datetime,
        *,
        response_timezone: str | None,
        exchange_timezone: str | None,
    ) -> datetime:
        localized_datetime = parsed_datetime

        if parsed_datetime.tzinfo is None and response_timezone is not None:
            try:
                localized_datetime = parsed_datetime.replace(
                    tzinfo=ZoneInfo(response_timezone)
                )
            except ZoneInfoNotFoundError:
                localized_datetime = parsed_datetime

        if localized_datetime.tzinfo is None or exchange_timezone is None:
            return localized_datetime

        try:
            return localized_datetime.astimezone(ZoneInfo(exchange_timezone))
        except ZoneInfoNotFoundError:
            return localized_datetime

    def _is_intraday_interval(self, interval: str | None) -> bool:
        if interval is None:
            return False
        normalized_interval = interval.casefold()
        return not normalized_interval.endswith(("day", "week", "month"))

    def _normalize_asset_type(self, asset_type: str | None) -> str | None:
        if asset_type is None:
            return None
        return asset_type.strip().casefold()

    def _extract_values_count(self, payload: Any) -> int:
        if not isinstance(payload, Mapping):
            return 0
        values = payload.get("values")
        if not isinstance(values, list):
            return 0
        return len(values)

    def _build_filter_info(
        self,
        *,
        requested: bool,
        applied: bool,
        original_count: int,
        filtered_count: int,
        reason: str | None,
        dropped_weekend: int = 0,
        dropped_holiday_like: int = 0,
    ) -> dict[str, Any]:
        return {
            "requested": requested,
            "applied": applied,
            "original_count": original_count,
            "filtered_count": filtered_count,
            "dropped_count": original_count - filtered_count,
            "dropped_weekend": dropped_weekend,
            "dropped_holiday_like": dropped_holiday_like,
            "reason": reason,
        }

    def _with_filter_reason(
        self,
        filter_info: Mapping[str, Any],
        reason: str,
    ) -> dict[str, Any]:
        updated_filter_info = dict(filter_info)
        updated_filter_info["reason"] = reason
        return updated_filter_info

    def _parse_candle_datetime(self, value: str | None) -> datetime | None:
        if value is None:
            return None

        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

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
