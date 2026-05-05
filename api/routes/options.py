from __future__ import annotations

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from api.deps import get_cache, get_tastytrade_provider, missing_tastytrade_secrets
from api.market_data import fetch_spy_spot_snapshot

router = APIRouter(prefix="/options", tags=["options"])
logger = logging.getLogger("spyprophet.api.options")


@router.get("/spy")
def spy_chain(
    expiration: str = Query(
        default_factory=lambda: date.today().isoformat(),
        description="ISO date (YYYY-MM-DD). Defaults to today (0DTE).",
    ),
    width: int = Query(
        default=10,
        ge=1,
        le=40,
        description="How many strikes above and below spot to include.",
    ),
):
    """Return the SPY option chain for a given expiration, normalised
    around the current spot price.

    Live bid/ask/Greek streaming for any specific strike is served by
    ``GET /api/quotes/spy?call_strike=...&put_strike=...``. This endpoint
    only returns the chain meta so the cockpit page can render the
    strike list quickly.
    """
    if missing := missing_tastytrade_secrets():
        raise HTTPException(
            status_code=503,
            detail={"error": "tastytrade_unconfigured", "missing_secrets": missing},
        )
    provider = get_tastytrade_provider()
    if provider is None:  # pragma: no cover
        raise HTTPException(status_code=503, detail="tastytrade_unconfigured")

    cache = get_cache()
    spot = cache.get_or_compute("spy_spot", fetch_spy_spot_snapshot, ttl=15.0)
    spot_price = spot.get("price")

    chain_key = f"spy_chain:{expiration}"

    def _fetch_chain():
        return provider.get_nested_option_chain("SPY", expiration)

    chain = cache.get_or_compute(chain_key, _fetch_chain, ttl=120.0)
    if not chain:
        raise HTTPException(
            status_code=502,
            detail="Tastytrade option chain unavailable.",
        )

    strikes = _extract_strikes(chain, expiration)
    if not strikes:
        raise HTTPException(
            status_code=404,
            detail=f"No strikes found for expiration {expiration}.",
        )

    if spot_price is not None:
        strikes.sort(key=lambda s: abs(s["strike"] - spot_price))
        nearest = strikes[: width * 2]
        nearest.sort(key=lambda s: s["strike"])
    else:
        # Fallback: take the middle slice of the full chain.
        all_sorted = sorted(strikes, key=lambda s: s["strike"])
        mid = len(all_sorted) // 2
        nearest = all_sorted[max(0, mid - width) : mid + width]

    return {
        "underlying": "SPY",
        "expiration": expiration,
        "spot_price": spot_price,
        "strikes": nearest,
    }


def _extract_strikes(chain: dict, expiration: str) -> list[dict]:
    """Walk Tastytrade's nested chain shape and pull out the strike list
    for the requested expiration. Tastytrade returns the chain in either
    a "strikes" array (each element has `strike-price`, `call`, `put`,
    `call-streamer-symbol`, `put-streamer-symbol`) or a legacy "calls"/
    "puts" pair — handle both so we don't break if the API shape shifts.
    """
    items = chain.get("data", {}).get("items", []) if isinstance(chain, dict) else []
    exp = None
    for it in items:
        if str(it.get("expiration-date")) == str(expiration):
            exp = it
            break
        for candidate in it.get("expirations", []) or []:
            if str(candidate.get("expiration-date")) == str(expiration):
                exp = candidate
                break
        if exp is not None:
            break
    if exp is None:
        return []

    out: list[dict] = []
    if exp.get("strikes"):
        for row in exp["strikes"]:
            try:
                strike = float(row.get("strike-price", 0) or 0)
            except (TypeError, ValueError):
                continue
            if strike <= 0:
                continue
            out.append(
                {
                    "strike": strike,
                    "call_symbol": row.get("call"),
                    "put_symbol": row.get("put"),
                    "call_streamer_symbol": row.get("call-streamer-symbol"),
                    "put_streamer_symbol": row.get("put-streamer-symbol"),
                }
            )
    else:
        calls = {int(float(c.get("strike-price", 0))): c for c in exp.get("calls", []) or []}
        puts = {int(float(p.get("strike-price", 0))): p for p in exp.get("puts", []) or []}
        for strike in sorted(set(calls) | set(puts)):
            if strike <= 0:
                continue
            c = calls.get(strike, {})
            p = puts.get(strike, {})
            out.append(
                {
                    "strike": float(strike),
                    "call_symbol": c.get("symbol"),
                    "put_symbol": p.get("symbol"),
                    "call_streamer_symbol": c.get("streamer-symbol"),
                    "put_streamer_symbol": p.get("streamer-symbol"),
                }
            )

    return out
