from __future__ import annotations

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter

from api.deps import get_cache
from api.market_data import (
    fetch_spy_spot_snapshot,
    fetch_vix_snapshot,
    watch_strikes,
)
from api.structure import compute_structure_projection

router = APIRouter(prefix="/brief", tags=["brief"])
logger = logging.getLogger("spyprophet.api.brief")


@router.get("/spy")
def daily_brief():
    """Slim morning-brief composite for the /brief page.

    Composes a trader-focused day-ahead read out of pieces we already
    have wired or can pull from app.py without dragging in the full
    OpenAI/UnusualWhales-dependent ``build_morning_briefing_bundle``:

    - Structure projection (descending lines, closest above/below)
    - SPY spot + change + VIX regime + watch strikes
    - Market news (top headlines with timestamps)
    - Upcoming economic events (next 7 days, US-focused)

    The Streamlit app's full briefing layers on options intelligence,
    GEX, technical context, and sentiment scoring — those wire in
    over later sessions.
    """
    cache = get_cache()
    spot = cache.get_or_compute("spy_spot", fetch_spy_spot_snapshot, ttl=15.0)
    vix = cache.get_or_compute("vix", fetch_vix_snapshot, ttl=30.0)
    structure = cache.get_or_compute(
        "structure_projection",
        lambda: compute_structure_projection(spot.get("price")),
        ttl=60.0,
    )

    news = cache.get_or_compute("brief:news", _fetch_news, ttl=900.0)
    events = cache.get_or_compute("brief:events", _fetch_events, ttl=900.0)
    sentiment = _score_sentiment(news)

    return {
        "as_of": datetime.now(ZoneInfo("America/Chicago")).isoformat(),
        "spot": {
            "price": spot.get("price"),
            "change": spot.get("change"),
            "change_pct": spot.get("change_pct"),
        },
        "vix": vix,
        "watch": watch_strikes(spot.get("price")),
        "structure": structure,
        "news": news,
        "events": events,
        "sentiment": sentiment,
    }


def _score_sentiment(news: list[dict]) -> dict:
    """Score the top headlines into a sentiment summary using app.py's
    rule-based scorer. No yfinance needed.
    """
    if not news:
        return {
            "score": 0,
            "tone": "neutral",
            "headline_count": 0,
            "explanation": "No fresh headlines to score.",
        }
    try:
        from app import market_moving_news_score

        positive = 0
        negative = 0
        for item in news:
            score = market_moving_news_score(
                item.get("title") or "",
                item.get("summary") or "",
            )
            if score > 0:
                positive += 1
            elif score < 0:
                negative += 1
        net = positive - negative
        tone = "neutral"
        if net >= 2:
            tone = "bullish"
        elif net <= -2:
            tone = "bearish"
        return {
            "score": net,
            "tone": tone,
            "headline_count": len(news),
            "positive_count": positive,
            "negative_count": negative,
            "explanation": _sentiment_explanation(tone, positive, negative),
        }
    except Exception as exc:
        logger.warning("sentiment scoring failed: %s", type(exc).__name__)
        return {
            "score": 0,
            "tone": "neutral",
            "headline_count": len(news),
            "explanation": "Sentiment scorer unavailable.",
        }


def _sentiment_explanation(tone: str, positive: int, negative: int) -> str:
    if tone == "bullish":
        return f"{positive} bullish vs {negative} bearish headline(s) — net positive."
    if tone == "bearish":
        return f"{negative} bearish vs {positive} bullish headline(s) — net negative."
    return f"{positive} bullish, {negative} bearish — balanced."


def _fetch_news() -> list[dict]:
    """Top market-moving headlines via app.fetch_market_news (RSS feeds
    pre-filtered for relevance). Returns a JSON-friendly list."""
    try:
        from dataclasses import asdict

        from app import fetch_market_news
    except Exception as exc:
        logger.warning("brief news import failed: %s", type(exc).__name__)
        return []
    try:
        items = fetch_market_news(limit=8)
    except Exception as exc:
        logger.warning("brief news fetch failed: %s", type(exc).__name__)
        return []

    out: list[dict] = []
    for item in items:
        try:
            d = asdict(item)
        except TypeError:
            d = item if isinstance(item, dict) else {}
        # Normalize timestamps
        for k in ("published", "fetched_at"):
            v = d.get(k)
            if v is not None and not isinstance(v, str):
                try:
                    d[k] = v.isoformat()
                except Exception:
                    d[k] = str(v)
        out.append(
            {
                "title": d.get("title"),
                "summary": d.get("summary"),
                "source": d.get("source"),
                "url": d.get("url") or d.get("link"),
                "published": d.get("published"),
                "score": d.get("score"),
                "relevance": d.get("relevance"),
            }
        )
    return out


def _fetch_events() -> list[dict]:
    """Upcoming economic events for the next 7 days via
    app.get_upcoming_economic_events."""
    try:
        from dataclasses import asdict

        from app import get_central_tz, get_upcoming_economic_events
    except Exception as exc:
        logger.warning("brief events import failed: %s", type(exc).__name__)
        return []
    try:
        import pandas as pd

        ct = get_central_tz()
        now_ct = pd.Timestamp.now(tz=ct)
        items = get_upcoming_economic_events(now_ct, days=7)
    except Exception as exc:
        logger.warning("brief events fetch failed: %s", type(exc).__name__)
        return []

    out: list[dict] = []
    for ev in items:
        try:
            d = asdict(ev)
        except TypeError:
            d = ev if isinstance(ev, dict) else {}
        for k in ("scheduled_at", "release_at"):
            v = d.get(k)
            if v is not None and not isinstance(v, str):
                try:
                    d[k] = v.isoformat()
                except Exception:
                    d[k] = str(v)
        out.append(
            {
                "title": d.get("title") or d.get("event"),
                "country": d.get("country"),
                "impact": d.get("impact"),
                "scheduled_at": d.get("scheduled_at") or d.get("release_at"),
                "actual": d.get("actual"),
                "forecast": d.get("forecast"),
                "previous": d.get("previous"),
                "source": d.get("source"),
            }
        )
    return out
