from typing import Any, Awaitable

from fastapi import APIRouter, Depends, Path, Query, Request
from fastapi.responses import JSONResponse
from fastapi_limiter.depends import RateLimiter

from app.depends.jwt_guard import verify_user
from app.schemas.response import APIResponse
from app.services.market_master import TwelveDataAPIError, market_master_service
from app.utils.helpers import ai_rate_limit_key


router = APIRouter(
    prefix="/market_master",
    tags=["Market Master"],
    dependencies=[Depends(verify_user)],
)


PRICE_LIMIT_PER_MINUTE = 8
QUOTE_LIMIT_PER_MINUTE = 6
TIME_SERIES_LIMIT_PER_MINUTE = 4
SYMBOL_SEARCH_LIMIT_PER_MINUTE = 10
MARKET_MOVERS_LIMIT_PER_MINUTE = 6
WATCHLIST_QUOTES_LIMIT_PER_MINUTE = 2
KLINE_DEFAULTS_LIMIT_PER_MINUTE = 6
UNIFIED_SEARCH_LIMIT_PER_MINUTE = 10


def _request_params(request: Request) -> dict[str, Any]:
    return dict(request.query_params)


async def _service_response(
    service_call: Awaitable[Any],
) -> APIResponse[Any] | JSONResponse:
    try:
        result = await service_call
    except TwelveDataAPIError as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "code": exc.status_code,
                "message": exc.message,
                "data": exc.payload,
            },
        )

    return APIResponse(data=result)


@router.get(
    "/price",
    response_model=APIResponse[Any],
    summary="获取最新价格",
    description=(
        "代理 Twelve Data 官方 /price REST 接口。免费方案只要 API Key 有效即可调用；"
        "若使用 figi、prepost 等高级参数，官方会按套餐权限决定是否返回 403。"
    ),
    dependencies=[
        Depends(
            RateLimiter(
                times=PRICE_LIMIT_PER_MINUTE,
                seconds=60,
                identifier=ai_rate_limit_key,
            )
        )
    ],
)
async def get_latest_price(
    request: Request,
    symbol: str | None = Query(
        None,
        description="标的代码。示例: AAPL、EUR/USD、BTC/USD。symbol/figi/isin/cusip 至少传一个。",
    ),
    figi: str | None = Query(
        None,
        description="FIGI 标识，可选。官方文档标注为 Ultra/Enterprise 及以上套餐可用。",
    ),
    isin: str | None = Query(
        None,
        description="ISIN 标识，可选。官方文档标注为 Data add-ons 能力。",
    ),
    cusip: str | None = Query(
        None,
        description="CUSIP 标识，可选。官方文档标注为 Data add-ons 能力。",
    ),
    exchange: str | None = Query(None, description="交易所，可选。示例: NASDAQ。"),
    mic_code: str | None = Query(None, description="MIC 代码，可选。示例: XNAS。"),
    country: str | None = Query(
        None, description="国家名称或国家代码，可选。示例: US。"
    ),
    asset_type: str | None = Query(
        None,
        alias="type",
        description="资产类型，可选。示例: Common Stock、ETF、Digital Currency。",
    ),
    response_format: str | None = Query(
        None,
        alias="format",
        description="响应格式，可选 JSON 或 CSV。默认返回 JSON。",
    ),
    prepost: bool | None = Query(
        None,
        description="是否包含盘前盘后数据，仅部分高级套餐支持。",
    ),
    dp: int | None = Query(
        None, ge=0, le=11, description="价格保留小数位，范围 0 到 11。"
    ),
):
    return await _service_response(
        market_master_service.get_latest_price(_request_params(request))
    )


@router.get(
    "/quote",
    response_model=APIResponse[Any],
    summary="获取实时报价快照",
    description=(
        "代理 Twelve Data 官方 /quote REST 接口，返回价格、开高低收、成交量和涨跌幅等快照数据。"
        "免费方案可用，但部分增值字段仍受套餐限制。"
    ),
    dependencies=[
        Depends(
            RateLimiter(
                times=QUOTE_LIMIT_PER_MINUTE,
                seconds=60,
                identifier=ai_rate_limit_key,
            )
        )
    ],
)
async def get_quote(
    request: Request,
    symbol: str | None = Query(
        None,
        description="标的代码。示例: AAPL、EUR/USD、BTC/USD。symbol/figi/isin/cusip 至少传一个。",
    ),
    figi: str | None = Query(
        None,
        description="FIGI 标识，可选。官方文档标注为 Ultra/Enterprise 及以上套餐可用。",
    ),
    isin: str | None = Query(
        None,
        description="ISIN 标识，可选。官方文档标注为 Data add-ons 能力。",
    ),
    cusip: str | None = Query(
        None,
        description="CUSIP 标识，可选。官方文档标注为 Data add-ons 能力。",
    ),
    interval: str | None = Query(
        None,
        description="报价聚合周期，可选。常见值如 1min、5min、15min、30min、1day。",
    ),
    exchange: str | None = Query(None, description="交易所，可选。示例: NASDAQ。"),
    mic_code: str | None = Query(None, description="MIC 代码，可选。示例: XNAS。"),
    country: str | None = Query(
        None, description="国家名称或国家代码，可选。示例: US。"
    ),
    volume_time_period: int | None = Query(
        None,
        ge=1,
        description="平均成交量统计周期数，可选。",
    ),
    asset_type: str | None = Query(
        None,
        alias="type",
        description="资产类型，可选。示例: Common Stock、ETF、Digital Currency。",
    ),
    response_format: str | None = Query(
        None,
        alias="format",
        description="响应格式，可选 JSON 或 CSV。默认返回 JSON。",
    ),
    prepost: bool | None = Query(
        None,
        description="是否包含盘前盘后数据，仅部分高级套餐支持。",
    ),
    eod: bool | None = Query(None, description="是否返回收盘日数据。"),
    rolling_period: int | None = Query(
        None,
        ge=1,
        le=168,
        description="滚动涨跌幅统计小时数，范围 1 到 168。",
    ),
    timezone: str | None = Query(
        None,
        description="输出时区，可选 Exchange、UTC 或具体 IANA 时区名。",
    ),
    dp: int | None = Query(
        None, ge=0, le=11, description="价格保留小数位，范围 0 到 11。"
    ),
):
    return await _service_response(
        market_master_service.get_quote(_request_params(request))
    )


@router.get(
    "/time-series",
    response_model=APIResponse[Any],
    summary="获取历史 K 线时序",
    description=(
        "代理 Twelve Data 官方 /time_series REST 接口。该接口用于获取历史 OHLCV 时序数据，"
        "免费方案可调用，单次请求的数据点、复权和盘前盘后能力仍以官方套餐权限为准。"
    ),
    dependencies=[
        Depends(
            RateLimiter(
                times=TIME_SERIES_LIMIT_PER_MINUTE,
                seconds=60,
                identifier=ai_rate_limit_key,
            )
        )
    ],
)
async def get_time_series(
    request: Request,
    interval: str = Query(
        ...,
        description=(
            "时间粒度，官方当前支持 1min、5min、15min、30min、45min、1h、2h、4h、8h、1day、1week、1month。"
        ),
    ),
    symbol: str | None = Query(
        None,
        description="标的代码。示例: AAPL、EUR/USD、BTC/USD。symbol/figi/isin/cusip 至少传一个。",
    ),
    figi: str | None = Query(
        None,
        description="FIGI 标识，可选。官方文档标注为 Ultra/Enterprise 及以上套餐可用。",
    ),
    isin: str | None = Query(
        None,
        description="ISIN 标识，可选。官方文档标注为 Data add-ons 能力。",
    ),
    cusip: str | None = Query(
        None,
        description="CUSIP 标识，可选。官方文档标注为 Data add-ons 能力。",
    ),
    outputsize: int | None = Query(
        None,
        ge=1,
        le=5000,
        description="返回数据点数量，官方范围 1 到 5000。",
    ),
    exchange: str | None = Query(None, description="交易所，可选。示例: NASDAQ。"),
    mic_code: str | None = Query(None, description="MIC 代码，可选。示例: XNAS。"),
    country: str | None = Query(
        None, description="国家名称或国家代码，可选。示例: US。"
    ),
    asset_type: str | None = Query(
        None,
        alias="type",
        description="资产类型，可选。示例: Common Stock、ETF、Digital Currency。",
    ),
    timezone: str | None = Query(
        None,
        description="输出时区，可选 Exchange、UTC 或具体 IANA 时区名。",
    ),
    start_date: str | None = Query(
        None,
        description="开始时间，可传 YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS。",
    ),
    end_date: str | None = Query(
        None,
        description="结束时间，可传 YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS。",
    ),
    date: str | None = Query(
        None,
        description="指定单日数据，可传具体日期，或 today、yesterday。",
    ),
    order: str | None = Query(
        None,
        description="返回排序方向，具体枚举以 Twelve Data 官方文档为准。",
    ),
    prepost: bool | None = Query(
        None,
        description="是否包含盘前盘后数据，仅部分高级套餐支持。",
    ),
    response_format: str | None = Query(
        None,
        alias="format",
        description="响应格式，可选 JSON 或 CSV。默认返回 JSON。",
    ),
    adjust: str | None = Query(
        None,
        description="价格复权模式，可选值以 Twelve Data 官方文档为准。",
    ),
    previous_close: bool | None = Query(
        None,
        description="是否在结果中补充上一根 K 线的收盘价。",
    ),
    dp: int | None = Query(
        None, ge=0, le=11, description="价格保留小数位，范围 0 到 11。"
    ),
    filter_non_trading: bool = Query(
        True,
        description=(
            "是否过滤明显处于休市状态的平盘 K 线。开启后会剔除周末的静态 K 线，"
            "以及整天都保持平盘的节假日样式 K 线；如需保留 Twelve Data 原始结果可设为 false。"
        ),
    ),
):
    return await _service_response(
        market_master_service.get_time_series(
            {
                key: value
                for key, value in _request_params(request).items()
                if key != "filter_non_trading"
            },
            filter_non_trading=filter_non_trading,
        )
    )


@router.get(
    "/symbol-search",
    response_model=APIResponse[Any],
    summary="搜索交易标的",
    description=(
        "代理 Twelve Data 官方 /symbol_search REST 接口。适合前端做股票、外汇、ETF、加密货币等交易标的搜索联想。"
    ),
    dependencies=[
        Depends(
            RateLimiter(
                times=SYMBOL_SEARCH_LIMIT_PER_MINUTE,
                seconds=60,
                identifier=ai_rate_limit_key,
            )
        )
    ],
)
async def symbol_search(
    request: Request,
    symbol: str = Query(
        ...,
        min_length=1,
        description="搜索关键字，可传代码、简称，官方也支持部分 ISIN 搜索能力。",
    ),
    outputsize: int | None = Query(
        None,
        ge=1,
        le=120,
        description="最多返回多少条匹配结果，官方上限 120。",
    ),
    show_plan: bool | None = Query(
        None,
        description="是否返回标的所属套餐信息，便于前端提示该标的是否受套餐限制。",
    ),
):
    return await _service_response(
        market_master_service.search_symbols(_request_params(request))
    )


@router.get(
    "/market-movers/{market}",
    response_model=APIResponse[Any],
    summary="获取市场异动榜",
    description=(
        "代理 Twelve Data 官方 /market_movers/{market} REST 接口，返回涨幅榜或跌幅榜。"
        "官方文档说明该接口支持国际股票、外汇和加密货币市场。"
    ),
    dependencies=[
        Depends(
            RateLimiter(
                times=MARKET_MOVERS_LIMIT_PER_MINUTE,
                seconds=60,
                identifier=ai_rate_limit_key,
            )
        )
    ],
)
async def get_market_movers(
    request: Request,
    market: str = Path(
        ...,
        description="市场类型。官方 OpenAPI 当前枚举值为 stocks、etf、mutual_funds、forex、crypto。",
    ),
    direction: str | None = Query(
        None,
        description="榜单方向，可选 gainers 或 losers，实际可用值以官方文档为准。",
    ),
    outputsize: int | None = Query(
        None,
        ge=1,
        le=50,
        description="榜单返回条数，官方范围 1 到 50。",
    ),
    country: str | None = Query(
        None,
        description="国家过滤，仅非货币类市场适用。可传国家名称或国家代码。",
    ),
    price_greater_than: str | None = Query(
        None,
        description="仅返回价格高于该阈值的标的。",
    ),
    dp: int | None = Query(
        None, ge=0, le=11, description="价格保留小数位，范围 0 到 11。"
    ),
):
    return await _service_response(
        market_master_service.get_market_movers(market, _request_params(request))
    )


@router.get(
    "/watchlist/quotes",
    response_model=APIResponse[Any],
    summary="批量获取自选列表报价",
    description=(
        "面向前端自选页的聚合接口。传入逗号分隔的 symbols 后，后端会批量调用 Twelve Data /quote，"
        "统一返回归一化后的价格结构，并保留部分失败项。单次最多 10 个代码。"
    ),
    dependencies=[
        Depends(
            RateLimiter(
                times=WATCHLIST_QUOTES_LIMIT_PER_MINUTE,
                seconds=60,
                identifier=ai_rate_limit_key,
            )
        )
    ],
)
async def get_watchlist_quotes(
    symbols: str = Query(
        ...,
        description="自选代码列表，使用逗号分隔。示例: AAPL,MSFT,NVDA。单次最多 10 个。",
    ),
    interval: str | None = Query(
        None,
        description="可选 quote 聚合周期。常见值如 1min、5min、15min、30min、1day。",
    ),
    exchange: str | None = Query(None, description="交易所过滤，可选。示例: NASDAQ。"),
    mic_code: str | None = Query(None, description="MIC 代码过滤，可选。示例: XNAS。"),
    country: str | None = Query(
        None, description="国家名称或国家代码，可选。示例: US。"
    ),
    asset_type: str | None = Query(
        None,
        alias="type",
        description="资产类型过滤，可选。示例: Common Stock、ETF、Digital Currency。",
    ),
    timezone: str | None = Query(
        None,
        description="输出时区，可选 Exchange、UTC 或具体 IANA 时区名。",
    ),
    eod: bool | None = Query(None, description="是否返回收盘日数据。"),
    prepost: bool | None = Query(
        None,
        description="是否包含盘前盘后数据，仅部分高级套餐支持。",
    ),
    dp: int | None = Query(
        None, ge=0, le=11, description="价格保留小数位，范围 0 到 11。"
    ),
):
    return await _service_response(
        market_master_service.get_watchlist_quotes(
            [item for item in symbols.split(",")],
            interval=interval,
            exchange=exchange,
            mic_code=mic_code,
            country=country,
            asset_type=asset_type,
            timezone=timezone,
            eod=eod,
            prepost=prepost,
            dp=dp,
        )
    )


@router.get(
    "/kline/defaults",
    response_model=APIResponse[Any],
    summary="获取前端友好的 K 线默认结构",
    description=(
        "对 Twelve Data /time_series 做默认参数封装。默认 outputsize=120、timezone=Exchange、"
        "order=desc、previous_close=true，并把返回值整理成前端更容易消费的 candles 数组。"
    ),
    dependencies=[
        Depends(
            RateLimiter(
                times=KLINE_DEFAULTS_LIMIT_PER_MINUTE,
                seconds=60,
                identifier=ai_rate_limit_key,
            )
        )
    ],
)
async def get_kline_defaults(
    symbol: str = Query(..., description="标的代码。示例: AAPL、EUR/USD、BTC/USD。"),
    interval: str = Query(
        "1day",
        description="K 线粒度，默认 1day。常见值如 1min、5min、1h、1day、1week。",
    ),
    outputsize: int = Query(
        120,
        ge=1,
        le=5000,
        description="默认返回 120 根 K 线，可按需调小或调大。",
    ),
    exchange: str | None = Query(None, description="交易所过滤，可选。示例: NASDAQ。"),
    mic_code: str | None = Query(None, description="MIC 代码过滤，可选。示例: XNAS。"),
    country: str | None = Query(
        None, description="国家名称或国家代码，可选。示例: US。"
    ),
    asset_type: str | None = Query(
        None,
        alias="type",
        description="资产类型过滤，可选。示例: Common Stock、ETF、Digital Currency。",
    ),
    timezone: str = Query(
        "Exchange",
        description="输出时区，默认 Exchange。也可传 UTC 或具体 IANA 时区名。",
    ),
    start_date: str | None = Query(
        None,
        description="开始时间，可传 YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS。",
    ),
    end_date: str | None = Query(
        None,
        description="结束时间，可传 YYYY-MM-DD 或 YYYY-MM-DDTHH:MM:SS。",
    ),
    adjust: str | None = Query(
        None,
        description="价格复权模式，可选值以 Twelve Data 官方文档为准。",
    ),
    prepost: bool | None = Query(
        None,
        description="是否包含盘前盘后数据，仅部分高级套餐支持。",
    ),
    dp: int | None = Query(
        None, ge=0, le=11, description="价格保留小数位，范围 0 到 11。"
    ),
    filter_non_trading: bool = Query(
        True,
        description=(
            "是否默认过滤明显处于休市状态的平盘 K 线。默认开启，适合直接给图表渲染；"
            "如需保留原始时序可设为 false。"
        ),
    ),
):
    return await _service_response(
        market_master_service.get_kline_defaults(
            symbol=symbol,
            interval=interval,
            outputsize=outputsize,
            exchange=exchange,
            mic_code=mic_code,
            country=country,
            asset_type=asset_type,
            timezone=timezone,
            start_date=start_date,
            end_date=end_date,
            adjust=adjust,
            prepost=prepost,
            dp=dp,
            filter_non_trading=filter_non_trading,
        )
    )


@router.get(
    "/search/unified",
    response_model=APIResponse[Any],
    summary="统一市场搜索结构",
    description=(
        "对 Twelve Data /symbol_search 做前端友好归一化，统一返回 symbol、label、market、"
        "asset_type、country、currency 等固定字段，便于搜索联想直接渲染。"
    ),
    dependencies=[
        Depends(
            RateLimiter(
                times=UNIFIED_SEARCH_LIMIT_PER_MINUTE,
                seconds=60,
                identifier=ai_rate_limit_key,
            )
        )
    ],
)
async def get_unified_search(
    keyword: str = Query(
        ...,
        min_length=1,
        description="搜索关键词，可传代码、简称或公司名片段。",
    ),
    outputsize: int = Query(
        10,
        ge=1,
        le=30,
        description="归一化结果条数，默认 10，建议前端联想不超过 10。",
    ),
    show_plan: bool = Query(
        False,
        description="是否透出官方套餐字段，便于前端提示标的可用性。",
    ),
):
    return await _service_response(
        market_master_service.search_unified(
            keyword=keyword,
            outputsize=outputsize,
            show_plan=show_plan,
        )
    )
