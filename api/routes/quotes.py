from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from api.deps import get_cache, get_tastytrade_provider, missing_tastytrade_secrets
from api.market_data import fetch_spy_spot_snapshot, watch_strikes
from api.schemas import OptionQuote, QuotePairResponse

router = APIRouter(prefix="/quotes", tags=["quotes"])
logger = logging.getLogger("spyprophet.api.quotes")


@router.get("/spy", response_model=QuotePairResponse)
def spy_quotes(
    expiration: str = Query(
        default_factory=lambda: date.today().isoformat(),
        description="ISO date (YYYY-MM-DD). Defaults to today (0DTE).",
    ),
    call_strike: int | None = Query(
        default=None, description="Override the watched call strike. Defaults to spot+2."
    ),
    put_strike: int | None = Query(
        default=None, description="Override the watched put strike. Defaults to spot-2."
    ),
) -> QuotePairResponse:
    if missing := missing_tastytrade_secrets():
        raise HTTPException(
            status_code=503,
            detail={
                "error": "tastytrade_unconfigured",
                "missing_secrets": missing,
            },
        )
    provider = get_tastytrade_provider()
    if provider is None:  # pragma: no cover — race with secrets churn
        raise HTTPException(status_code=503, detail="tastytrade_unconfigured")

    cache = get_cache()
    spot = cache.get_or_compute("spy_spot", fetch_spy_spot_snapshot, ttl=15.0)
    spot_price = spot.get("price")

    if call_strike is None or put_strike is None:
        watch = watch_strikes(spot_price)
        call_strike = call_strike or watch["call"]
        put_strike = put_strike or watch["put"]

    if not call_strike or not put_strike:
        raise HTTPException(
            status_code=502,
            detail="Spot price unavailable; cannot infer default strikes.",
        )

    cache_key = f"spy_quotes:{expiration}:{call_strike}:{put_strike}"

    def _compute():
        return provider.get_selected_quotes(
            spot_price or 0.0, expiration, call_strike, put_strike
        )

    result = cache.get_or_compute(cache_key, _compute, ttl=10.0)

    return QuotePairResponse(
        underlying="SPY",
        underlying_price=spot_price,
        expiration=expiration,
        call=_to_option_quote(result.get("CALL")),
        put=_to_option_quote(result.get("PUT")),
        provider_status=result.get("status") or {},
        warning=result.get("warning"),
    )


def _to_option_quote(raw: dict | None) -> OptionQuote | None:
    if not raw:
        return None
    return OptionQuote(
        symbol=str(raw.get("symbol") or ""),
        underlying=str(raw.get("underlying") or "SPY"),
        expiration=raw.get("expiration"),
        strike=int(raw.get("strike") or 0),
        option_type=raw.get("option_type") or "CALL",
        bid=_nullable(raw.get("bid")),
        ask=_nullable(raw.get("ask")),
        mark=_nullable(raw.get("mark")),
        spread=_nullable(raw.get("spread")),
        delta=_nullable(raw.get("delta")),
        gamma=_nullable(raw.get("gamma")),
        theta=_nullable(raw.get("theta")),
        vega=_nullable(raw.get("vega")),
        iv=_nullable(raw.get("iv")),
        provider=str(raw.get("provider") or ""),
        warning=raw.get("warning"),
    )


def _nullable(value):
    if value is None:
        return None
    try:
        import math

        if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
            return None
    except Exception:
        return None
    return value
