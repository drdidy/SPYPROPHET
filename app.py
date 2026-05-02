from __future__ import annotations

import hashlib
import json
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, time
from email.utils import parsedate_to_datetime
from html import escape, unescape
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import plotly.graph_objects as go
from tastytrade_provider import TastytradeProvider, TastytradeProviderStatus
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SYMBOL = "SPY"
VIX_SYMBOL = "^VIX"
CENTRAL_TZ_NAME = "America/Chicago"
CENTRAL_TZ_ALIASES = (CENTRAL_TZ_NAME, "US/Central")
DEFAULT_SLOPE_PER_HOUR = 0.108
STRUCTURE_CALIBRATION_KEYS = ("SPYPROPHET_STRUCTURE_CALIBRATION", "SPYPROPHET_SLOPE_PER_HOUR")
TARGET_OTM_STRIKE_DISTANCE = 2.0
FLOW_STRIKE_MAX_OTM_DISTANCE = 3.0
SPY_STRIKE_INCREMENT = 1
EXPECTED_OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
TASTYTRADE_SECRET_KEYS = ["TASTYTRADE_CLIENT_ID", "TASTYTRADE_CLIENT_SECRET", "TASTYTRADE_REFRESH_TOKEN"]
RTH_SESSION_START = time(8, 30)
RTH_SESSION_END = time(15, 0)
NEWS_RSS_FEEDS = (
    ("Yahoo Finance SPY", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=SPY&region=US&lang=en-US"),
    ("Yahoo Finance VIX", "https://feeds.finance.yahoo.com/rss/2.0/headline?s=%5EVIX&region=US&lang=en-US"),
    ("CNBC Markets", "https://www.cnbc.com/id/100003114/device/rss/rss.html"),
    ("MarketWatch Top Stories", "https://www.marketwatch.com/rss/topstories"),
    ("Investing.com Stock Market News", "https://www.investing.com/rss/news_25.rss"),
    ("Federal Reserve Press Releases", "https://www.federalreserve.gov/feeds/press_all.xml"),
    ("Federal Reserve Monetary Policy", "https://www.federalreserve.gov/feeds/press_monetary.xml"),
    ("Federal Reserve Speeches", "https://www.federalreserve.gov/feeds/speeches.xml"),
)
NEWS_RSS_URLS = tuple(url for _, url in NEWS_RSS_FEEDS)
ECONOMIC_CALENDAR_PATH = "data/economic_calendar.json"
REPLAY_LEARNING_DAYS = 45
TRADING_ECONOMICS_CALENDAR_URL = "https://api.tradingeconomics.com/calendar/country/united%20states/{start}/{end}"
TRADING_ECONOMICS_GUEST_CREDENTIAL = "guest:guest"
MORNING_BRIEFING_PATH = "data/morning_briefings.json"
MORNING_BRIEFING_NEWS_MAX_AGE_DAYS = 1
MARKET_MOVING_NEWS_LIMIT = 4
OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
OPENAI_DEFAULT_MODEL = "gpt-4.1-mini"
OPENAI_WEB_SEARCH_DEFAULT = "true"
UNUSUAL_WHALES_BASE_URL = "https://api.unusualwhales.com"
UNUSUAL_WHALES_TOKEN_KEYS = ("UNUSUAL_WHALES_API_KEY", "UNUSUAL_WHALES_REFRESH_TOKEN")
CURATED_MORNING_SOURCES = [
    {"name": "Federal Reserve", "url": "https://www.federalreserve.gov/feeds/default.htm", "role": "Official Fed press releases, monetary policy, and speeches"},
    {"name": "BLS", "url": "https://www.bls.gov/feed/", "role": "Official labor and inflation release feeds"},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/quote/SPY/news/", "role": "SPY and VIX market headlines"},
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/markets/", "role": "Market-moving headlines"},
    {"name": "MarketWatch", "url": "https://www.marketwatch.com/", "role": "Broad market headlines"},
    {"name": "Investing.com News", "url": "https://www.investing.com/news/stock-market-news", "role": "Stock market news feed"},
    {"name": "Tradytics", "url": "https://x.com/Tradytics", "role": "Options flow videos and trader context"},
    {"name": "Investing.com Calendar", "url": "https://www.investing.com/economic-calendar/", "role": "Macro event timing"},
    {"name": "ForexFactory Calendar", "url": "https://www.forexfactory.com/calendar", "role": "Macro event risk flags"},
    {"name": "Reuters Markets", "url": "https://www.reuters.com/markets/", "role": "Verified global headlines"},
]
GLOBAL_CONTEXT_TICKERS = {
    "ES futures": "ES=F",
    "DAX": "^GDAXI",
    "FTSE 100": "^FTSE",
    "Nikkei 225": "^N225",
    "Hang Seng": "^HSI",
    "Dollar Index": "DX-Y.NYB",
    "10Y yield": "^TNX",
    "5Y yield": "^FVX",
}
SECTOR_TICKERS = {
    "Technology": "XLK",
    "Financials": "XLF",
    "Healthcare": "XLV",
    "Consumer Disc.": "XLY",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Utilities": "XLU",
}


@dataclass(frozen=True)
class Pivot:
    name: str
    price: float
    timestamp: pd.Timestamp | None
    source: str
    candle_color: str
    fallback_used: bool


@dataclass(frozen=True)
class SecondaryPivot:
    name: str
    price: float
    timestamp: pd.Timestamp | None
    direction: str
    source: str


@dataclass(frozen=True)
class MarketContext:
    vix_price: float
    vix_label: str
    vix_tone: str
    vix_copy: str
    spy_pressure: str
    spy_pressure_tone: str
    spy_pressure_value: float
    trigger_gap: float
    trigger_gap_label: str
    trigger_gap_tone: str


@dataclass(frozen=True)
class NewsItem:
    title: str
    link: str | None
    published: pd.Timestamp | None
    source: str
    summary: str | None
    relevance: str


@dataclass(frozen=True)
class EconomicEvent:
    event_date: object
    time_label: str
    event: str
    impact: str
    source: str
    notes: str | None = None


@dataclass(frozen=True)
class SourceStatus:
    name: str
    status: str
    detail: str
    as_of: pd.Timestamp | None = None
    url: str | None = None


@dataclass(frozen=True)
class MarketMove:
    label: str
    symbol: str
    last: float
    change: float
    change_pct: float
    as_of: pd.Timestamp | None
    source: str


@dataclass(frozen=True)
class OptionsIntelligence:
    status: SourceStatus
    put_call_open_interest_ratio: float
    put_call_volume_ratio: float
    max_pain: float
    call_wall: float
    put_wall: float
    high_open_interest: list[dict]
    selected_quotes: list[dict] | None = None
    unusual_whales: dict | None = None


@dataclass(frozen=True)
class GammaExposureInsight:
    status: SourceStatus
    gamma_flip: float | None
    dealer_tone: str
    magnet_strikes: list[float]
    notes: str
    provider_payload: dict | None = None


@dataclass(frozen=True)
class TechnicalContext:
    status: SourceStatus
    prior_high: float
    prior_low: float
    prior_close: float
    ma50: float
    ma200: float
    weekly_high: float
    weekly_low: float
    monthly_high: float
    monthly_low: float
    gap_from_prior_close: float


@dataclass(frozen=True)
class SentimentContext:
    status: SourceStatus
    headline_score: int
    label: str
    bullish_count: int
    bearish_count: int
    social_payload: dict | None = None


@dataclass(frozen=True)
class MorningBriefingBundle:
    generated_at: pd.Timestamp
    lines: list[dict]
    economic_events: list[EconomicEvent]
    global_context: list[MarketMove]
    macro_context: list[MarketMove]
    sector_context: list[MarketMove]
    options_intelligence: OptionsIntelligence
    gamma_insight: GammaExposureInsight
    sentiment: SentimentContext
    technical_context: TechnicalContext
    news_items: list[NewsItem]
    learning_profile: "StructureLearningProfile"
    source_statuses: list[SourceStatus]


@dataclass(frozen=True)
class MorningBriefingResult:
    generated_at: pd.Timestamp
    provider: str
    model: str | None
    text: str
    confidence: int
    warnings: list[str]
    source_statuses: list[SourceStatus]
    citations: list[dict] | None = None


def market_hours_between(start_dt: datetime | pd.Timestamp, end_dt: datetime | pd.Timestamp) -> float:
    ct = get_central_tz()
    start = pd.Timestamp(start_dt)
    end = pd.Timestamp(end_dt)
    start = start.tz_localize(ct) if start.tzinfo is None else start.tz_convert(ct)
    end = end.tz_localize(ct) if end.tzinfo is None else end.tz_convert(ct)
    if end == start:
        return 0.0
    sign = 1.0
    if end < start:
        start, end = end, start
        sign = -1.0

    total_seconds = 0.0
    day = start.date()
    last_day = end.date()
    while day <= last_day:
        if pd.Timestamp(day).weekday() < 5:
            day_start = pd.Timestamp(day, tz=ct)
            day_end = day_start + pd.Timedelta(days=1)
            left = max(start, day_start)
            right = min(end, day_end)
            if right > left:
                total_seconds += (right - left).total_seconds()
        day = (pd.Timestamp(day) + pd.Timedelta(days=1)).date()
    return sign * total_seconds / 3600.0


@dataclass(frozen=True)
class DynamicLine:
    name: str
    anchor_price: float
    anchor_time: pd.Timestamp | None
    slope_per_hour: float
    direction: str
    zone_type: str
    source: str
    is_primary: bool
    description: str

    def hours_since(self, dt: datetime | pd.Timestamp) -> float:
        if self.anchor_time is None or pd.isna(self.anchor_price):
            return float("nan")
        ct = get_central_tz()
        cur = pd.Timestamp(dt)
        anc = pd.Timestamp(self.anchor_time)
        cur = cur.tz_localize(ct) if cur.tzinfo is None else cur.tz_convert(ct)
        anc = anc.tz_localize(ct) if anc.tzinfo is None else anc.tz_convert(ct)
        return market_hours_between(anc, cur)

    def raw_value_at(self, dt: datetime | pd.Timestamp) -> float:
        hours = self.hours_since(dt)
        if pd.isna(hours) or pd.isna(self.anchor_price):
            return float("nan")
        if self.direction == "ascending":
            return float(self.anchor_price + (self.slope_per_hour * hours))
        if self.direction == "descending":
            return float(self.anchor_price - (self.slope_per_hour * hours))
        return float("nan")

    def value_at(self, dt: datetime | pd.Timestamp) -> float:
        return self.raw_value_at(dt)

    def tradable_value_at(self, dt: datetime | pd.Timestamp) -> float:
        raw = self.raw_value_at(dt)
        if pd.isna(raw):
            return float("nan")
        return round(raw, 2)

    def distance_from_price(self, price: float, dt: datetime | pd.Timestamp, use_tradable_value: bool = True) -> float:
        if price is None or pd.isna(price):
            return float("nan")
        line_val = self.tradable_value_at(dt) if use_tradable_value else self.raw_value_at(dt)
        if pd.isna(line_val):
            return float("nan")
        return float(price - line_val)

    def abs_distance_from_price(self, price: float, dt: datetime | pd.Timestamp, use_tradable_value: bool = True) -> float:
        dist = self.distance_from_price(price, dt, use_tradable_value)
        return float(abs(dist)) if not pd.isna(dist) else float("nan")

    def percent_distance_from_price(self, price: float, dt: datetime | pd.Timestamp, use_tradable_value: bool = True) -> float:
        if price is None or pd.isna(price) or price == 0:
            return float("nan")
        abs_dist = self.abs_distance_from_price(price, dt, use_tradable_value)
        return float((abs_dist / price) * 100) if not pd.isna(abs_dist) else float("nan")


def get_central_tz():
    for tz_name in CENTRAL_TZ_ALIASES:
        try:
            return ZoneInfo(tz_name)
        except ZoneInfoNotFoundError:
            continue

    import pytz
    return pytz.timezone(CENTRAL_TZ_NAME)


def get_missing_tastytrade_secrets() -> list[str]:
    try:
        return [k for k in TASTYTRADE_SECRET_KEYS if not str(st.secrets.get(k, "")).strip()]
    except Exception:
        return list(TASTYTRADE_SECRET_KEYS)


def normalize_yfinance_frame(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    normalized = df.copy()
    if isinstance(normalized.columns, pd.MultiIndex):
        normalized.columns = normalized.columns.get_level_values(0)
    normalized.columns = [str(c).strip() for c in normalized.columns]
    lower_map = {c.lower(): c for c in normalized.columns}
    for expected in EXPECTED_OHLCV_COLUMNS:
        match = lower_map.get(expected.lower())
        if match and match != expected:
            normalized = normalized.rename(columns={match: expected})
    return normalized.sort_index()


def ensure_central_index(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    if not isinstance(out.index, pd.DatetimeIndex):
        out.index = pd.to_datetime(out.index, errors="coerce")
    out = out[~out.index.isna()]
    if out.empty:
        return pd.DataFrame()
    idx = out.index
    out.index = idx.tz_localize("UTC") if idx.tz is None else idx.tz_convert("UTC")
    out.index = out.index.tz_convert(get_central_tz())
    return out.sort_index()


def fetch_spy_hourly(period: str = "10d") -> pd.DataFrame:
    raw = yf.download(tickers=SYMBOL, period=period, interval="60m", prepost=True, progress=False, auto_adjust=False, actions=False)
    return ensure_central_index(normalize_yfinance_frame(raw))


@st.cache_data(ttl=120, show_spinner=False)
def fetch_vix_latest(period: str = "5d", interval: str = "15m") -> float:
    try:
        raw = yf.download(tickers=VIX_SYMBOL, period=period, interval=interval, prepost=True, progress=False, auto_adjust=False, actions=False)
        df = ensure_central_index(normalize_yfinance_frame(raw))
    except Exception:
        return float("nan")
    if df.empty or "Close" not in df:
        return float("nan")
    close = df["Close"].dropna()
    return float(close.iloc[-1]) if not close.empty else float("nan")


def classify_vix(vix_price: float) -> tuple[str, str, str]:
    if vix_price is None or pd.isna(vix_price):
        return "Unavailable", "amber", "Yahoo VIX feed unavailable"
    if vix_price < 15:
        return "Calm", "blue", "Premium can be thin"
    if vix_price < 20:
        return "Normal", "green", "Clean trigger reads"
    if vix_price < 25:
        return "Elevated", "amber", "Use tighter confirmation"
    return "Stress", "red", "Avoid chasing wicks"


def calculate_spy_pressure(df: pd.DataFrame, lookback_bars: int = 3) -> tuple[str, str, float]:
    if df is None or df.empty or "Close" not in df:
        return "Unavailable", "amber", float("nan")
    close = df["Close"].dropna()
    if len(close) <= lookback_bars:
        return "Building", "blue", float("nan")
    change = float(close.iloc[-1] - close.iloc[-1 - lookback_bars])
    if change > 1.0:
        return "Lifting", "green", change
    if change < -1.0:
        return "Fading", "red", change
    return "Balanced", "blue", change


def build_market_context(df: pd.DataFrame, latest_price: float | None, closest_line: DynamicLine | None, now_ct, vix_price: float | None = None) -> MarketContext:
    vix = fetch_vix_latest() if vix_price is None else vix_price
    vix_label, vix_tone, vix_copy = classify_vix(vix)
    pressure, pressure_tone, pressure_value = calculate_spy_pressure(df)
    if closest_line is not None and latest_price is not None and not pd.isna(latest_price):
        trigger_gap = closest_line.distance_from_price(latest_price, now_ct)
    else:
        trigger_gap = float("nan")
    abs_gap = abs(trigger_gap) if not pd.isna(trigger_gap) else float("nan")
    if pd.isna(abs_gap):
        gap_label, gap_tone = "Waiting", "amber"
    elif abs_gap <= 0.5:
        gap_label, gap_tone = "At trigger", "green"
    elif abs_gap <= 1.5:
        gap_label, gap_tone = "Near trigger", "blue"
    else:
        gap_label, gap_tone = "Room to wait", "amber"
    return MarketContext(vix, vix_label, vix_tone, vix_copy, pressure, pressure_tone, pressure_value, trigger_gap, gap_label, gap_tone)


def strip_markup(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", unescape(str(value)))).strip()


def market_moving_news_score(title: str, summary: str | None = None) -> int:
    title_text = (title or "").lower()
    text = f"{title or ''} {summary or ''}".lower()
    macro_terms = [
        "fed", "fomc", "powell", "cpi", "pce", "payroll", "nonfarm", "jobs report", "jobless claims",
        "unemployment", "inflation", "gdp", "retail sales", "ism", "pmi", "rate cut", "rate hike",
    ]
    index_terms = [
        "spy", "spx", "s&p", "s&p 500", "spdr", "equity futures", "stock futures", "futures rise",
        "futures fall", "wall street", "nasdaq", "dow jones", "russell", "stocks open", "stocks rise",
        "stocks fall", "market rally", "market selloff",
    ]
    volatility_terms = ["vix", "volatility", "treasury", "yield", "yields", "bond auction", "dollar", "dxy", "oil", "geopolitical"]
    mega_cap_terms = ["nvidia", "nvda", "apple", "aapl", "microsoft", "msft", "amazon", "amzn", "meta", "tesla", "tsla", "alphabet", "googl"]
    personal_finance_terms = ["mortgage", "retirement", "homeowner", "credit card", "personal finance", "social security"]
    stale_investor_terms = ["if i had invested", "turn $", "turned $", "portfolio over"]
    company_noise_terms = [
        "airline", "airlines", "spirit airlines", "restaurant", "retailer", "bankruptcy", "chapter 11",
        "merger", "acquisition", "ceo", "analyst says", "shares of", "stock jumps", "stock falls",
    ]
    asset_noise_terms = ["gold", "bitcoin", "crypto", "ethereum", "forex"]

    score = 0
    macro_hit = any(term in text for term in macro_terms)
    index_hit = any(term in text for term in index_terms)
    title_macro_hit = any(term in title_text for term in macro_terms)
    title_index_hit = any(term in title_text for term in index_terms)
    volatility_hit = any(term in text for term in volatility_terms)
    mega_cap_hit = any(term in text for term in mega_cap_terms)
    if macro_hit:
        score += 100
    if index_hit:
        score += 80
    if volatility_hit:
        score += 65
    if mega_cap_hit:
        score += 30
    if any(term in text for term in personal_finance_terms + stale_investor_terms):
        score -= 120
    if any(term in title_text for term in company_noise_terms) and not (title_macro_hit or title_index_hit):
        score -= 100
    if any(term in title_text for term in asset_noise_terms) and not (title_macro_hit or title_index_hit):
        score -= 180
    return score


def classify_news_relevance(title: str, summary: str | None = None) -> str:
    text = f"{title or ''} {summary or ''}".lower()
    high_impact = ["fed", "fomc", "powell", "cpi", "pce", "payroll", "jobs report", "unemployment", "inflation", "rate cut", "rate hike"]
    volatility = ["vix", "volatility", "treasury", "yield", "auction", "dollar", "oil", "geopolitical"]
    spy_market = ["spy", "spx", "s&p", "s&p 500", "nasdaq", "stock futures", "equity futures", "wall street"]
    if any(word in text for word in high_impact):
        return "Macro catalyst"
    if any(word in text for word in volatility):
        return "Volatility watch"
    if any(word in text for word in spy_market):
        return "SPY context"
    return "General market"


def is_market_news_relevant(title: str, summary: str | None = None) -> bool:
    return market_moving_news_score(title, summary) >= 60


def parse_rss_items(xml_text: str, source: str = "Yahoo Finance", limit: int = 8) -> list[NewsItem]:
    if not xml_text:
        return []
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    items = []
    for item in root.findall(".//item"):
        title = strip_markup(item.findtext("title"))
        if not title:
            continue
        summary = strip_markup(item.findtext("description")) or None
        link = strip_markup(item.findtext("link")) or None
        published = None
        pub_text = item.findtext("pubDate") or item.findtext("published")
        if pub_text:
            try:
                published = pd.Timestamp(parsedate_to_datetime(pub_text))
            except Exception:
                published = None
        items.append(NewsItem(title, link, published, source, summary, classify_news_relevance(title, summary)))
        if len(items) >= limit:
            break
    if items:
        return items
    for entry in root.findall(".//{http://www.w3.org/2005/Atom}entry"):
        title = strip_markup(entry.findtext("{http://www.w3.org/2005/Atom}title"))
        if not title:
            continue
        summary = strip_markup(entry.findtext("{http://www.w3.org/2005/Atom}summary") or entry.findtext("{http://www.w3.org/2005/Atom}content")) or None
        link = None
        link_node = entry.find("{http://www.w3.org/2005/Atom}link")
        if link_node is not None:
            link = strip_markup(link_node.attrib.get("href"))
        published = None
        pub_text = entry.findtext("{http://www.w3.org/2005/Atom}published") or entry.findtext("{http://www.w3.org/2005/Atom}updated")
        if pub_text:
            try:
                published = pd.Timestamp(parsedate_to_datetime(pub_text))
            except Exception:
                try:
                    published = pd.Timestamp(pub_text)
                except Exception:
                    published = None
        items.append(NewsItem(title, link, published, source, summary, classify_news_relevance(title, summary)))
        if len(items) >= limit:
            break
    return items


def news_sort_key(item: NewsItem) -> tuple[int, int, pd.Timestamp]:
    relevance_rank = {
        "Macro catalyst": 0,
        "Volatility watch": 1,
        "SPY context": 2,
        "General market": 3,
    }.get(item.relevance, 4)
    official_rank = 0 if item.source.startswith("Federal Reserve") else 1
    published = item.published if item.published is not None else pd.Timestamp.min.tz_localize("UTC")
    try:
        published = pd.Timestamp(published)
        published = published.tz_localize("UTC") if published.tzinfo is None else published.tz_convert("UTC")
    except Exception:
        published = pd.Timestamp.min.tz_localize("UTC")
    return -market_moving_news_score(item.title, item.summary), relevance_rank, official_rank, -published.value


def is_fresh_for_0dte(published, now_ct=None, max_age_days: int = MORNING_BRIEFING_NEWS_MAX_AGE_DAYS) -> bool:
    if published is None:
        return False
    try:
        ts = pd.Timestamp(published)
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
        ct = get_central_tz()
        pub_date = ts.tz_convert(ct).date()
        now_ts = pd.Timestamp(now_ct if now_ct is not None else datetime.now(tz=ct))
        now_ts = now_ts.tz_localize(ct) if now_ts.tzinfo is None else now_ts.tz_convert(ct)
        today = now_ts.date()
    except Exception:
        return False
    earliest = (pd.Timestamp(today) - pd.Timedelta(days=max_age_days)).date()
    return earliest <= pub_date <= today


@st.cache_data(ttl=900, show_spinner=False)
def fetch_market_news_rows(limit: int = MARKET_MOVING_NEWS_LIMIT) -> list[dict]:
    now_ct = datetime.now(tz=get_central_tz())
    results: list[NewsItem] = []
    seen: set[str] = set()
    for source, url in NEWS_RSS_FEEDS:
        try:
            response = requests.get(url, timeout=6, headers={"User-Agent": "SPYProphet/1.0"})
            response.raise_for_status()
        except Exception:
            continue
        for item in parse_rss_items(response.text, source, limit=max(limit * 4, 12)):
            if not is_fresh_for_0dte(item.published, now_ct):
                continue
            if not is_market_news_relevant(item.title, item.summary):
                continue
            key = item.link or item.title
            if key in seen:
                continue
            seen.add(key)
            results.append(item)
    return [
        {
            "title": item.title,
            "link": item.link,
            "published": item.published.isoformat() if item.published is not None else None,
            "source": item.source,
            "summary": item.summary,
            "relevance": item.relevance,
        }
        for item in sorted(results, key=news_sort_key)[:limit]
    ]


def news_item_from_row(row: dict) -> NewsItem:
    published = None
    if row.get("published"):
        try:
            published = pd.Timestamp(row.get("published"))
        except Exception:
            published = None
    return NewsItem(
        str(row.get("title") or ""),
        row.get("link"),
        published,
        str(row.get("source") or "Market news"),
        row.get("summary"),
        str(row.get("relevance") or "General market"),
    )


def fetch_market_news(limit: int = MARKET_MOVING_NEWS_LIMIT) -> list[NewsItem]:
    return [news_item_from_row(row) for row in fetch_market_news_rows(limit)]


def economic_event_from_dict(raw: dict) -> EconomicEvent | None:
    event_date = raw.get("date") or raw.get("event_date")
    event_name = raw.get("event") or raw.get("name") or raw.get("title")
    if not event_date or not event_name:
        return None
    try:
        parsed_date = pd.Timestamp(event_date).date()
    except Exception:
        return None
    return EconomicEvent(
        parsed_date,
        str(raw.get("time") or raw.get("time_label") or "Time varies"),
        str(event_name),
        str(raw.get("impact") or "Medium"),
        str(raw.get("source") or "Local calendar"),
        raw.get("notes"),
    )


def load_economic_calendar(path: str = ECONOMIC_CALENDAR_PATH) -> list[EconomicEvent]:
    p = Path(path)
    if not p.exists():
        return []
    try:
        payload = json.loads(p.read_text())
    except Exception:
        return []
    rows = payload.get("events", payload) if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        return []
    events = [event for event in (economic_event_from_dict(row) for row in rows if isinstance(row, dict)) if event is not None]
    return sorted(events, key=lambda e: (pd.Timestamp(e.event_date), e.time_label))


def get_trading_economics_credential() -> str:
    try:
        secret_value = str(st.secrets.get("TRADING_ECONOMICS_CREDENTIAL", "")).strip()
        if secret_value:
            return secret_value
    except Exception:
        pass
    return os.getenv("TRADING_ECONOMICS_CREDENTIAL", "").strip()


def format_calendar_time_from_utc(value: str | None) -> tuple[object | None, str]:
    if not value:
        return None, "Time varies"
    try:
        ts = pd.Timestamp(value)
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts.tz_convert("UTC")
        eastern = ts.tz_convert(ZoneInfo("America/New_York"))
        central = ts.tz_convert(get_central_tz())
        return central.date(), f"{eastern.strftime('%I:%M %p').lstrip('0')} ET / {central.strftime('%I:%M %p').lstrip('0')} CT"
    except Exception:
        return None, "Time varies"


def economic_event_from_trading_economics(raw: dict) -> EconomicEvent | None:
    event_name = raw.get("Event") or raw.get("Category")
    if not event_name:
        return None
    event_date, time_label = format_calendar_time_from_utc(raw.get("Date"))
    if event_date is None:
        return None
    importance = raw.get("Importance")
    try:
        importance_value = int(importance)
    except Exception:
        importance_value = 2
    impact = "High" if importance_value >= 3 else "Medium" if importance_value == 2 else "Low"
    values = []
    for label, key in [("Forecast", "Forecast"), ("Previous", "Previous"), ("Actual", "Actual")]:
        value = raw.get(key)
        if value not in [None, ""]:
            values.append(f"{label} {value}")
    reference = raw.get("Reference")
    if reference:
        values.append(f"Ref {reference}")
    return EconomicEvent(event_date, time_label, str(event_name), impact, str(raw.get("Source") or "Trading Economics"), "; ".join(values) or None)


def economic_event_from_provider_dict(raw: dict, default_source: str = "Configured calendar API") -> EconomicEvent | None:
    event_name = raw.get("event") or raw.get("name") or raw.get("title") or raw.get("Event") or raw.get("Category")
    if not event_name:
        return None
    date_value = raw.get("date") or raw.get("datetime") or raw.get("time") or raw.get("Date") or raw.get("timestamp")
    event_date, time_label = format_calendar_time_from_utc(str(date_value) if date_value else None)
    if event_date is None:
        day = raw.get("event_date") or raw.get("release_date")
        if not day:
            return None
        try:
            event_date = pd.Timestamp(day).date()
        except Exception:
            return None
        time_label = str(raw.get("time_label") or raw.get("release_time") or "Time varies")
    impact_raw = str(raw.get("impact") or raw.get("importance") or raw.get("volatility") or raw.get("Impact") or "Medium").strip()
    if impact_raw.isdigit():
        impact = "High" if int(impact_raw) >= 3 else "Medium" if int(impact_raw) == 2 else "Low"
    else:
        impact = "High" if impact_raw.lower() in {"high", "3"} else "Medium" if impact_raw.lower() in {"medium", "med", "2"} else "Low" if impact_raw.lower() in {"low", "1"} else impact_raw.title()
    source = str(raw.get("source") or raw.get("Source") or raw.get("provider") or default_source)
    notes = []
    for label, keys in [("Forecast", ("forecast", "consensus", "Forecast")), ("Previous", ("previous", "Previous")), ("Actual", ("actual", "Actual"))]:
        for key in keys:
            value = raw.get(key)
            if value not in [None, ""]:
                notes.append(f"{label} {value}")
                break
    return EconomicEvent(event_date, time_label, str(event_name), impact, source, "; ".join(notes) or None)


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_trading_economics_calendar(start_iso: str, end_iso: str, credential: str = "") -> list[EconomicEvent]:
    credentials = [credential] if credential else []
    if TRADING_ECONOMICS_GUEST_CREDENTIAL not in credentials:
        credentials.append(TRADING_ECONOMICS_GUEST_CREDENTIAL)
    url = TRADING_ECONOMICS_CALENDAR_URL.format(start=start_iso, end=end_iso)
    for cred in credentials:
        try:
            response = requests.get(url, params={"c": cred, "importance": "2", "f": "json"}, timeout=8)
            response.raise_for_status()
            payload = response.json()
        except Exception:
            continue
        if isinstance(payload, list):
            events = [event for event in (economic_event_from_trading_economics(row) for row in payload if isinstance(row, dict)) if event is not None]
            if events:
                return sorted(events, key=lambda e: (pd.Timestamp(e.event_date), e.time_label))
    return []


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_configured_economic_calendar(start_iso: str, end_iso: str) -> list[EconomicEvent]:
    url = get_secret_or_env("ECONOMIC_CALENDAR_API_URL")
    if not url:
        return []
    headers = {"User-Agent": "SPYProphet/1.0", "Accept": "application/json"}
    token = get_secret_or_env("ECONOMIC_CALENDAR_API_KEY")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(url, params={"start": start_iso, "end": end_iso, "country": "US"}, headers=headers, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except Exception:
        return []
    rows = payload
    if isinstance(payload, dict):
        for key in ["events", "data", "calendar", "results"]:
            if isinstance(payload.get(key), list):
                rows = payload[key]
                break
    if not isinstance(rows, list):
        return []
    events = [event for event in (economic_event_from_provider_dict(row) for row in rows if isinstance(row, dict)) if event is not None]
    return sorted(events, key=lambda e: (pd.Timestamp(e.event_date), e.time_label))


def get_upcoming_economic_events(now_ct, days: int = 7, path: str = ECONOMIC_CALENDAR_PATH) -> list[EconomicEvent]:
    today = pd.Timestamp(now_ct).date()
    end = (pd.Timestamp(today) + pd.Timedelta(days=days)).date()
    local_events = [event for event in load_economic_calendar(path) if today <= event.event_date <= end]
    if local_events:
        return local_events
    configured_events = [event for event in fetch_configured_economic_calendar(str(today), str(end)) if today <= event.event_date <= end]
    if configured_events:
        return configured_events
    live_events = fetch_trading_economics_calendar(str(today), str(end), get_trading_economics_credential())
    if live_events:
        return [event for event in live_events if today <= event.event_date <= end]
    return []


def get_secret_or_env(name: str, default: str = "") -> str:
    try:
        value = str(st.secrets.get(name, "")).strip()
        if value:
            return value
    except Exception:
        pass
    return os.getenv(name, default).strip()


def get_structure_calibration(default: float = DEFAULT_SLOPE_PER_HOUR) -> float:
    for key in STRUCTURE_CALIBRATION_KEYS:
        raw = get_secret_or_env(key)
        if not raw:
            continue
        try:
            value = float(raw)
        except Exception:
            continue
        if 0.001 <= value <= 1.0:
            return value
    return float(default)


def is_admin_diagnostics_enabled() -> bool:
    return get_secret_or_env("SPYPROPHET_ADMIN_MODE", "").lower() in {"1", "true", "yes", "on"}


def source_status(name: str, ok: bool, detail: str, as_of=None, url: str | None = None) -> SourceStatus:
    return SourceStatus(name, "connected" if ok else "unavailable", detail, pd.Timestamp(as_of) if as_of is not None else None, url)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_yfinance_history(ticker: str, period: str = "5d", interval: str = "1d") -> pd.DataFrame:
    try:
        raw = yf.download(tickers=ticker, period=period, interval=interval, prepost=True, progress=False, auto_adjust=False, actions=False)
        return normalize_yfinance_frame(raw)
    except Exception:
        return pd.DataFrame()


def market_move_from_history(label: str, symbol: str, df: pd.DataFrame, source: str = "Yahoo Finance") -> MarketMove | None:
    if df is None or df.empty or "Close" not in df:
        return None
    close = df["Close"].dropna()
    if close.empty:
        return None
    last = float(close.iloc[-1])
    prev = float(close.iloc[-2]) if len(close) > 1 else last
    change = last - prev
    change_pct = (change / prev) * 100 if prev else float("nan")
    as_of = close.index[-1] if isinstance(close.index, pd.DatetimeIndex) else None
    return MarketMove(label, symbol, last, change, change_pct, pd.Timestamp(as_of) if as_of is not None else None, source)


def fetch_market_moves(tickers: dict[str, str], period: str = "5d", interval: str = "1d") -> list[MarketMove]:
    moves = []
    for label, symbol in tickers.items():
        move = market_move_from_history(label, symbol, fetch_yfinance_history(symbol, period, interval))
        if move is not None:
            moves.append(move)
    return moves


def fetch_global_context() -> list[MarketMove]:
    return fetch_market_moves(GLOBAL_CONTEXT_TICKERS, period="5d", interval="1d")


def fetch_sector_context() -> list[MarketMove]:
    return sorted(fetch_market_moves(SECTOR_TICKERS, period="5d", interval="1d"), key=lambda m: m.change_pct if not pd.isna(m.change_pct) else -999, reverse=True)


@st.cache_data(ttl=300, show_spinner=False)
def fetch_spy_daily(period: str = "1y") -> pd.DataFrame:
    try:
        raw = yf.download(tickers=SYMBOL, period=period, interval="1d", prepost=False, progress=False, auto_adjust=False, actions=False)
        return normalize_yfinance_frame(raw)
    except Exception:
        return pd.DataFrame()


def build_technical_context(daily_df: pd.DataFrame, latest_price: float | None) -> TechnicalContext:
    if daily_df is None or daily_df.empty or "Close" not in daily_df:
        return TechnicalContext(source_status("Yahoo Finance daily SPY", False, "Daily SPY history unavailable."), float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan"))
    df = daily_df.dropna(subset=["Close"]).sort_index()
    prior = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
    close = df["Close"].dropna()
    ma50 = float(close.tail(50).mean()) if len(close) >= 50 else float("nan")
    ma200 = float(close.tail(200).mean()) if len(close) >= 200 else float("nan")
    weekly = df.tail(5)
    monthly = df.tail(21)
    gap = float(latest_price - prior["Close"]) if latest_price is not None and not pd.isna(latest_price) else float("nan")
    return TechnicalContext(
        source_status("Yahoo Finance daily SPY", True, "Prior levels and moving averages from daily SPY candles.", df.index[-1]),
        float(prior.get("High", float("nan"))),
        float(prior.get("Low", float("nan"))),
        float(prior.get("Close", float("nan"))),
        ma50,
        ma200,
        float(weekly["High"].max()) if "High" in weekly else float("nan"),
        float(weekly["Low"].min()) if "Low" in weekly else float("nan"),
        float(monthly["High"].max()) if "High" in monthly else float("nan"),
        float(monthly["Low"].min()) if "Low" in monthly else float("nan"),
        gap,
    )


def option_chain_for_expiration(expiration_date) -> tuple[pd.DataFrame, pd.DataFrame, SourceStatus]:
    try:
        chain = yf.Ticker(SYMBOL).option_chain(str(expiration_date))
        return chain.calls, chain.puts, source_status("Yahoo Finance option chain", True, "Option chain loaded for near-SPY open interest, volume, max-pain, and magnet levels.")
    except Exception as e:
        return pd.DataFrame(), pd.DataFrame(), source_status("Yahoo Finance option chain", False, f"Option chain unavailable: {type(e).__name__}")


def calculate_max_pain(calls: pd.DataFrame, puts: pd.DataFrame) -> float:
    if calls is None or puts is None or calls.empty or puts.empty or "strike" not in calls or "strike" not in puts:
        return float("nan")
    strikes = sorted(set(calls["strike"].dropna().astype(float)).union(set(puts["strike"].dropna().astype(float))))
    if not strikes:
        return float("nan")
    call_oi = calls.set_index("strike")["openInterest"].fillna(0) if "openInterest" in calls else pd.Series(dtype="float64")
    put_oi = puts.set_index("strike")["openInterest"].fillna(0) if "openInterest" in puts else pd.Series(dtype="float64")
    losses = {}
    for expiry_price in strikes:
        call_loss = sum(max(0.0, expiry_price - float(strike)) * float(oi) for strike, oi in call_oi.items())
        put_loss = sum(max(0.0, float(strike) - expiry_price) * float(oi) for strike, oi in put_oi.items())
        losses[expiry_price] = call_loss + put_loss
    return float(min(losses.items(), key=lambda kv: kv[1])[0])


def top_open_interest_rows(calls: pd.DataFrame, puts: pd.DataFrame, limit: int = 6) -> list[dict]:
    rows = []
    for option_type, df in [("CALL", calls), ("PUT", puts)]:
        if df is None or df.empty or "openInterest" not in df:
            continue
        for _, row in df.sort_values("openInterest", ascending=False).head(limit).iterrows():
            rows.append({
                "type": option_type,
                "strike": float(row.get("strike", float("nan"))),
                "open_interest": int(row.get("openInterest") or 0),
                "volume": int(row.get("volume") or 0),
                "last": _finite_float(row.get("lastPrice")),
                "bid": _finite_float(row.get("bid")),
                "ask": _finite_float(row.get("ask")),
            })
    return sorted(rows, key=lambda r: r["open_interest"], reverse=True)[:limit]


def option_quote_summary(quote: OptionQuote | None) -> dict | None:
    if quote is None:
        return None
    return {
        "type": quote.option_type,
        "strike": quote.strike,
        "bid": quote.bid,
        "ask": quote.ask,
        "mark": quote.mark,
        "spread": quote.spread,
        "delta": quote.delta,
        "gamma": quote.gamma,
        "iv": quote.iv,
        "provider": quote.provider,
        "timestamp": str(quote.timestamp) if quote.timestamp is not None else None,
    }


def selected_option_quote_summaries(option_state: OptionsCockpitState | None = None) -> list[dict]:
    if option_state is None:
        return []
    out = []
    for quote in [option_state.call_quote, option_state.put_quote]:
        summary = option_quote_summary(quote)
        if summary is not None:
            out.append(summary)
    return out


def fetch_external_json_payload(url_key: str, token_key: str | None = None) -> tuple[dict | None, SourceStatus]:
    url = get_secret_or_env(url_key)
    if not url:
        return None, source_status(url_key, False, f"{url_key} is not configured.")
    headers = {"User-Agent": "SPYProphet/1.0"}
    token = get_secret_or_env(token_key) if token_key else ""
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        payload = response.json()
    except Exception as e:
        return None, source_status(url_key, False, f"Configured endpoint failed: {type(e).__name__}", url=url)
    return payload if isinstance(payload, dict) else {"data": payload}, source_status(url_key, True, "Configured external endpoint returned data.", pd.Timestamp.now(tz=get_central_tz()), url)


def get_unusual_whales_token() -> str:
    for key in UNUSUAL_WHALES_TOKEN_KEYS:
        token = get_secret_or_env(key)
        if token:
            return token
    return ""


def unusual_whales_status(ok: bool, detail: str, as_of=None, url: str | None = None, skipped: bool = False) -> SourceStatus:
    state = "skipped" if skipped else "connected" if ok else "unavailable"
    return SourceStatus("Order Flow Feed", state, detail, pd.Timestamp(as_of) if as_of is not None else None, url)


@st.cache_data(ttl=180, show_spinner=False)
def fetch_unusual_whales_json(endpoint: str, params: tuple[tuple[str, object], ...] = ()) -> tuple[dict | None, str | None]:
    token = get_unusual_whales_token()
    if not token:
        return None, "Order flow token is not configured."
    url = f"{UNUSUAL_WHALES_BASE_URL}{endpoint}"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
        "UW-CLIENT-API-ID": "100001",
        "User-Agent": "SPYProphet/1.0",
    }
    try:
        response = requests.get(url, headers=headers, params=list(params), timeout=12)
        response.raise_for_status()
        payload = response.json()
    except requests.HTTPError as e:
        status = getattr(e.response, "status_code", "HTTP")
        return None, f"Order flow feed returned {status}."
    except Exception as e:
        return None, f"Order flow feed failed: {type(e).__name__}."
    if isinstance(payload, dict):
        return payload, None
    return {"data": payload}, None


def payload_rows(payload: dict | list | None) -> list[dict]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    for key in ["data", "results", "rows", "events", "calendar"]:
        rows = payload.get(key)
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return [payload]


def parse_market_timestamp(value) -> pd.Timestamp | None:
    if not value:
        return None
    try:
        ts = pd.Timestamp(value)
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
        return ts.tz_convert(get_central_tz())
    except Exception:
        return None


def row_is_current_for_0dte(row: dict, now_ct, time_keys: tuple[str, ...] = ("created_at", "timestamp", "time", "date")) -> bool:
    for key in time_keys:
        ts = parse_market_timestamp(row.get(key))
        if ts is not None:
            return is_fresh_for_0dte(ts, now_ct)
    return False


def _sum_rows(rows: list[dict], key: str) -> float:
    return float(sum(_finite_float(row.get(key), 0.0) for row in rows))


def _strike_key(value) -> float | None:
    strike = _finite_float(value)
    return None if pd.isna(strike) else float(strike)


def summarize_unusual_whales_flow_alerts(payload: dict | None, now_ct, expiration_date=None) -> dict:
    expiry_target = str(expiration_date) if expiration_date is not None else ""
    rows = []
    for row in payload_rows(payload):
        ticker = str(row.get("ticker") or row.get("ticker_symbol") or row.get("underlying_symbol") or "").upper()
        if ticker and ticker != SYMBOL:
            continue
        row_expiry = str(row.get("expiry") or row.get("expiration") or "")
        if expiry_target and row_expiry and row_expiry != expiry_target:
            continue
        if not row_is_current_for_0dte(row, now_ct, ("created_at", "timestamp", "time")):
            continue
        rows.append(row)
    call_rows = [row for row in rows if str(row.get("type") or row.get("option_type") or "").lower() == "call"]
    put_rows = [row for row in rows if str(row.get("type") or row.get("option_type") or "").lower() == "put"]
    call_ask = _sum_rows(call_rows, "total_ask_side_prem")
    call_bid = _sum_rows(call_rows, "total_bid_side_prem")
    put_ask = _sum_rows(put_rows, "total_ask_side_prem")
    put_bid = _sum_rows(put_rows, "total_bid_side_prem")
    call_premium = _sum_rows(call_rows, "total_premium")
    put_premium = _sum_rows(put_rows, "total_premium")
    bullish = call_ask + put_bid
    bearish = put_ask + call_bid
    gross = max(bullish + bearish, 1.0)
    net = bullish - bearish
    if net > max(100000, gross * 0.15):
        bias = "Bullish flow"
    elif net < -max(100000, gross * 0.15):
        bias = "Bearish flow"
    else:
        bias = "Mixed flow"
    by_strike: dict[float, dict] = {}
    for row in rows:
        strike = _strike_key(row.get("strike"))
        if strike is None:
            continue
        side = str(row.get("type") or row.get("option_type") or "").lower()
        bucket = by_strike.setdefault(strike, {"strike": strike, "call_premium": 0.0, "put_premium": 0.0, "net_pressure": 0.0, "alerts": 0})
        premium = _finite_float(row.get("total_premium"), 0.0)
        ask = _finite_float(row.get("total_ask_side_prem"), 0.0)
        bid = _finite_float(row.get("total_bid_side_prem"), 0.0)
        if side == "call":
            bucket["call_premium"] += premium
            bucket["net_pressure"] += ask - bid
        elif side == "put":
            bucket["put_premium"] += premium
            bucket["net_pressure"] += bid - ask
        bucket["alerts"] += 1
    largest = sorted(rows, key=lambda row: _finite_float(row.get("total_premium"), 0.0), reverse=True)[:5]
    alert_summaries = [
        {
            "type": str(row.get("type") or row.get("option_type") or "").upper(),
            "strike": _finite_float(row.get("strike")),
            "expiry": row.get("expiry"),
            "premium": _finite_float(row.get("total_premium"), 0.0),
            "ask_premium": _finite_float(row.get("total_ask_side_prem"), 0.0),
            "bid_premium": _finite_float(row.get("total_bid_side_prem"), 0.0),
            "rule": row.get("alert_rule") or row.get("rule_name"),
            "sweep": bool(row.get("has_sweep") or row.get("is_sweep")),
            "created_at": row.get("created_at") or row.get("timestamp"),
        }
        for row in largest
    ]
    key_strikes = sorted(by_strike.values(), key=lambda row: abs(row.get("net_pressure", 0.0)) + row.get("call_premium", 0.0) + row.get("put_premium", 0.0), reverse=True)[:6]
    latest_ts = max((parse_market_timestamp(row.get("created_at") or row.get("timestamp") or row.get("time")) for row in rows), default=None)
    return {
        "flow_bias": bias,
        "alert_count": len(rows),
        "call_premium": call_premium,
        "put_premium": put_premium,
        "bullish_premium": bullish,
        "bearish_premium": bearish,
        "net_premium_pressure": net,
        "largest_alerts": alert_summaries,
        "key_strikes": key_strikes,
        "as_of": str(latest_ts) if latest_ts is not None else None,
    }


def _option_row_type(row: dict) -> str:
    raw = str(row.get("type") or row.get("option_type") or row.get("contract_type") or row.get("side") or "").upper()
    if raw in {"C", "CALLS"}:
        return "CALL"
    if raw in {"P", "PUTS"}:
        return "PUT"
    if raw in {"CALL", "PUT"}:
        return raw
    symbol = str(row.get("option_symbol") or row.get("contract") or "").upper()
    if re.search(r"\d+C\d", symbol):
        return "CALL"
    if re.search(r"\d+P\d", symbol):
        return "PUT"
    return raw


def _row_trade_premium(row: dict) -> float:
    premium = _finite_float(
        row.get("total_premium"),
        _finite_float(row.get("premium"), _finite_float(row.get("notional"), _finite_float(row.get("value"), 0.0))),
    )
    if premium:
        return premium
    price = _finite_float(row.get("price") or row.get("avg_price"), 0.0)
    size = _finite_float(row.get("size") or row.get("volume") or row.get("open_volume"), 0.0)
    return price * size * 100


def _row_side_pressure(row: dict, option_type: str, fallback_premium: float) -> float:
    ask = _finite_float(row.get("total_ask_side_prem"), _finite_float(row.get("ask_side_premium"), _finite_float(row.get("ask_side"), 0.0)))
    bid = _finite_float(row.get("total_bid_side_prem"), _finite_float(row.get("bid_side_premium"), _finite_float(row.get("bid_side"), 0.0)))
    if ask or bid:
        return (ask - bid) if option_type == "CALL" else (bid - ask)
    side = str(row.get("trade_side") or row.get("side") or row.get("sentiment") or "").lower()
    if "ask" in side or "buy" in side or "bull" in side:
        return fallback_premium if option_type == "CALL" else -fallback_premium
    if "bid" in side or "sell" in side or "bear" in side:
        return -fallback_premium if option_type == "CALL" else fallback_premium
    return fallback_premium if option_type == "CALL" else -fallback_premium


def summarize_unusual_whales_recent_flow(payload: dict | None, now_ct, expiration_date=None, latest_price: float | None = None) -> dict | None:
    expiry_target = str(expiration_date) if expiration_date is not None else ""
    rows = []
    for row in payload_rows(payload):
        ticker = str(row.get("ticker") or row.get("ticker_symbol") or row.get("underlying_symbol") or row.get("symbol") or "").upper()
        if ticker and ticker != SYMBOL:
            continue
        row_expiry = str(row.get("expiry") or row.get("expiration") or row.get("expiration_date") or "")
        if expiry_target and row_expiry and row_expiry != expiry_target:
            continue
        if not row_is_current_for_0dte(row, now_ct, ("executed_at", "created_at", "timestamp", "time", "date")):
            continue
        option_type = _option_row_type(row)
        if option_type not in {"CALL", "PUT"}:
            continue
        rows.append(row)
    if not rows:
        return None

    call_premium = 0.0
    put_premium = 0.0
    net_pressure = 0.0
    by_strike: dict[float, dict] = {}
    for row in rows:
        option_type = _option_row_type(row)
        strike = _strike_key(row.get("strike"))
        premium = _row_trade_premium(row)
        pressure = _row_side_pressure(row, option_type, premium)
        if option_type == "CALL":
            call_premium += premium
        else:
            put_premium += premium
        net_pressure += pressure
        if strike is None:
            continue
        if latest_price is not None and not pd.isna(latest_price) and abs(strike - float(latest_price)) > 12:
            continue
        bucket = by_strike.setdefault(strike, {"strike": strike, "call_premium": 0.0, "put_premium": 0.0, "net_pressure": 0.0, "trades": 0})
        bucket["call_premium" if option_type == "CALL" else "put_premium"] += premium
        bucket["net_pressure"] += pressure
        bucket["trades"] += 1

    gross = max(call_premium + put_premium, 1.0)
    if net_pressure > max(75000, gross * 0.12):
        tone = "Recent call buying"
    elif net_pressure < -max(75000, gross * 0.12):
        tone = "Recent put buying"
    else:
        tone = "Balanced recent flow"
    latest_ts = max((parse_market_timestamp(row.get("executed_at") or row.get("created_at") or row.get("timestamp") or row.get("time")) for row in rows), default=None)
    top_strikes = sorted(by_strike.values(), key=lambda row: abs(row.get("net_pressure", 0.0)) + row.get("call_premium", 0.0) + row.get("put_premium", 0.0), reverse=True)[:6]
    return {
        "tone": tone,
        "trade_count": len(rows),
        "call_premium": call_premium,
        "put_premium": put_premium,
        "net_pressure": net_pressure,
        "top_strikes": top_strikes,
        "as_of": str(latest_ts) if latest_ts is not None else None,
    }


def summarize_unusual_whales_net_premium_ticks(payload: dict | None, now_ct) -> dict | None:
    rows = [row for row in payload_rows(payload) if row_is_current_for_0dte(row, now_ct, ("timestamp", "date", "time"))]
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: parse_market_timestamp(row.get("timestamp") or row.get("date") or row.get("time")) or pd.Timestamp.min.tz_localize("UTC"))

    def _net(row: dict) -> float:
        direct = _finite_float(row.get("net_premium") or row.get("net_prem"))
        if not pd.isna(direct):
            return direct
        call_net = _finite_float(row.get("net_call_premium") or row.get("call_premium") or row.get("call_net_premium"), 0.0)
        put_net = _finite_float(row.get("net_put_premium") or row.get("put_premium") or row.get("put_net_premium"), 0.0)
        return call_net - abs(put_net)

    latest = rows[-1]
    latest_net = _net(latest)
    prior_net = _net(rows[-min(len(rows), 12)])
    trend = latest_net - prior_net
    if latest_net > 750000 and trend >= 0:
        tone = "Call premium building"
    elif latest_net < -750000 and trend <= 0:
        tone = "Put premium building"
    elif latest_net > 0:
        tone = "Call premium holding"
    elif latest_net < 0:
        tone = "Put premium holding"
    else:
        tone = "Balanced premium tape"
    return {
        "tone": tone,
        "net_premium": latest_net,
        "trend_pressure": trend,
        "net_call_premium": _finite_float(latest.get("net_call_premium") or latest.get("call_premium") or latest.get("call_net_premium"), 0.0),
        "net_put_premium": _finite_float(latest.get("net_put_premium") or latest.get("put_premium") or latest.get("put_net_premium"), 0.0),
        "timestamp": latest.get("timestamp") or latest.get("date") or latest.get("time"),
    }


def summarize_unusual_whales_greeks(payload: dict | None, expiration_date=None, latest_price: float | None = None) -> dict | None:
    expiry_target = str(expiration_date) if expiration_date is not None else ""
    rows = []
    for row in payload_rows(payload):
        row_expiry = str(row.get("expiry") or row.get("expiration") or row.get("expiration_date") or "")
        if expiry_target and row_expiry and row_expiry != expiry_target:
            continue
        strike = _strike_key(row.get("strike"))
        if strike is None:
            continue
        if latest_price is not None and not pd.isna(latest_price) and abs(strike - float(latest_price)) > 8:
            continue
        call_delta = _finite_float(row.get("call_delta") or row.get("delta_call") or row.get("call_delta_oi") or row.get("delta"))
        put_delta = _finite_float(row.get("put_delta") or row.get("delta_put") or row.get("put_delta_oi"))
        call_gamma = _finite_float(row.get("call_gamma") or row.get("gamma_call") or row.get("call_gamma_oi") or row.get("gamma"))
        put_gamma = _finite_float(row.get("put_gamma") or row.get("gamma_put") or row.get("put_gamma_oi"))
        rows.append({
            "strike": strike,
            "call_delta": None if pd.isna(call_delta) else call_delta,
            "put_delta": None if pd.isna(put_delta) else put_delta,
            "call_gamma": None if pd.isna(call_gamma) else call_gamma,
            "put_gamma": None if pd.isna(put_gamma) else put_gamma,
        })
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: abs(row["strike"] - float(latest_price)) if latest_price is not None and not pd.isna(latest_price) else row["strike"])
    nearest = rows[0]
    return {
        "nearest": nearest,
        "levels": rows[:8],
        "as_of": str(pd.Timestamp.now(tz=get_central_tz())),
    }


def summarize_unusual_whales_options_volume(payload: dict | None, now_ct) -> dict | None:
    rows = [row for row in payload_rows(payload) if row_is_current_for_0dte(row, now_ct, ("timestamp", "date", "time"))]
    if not rows:
        return None
    row = rows[-1]
    call_volume = _finite_float(row.get("call_volume") or row.get("calls_volume") or row.get("call_vol"), 0.0)
    put_volume = _finite_float(row.get("put_volume") or row.get("puts_volume") or row.get("put_vol"), 0.0)
    ratio = _finite_float(row.get("put_call_ratio") or row.get("put_call_volume_ratio"))
    if pd.isna(ratio) and call_volume:
        ratio = put_volume / call_volume
    return {
        "call_volume": call_volume,
        "put_volume": put_volume,
        "put_call_volume_ratio": ratio,
        "timestamp": row.get("timestamp") or row.get("date") or row.get("time"),
    }


def summarize_unusual_whales_iv(payload: dict | None) -> dict | None:
    rows = payload_rows(payload)
    if not rows:
        return None
    row = rows[-1]
    return {
        "iv": _finite_float(row.get("iv") or row.get("implied_volatility") or row.get("interpolated_iv")),
        "iv_rank": _finite_float(row.get("iv_rank") or row.get("rank")),
        "iv_percentile": _finite_float(row.get("iv_percentile") or row.get("percentile")),
        "term_note": row.get("tenor") or row.get("expiry") or row.get("date"),
    }


def summarize_unusual_whales_darkpool(payload: dict | None, now_ct, latest_price: float | None = None) -> dict | None:
    rows = []
    for row in payload_rows(payload):
        ticker = str(row.get("ticker") or row.get("symbol") or "").upper()
        if ticker and ticker != SYMBOL:
            continue
        if not row_is_current_for_0dte(row, now_ct, ("executed_at", "timestamp", "time")):
            continue
        rows.append(row)
    if not rows:
        return None
    total_premium = _sum_rows(rows, "premium")
    largest = sorted(rows, key=lambda row: _finite_float(row.get("premium"), 0.0), reverse=True)[:5]
    levels: dict[float, float] = {}
    for row in rows:
        price = _finite_float(row.get("price"))
        if pd.isna(price):
            continue
        rounded = round(price, 1)
        if latest_price is not None and not pd.isna(latest_price) and abs(rounded - float(latest_price)) > 15:
            continue
        levels[rounded] = levels.get(rounded, 0.0) + _finite_float(row.get("premium"), 0.0)
    return {
        "print_count": len(rows),
        "total_premium": total_premium,
        "largest_prints": [
            {
                "price": _finite_float(row.get("price")),
                "premium": _finite_float(row.get("premium"), 0.0),
                "size": _finite_float(row.get("size"), 0.0),
                "executed_at": row.get("executed_at") or row.get("timestamp"),
            }
            for row in largest
        ],
        "key_levels": [{"price": price, "premium": premium} for price, premium in sorted(levels.items(), key=lambda item: item[1], reverse=True)[:5]],
    }


def summarize_unusual_whales_market_tide(payload: dict | None, now_ct) -> dict | None:
    rows = [row for row in payload_rows(payload) if row_is_current_for_0dte(row, now_ct, ("timestamp", "date"))]
    if not rows:
        return None
    rows = sorted(rows, key=lambda row: parse_market_timestamp(row.get("timestamp") or row.get("date")) or pd.Timestamp.min.tz_localize("UTC"))
    latest = rows[-1]
    call_net = _finite_float(latest.get("net_call_premium"), 0.0)
    put_net = _finite_float(latest.get("net_put_premium"), 0.0)
    net = call_net - abs(put_net)
    if net > 1000000:
        tone = "Risk-on options tide"
    elif net < -1000000:
        tone = "Risk-off options tide"
    else:
        tone = "Balanced options tide"
    return {
        "tone": tone,
        "net_call_premium": call_net,
        "net_put_premium": put_net,
        "net_volume": _finite_float(latest.get("net_volume"), 0.0),
        "timestamp": latest.get("timestamp") or latest.get("date"),
    }


def summarize_unusual_whales_gex(payload: dict | None, latest_price: float | None = None) -> dict:
    rows = []
    for row in payload_rows(payload):
        strike = _strike_key(row.get("strike") or row.get("price"))
        if strike is None:
            continue
        call_gex = _finite_float(row.get("call_gex"), _finite_float(row.get("call_gamma_oi"), 0.0))
        put_gex = _finite_float(row.get("put_gex"), _finite_float(row.get("put_gamma_oi"), 0.0))
        total = call_gex + put_gex
        rows.append({"strike": strike, "total_gex": total, "call_gex": call_gex, "put_gex": put_gex})
    if latest_price is not None and not pd.isna(latest_price):
        rows = [row for row in rows if abs(row["strike"] - float(latest_price)) <= 35] or rows
    rows = sorted(rows, key=lambda row: row["strike"])
    gamma_flip = None
    for left, right in zip(rows, rows[1:]):
        if left["total_gex"] == 0:
            gamma_flip = left["strike"]
            break
        if (left["total_gex"] < 0 < right["total_gex"]) or (left["total_gex"] > 0 > right["total_gex"]):
            gamma_flip = round((left["strike"] + right["strike"]) / 2, 2)
            break
    ranked = sorted(rows, key=lambda row: abs(row["total_gex"]), reverse=True)[:6]
    net = sum(row["total_gex"] for row in rows)
    tone = "Stabilizing positive gamma" if net > 0 else "Volatile negative gamma" if net < 0 else "Neutral gamma"
    return {"gamma_flip": gamma_flip, "dealer_tone": tone, "levels": ranked, "net_gex": net}


def fetch_unusual_whales_intelligence(expiration_date, latest_price: float | None = None, now_ct=None) -> tuple[dict | None, SourceStatus]:
    now = pd.Timestamp(now_ct if now_ct is not None else datetime.now(tz=get_central_tz()))
    now = now.tz_localize(get_central_tz()) if now.tzinfo is None else now.tz_convert(get_central_tz())
    if not get_unusual_whales_token():
        return None, unusual_whales_status(False, "Premium order-flow feed is not configured.", skipped=True)
    today = str(now.date())
    errors = []
    flow_payload, err = fetch_unusual_whales_json(
        "/api/option-trades/flow-alerts",
        (
            ("ticker_symbol", SYMBOL),
            ("is_otm", True),
            ("min_premium", 10000),
            ("limit", 100),
        ),
    )
    if err:
        errors.append(err)
    recent_flow_payload, err = fetch_unusual_whales_json(f"/api/stock/{SYMBOL}/flow-recent")
    if err:
        errors.append(err)
    tide_payload, err = fetch_unusual_whales_json("/api/market/market-tide", (("date", today), ("otm_only", "true"), ("interval_5m", "true")))
    if err:
        errors.append(err)
    net_premium_payload, err = fetch_unusual_whales_json(f"/api/stock/{SYMBOL}/net-prem-ticks")
    if err:
        errors.append(err)
    options_volume_payload, err = fetch_unusual_whales_json(f"/api/stock/{SYMBOL}/options-volume", (("date", today),))
    if err:
        errors.append(err)
    iv_payload, err = fetch_unusual_whales_json(f"/api/stock/{SYMBOL}/interpolated-iv", (("date", today),))
    if err:
        errors.append(err)
    gex_payload, err = fetch_unusual_whales_json(
        f"/api/stock/{SYMBOL}/spot-exposures/strike",
        tuple(
            (key, value)
            for key, value in [
                ("date", today),
                ("min_strike", int(float(latest_price) - 35) if latest_price is not None and not pd.isna(latest_price) else None),
                ("max_strike", int(float(latest_price) + 35) if latest_price is not None and not pd.isna(latest_price) else None),
                ("limit", 100),
            ]
            if value is not None
        ),
    )
    if err:
        errors.append(err)
    greeks_payload, err = fetch_unusual_whales_json(f"/api/stock/{SYMBOL}/greeks")
    if err:
        errors.append(err)
    darkpool_payload, err = fetch_unusual_whales_json(f"/api/darkpool/{SYMBOL}", (("limit", 50),))
    if err:
        errors.append(err)
    news_payload, err = fetch_unusual_whales_json("/api/news/headlines", (("ticker", SYMBOL), ("limit", 10),))
    if err:
        errors.append(err)
    flow = summarize_unusual_whales_flow_alerts(flow_payload, now, expiration_date)
    recent_flow = summarize_unusual_whales_recent_flow(recent_flow_payload, now, expiration_date, latest_price)
    tide = summarize_unusual_whales_market_tide(tide_payload, now)
    net_premium = summarize_unusual_whales_net_premium_ticks(net_premium_payload, now)
    volume = summarize_unusual_whales_options_volume(options_volume_payload, now)
    iv = summarize_unusual_whales_iv(iv_payload)
    darkpool = summarize_unusual_whales_darkpool(darkpool_payload, now, latest_price)
    gex = summarize_unusual_whales_gex(gex_payload, latest_price)
    greeks = summarize_unusual_whales_greeks(greeks_payload, expiration_date, latest_price)
    uw_news_rows = [row for row in payload_rows(news_payload) if row_is_current_for_0dte(row, now, ("created_at", "published_at", "timestamp", "time", "date"))][:5]
    has_data = bool(flow["alert_count"] or recent_flow or tide or net_premium or volume or iv or darkpool or uw_news_rows or gex.get("levels") or greeks)
    if not has_data:
        detail = "Premium order-flow feed is connected, but no current SPY 0DTE rows returned yet."
        if errors:
            detail = errors[0]
        return None, unusual_whales_status(False, detail, now)
    payload = {
        "source": "Premium order-flow feed",
        "date": today,
        "flow_alerts": flow,
        "recent_flow": recent_flow,
        "market_tide": tide,
        "net_premium_ticks": net_premium,
        "options_volume": volume,
        "interpolated_iv": iv,
        "darkpool": darkpool,
        "fresh_news": [
            {
                "title": row.get("title") or row.get("headline"),
                "source": row.get("source") or row.get("provider") or "Premium order-flow feed",
                "published_at": row.get("created_at") or row.get("published_at") or row.get("timestamp") or row.get("date"),
                "url": row.get("url") or row.get("link"),
            }
            for row in uw_news_rows
        ],
        "gex": gex,
        "greeks": greeks,
    }
    bits = []
    if flow["alert_count"]:
        bits.append(f"{flow['alert_count']} SPY 0DTE OTM flow alerts")
    if recent_flow:
        bits.append("recent SPY flow tape")
    if net_premium:
        bits.append("net premium tape")
    if tide:
        bits.append(tide["tone"])
    if gex.get("levels"):
        bits.append("GEX by strike")
    if greeks:
        bits.append("near-strike Greeks")
    if darkpool:
        bits.append("SPY dark-pool prints")
    detail = "Loaded " + ", ".join(bits or ["premium SPY flow context"]) + "."
    return payload, unusual_whales_status(True, detail, flow.get("as_of") or now)


def filter_near_spy_strikes(calls: pd.DataFrame, puts: pd.DataFrame, underlying_price: float | None, width: float = 25.0) -> tuple[pd.DataFrame, pd.DataFrame]:
    if underlying_price is None or pd.isna(underlying_price):
        return calls, puts
    def _near(df: pd.DataFrame) -> pd.DataFrame:
        if df is None or df.empty or "strike" not in df:
            return df
        return df[(df["strike"].astype(float) - float(underlying_price)).abs() <= width]
    near_calls, near_puts = _near(calls), _near(puts)
    if near_calls.empty or near_puts.empty:
        return calls, puts
    return near_calls, near_puts


def build_options_intelligence(expiration_date, underlying_price: float | None = None, option_state: OptionsCockpitState | None = None) -> OptionsIntelligence:
    selected_quotes = selected_option_quote_summaries(option_state)
    whales_payload, whales_status = fetch_unusual_whales_intelligence(expiration_date, underlying_price)
    if whales_payload is not None:
        whales_payload = {**whales_payload, "status": asdict(whales_status)}
    calls, puts, chain_status = option_chain_for_expiration(expiration_date)
    calls, puts = filter_near_spy_strikes(calls, puts, underlying_price)
    if calls.empty or puts.empty:
        status = whales_status if whales_payload else chain_status
        return OptionsIntelligence(status, float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), [], selected_quotes, whales_payload)
    call_oi = float(calls.get("openInterest", pd.Series(dtype="float64")).fillna(0).sum())
    put_oi = float(puts.get("openInterest", pd.Series(dtype="float64")).fillna(0).sum())
    call_vol = float(calls.get("volume", pd.Series(dtype="float64")).fillna(0).sum())
    put_vol = float(puts.get("volume", pd.Series(dtype="float64")).fillna(0).sum())
    call_wall = float(calls.sort_values("openInterest", ascending=False).iloc[0]["strike"]) if call_oi > 0 else float("nan")
    put_wall = float(puts.sort_values("openInterest", ascending=False).iloc[0]["strike"]) if put_oi > 0 else float("nan")
    detail = "Available option-chain context using near-SPY open interest, volume, and selected contract quotes."
    if whales_payload:
        detail += " Premium flow and gamma context is loaded."
    status = source_status("Options intelligence", True, detail, pd.Timestamp.now(tz=get_central_tz()))
    return OptionsIntelligence(
        status,
        put_oi / call_oi if call_oi else float("nan"),
        put_vol / call_vol if call_vol else float("nan"),
        calculate_max_pain(calls, puts),
        call_wall,
        put_wall,
        top_open_interest_rows(calls, puts),
        selected_quotes,
        whales_payload,
    )


def build_gamma_exposure_insight(options_intel: OptionsIntelligence) -> GammaExposureInsight:
    whales = options_intel.unusual_whales or {}
    whales_gex = whales.get("gex") if isinstance(whales, dict) else None
    if isinstance(whales_gex, dict) and (whales_gex.get("levels") or whales_gex.get("gamma_flip")):
        levels = whales_gex.get("levels") or []
        magnets = [row.get("strike") for row in levels if isinstance(row, dict) and row.get("strike") is not None]
        notes = "Spot GEX by strike is loaded; use these levels as volatility/magnet context, not as standalone entries."
        return GammaExposureInsight(
            source_status("Dealer Gamma", True, "SPY spot GEX by strike loaded.", pd.Timestamp.now(tz=get_central_tz())),
            whales_gex.get("gamma_flip"),
            str(whales_gex.get("dealer_tone") or "Dealer Gamma"),
            [float(x) for x in magnets[:6] if not pd.isna(_finite_float(x))],
            notes,
            whales,
        )
    if not get_secret_or_env("GEX_API_URL"):
        magnets = [x for x in [options_intel.put_wall, options_intel.max_pain, options_intel.call_wall] if x is not None and not pd.isna(x)]
        return GammaExposureInsight(source_status("OI magnet proxy", True, "Near-SPY option open interest proxy from available option chain."), None, "OI proxy", magnets, "Near-SPY open-interest magnets from the option chain.", None)
    payload, status = fetch_external_json_payload("GEX_API_URL", "GEX_API_KEY")
    if payload:
        gamma_flip = _finite_float(payload.get("gamma_flip") or payload.get("gammaFlip") or payload.get("flip"))
        magnets = payload.get("magnet_strikes") or payload.get("magnets") or []
        magnets = [float(x) for x in magnets if not pd.isna(_finite_float(x))][:6] if isinstance(magnets, list) else []
        tone = str(payload.get("dealer_tone") or payload.get("tone") or "Provider supplied")
        notes = str(payload.get("notes") or "True GEX supplied by configured provider.")
        return GammaExposureInsight(source_status("Gamma exposure", True, "Configured GEX provider returned data.", pd.Timestamp.now(tz=get_central_tz()), status.url), gamma_flip if not pd.isna(gamma_flip) else None, tone, magnets, notes, payload)
    magnets = [x for x in [options_intel.put_wall, options_intel.max_pain, options_intel.call_wall] if x is not None and not pd.isna(x)]
    return GammaExposureInsight(source_status("OI magnet proxy", True, "GEX provider did not return data; using near-SPY option open interest proxy."), None, "OI proxy", magnets, "Near-SPY open-interest magnets from the option chain.", None)


def score_headline_sentiment(news_items: list[NewsItem]) -> SentimentContext:
    social_payload, social_status = fetch_external_json_payload("SOCIAL_SENTIMENT_API_URL", "SOCIAL_SENTIMENT_API_KEY")
    if social_payload:
        label = str(social_payload.get("label") or social_payload.get("sentiment") or "Provider supplied")
        score = int(_finite_float(social_payload.get("score"), 0))
        return SentimentContext(source_status("Social sentiment", True, "Configured social sentiment provider returned data.", pd.Timestamp.now(tz=get_central_tz()), social_status.url), score, label, 0, 0, social_payload)
    bullish_words = ["rally", "risk-on", "higher", "beats", "easing", "cooling inflation", "cut", "green", "surge"]
    bearish_words = ["selloff", "risk-off", "lower", "miss", "hot inflation", "hike", "red", "fear", "stress"]
    bull = bear = 0
    for item in news_items:
        text = f"{item.title} {item.summary or ''}".lower()
        bull += sum(1 for word in bullish_words if word in text)
        bear += sum(1 for word in bearish_words if word in text)
    score = bull - bear
    label = "Bullish headlines" if score > 1 else "Bearish headlines" if score < -1 else "Mixed headlines"
    return SentimentContext(source_status("Fresh headline read", True if news_items else False, "Same-day and previous-day market headlines scanned for catalyst tone."), score, label, bull, bear, None)


def structure_lines_for_briefing(primary_lines: list[DynamicLine], projection_time) -> list[dict]:
    rows = []
    for name in ["UA", "UD", "LA", "LD"]:
        line = get_line_by_name(primary_lines or [], name)
        if not line:
            continue
        rows.append({
            "code": name,
            "name": display_line_name(name),
            "role": zone_side_label(line.zone_type),
            "value": line.tradable_value_at(projection_time),
            "anchor_price": line.anchor_price,
            "anchor_time": fmt_time(line.anchor_time),
        })
    return rows


def build_morning_briefing_bundle(primary_lines, projection_time, economic_events, news_items, learning_profile, latest_price, selected_strikes=None, option_state=None) -> MorningBriefingBundle:
    global_context = fetch_global_context()
    sector_context = fetch_sector_context()
    daily = fetch_spy_daily("1y")
    technical = build_technical_context(daily, latest_price)
    expiration = selected_strikes.expiration_date if selected_strikes else pd.Timestamp(projection_time).date()
    options_intel = build_options_intelligence(expiration, latest_price, option_state)
    gamma = build_gamma_exposure_insight(options_intel)
    sentiment = score_headline_sentiment(news_items)
    macro_context = [move for move in global_context if move.label in {"Dollar Index", "10Y yield", "5Y yield"}]
    source_statuses = [technical.status, options_intel.status, sentiment.status]
    whales_status_raw = (options_intel.unusual_whales or {}).get("status") if isinstance(options_intel.unusual_whales, dict) else None
    if isinstance(whales_status_raw, dict):
        source_statuses.append(SourceStatus(
            str(whales_status_raw.get("name") or "Order Flow Feed"),
            str(whales_status_raw.get("status") or "connected"),
            str(whales_status_raw.get("detail") or "Premium order-flow data loaded."),
            pd.Timestamp(whales_status_raw.get("as_of")) if whales_status_raw.get("as_of") else None,
            whales_status_raw.get("url"),
        ))
    if gamma.provider_payload:
        source_statuses.append(gamma.status)
    source_statuses.append(source_status("Global yfinance markets", bool(global_context), f"{len(global_context)} instruments loaded from Yahoo Finance."))
    calendar_detail = (
        f"{len(economic_events)} verified calendar rows loaded from local calendar or Trading Economics."
        if economic_events
        else "No dated macro event is loaded yet; Foresight can scan current calendar sources before trading."
    )
    source_statuses.append(source_status("Economic calendar", bool(economic_events), calendar_detail))
    news_sources = sorted({item.source for item in news_items})
    news_detail = (
        f"{len(news_items)} fresh 0DTE headlines loaded from {', '.join(news_sources)}; only today or previous-day items are included."
        if news_items
        else f"No same-day or previous-day market headlines loaded from {len(NEWS_RSS_FEEDS)} configured public feeds."
    )
    source_statuses.append(source_status("Market news", bool(news_items), news_detail))
    return MorningBriefingBundle(
        pd.Timestamp.now(tz=get_central_tz()),
        structure_lines_for_briefing(primary_lines, projection_time),
        economic_events,
        global_context,
        macro_context,
        sector_context,
        options_intel,
        gamma,
        sentiment,
        technical,
        news_items,
        learning_profile,
        source_statuses,
    )


def briefing_bundle_to_dict(bundle: MorningBriefingBundle) -> dict:
    return json.loads(json.dumps(asdict(bundle), default=str))


def build_morning_briefing_prompt(bundle: MorningBriefingBundle) -> str:
    payload = briefing_bundle_to_dict(bundle)
    curated = json.dumps(CURATED_MORNING_SOURCES, indent=2)
    return (
        "You are the Prophet Foresight Engine inside SPY Prophet. Produce an actionable, structured read for a novice 0DTE SPY options trader.\n"
        "Rules: use the verified JSON facts plus live web search facts you can cite. Do not invent unavailable options flow, social, or news. "
        "If premium order-flow data is present, treat it as the primary paid options-flow source and explicitly weigh SPY 0DTE OTM flow alerts, recent tape, net premium ticks, market tide, key strikes, near-strike Greeks, dark-pool levels, IV, and GEX; pair that with local max pain before choosing CALL/PUT/WAIT. "
        "For 0DTE relevance, use only same-day or previous-day external headlines and clearly ignore stale articles. "
        "Only discuss true dealer GEX if a configured provider payload is present; otherwise use the option-chain magnet proxy without saying GEX is missing. "
        "If a premium source is not accessible, omit that section from the main briefing instead of padding with apologies. "
        "Use probabilistic wording, not certainty. Include exact avoid-trading times around high-impact events. "
        "Tie every recommendation back to SPY Prophet lines and external context. "
        "Prefer sources on the scout list when current public pages are accessible, especially Tradytics public posts/videos, but cite only pages you actually used. "
        "Return ONLY valid JSON. No Markdown, no bullets outside JSON, no long narrative. "
        "If there is no clean trade, make the stance WAIT and explain the exact condition that would change it.\n\n"
        "JSON_OUTPUT_SCHEMA:\n"
        "{\n"
        "  \"stance\": \"WAIT | WATCH_CALL | WATCH_PUT | NO_TRADE\",\n"
        "  \"headline\": \"One plain-English sentence saying what to do now.\",\n"
        "  \"primary_trade\": {\n"
        "    \"label\": \"Primary setup name or Wait\",\n"
        "    \"trigger_line\": \"SPY Prophet line name\",\n"
        "    \"trigger_price\": \"price or '-'\",\n"
        "    \"contract\": \"specific 0DTE contract or '-'\",\n"
        "    \"entry_timing\": \"exact time/candle rule\",\n"
        "    \"entry_rule\": \"what must happen before entry\",\n"
        "    \"stop\": \"invalidating price/candle rule\",\n"
        "    \"target\": \"target line/price\",\n"
        "    \"confidence\": 0\n"
        "  },\n"
        "  \"why\": [\"3 to 5 concrete reasons, each tied to loaded data\"],\n"
        "  \"avoid\": [{\"label\":\"what to avoid\", \"reason\":\"why\"}],\n"
        "  \"risk_flags\": [\"specific timing/news/liquidity risks\"],\n"
        "  \"source_notes\": [\"short source note, not URLs\"],\n"
        "  \"novice_summary\": \"One sentence a beginner can act on.\"\n"
        "}\n\n"
        f"SCOUT_LIST_JSON:\n{curated}\n\n"
        f"VERIFIED_DATA_JSON:\n{json.dumps(payload, default=str, indent=2)}"
    )


def extract_openai_text(payload: dict) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"]).strip()
    pieces = []
    for item in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
        for content in item.get("content", []) if isinstance(item, dict) else []:
            text = content.get("text") if isinstance(content, dict) else None
            if text:
                pieces.append(str(text))
    return "\n".join(pieces).strip()


def normalize_citation_url(url: str | None) -> str:
    text = str(url or "").strip()
    if not text:
        return ""
    text = text.split("#", 1)[0].rstrip("/")
    return text


def citation_title(citation: dict) -> str:
    title = str(citation.get("title") or "").strip()
    url = normalize_citation_url(citation.get("url"))
    if title and title != url:
        return title
    match = re.match(r"https?://(?:www\.)?([^/]+)", url)
    return match.group(1) if match else (title or url or "AI source")


def extract_openai_citations(payload: dict) -> list[dict]:
    citations = []
    seen = set()
    for item in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
        if isinstance(item, dict) and item.get("type") == "web_search_call":
            action = item.get("action") or {}
            for source in action.get("sources") or []:
                url = normalize_citation_url(source.get("url") if isinstance(source, dict) else None)
                if url and url not in seen:
                    seen.add(url)
                    citations.append({"url": url, "title": source.get("title") or url})
        for content in item.get("content", []) if isinstance(item, dict) else []:
            for ann in content.get("annotations", []) if isinstance(content, dict) else []:
                url = normalize_citation_url(ann.get("url") if isinstance(ann, dict) else None)
                if url and url not in seen:
                    seen.add(url)
                    citations.append({"url": url, "title": ann.get("title") or url})
    return citations


def extract_json_payload_from_text(text: str) -> dict | None:
    cleaned = str(text or "").strip()
    if not cleaned:
        return None
    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", cleaned, re.IGNORECASE | re.DOTALL)
    if fence_match:
        cleaned = fence_match.group(1).strip()
    if not cleaned.startswith("{"):
        start = cleaned.find("{")
        if start >= 0:
            cleaned = cleaned[start:]
    depth = 0
    in_string = False
    escape_next = False
    for idx, char in enumerate(cleaned):
        if in_string:
            if escape_next:
                escape_next = False
            elif char == "\\":
                escape_next = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                try:
                    payload = json.loads(cleaned[: idx + 1])
                except Exception:
                    return None
                return payload if isinstance(payload, dict) else None
    try:
        payload = json.loads(cleaned)
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def openai_web_search_enabled() -> bool:
    return get_secret_or_env("OPENAI_ENABLE_WEB_SEARCH", OPENAI_WEB_SEARCH_DEFAULT).lower() in {"1", "true", "yes", "on"}


def build_openai_request_payload(prompt: str, model: str, enable_web_search: bool = True) -> dict:
    payload = {"model": model, "input": prompt, "max_output_tokens": 1900}
    if enable_web_search:
        payload["tools"] = [{
            "type": "web_search",
            "user_location": {"type": "approximate", "country": "US", "timezone": CENTRAL_TZ_NAME},
        }]
        payload["tool_choice"] = "auto"
        payload["include"] = ["web_search_call.action.sources"]
    return payload


def build_openai_calendar_prompt(now_ct, days: int = 0) -> str:
    start = pd.Timestamp(now_ct).date()
    end = (pd.Timestamp(start) + pd.Timedelta(days=days)).date()
    date_label = str(start) if start == end else f"{start} through {end}"
    return (
        "You are the SPY Prophet economic-calendar scout for a 0DTE SPY options trader.\n"
        f"Find verified United States economic calendar events scheduled for {date_label}. "
        "Use current public web sources only, such as Investing.com Economic Calendar, ForexFactory Calendar, "
        "MarketWatch Economic Calendar, Nasdaq Economic Calendar, Trading Economics public calendar, Federal Reserve, "
        "BLS, BEA, Census, Treasury, or other official agency release calendars.\n\n"
        "Rules:\n"
        "- Return ONLY a JSON object. No prose, no Markdown.\n"
        "- Include only events with an exact event_date, time_label, event name, impact, and source.\n"
        "- Convert times to both ET and CT in time_label, for example '8:30 AM ET / 7:30 AM CT'.\n"
        "- Mark CPI, PCE, NFP, FOMC, Fed Chair/scheduled Fed decision, GDP, retail sales, jobless claims, "
        "ISM/PMI, treasury auctions, and major Treasury/Fed releases as High when appropriate.\n"
        "- Put forecast, previous, actual, or source evidence in notes when available.\n"
        "- Do not include generic reminders, stale events, or events from another date.\n"
        "- If no verified rows are found, return {\"events\":[]}.\n\n"
        "JSON schema:\n"
        "{\n"
        "  \"events\": [\n"
        "    {\n"
        "      \"event_date\": \"YYYY-MM-DD\",\n"
        "      \"time_label\": \"8:30 AM ET / 7:30 AM CT\",\n"
        "      \"event\": \"Event name\",\n"
        "      \"impact\": \"High\",\n"
        "      \"source\": \"Source name\",\n"
        "      \"notes\": \"forecast/previous/actual or why this matters\"\n"
        "    }\n"
        "  ]\n"
        "}"
    )


def economic_event_from_ai_calendar_dict(raw: dict) -> EconomicEvent | None:
    event_name = raw.get("event") or raw.get("name") or raw.get("title")
    if not event_name:
        return None
    try:
        event_date = pd.Timestamp(raw.get("event_date") or raw.get("date") or raw.get("release_date")).date()
    except Exception:
        return None
    time_label = str(raw.get("time_label") or raw.get("time") or raw.get("release_time") or "").strip()
    source = str(raw.get("source") or raw.get("provider") or "Calendar scout").strip()
    if not time_label or not source:
        return None
    impact_raw = str(raw.get("impact") or "Medium").strip().lower()
    impact = "High" if impact_raw in {"high", "3"} else "Medium" if impact_raw in {"medium", "med", "2"} else "Low" if impact_raw in {"low", "1"} else str(raw.get("impact")).title()
    notes = str(raw.get("notes") or raw.get("evidence") or "").strip() or None
    return EconomicEvent(event_date, time_label, str(event_name), impact, source, notes)


def call_openai_calendar_scout(now_ct, days: int = 0) -> tuple[list[EconomicEvent], list[dict], str | None]:
    api_key = get_secret_or_env("OPENAI_API_KEY")
    if not api_key:
        return [], [], "Live synthesis key is not configured."
    if not openai_web_search_enabled():
        return [], [], "Current source scan is not enabled."
    model = get_secret_or_env("OPENAI_MODEL", OPENAI_DEFAULT_MODEL)
    try:
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=build_openai_request_payload(build_openai_calendar_prompt(now_ct, days), model, True),
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        text = extract_openai_text(payload)
        citations = extract_openai_citations(payload)
        data = extract_json_payload_from_text(text)
    except Exception as e:
        return [], [], f"Calendar scout failed: {type(e).__name__}"
    if not isinstance(data, dict):
        return [], citations, "Calendar scout did not return parseable JSON."
    start = pd.Timestamp(now_ct).date()
    end = (pd.Timestamp(start) + pd.Timedelta(days=days)).date()
    rows = data.get("events") if isinstance(data.get("events"), list) else []
    events = [
        event for event in (economic_event_from_ai_calendar_dict(row) for row in rows if isinstance(row, dict))
        if event is not None and start <= event.event_date <= end
    ]
    events = sorted(events, key=lambda e: (pd.Timestamp(e.event_date), e.time_label, e.event))
    return events, citations, None


def bundle_with_economic_events(bundle: MorningBriefingBundle, events: list[EconomicEvent], scout_warning: str | None = None) -> MorningBriefingBundle:
    statuses = [status for status in bundle.source_statuses if status.name not in {"Economic calendar", "Calendar scout"}]
    calendar_detail = (
        f"{len(events)} verified calendar rows found by current source scan for today's 0DTE session."
        if events
        else scout_warning or "Calendar scout finished with no dated macro events for today's 0DTE session."
    )
    statuses.append(source_status("Economic calendar", bool(events), calendar_detail, pd.Timestamp.now(tz=get_central_tz())))
    statuses.append(source_status("Calendar scout", bool(events), calendar_detail, pd.Timestamp.now(tz=get_central_tz())))
    return replace(bundle, economic_events=events, source_statuses=statuses)


def merge_citations(primary: list[dict] | None, extra: list[dict] | None) -> list[dict]:
    merged = []
    seen = set()
    for citation in list(primary or []) + list(extra or []):
        if not isinstance(citation, dict):
            continue
        url = normalize_citation_url(citation.get("url"))
        key = url or citation.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append({**citation, "url": url} if url else citation)
    return merged


def result_with_extra_citations(result: MorningBriefingResult, extra: list[dict]) -> MorningBriefingResult:
    merged = merge_citations(result.citations, extra)
    return replace(result, citations=merged)


def morning_decision_from_result(result: MorningBriefingResult | None) -> dict | None:
    if result is None:
        return None
    data = extract_json_payload_from_text(result.text)
    if not isinstance(data, dict):
        return None
    trade = data.get("primary_trade")
    if not isinstance(trade, dict):
        trade = {}
    data["primary_trade"] = trade
    for key in ["why", "risk_flags", "source_notes"]:
        if not isinstance(data.get(key), list):
            data[key] = []
    if not isinstance(data.get("avoid"), list):
        data["avoid"] = []
    return data


def fallback_morning_decision(bundle: MorningBriefingBundle, result: MorningBriefingResult | None = None) -> dict:
    event = _first_high_impact_event(bundle.economic_events)
    first_line = bundle.lines[0] if bundle.lines else {}
    quote_value, _, _ = _first_quote_label(bundle.options_intelligence)
    role_text = str(first_line.get("role") or "").upper()
    desired_type = "PUT" if "PUT" in role_text else "CALL" if "CALL" in role_text else ""
    for quote in bundle.options_intelligence.selected_quotes or []:
        if desired_type and str(quote.get("type") or "").upper() == desired_type:
            quote_value = f"{desired_type} {fmt_price(quote.get('strike'), 0)}"
            break
    confidence = int(result.confidence if result else 45)
    flow = (bundle.options_intelligence.unusual_whales or {}).get("flow_alerts", {}) if isinstance(bundle.options_intelligence.unusual_whales, dict) else {}
    flow_reason = (
        f"Flow pressure reads {flow.get('flow_bias')} with net pressure {fmt_money_short(flow.get('net_premium_pressure'))}."
        if isinstance(flow, dict) and flow.get("flow_bias")
        else f"Options context shows max pain near {fmt_price(bundle.options_intelligence.max_pain)}."
    )
    return {
        "stance": "WAIT",
        "headline": "Wait for a confirmed hourly rejection before choosing a 0DTE contract.",
        "primary_trade": {
            "label": "Structure confirmation required",
            "trigger_line": first_line.get("name") or "-",
            "trigger_price": fmt_price(first_line.get("value")),
            "contract": quote_value if quote_value != "No contract loaded" else "-",
            "entry_timing": "Next candle open after confirmation",
            "entry_rule": "Price must reject the trigger line and the next candle must confirm direction.",
            "stop": "Invalid if SPY closes back through the trigger after entry.",
            "target": "Nearest valid SPY Prophet target line",
            "confidence": confidence,
        },
        "why": [
            f"Structure learning is {bundle.learning_profile.confidence_label} with target-first {fmt_pct(bundle.learning_profile.target_first_rate * 100, 0)}.",
            flow_reason,
            f"Macro timing: {event.event} at {event.time_label}." if event else "Macro timing is not loaded yet.",
        ],
        "avoid": [
            {"label": "Chasing between lines", "reason": "Your edge is at the structure trigger, not in the middle of the channel."},
        ],
        "risk_flags": [
            f"High-impact macro event: {event.event} at {event.time_label}." if event else "Calendar scout should run before assuming there is no catalyst.",
        ],
        "source_notes": ["Rule-based summary from the loaded SPY Prophet data bundle."],
        "novice_summary": "Do nothing until the line rejection confirms; then use the nearest valid OTM contract.",
    }


def call_openai_morning_briefing(prompt: str) -> tuple[str | None, str | None, list[dict]]:
    api_key = get_secret_or_env("OPENAI_API_KEY")
    if not api_key:
        return None, "Live synthesis key is not configured.", []
    model = get_secret_or_env("OPENAI_MODEL", OPENAI_DEFAULT_MODEL)
    try:
        response = requests.post(
            OPENAI_RESPONSES_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json=build_openai_request_payload(prompt, model, openai_web_search_enabled()),
            timeout=45,
        )
        response.raise_for_status()
        payload = response.json()
        text = extract_openai_text(payload)
        citations = extract_openai_citations(payload)
    except Exception as e:
        return None, f"Foresight synthesis failed: {type(e).__name__}", []
    return text or None, None if text else "Foresight synthesis returned an empty read.", citations


def move_line(move: MarketMove) -> str:
    return f"{move.label} {fmt_price(move.last)} ({fmt_float(move.change_pct)}%)"


def rule_based_morning_briefing(bundle: MorningBriefingBundle, ai_warning: str | None = None) -> MorningBriefingResult:
    warnings = [status.detail for status in bundle.source_statuses if status.status != "connected"]
    if ai_warning:
        warnings.insert(0, ai_warning)
    high_events = [event for event in bundle.economic_events if str(event.impact).lower() == "high"]
    risk_score = 45
    risk_score += min(len(high_events) * 8, 24)
    if bundle.gamma_insight.provider_payload is None and str(bundle.gamma_insight.dealer_tone).upper() != "OI PROXY":
        risk_score -= 5
    if bundle.sentiment.label.startswith("Bullish"):
        risk_score += 6
    if bundle.sentiment.label.startswith("Bearish"):
        risk_score -= 6
    risk_score = int(max(15, min(85, risk_score)))
    lines = "\n".join(f"- {row['name']}: {fmt_price(row['value'])} ({row['role']}, anchor {fmt_price(row['anchor_price'])})" for row in bundle.lines) or "- Structure lines unavailable."
    event_lines = "\n".join(f"- {event.event} at {event.time_label} ({event.impact})" for event in bundle.economic_events[:6]) or "- No dated macro events loaded."
    global_lines = "\n".join(f"- {move_line(move)}" for move in bundle.global_context[:8]) or "- Global market data unavailable."
    top_sectors = ", ".join(move_line(move) for move in bundle.sector_context[:3]) or "Unavailable"
    weak_sectors = ", ".join(move_line(move) for move in bundle.sector_context[-3:]) or "Unavailable"
    technical = bundle.technical_context
    options = bundle.options_intelligence
    gamma = bundle.gamma_insight
    recommendation = "Wait for a clean hourly rejection at one of the SPY Prophet triggers before choosing direction."
    if bundle.learning_profile.target_first_rate > bundle.learning_profile.stop_first_rate and bundle.lines:
        recommendation = f"Favor the nearest valid trigger only after confirmation; historical target-first rate is {fmt_pct(bundle.learning_profile.target_first_rate * 100, 0)} for the matched structure set."
    gamma_line = f"- Gamma exposure: {gamma.dealer_tone}. {gamma.notes}\n" if gamma.provider_payload else ""
    oi_magnets = ", ".join(fmt_price(x) for x in gamma.magnet_strikes) if gamma.magnet_strikes else "Unavailable"
    social_text = "connected" if bundle.sentiment.social_payload else "headline-only"
    selected_quote_lines = ""
    if options.selected_quotes:
        selected_quote_lines = "\n".join(
            f"- {quote.get('provider')} {quote.get('type')} {quote.get('strike')}: mark {fmt_price(quote.get('mark'))}, bid/ask {fmt_price(quote.get('bid'))}/{fmt_price(quote.get('ask'))}, delta {fmt_float(quote.get('delta'))}, spread {fmt_price(quote.get('spread'))}."
            for quote in options.selected_quotes
        )
    whales = options.unusual_whales or {}
    flow = whales.get("flow_alerts", {}) if isinstance(whales, dict) else {}
    recent_flow = whales.get("recent_flow") if isinstance(whales, dict) else None
    tide = whales.get("market_tide") if isinstance(whales, dict) else None
    net_premium = whales.get("net_premium_ticks") if isinstance(whales, dict) else None
    greeks = whales.get("greeks") if isinstance(whales, dict) else None
    flow_line = ""
    if flow:
        first_strike = (flow.get("key_strikes") or [{}])[0]
        strike_text = f" Key strike {fmt_price(first_strike.get('strike'), 0)}." if isinstance(first_strike, dict) and first_strike.get("strike") is not None else ""
        flow_line = f"- Flow pressure: {flow.get('flow_bias')} with net premium pressure {fmt_money_short(flow.get('net_premium_pressure'))}.{strike_text}\n"
    if isinstance(recent_flow, dict):
        first_recent = (recent_flow.get("top_strikes") or [{}])[0]
        strike_text = f" Leading strike {fmt_price(first_recent.get('strike'), 0)}." if isinstance(first_recent, dict) and first_recent.get("strike") is not None else ""
        flow_line += f"- Recent tape: {recent_flow.get('tone')} across {recent_flow.get('trade_count', 0)} SPY prints; pressure {fmt_money_short(recent_flow.get('net_pressure'))}.{strike_text}\n"
    if tide:
        flow_line += f"- Market tide: {tide.get('tone')} with call net {fmt_money_short(tide.get('net_call_premium'))} and put net {fmt_money_short(tide.get('net_put_premium'))}.\n"
    if isinstance(net_premium, dict):
        flow_line += f"- Premium tape: {net_premium.get('tone')} with net premium {fmt_money_short(net_premium.get('net_premium'))}.\n"
    if isinstance(greeks, dict) and isinstance(greeks.get("nearest"), dict):
        nearest = greeks["nearest"]
        flow_line += f"- Near-strike Greeks: {fmt_price(nearest.get('strike'), 0)} strike loaded for delta/gamma context.\n"
    risk_items = []
    for event in high_events[:3]:
        risk_items.append(f"{event.event} at {event.time_label}: avoid fresh entries immediately before the release and wait for post-release structure.")
    if options.put_call_open_interest_ratio is not None and not pd.isna(options.put_call_open_interest_ratio) and options.put_call_open_interest_ratio > 1.5:
        risk_items.append("Put open interest is heavy near today's chain; treat bearish reads carefully because hedging can look directional.")
    if isinstance(flow, dict) and flow.get("flow_bias") in {"Bearish flow", "Bullish flow"}:
        risk_items.append(f"Flow pressure is {flow.get('flow_bias').lower()}; do not take the opposite side unless SPY Prophet confirms a rejection.")
    risk_text = "\n".join(f"- {item}" for item in risk_items) if risk_items else "- No major risk flags from the loaded sources."
    text = f"""Good morning. Here is what you need to know for SPY trading today.

YOUR LINES TODAY:
{lines}

EXTERNAL FACTORS AFFECTING THESE LINES:
{event_lines}
- Options OI put/call ratio: {fmt_float(options.put_call_open_interest_ratio)}; volume put/call ratio: {fmt_float(options.put_call_volume_ratio)}.
- Max pain/OI magnet proxy: {fmt_price(options.max_pain)}; call wall {fmt_price(options.call_wall)}; put wall {fmt_price(options.put_wall)}.
{selected_quote_lines}
{flow_line}
{gamma_line}- OI magnets: {oi_magnets}.
- Global tone: {global_lines}
- Sector leadership: {top_sectors}. Laggards: {weak_sectors}.
- Technical: prior high {fmt_price(technical.prior_high)}, prior low {fmt_price(technical.prior_low)}, prior close {fmt_price(technical.prior_close)}, 50DMA {fmt_price(technical.ma50)}, 200DMA {fmt_price(technical.ma200)}, gap {fmt_price(technical.gap_from_prior_close)}.
- Sentiment: {bundle.sentiment.label} (headline score {bundle.sentiment.headline_score}; {social_text}).

MY RECOMMENDATION:
{recommendation}

Confidence: {risk_score}%

RISK FACTORS:
{risk_text}
"""
    return MorningBriefingResult(bundle.generated_at, "Rule-based verified briefing", None, text, risk_score, warnings, bundle.source_statuses, [])


def generate_morning_briefing(bundle: MorningBriefingBundle, use_ai: bool = True) -> MorningBriefingResult:
    if use_ai:
        ai_text, warning, citations = call_openai_morning_briefing(build_morning_briefing_prompt(bundle))
        if ai_text:
            base = rule_based_morning_briefing(bundle)
            provider = "Prophet Foresight synthesis"
            decision = extract_json_payload_from_text(ai_text)
            confidence = base.confidence
            if isinstance(decision, dict):
                trade = decision.get("primary_trade") if isinstance(decision.get("primary_trade"), dict) else {}
                try:
                    confidence = int(trade.get("confidence") or confidence)
                except Exception:
                    confidence = base.confidence
            warnings = list(base.warnings)
            if not isinstance(decision, dict):
                warnings.insert(0, "Foresight synthesis returned narrative text instead of the structured decision schema.")
            return MorningBriefingResult(bundle.generated_at, provider, get_secret_or_env("OPENAI_MODEL", OPENAI_DEFAULT_MODEL), ai_text, confidence, warnings, bundle.source_statuses, citations)
        return rule_based_morning_briefing(bundle, warning)
    return rule_based_morning_briefing(bundle)


def save_morning_briefing(result: MorningBriefingResult, path: str = MORNING_BRIEFING_PATH) -> None:
    ensure_data_dir(Path(path).parent)
    p = Path(path)
    rows = []
    if p.exists():
        try:
            rows = json.loads(p.read_text())
        except Exception:
            rows = []
    rows.append(json.loads(json.dumps(asdict(result), default=str)))
    p.write_text(json.dumps(rows[-60:], indent=2, default=str))


def get_primary_anchor_summary(primary_lines: list[DynamicLine] | None) -> dict:
    lines = primary_lines or []
    high_line = get_line_by_name(lines, "UA") or get_line_by_name(lines, "UD")
    low_line = get_line_by_name(lines, "LA") or get_line_by_name(lines, "LD")
    return {
        "high_time": high_line.anchor_time if high_line else None,
        "high_price": high_line.anchor_price if high_line else float("nan"),
        "low_time": low_line.anchor_time if low_line else None,
        "low_price": low_line.anchor_price if low_line else float("nan"),
    }


def get_available_trading_days(df: pd.DataFrame) -> list[date]:
    if df is None or df.empty:
        return []
    return sorted(set(df.index.date))


def get_prior_trading_day(df: pd.DataFrame, current_dt: datetime) -> Optional[date]:
    if df is None or df.empty:
        return None
    cur = current_dt.replace(tzinfo=get_central_tz()) if current_dt.tzinfo is None else current_dt.astimezone(get_central_tz())
    for day in reversed(get_available_trading_days(df)):
        if day < cur.date():
            return day
    return None


def get_latest_available_trading_day(df: pd.DataFrame, current_dt: datetime) -> Optional[date]:
    if df is None or df.empty:
        return None
    cur = current_dt.replace(tzinfo=get_central_tz()) if current_dt.tzinfo is None else current_dt.astimezone(get_central_tz())
    for day in reversed(get_available_trading_days(df)):
        if day <= cur.date():
            return day
    return None


def get_live_signal_day(df: pd.DataFrame, current_dt: datetime) -> Optional[date]:
    latest_day = get_latest_available_trading_day(df, current_dt)
    if latest_day is None:
        return None
    cur = current_dt.replace(tzinfo=get_central_tz()) if current_dt.tzinfo is None else current_dt.astimezone(get_central_tz())
    if latest_day < cur.date():
        return cur.date()
    return latest_day


def next_weekday(day_value) -> date:
    day = pd.Timestamp(day_value).date()
    while day.weekday() >= 5:
        day = (pd.Timestamp(day) + pd.Timedelta(days=1)).date()
    return day


def next_session_date(day_value) -> date:
    day = pd.Timestamp(day_value).date()
    if day.weekday() == 5:
        return (pd.Timestamp(day) + pd.Timedelta(days=2)).date()
    if day.weekday() == 6:
        return (pd.Timestamp(day) + pd.Timedelta(days=1)).date()
    return day


def next_session_after(day_value) -> date:
    day = (pd.Timestamp(day_value) + pd.Timedelta(days=1)).date()
    return next_weekday(day)


def default_session_date(df: pd.DataFrame, current_dt: datetime) -> date:
    current_day = pd.Timestamp(current_dt).date()
    if current_day.weekday() >= 5:
        return next_session_date(current_day)
    available = get_available_trading_days(df)
    if current_day in available or not available:
        return current_day
    return current_day


def resolve_session_clock(df: pd.DataFrame, session_day: date, current_dt: datetime) -> pd.Timestamp:
    ct = get_central_tz()
    now = pd.Timestamp(current_dt)
    now = now.tz_localize(ct) if now.tzinfo is None else now.tz_convert(ct)
    if session_day == now.date():
        return now
    session_df = df[df.index.date == session_day].sort_index() if df is not None and not df.empty else pd.DataFrame()
    rth_session = filter_rth_session(df, session_day) if df is not None and not df.empty else pd.DataFrame()
    def _to_ct(value) -> pd.Timestamp:
        ts = pd.Timestamp(value)
        return ts.tz_localize(ct) if ts.tzinfo is None else ts.tz_convert(ct)
    if not rth_session.empty:
        return _to_ct(rth_session.index[-1])
    if not session_df.empty:
        return _to_ct(session_df.index[-1])
    return pd.Timestamp(session_day, tz=ct) + pd.Timedelta(hours=9)


def latest_price_for_session(df: pd.DataFrame, session_day: date, current_dt: datetime) -> float | None:
    if df is None or df.empty or "Close" not in df:
        return None
    rth_df = filter_rth_session(df, session_day)
    if not rth_df.empty and not rth_df["Close"].dropna().empty:
        return float(rth_df["Close"].dropna().iloc[-1])
    day_df = df[df.index.date == session_day].sort_index()
    if not day_df.empty and not day_df["Close"].dropna().empty:
        return float(day_df["Close"].dropna().iloc[-1])
    close_series = df.get("Close", pd.Series(dtype="float64")).dropna()
    return float(close_series.iloc[-1]) if not close_series.empty else None


def filter_rth_session(df: pd.DataFrame, trading_day: date) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    session = df[df.index.date == trading_day].sort_index()
    rth = session.between_time(RTH_SESSION_START, RTH_SESSION_END, inclusive="both")
    diffs = session.index.to_series().diff().dropna()
    if not diffs.empty and diffs.median() >= pd.Timedelta(minutes=30):
        rth = rth[rth.index.time < RTH_SESSION_END]
    return rth


def filter_extended_session(df: pd.DataFrame, trading_day: date) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df[df.index.date == trading_day].between_time(time(3, 0), time(19, 0), inclusive="both")


def get_structure_projection_time(current_dt: datetime | pd.Timestamp, hour: int = 9, minute: int = 0) -> pd.Timestamp:
    dt = pd.Timestamp(current_dt)
    ct = get_central_tz()
    dt = dt.tz_localize(ct) if dt.tzinfo is None else dt.tz_convert(ct)
    decision_time = pd.Timestamp(dt.date(), tz=ct) + pd.Timedelta(hours=hour, minutes=minute)
    return decision_time if dt < decision_time else dt


def candle_color(row: pd.Series) -> str:
    open_key = next((k for k in row.index if str(k).lower() == "open"), None)
    close_key = next((k for k in row.index if str(k).lower() == "close"), None)
    if open_key is None or close_key is None:
        return "doji"
    o, c = float(row[open_key]), float(row[close_key])
    return "green" if c > o else "red" if c < o else "doji"


def _empty_pivot(name: str) -> Pivot:
    return Pivot(name=name, price=float("nan"), timestamp=None, source="empty_rth", candle_color="none", fallback_used=True)


def get_hourly_candle_close_time(df: pd.DataFrame, candle_time: pd.Timestamp) -> pd.Timestamp:
    idx = df.sort_index().index
    pos = idx.get_loc(candle_time)
    if isinstance(pos, slice):
        pos = pos.start
    elif not isinstance(pos, int):
        pos = int(pos[0])
    if pos + 1 < len(idx):
        return pd.Timestamp(idx[pos + 1])

    ts = pd.Timestamp(candle_time)
    ct = get_central_tz()
    ts = ts.tz_localize(ct) if ts.tzinfo is None else ts.tz_convert(ct)
    rth_close = pd.Timestamp(ts.date(), tz=ct) + pd.Timedelta(hours=15)
    if ts >= rth_close:
        return ts
    return min(ts + pd.Timedelta(hours=1), rth_close)


def find_high_pivot(rth_df: pd.DataFrame) -> Pivot:
    if rth_df is None or rth_df.empty:
        return _empty_pivot("HIGH_PIVOT")
    df = rth_df.sort_index()
    high_ts = df["High"].idxmax()
    anchor_ts = get_hourly_candle_close_time(df, high_ts)
    return Pivot("HIGH_PIVOT", float(df.loc[high_ts, "High"]), anchor_ts, "session_high", candle_color(df.loc[high_ts]), False)


def find_low_pivot(rth_df: pd.DataFrame) -> Pivot:
    if rth_df is None or rth_df.empty:
        return _empty_pivot("LOW_PIVOT")
    df = rth_df.sort_index()
    low_ts = df["Low"].idxmin()
    anchor_ts = get_hourly_candle_close_time(df, low_ts)
    return Pivot("LOW_PIVOT", float(df.loc[low_ts, "Low"]), anchor_ts, "session_low", candle_color(df.loc[low_ts]), False)


def find_primary_pivots(rth_df: pd.DataFrame) -> dict:
    return {"high": find_high_pivot(rth_df), "low": find_low_pivot(rth_df)}


def find_secondary_pivots(rth_df: pd.DataFrame) -> list[SecondaryPivot]:
    if rth_df is None or rth_df.empty:
        return []
    df = rth_df.sort_index()
    out: list[SecondaryPivot] = []
    for i in range(len(df) - 1):
        cur_color, nxt_color = candle_color(df.iloc[i]), candle_color(df.iloc[i + 1])
        if cur_color == "red" and nxt_color == "green":
            out.append(SecondaryPivot("SECONDARY_DESCENDING", float(df.iloc[i]["Low"]), df.index[i], "descending", "secondary_transition"))
        elif cur_color == "green" and nxt_color == "red":
            out.append(SecondaryPivot("SECONDARY_ASCENDING", float(df.iloc[i]["High"]), df.index[i], "ascending", "secondary_transition"))
    return out


def calculate_slope_from_observed(anchor_price: float, observed_value: float, elapsed_hours: float, direction: str) -> float:
    if any(pd.isna(v) for v in [anchor_price, observed_value, elapsed_hours]) or elapsed_hours <= 0:
        return float("nan")
    if direction == "descending":
        return float((anchor_price - observed_value) / elapsed_hours)
    if direction == "ascending":
        return float((observed_value - anchor_price) / elapsed_hours)
    return float("nan")


def build_primary_lines(high_pivot: Pivot, low_pivot: Pivot, slope_per_hour: float = DEFAULT_SLOPE_PER_HOUR) -> list[DynamicLine]:
    return [
        DynamicLine("UA", high_pivot.price, high_pivot.timestamp, slope_per_hour, "ascending", "PUT_ZONE", "PRIMARY_HIGH", True, "Upper ascending from high pivot"),
        DynamicLine("UD", high_pivot.price, high_pivot.timestamp, slope_per_hour, "descending", "CALL_ZONE", "PRIMARY_HIGH", True, "Upper descending from high pivot"),
        DynamicLine("LA", low_pivot.price, low_pivot.timestamp, slope_per_hour, "ascending", "PUT_ZONE", "PRIMARY_LOW", True, "Lower ascending from low pivot"),
        DynamicLine("LD", low_pivot.price, low_pivot.timestamp, slope_per_hour, "descending", "CALL_ZONE", "PRIMARY_LOW", True, "Lower descending from low pivot"),
    ]


def build_secondary_lines(secondary_pivots: list[SecondaryPivot], slope_per_hour: float = DEFAULT_SLOPE_PER_HOUR) -> list[DynamicLine]:
    lines: list[DynamicLine] = []
    asc_i, desc_i = 1, 1
    for p in secondary_pivots:
        if p.direction == "ascending":
            name = f"S_ASC_{asc_i:03d}"
            asc_i += 1
        else:
            name = f"S_DESC_{desc_i:03d}"
            desc_i += 1
        lines.append(DynamicLine(name, p.price, p.timestamp, slope_per_hour, p.direction, "TARGET_ONLY", "SECONDARY", False, "Secondary target/reference line"))
    return lines


def project_lines(lines: list[DynamicLine], current_dt: datetime, current_price: float | None) -> pd.DataFrame:
    records = []
    for line in lines:
        raw = line.raw_value_at(current_dt)
        tradable = line.tradable_value_at(current_dt)
        dist = line.distance_from_price(current_price, current_dt, use_tradable_value=True) if current_price is not None else float("nan")
        records.append({
            "name": line.name,
            "level": display_line_name(line.name),
            "role": display_line_description(line.name),
            "raw_projected_value": raw,
            "tradable_value": tradable,
            "distance": dist,
            "abs_distance": abs(dist) if not pd.isna(dist) else float("nan"),
            "percent_distance": (abs(dist) / current_price * 100) if (current_price not in [None, 0] and not pd.isna(dist)) else float("nan"),
            "direction": line.direction,
            "zone_type": line.zone_type,
            "source": line.source,
            "is_primary": line.is_primary,
            "anchor_price": line.anchor_price,
            "anchor_time": line.anchor_time,
            "slope_per_hour": line.slope_per_hour,
            "description": line.description,
        })
    return pd.DataFrame(records)


def build_pivot_source_table(rth_df: pd.DataFrame) -> pd.DataFrame:
    if rth_df is None or rth_df.empty:
        return pd.DataFrame()
    df = rth_df.sort_index()
    rows = []
    for label, price_col, idx in [
        ("High Pivot", "High", df["High"].idxmax()),
        ("Low Pivot", "Low", df["Low"].idxmin()),
    ]:
        candle = df.loc[idx]
        close_time = get_hourly_candle_close_time(df, idx)
        rows.append({
            "Pivot": label,
            "Source": "Yahoo SPY 60m RTH",
            "Candle Starts": idx,
            "Candle Closes": close_time,
            "Pivot Price": float(candle[price_col]),
            "Open": float(candle["Open"]),
            "High": float(candle["High"]),
            "Low": float(candle["Low"]),
            "Close": float(candle["Close"]),
        })
    return pd.DataFrame(rows)


def zone_side_label(zone_type: str | None) -> str:
    if zone_type == "CALL_ZONE":
        return "Call Trigger"
    if zone_type == "PUT_ZONE":
        return "Put Trigger"
    return "Target"


def build_structure_projection_table(primary_lines: list[DynamicLine], current_dt: datetime, current_price: float | None, structure_day: date | None, signal_day: date | None) -> pd.DataFrame:
    rows = []
    for line in primary_lines or []:
        pivot_name = "High Pivot" if line.source == "PRIMARY_HIGH" else "Low Pivot" if line.source == "PRIMARY_LOW" else _humanize(line.source)
        tradable = line.tradable_value_at(current_dt)
        distance = line.distance_from_price(current_price, current_dt) if current_price is not None else float("nan")
        hours = line.hours_since(current_dt)
        rows.append({
            "Trigger": display_line_name(line.name),
            "Type": zone_side_label(line.zone_type),
            "Based On": pivot_name,
            "Yahoo Structure Day": structure_day,
            "Signal Day": signal_day,
            "Pivot Price": line.anchor_price,
            "Pivot Candle Closes": line.anchor_time,
            "Projection Time": pd.Timestamp(current_dt),
            "Projection Method": "Protected weekend-adjusted calibration" if not pd.isna(hours) and not pd.isna(line.anchor_price) else "-",
            "Projection Hours Since Anchor": hours,
            "Projected SPY Level": tradable,
            "Current SPY": current_price,
            "Distance From SPY": distance,
        })
    return pd.DataFrame(rows)


def get_closest_primary_line(lines: list[DynamicLine], current_dt: datetime, current_price: float) -> DynamicLine | None:
    candidates: list[tuple[float, DynamicLine]] = []
    for line in lines:
        if not line.is_primary:
            continue
        v = line.tradable_value_at(current_dt)
        if pd.isna(v):
            continue
        candidates.append((abs(current_price - v), line))
    return min(candidates, key=lambda x: x[0])[1] if candidates else None


def get_lines_by_zone(lines: list[DynamicLine], zone_type: str) -> list[DynamicLine]:
    return [line for line in lines if line.zone_type == zone_type]




@dataclass(frozen=True)
class BiasState:
    bias: str
    current_price: float
    current_time: pd.Timestamp
    watched_call_lines: list[str]
    watched_put_lines: list[str]
    primary_line: str | None
    final_take_profit_line: str | None
    strength_score: float
    explanation: str
    ua_value: float
    ud_value: float
    la_value: float
    ld_value: float


@dataclass(frozen=True)
class SelectedStrikes:
    underlying_price: float
    call_strike: int
    put_strike: int
    expiration_date: object
    dte_label: str
    warning: str | None


def get_line_by_name(lines: list[DynamicLine], name: str) -> DynamicLine | None:
    for line in lines:
        if line.name == name:
            return line
    return None


def calculate_bias_strength(current_price: float, ua_value: float, ud_value: float, bias: str) -> float:
    vals = [current_price, ua_value, ud_value]
    if any(v is None or pd.isna(v) for v in vals):
        return 0.0
    top, bot = max(ua_value, ud_value), min(ua_value, ud_value)
    width = max(top - bot, 0.01)
    if bias == "BULLISH":
        score = min(100.0, ((current_price - top) / width) * 100)
    elif bias == "BEARISH":
        score = min(100.0, ((bot - current_price) / width) * 100)
    elif bias in {"NEUTRAL", "REGULAR_SESSION"}:
        center = (top + bot) / 2
        dist = abs(current_price - center)
        score = max(0.0, 100.0 - (dist / (width / 2)) * 100)
        if bias == "REGULAR_SESSION":
            score = min(score, 70.0)
    else:
        score = 0.0
    return float(max(0.0, min(100.0, score)))


def determine_preopen_bias(lines: list[DynamicLine], current_price: float, current_dt: datetime) -> BiasState:
    ct = get_central_tz()
    now = pd.Timestamp(current_dt)
    now = now.tz_localize(ct) if now.tzinfo is None else now.tz_convert(ct)
    ua = get_line_by_name(lines, "UA")
    ud = get_line_by_name(lines, "UD")
    la = get_line_by_name(lines, "LA")
    ld = get_line_by_name(lines, "LD")
    ua_v = ua.tradable_value_at(now) if ua else float("nan")
    ud_v = ud.tradable_value_at(now) if ud else float("nan")
    la_v = la.tradable_value_at(now) if la else float("nan")
    ld_v = ld.tradable_value_at(now) if ld else float("nan")

    if ua is None or ud is None or pd.isna(ua_v) or pd.isna(ud_v):
        return BiasState("UNKNOWN", current_price, now, [], [], None, None, 0.0, "Missing upper trade structure; cannot determine bias safely.", ua_v, ud_v, la_v, ld_v)

    preopen = now.time() < time(9, 0)
    top, bot = max(ua_v, ud_v), min(ua_v, ud_v)

    if current_price > top:
        bias = "BULLISH" if preopen else "REGULAR_SESSION"
        watched_call, watched_put = ["UD"], []
        primary, tp = "UD", None
        expl = "Price is above the upper structure; primary CALL watch is the Upper Call Trigger." if preopen else "Regular session posture: above upper structure; pre-open mode no longer active."
    elif bot <= current_price <= top:
        bias = "NEUTRAL" if preopen else "REGULAR_SESSION"
        watched_call, watched_put = ["UD"], ["UA"]
        primary, tp = "UD", "UA"
        expl = "Price is inside the upper channel; both call and put triggers are active." if preopen else "Regular session posture: price remains in upper channel; pre-open mode no longer active."
    else:
        bias = "BEARISH" if preopen else "REGULAR_SESSION"
        watched_call, watched_put = ["LD"], ["LA"]
        primary, tp = "LD", "LA"
        expl = "Price is below the upper channel; lower call and put triggers are more important." if preopen else "Regular session posture: below upper channel, monitoring lower structure; pre-open mode no longer active."

    score = calculate_bias_strength(current_price, ua_v, ud_v, bias)
    return BiasState(bias, current_price, now, watched_call, watched_put, primary, tp, score, expl, ua_v, ud_v, la_v, ld_v)


def select_0dte_strikes(current_price: float, current_dt: datetime) -> SelectedStrikes:
    import math
    now = pd.Timestamp(current_dt)
    now = now.tz_localize(get_central_tz()) if now.tzinfo is None else now.tz_convert(get_central_tz())
    if current_price is None or pd.isna(current_price):
        return SelectedStrikes(float("nan"), 0, 0, now.date(), "0DTE", "Invalid underlying price.")
    target_call = current_price + TARGET_OTM_STRIKE_DISTANCE
    target_put = current_price - TARGET_OTM_STRIKE_DISTANCE
    call_strike = int(math.floor(target_call / SPY_STRIKE_INCREMENT + 0.5) * SPY_STRIKE_INCREMENT)
    put_strike = int(math.floor(target_put / SPY_STRIKE_INCREMENT + 0.5) * SPY_STRIKE_INCREMENT)
    if call_strike <= current_price:
        call_strike = int(math.ceil(current_price / SPY_STRIKE_INCREMENT) * SPY_STRIKE_INCREMENT)
        if call_strike <= current_price:
            call_strike += SPY_STRIKE_INCREMENT
    if put_strike >= current_price:
        put_strike = int(math.floor(current_price / SPY_STRIKE_INCREMENT) * SPY_STRIKE_INCREMENT)
        if put_strike >= current_price:
            put_strike -= SPY_STRIKE_INCREMENT
    return SelectedStrikes(float(current_price), call_strike, put_strike, now.date(), "0DTE", None)


def get_contract_watch_price(current_price: float, current_dt: datetime, active_signal=None, all_lines=None) -> float:
    if active_signal is None:
        return current_price
    if active_signal.entry_price is not None and not pd.isna(active_signal.entry_price):
        return float(active_signal.entry_price)
    line = get_line_by_name(all_lines or [], active_signal.line_name)
    if line is not None:
        line_value = line.tradable_value_at(current_dt)
        if line_value is not None and not pd.isna(line_value):
            return float(line_value)
    if active_signal.line_value_at_rejection is not None and not pd.isna(active_signal.line_value_at_rejection):
        return float(active_signal.line_value_at_rejection)
    return current_price


def select_watch_contracts(current_price: float, current_dt: datetime, active_signal=None, all_lines=None) -> SelectedStrikes:
    reference_price = get_contract_watch_price(current_price, current_dt, active_signal, all_lines)
    return select_0dte_strikes(reference_price, current_dt)


def premium_flow_payload(options_intel: OptionsIntelligence | None) -> dict:
    whales = getattr(options_intel, "unusual_whales", None) or {}
    return whales if isinstance(whales, dict) else {}


def premium_flow_direction(options_intel: OptionsIntelligence | None) -> dict:
    whales = premium_flow_payload(options_intel)
    flow = whales.get("flow_alerts") or {}
    recent_flow = whales.get("recent_flow") or {}
    tide = whales.get("market_tide") or {}
    net_premium = whales.get("net_premium_ticks") or {}
    volume = whales.get("options_volume") or {}
    gex = whales.get("gex") or {}
    greeks = whales.get("greeks") or {}
    score = 0
    reasons: list[str] = []

    bias = str(flow.get("flow_bias") or "")
    if "bull" in bias.lower():
        score += 2
        reasons.append("SPY 0DTE flow leans call-side")
    elif "bear" in bias.lower():
        score -= 2
        reasons.append("SPY 0DTE flow leans put-side")
    elif bias:
        reasons.append("SPY 0DTE flow is mixed")

    recent_tone = str(recent_flow.get("tone") or "")
    recent_pressure = _finite_float(recent_flow.get("net_pressure"))
    if "call" in recent_tone.lower() or (not pd.isna(recent_pressure) and recent_pressure > 150000):
        score += 1
        reasons.append("recent SPY tape is call-led")
    elif "put" in recent_tone.lower() or (not pd.isna(recent_pressure) and recent_pressure < -150000):
        score -= 1
        reasons.append("recent SPY tape is put-led")

    tide_tone = str(tide.get("tone") or "")
    if "risk-on" in tide_tone.lower():
        score += 1
        reasons.append("market tide is risk-on")
    elif "risk-off" in tide_tone.lower():
        score -= 1
        reasons.append("market tide is risk-off")

    premium_tone = str(net_premium.get("tone") or "")
    if "call premium" in premium_tone.lower():
        score += 1
        reasons.append("net premium is building toward calls")
    elif "put premium" in premium_tone.lower():
        score -= 1
        reasons.append("net premium is building toward puts")

    pc_ratio = _finite_float(volume.get("put_call_volume_ratio"))
    if not pd.isna(pc_ratio):
        if pc_ratio >= 1.25:
            score -= 1
            reasons.append(f"volume put/call is elevated at {fmt_float(pc_ratio)}")
        elif pc_ratio <= 0.80:
            score += 1
            reasons.append(f"volume put/call is call-heavy at {fmt_float(pc_ratio)}")

    net_gex = _finite_float(gex.get("net_gex"))
    gamma_note = ""
    if not pd.isna(net_gex):
        gamma_note = "positive gamma may dampen moves" if net_gex > 0 else "negative gamma can amplify breaks" if net_gex < 0 else "gamma is balanced"
        reasons.append(gamma_note)

    nearest_greeks = greeks.get("nearest") if isinstance(greeks, dict) else None
    if isinstance(nearest_greeks, dict):
        strike = nearest_greeks.get("strike")
        if strike is not None:
            reasons.append(f"near-strike Greeks loaded around {fmt_price(strike, 0)}")

    if score >= 2:
        side = "CALL"
        label = "Call pressure"
    elif score <= -2:
        side = "PUT"
        label = "Put pressure"
    elif whales:
        side = "MIXED"
        label = "Mixed pressure"
    else:
        side = None
        label = "No flow read"

    return {
        "side": side,
        "label": label,
        "score": score,
        "reasons": reasons[:4],
        "flow_bias": bias or None,
        "tide": tide_tone or None,
        "recent_tone": recent_tone or None,
        "premium_tone": premium_tone or None,
        "gamma_note": gamma_note or None,
    }


def premium_flow_alignment(options_intel: OptionsIntelligence | None, watch_side: str | None = None) -> dict:
    read = premium_flow_direction(options_intel)
    side = read.get("side")
    if not side:
        return {"state": "unavailable", "title": "Flow Pressure", "copy": "No current flow context is loaded yet.", **read}
    if not watch_side or side == "MIXED":
        title = str(read.get("label") or "Mixed pressure")
        copy = "; ".join(read.get("reasons") or ["Flow is loaded, but not directional enough to overrule structure."])
        return {"state": "neutral", "title": title, "copy": copy, **read}
    aligned = side == watch_side
    if aligned:
        title = f"Supports {watch_side}"
        copy = "Flow agrees with the current structure watch. Still wait for SPY Prophet confirmation at the line."
        state = "aligned"
    else:
        title = f"Fights {watch_side}"
        copy = "Flow is leaning the other way, so require a cleaner rejection or wait."
        state = "opposes"
    reason_text = "; ".join(read.get("reasons") or [])
    if reason_text:
        copy = f"{copy} {reason_text}."
    return {"state": state, "title": title, "copy": copy, **read}


def premium_flow_tags(options_intel: OptionsIntelligence | None) -> list[str]:
    read = premium_flow_direction(options_intel)
    tags = []
    side = read.get("side")
    if side in {"CALL", "PUT", "MIXED"}:
        tags.append(f"FLOW_{side}")
    tide = str(read.get("tide") or "").upper().replace("-", "_").replace(" ", "_")
    if tide:
        tags.append(tide)
    recent = str(read.get("recent_tone") or "").upper().replace("-", "_").replace(" ", "_")
    if recent:
        tags.append(recent[:40])
    premium = str(read.get("premium_tone") or "").upper().replace("-", "_").replace(" ", "_")
    if premium:
        tags.append(premium[:40])
    gamma = str(read.get("gamma_note") or "").upper().replace(" ", "_")
    if gamma:
        tags.append(gamma[:40])
    return tags


def premium_flow_strike_candidates(options_intel: OptionsIntelligence | None, option_type: str, reference_price: float) -> list[tuple[float, float]]:
    whales = premium_flow_payload(options_intel)
    flow = whales.get("flow_alerts") or {}
    recent_flow = whales.get("recent_flow") or {}
    if reference_price is None or pd.isna(reference_price):
        return []
    option_type = str(option_type).upper()
    candidates: list[tuple[float, float]] = []
    if isinstance(flow, dict):
        for row in flow.get("largest_alerts") or []:
            if not isinstance(row, dict) or str(row.get("type") or "").upper() != option_type:
                continue
            strike = _strike_key(row.get("strike"))
            if strike is not None:
                candidates.append((strike, _finite_float(row.get("premium"), 0.0)))
        for row in flow.get("key_strikes") or []:
            if not isinstance(row, dict):
                continue
            strike = _strike_key(row.get("strike"))
            if strike is None:
                continue
            call_premium = _finite_float(row.get("call_premium"), 0.0)
            put_premium = _finite_float(row.get("put_premium"), 0.0)
            if option_type == "CALL" and call_premium >= put_premium and call_premium > 0:
                candidates.append((strike, call_premium))
            if option_type == "PUT" and put_premium > call_premium and put_premium > 0:
                candidates.append((strike, put_premium))
    if isinstance(recent_flow, dict):
        for row in recent_flow.get("top_strikes") or []:
            if not isinstance(row, dict):
                continue
            strike = _strike_key(row.get("strike"))
            if strike is None:
                continue
            call_premium = _finite_float(row.get("call_premium"), 0.0)
            put_premium = _finite_float(row.get("put_premium"), 0.0)
            if option_type == "CALL" and call_premium >= put_premium and call_premium > 0:
                candidates.append((strike, call_premium))
            if option_type == "PUT" and put_premium > call_premium and put_premium > 0:
                candidates.append((strike, put_premium))

    valid = []
    for strike, premium in candidates:
        distance = strike - float(reference_price) if option_type == "CALL" else float(reference_price) - strike
        if 0 < distance <= FLOW_STRIKE_MAX_OTM_DISTANCE:
            valid.append((strike, premium))
    return sorted(valid, key=lambda item: (abs(abs(item[0] - float(reference_price)) - TARGET_OTM_STRIKE_DISTANCE), -item[1]))


def select_flow_aware_watch_contracts(current_price: float, current_dt: datetime, active_signal=None, all_lines=None, options_intel: OptionsIntelligence | None = None) -> SelectedStrikes:
    base = select_watch_contracts(current_price, current_dt, active_signal, all_lines)
    if base.warning:
        return base
    reference_price = base.underlying_price
    call_candidates = premium_flow_strike_candidates(options_intel, "CALL", reference_price)
    put_candidates = premium_flow_strike_candidates(options_intel, "PUT", reference_price)
    call_strike = int(round(call_candidates[0][0])) if call_candidates else base.call_strike
    put_strike = int(round(put_candidates[0][0])) if put_candidates else base.put_strike
    if call_strike == base.call_strike and put_strike == base.put_strike:
        return base
    return replace(base, call_strike=call_strike, put_strike=put_strike)


def get_watch_option_type(active_signal=None, bias_state=None) -> str | None:
    if active_signal and active_signal.signal_type in {"CALL", "PUT"}:
        return active_signal.signal_type
    if bias_state:
        has_call = bool(bias_state.watched_call_lines)
        has_put = bool(bias_state.watched_put_lines)
        if has_call and not has_put:
            return "CALL"
        if has_put and not has_call:
            return "PUT"
    return None


def format_watch_contract(selected_strikes: SelectedStrikes | None, active_signal=None, bias_state=None) -> str:
    if selected_strikes is None:
        return "-"
    watch_type = get_watch_option_type(active_signal, bias_state)
    if watch_type == "CALL":
        return f"WATCH CALL {selected_strikes.call_strike}"
    if watch_type == "PUT":
        return f"WATCH PUT {selected_strikes.put_strike}"
    return f"CALL {selected_strikes.call_strike} / PUT {selected_strikes.put_strike}"


def format_watch_contract_short(selected_strikes: SelectedStrikes | None, active_signal=None, bias_state=None) -> str:
    if selected_strikes is None:
        return "C -<br>P -"
    watch_type = get_watch_option_type(active_signal, bias_state)
    if watch_type == "CALL":
        return f"CALL<br>{selected_strikes.call_strike}"
    if watch_type == "PUT":
        return f"PUT<br>{selected_strikes.put_strike}"
    return f"C {selected_strikes.call_strike}<br>P {selected_strikes.put_strike}"




@dataclass(frozen=True)
class TradeSignal:
    signal_id: str
    signal_type: str
    status: str
    line_name: str
    line_value_at_rejection: float
    rejection_time: pd.Timestamp
    rejection_open: float
    rejection_high: float
    rejection_low: float
    rejection_close: float
    entry_time: pd.Timestamp | None
    entry_price: float
    stop_price: float
    target_line_name: str | None
    target_price: float
    risk: float
    reward: float
    rr_ratio: float
    breakeven_rule: str
    explanation: str


def is_call_rejection(candle_row: pd.Series, line: DynamicLine, candle_time: pd.Timestamp) -> bool:
    lv = line.tradable_value_at(candle_time)
    if pd.isna(lv):
        return False
    o,h,l,c = candle_row["Open"], candle_row["High"], candle_row["Low"], candle_row["Close"]
    return (c <= o) and (o > lv) and (l <= lv) and (c > lv)


def is_put_rejection(candle_row: pd.Series, line: DynamicLine, candle_time: pd.Timestamp) -> bool:
    lv = line.tradable_value_at(candle_time)
    if pd.isna(lv):
        return False
    o,h,l,c = candle_row["Open"], candle_row["High"], candle_row["Low"], candle_row["Close"]
    return (c >= o) and (o < lv) and (h >= lv) and (c < lv)


def find_target_for_signal(signal_type: str, rejected_line_name: str, reference_price: float, reference_time: pd.Timestamp, all_lines: list[DynamicLine]) -> tuple[str | None, float]:
    candidates = []
    for line in all_lines:
        if line.name == rejected_line_name:
            continue
        v = line.tradable_value_at(reference_time)
        if pd.isna(v):
            continue
        if signal_type == "CALL" and v > reference_price:
            candidates.append((v-reference_price, line.name, v))
        if signal_type == "PUT" and v < reference_price:
            candidates.append((reference_price-v, line.name, v))
    if not candidates:
        return None, float("nan")
    _, n, v = min(candidates, key=lambda x:x[0])
    return n, float(v)


def calculate_signal_risk_reward(signal_type: str, entry_price: float, stop_price: float, target_price: float) -> tuple[float, float, float]:
    if any(pd.isna(v) for v in [entry_price, stop_price, target_price]):
        return float("nan"), float("nan"), float("nan")
    if signal_type == "CALL":
        risk, reward = entry_price-stop_price, target_price-entry_price
    else:
        risk, reward = stop_price-entry_price, entry_price-target_price
    rr = reward/risk if risk > 0 and not pd.isna(reward) else float("nan")
    return float(risk), float(reward), float(rr)


def build_trade_signal_from_rejection(signal_type: str, line: DynamicLine, rejection_row: pd.Series, rejection_time: pd.Timestamp, next_row: pd.Series | None, next_time: pd.Timestamp | None, all_lines: list[DynamicLine]) -> TradeSignal:
    confirmed = next_row is not None and next_time is not None
    status = "CONFIRMED" if confirmed else "PENDING_CONFIRMATION"
    entry_time = next_time if confirmed else None
    entry_price = float(next_row["Open"]) if confirmed else float("nan")
    stop_price = float(rejection_row["Low"] - 0.50) if signal_type == "CALL" else float(rejection_row["High"] + 0.50)
    ref_time = entry_time if confirmed else rejection_time
    ref_price = entry_price if confirmed else float(rejection_row["Close"])
    target_name, target_price = find_target_for_signal(signal_type, line.name, ref_price, ref_time, all_lines)
    risk, reward, rr = calculate_signal_risk_reward(signal_type, entry_price, stop_price, target_price)
    lv = line.tradable_value_at(rejection_time)
    sid = f"{signal_type}_{line.name}_{rejection_time.isoformat()}"
    expl = f"{signal_type} rejection at {display_line_name(line.name)}; candle rejected tradable line and {'confirmed by next open' if confirmed else 'awaiting next candle confirmation'}"
    if target_name is None:
        expl += "; no structural target found in trade direction"
    return TradeSignal(sid, signal_type, status, line.name, float(lv), rejection_time, float(rejection_row['Open']), float(rejection_row['High']), float(rejection_row['Low']), float(rejection_row['Close']), entry_time, entry_price, stop_price, target_name, target_price, risk, reward, rr, "Move to breakeven after +$0.50 favorable SPY move.", expl)


def detect_rejection_signals(candles_df: pd.DataFrame, primary_lines: list[DynamicLine], secondary_lines: list[DynamicLine]) -> list[TradeSignal]:
    if candles_df is None or candles_df.empty:
        return []
    df = candles_df.sort_index()
    all_lines = primary_lines + secondary_lines
    out: list[TradeSignal] = []
    seen = set()
    for i in range(len(df)):
        row = df.iloc[i]
        ts = df.index[i]
        next_row = df.iloc[i+1] if i+1 < len(df) else None
        next_ts = df.index[i+1] if i+1 < len(df) else None
        for line in primary_lines:
            if not line.is_primary:
                continue
            sig = None
            if line.zone_type == "CALL_ZONE" and line.direction == "descending" and is_call_rejection(row, line, ts):
                sig = build_trade_signal_from_rejection("CALL", line, row, ts, next_row, next_ts, all_lines)
            elif line.zone_type == "PUT_ZONE" and line.direction == "ascending" and is_put_rejection(row, line, ts):
                sig = build_trade_signal_from_rejection("PUT", line, row, ts, next_row, next_ts, all_lines)
            if sig and sig.signal_id not in seen:
                seen.add(sig.signal_id)
                out.append(sig)
    return out


def _candle_triplet(df: pd.DataFrame, ts: pd.Timestamp | None) -> dict:
    if ts is None or df.empty or ts not in df.index:
        return {}
    pos = df.index.get_loc(ts)
    return {"before": df.iloc[pos - 1] if pos > 0 else None, "pivot": df.iloc[pos], "after": df.iloc[pos + 1] if pos + 1 < len(df) else None}




@dataclass(frozen=True)
class SignalQuality:
    signal_id: str
    grade: str
    score: float
    close_distance: float
    close_distance_pct_of_candle: float
    wick_penetration: float
    wick_rejection_ratio: float
    body_position_score: float
    risk_reward_score: float
    target_quality: str
    warnings: list[str]
    strengths: list[str]
    action_label: str
    explanation: str

@dataclass(frozen=True)
class RiskGuardrailState:
    signal_id: str | None
    chase_status: str
    chase_distance: float
    chase_warning: str | None
    retest_status: str
    retest_line_name: str | None
    structure_status: str
    structure_warning: str | None
    daily_action: str
    explanation: str

@dataclass(frozen=True)
class DecisionState:
    latest_signal: TradeSignal | None
    signal_quality: SignalQuality | None
    guardrail_state: RiskGuardrailState
    final_decision: str
    final_explanation: str

# decision-quality helpers ...
def calculate_close_distance(signal: TradeSignal) -> float:
    return abs(signal.rejection_close - signal.line_value_at_rejection) if signal else float("nan")

def calculate_wick_rejection_metrics(signal: TradeSignal) -> dict:
    rng = round(signal.rejection_high - signal.rejection_low, 10)
    if rng <= 0:
        return {"candle_range": rng, "wick_penetration": 0.0, "wick_rejection_ratio": 0.0, "body_position_score": 0.0}
    if signal.signal_type == "CALL":
        wick_pen = round(max(0.0, signal.line_value_at_rejection - signal.rejection_low), 10)
        rej_dist = round(signal.rejection_close - signal.rejection_low, 10)
    else:
        wick_pen = round(max(0.0, signal.rejection_high - signal.line_value_at_rejection), 10)
        rej_dist = round(signal.rejection_high - signal.rejection_close, 10)
    ratio = rej_dist / rng
    return {"candle_range": rng, "wick_penetration": wick_pen, "wick_rejection_ratio": ratio, "body_position_score": ratio}

def score_signal_quality(signal: TradeSignal) -> SignalQuality:
    score=100.0; warnings=[]; strengths=[]; target_quality="VALID_TARGET"
    close_distance = calculate_close_distance(signal)
    candle_range = signal.rejection_high - signal.rejection_low
    close_pct = (close_distance/candle_range*100) if candle_range>0 else float("nan")
    if close_distance > 1.0:
        score -= 45; warnings.append("CLOSE_TOO_FAR_FROM_LINE")
    elif close_distance > 0.5: score -= 30
    elif close_distance > 0.25: score -= 15
    elif close_distance > 0.1: score -= 5
    m = calculate_wick_rejection_metrics(signal); ratio = m["wick_rejection_ratio"]
    if m["candle_range"] <= 0:
        score -= 20; warnings.append("INVALID_CANDLE_RANGE")
    elif ratio >= 0.60: strengths.append("STRONG_WICK_REJECTION")
    elif ratio >= 0.40: score -= 5
    elif ratio >= 0.20: score -= 15; warnings.append("WEAK_REJECTION")
    else: score -= 30; warnings.append("VERY_WEAK_REJECTION")
    if pd.isna(signal.rr_ratio): score -= 15; warnings.append("NO_RR_AVAILABLE")
    elif signal.rr_ratio < 1.0: score -= 30; warnings.append("POOR_RISK_REWARD")
    elif signal.rr_ratio < 1.5: score -= 15
    elif signal.rr_ratio < 2.0: score -= 5
    else: strengths.append("GOOD_RISK_REWARD")
    if signal.target_line_name is None or pd.isna(signal.target_price):
        target_quality = "NO_TARGET"; score -= 25; warnings.append("NO_STRUCTURAL_TARGET")
    else:
        gap = (signal.target_price-signal.entry_price) if signal.signal_type=="CALL" else (signal.entry_price-signal.target_price)
        if not pd.isna(gap) and gap < 0.50: score -= 20; warnings.append("TARGET_TOO_CLOSE")
    if signal.status == "PENDING_CONFIRMATION": score -= 10; warnings.append("WAIT_FOR_NEXT_CANDLE_OPEN")
    score = max(0.0, min(100.0, score))
    grade = "A+" if score>=90 else "A" if score>=80 else "B" if score>=70 else "C" if score>=60 else "D" if score>=40 else "NO_TRADE"
    if signal.status == "PENDING_CONFIRMATION": action = "WAIT_FOR_CONFIRMATION"
    elif grade in {"A+", "A"}: action = "TRADE_ALLOWED"
    elif grade == "B": action = "SELECTIVE_TRADE"
    elif grade == "C": action = "WAIT_FOR_RETEST"
    elif grade == "D": action = "AVOID"
    else: action = "NO_TRADE"
    explanation = f"Grade {grade}, score {score:.1f}. Warnings: {', '.join(warnings) if warnings else 'none'}. Strengths: {', '.join(strengths) if strengths else 'none'}."
    return SignalQuality(signal.signal_id, grade, score, close_distance, close_pct, m['wick_penetration'], ratio, m['body_position_score'], signal.rr_ratio if not pd.isna(signal.rr_ratio) else float('nan'), target_quality, warnings, strengths, action, explanation)


def evaluate_chase_status(signal, current_price, max_chase_distance=0.30):
    if signal is None: return {"chase_status":"NO_SIGNAL","chase_distance":float("nan"),"chase_warning":None,"explanation":"No signal"}
    if signal.status=="PENDING_CONFIRMATION": return {"chase_status":"OK","chase_distance":float("nan"),"chase_warning":None,"explanation":"Waiting for confirmation"}
    d=(current_price-signal.entry_price) if signal.signal_type=="CALL" else (signal.entry_price-current_price)
    if d>max_chase_distance: return {"chase_status":"MISSED_ENTRY","chase_distance":d,"chase_warning":"MISSED ENTRY. Do not chase. Wait for retest.","explanation":"Moved too far"}
    return {"chase_status":"OK","chase_distance":d,"chase_warning":None,"explanation":"Within chase limits"}

def evaluate_retest_status(signal, current_price, current_dt, rejected_line, tolerance=0.10):
    if signal is None or signal.status != "CONFIRMED" or rejected_line is None:
        return {"retest_status":"NONE","retest_line_name":None,"explanation":"Retest requires confirmed signal and rejected line."}
    lv = rejected_line.tradable_value_at(current_dt)
    if pd.isna(lv):
        return {"retest_status":"NONE","retest_line_name":rejected_line.name,"explanation":"Line value unavailable."}
    if abs(current_price-lv) <= tolerance:
        return {"retest_status":"WATCHING_RETEST","retest_line_name":rejected_line.name,"explanation":"Price is near rejected line; monitoring retest."}
    if signal.signal_type=="CALL":
        status = "RETEST_CONFIRMED" if current_price > lv else "RETEST_FAILED"
    else:
        status = "RETEST_CONFIRMED" if current_price < lv else "RETEST_FAILED"
    return {"retest_status":status,"retest_line_name":rejected_line.name,"explanation":"Current-price retest heuristic (close confirmation to be added later)."}


def evaluate_structure_status(signal, latest_candle_row, rejected_line, latest_time):
    if signal is None or latest_candle_row is None or rejected_line is None: return {"structure_status":"UNKNOWN","structure_warning":None}
    lv=rejected_line.tradable_value_at(latest_time)
    if pd.isna(lv): return {"structure_status":"UNKNOWN","structure_warning":None}
    c=latest_candle_row['Close']
    if signal.signal_type=="CALL": return {"structure_status":"INTACT" if c>=lv else "BROKEN","structure_warning":None if c>=lv else "CALL structure failed. Price closed below rejected support."}
    return {"structure_status":"INTACT" if c<=lv else "BROKEN","structure_warning":None if c<=lv else "PUT structure failed. Price closed above rejected resistance."}

def evaluate_daily_risk(signals_today, qualities_today=None, max_signals_per_day=3, min_grade_to_trade="B"):
    confirmed = [s for s in signals_today if s.status=="CONFIRMED"]
    if len(confirmed) >= max_signals_per_day:
        return {"daily_action":"STOP_TRADING","explanation":"Maximum daily signal count reached."}
    if qualities_today:
        g = qualities_today[-1].grade
        if g in {"C","D","NO_TRADE"}:
            return {"daily_action":"NO_TRADE","explanation":"Latest signal quality is below trade threshold."}
        if g in {"A+","A","B"}:
            return {"daily_action":"TRADE_ALLOWED" if g in {"A+","A"} else "SELECTIVE_TRADE","explanation":"Daily risk allows qualified setup."}
    return {"daily_action":"WAIT","explanation":"No qualifying quality context yet."}


def build_decision_state(latest_signal, all_lines, current_price, current_dt, latest_candle_row, signals_today=None):
    if latest_signal is None:
        guard = RiskGuardrailState(None,"NO_SIGNAL",float("nan"),None,"NONE",None,"UNKNOWN",None,"WAIT","No confirmed/pending rejection yet.")
        return DecisionState(None,None,guard,"WAIT","No confirmed/pending rejection yet.")
    quality = score_signal_quality(latest_signal)
    line = get_line_by_name(all_lines, latest_signal.line_name)
    chase = evaluate_chase_status(latest_signal,current_price)
    ret = evaluate_retest_status(latest_signal,current_price,current_dt,line)
    struct = evaluate_structure_status(latest_signal,latest_candle_row,line,current_dt)
    daily = evaluate_daily_risk(signals_today or [latest_signal],[quality])
    guard = RiskGuardrailState(latest_signal.signal_id,chase["chase_status"],chase["chase_distance"],chase["chase_warning"],ret["retest_status"],ret["retest_line_name"],struct["structure_status"],struct["structure_warning"],daily["daily_action"],f"{chase['explanation']} | {ret.get('explanation','')} | {daily['explanation']}")
    if latest_signal.status == "PENDING_CONFIRMATION": final = "WAIT_FOR_CONFIRMATION"
    elif struct["structure_status"] == "BROKEN": final = "NO_TRADE"
    elif chase["chase_status"] == "MISSED_ENTRY": final = "WAIT_FOR_RETEST"
    elif daily["daily_action"] == "STOP_TRADING": final = "STOP_TRADING"
    elif quality.grade in {"A+","A"}: final = "TRADE_ALLOWED"
    elif quality.grade == "B": final = "SELECTIVE_TRADE"
    elif quality.grade == "C": final = "WAIT_FOR_RETEST"
    else: final = "NO_TRADE"
    return DecisionState(latest_signal,quality,guard,final,f"{quality.explanation} Final decision: {final}.")



@dataclass(frozen=True)
class ReplaySignalOutcome:
    signal_id: str
    signal_type: str
    entry_time: pd.Timestamp | None
    entry_price: float
    stop_price: float
    target_price: float
    target_line_name: str | None
    outcome: str
    outcome_time: pd.Timestamp | None
    max_favorable_move: float
    max_adverse_move: float
    bars_to_outcome: int | None
    explanation: str

@dataclass(frozen=True)
class ReplayState:
    replay_date: object
    replay_time: pd.Timestamp | None
    prior_trading_day: object | None
    high_pivot: Pivot | None
    low_pivot: Pivot | None
    primary_lines: list[DynamicLine]
    secondary_lines: list[DynamicLine]
    bias_state: BiasState | None
    signals: list[TradeSignal]
    signal_qualities: dict[str, SignalQuality]
    outcomes: dict[str, ReplaySignalOutcome]
    selected_signal_id: str | None
    explanation: str
    warnings: list[str]


def filter_replay_day(df: pd.DataFrame, replay_date) -> pd.DataFrame:
    if df is None or df.empty: return pd.DataFrame()
    return df[df.index.date == replay_date].sort_index()


def get_available_replay_dates(df: pd.DataFrame) -> list:
    return get_available_trading_days(df)


def evaluate_signal_outcome(signal: TradeSignal, future_candles_df: pd.DataFrame) -> ReplaySignalOutcome:
    if signal.status == "PENDING_CONFIRMATION":
        return ReplaySignalOutcome(signal.signal_id, signal.signal_type, signal.entry_time, signal.entry_price, signal.stop_price, signal.target_price, signal.target_line_name, "PENDING", None, float('nan'), float('nan'), None, "Pending next candle open.")
    if signal.entry_time is None or pd.isna(signal.entry_price):
        return ReplaySignalOutcome(signal.signal_id, signal.signal_type, signal.entry_time, signal.entry_price, signal.stop_price, signal.target_price, signal.target_line_name, "UNKNOWN", None, float('nan'), float('nan'), None, "Invalid entry context.")
    fut = future_candles_df[future_candles_df.index > signal.entry_time].sort_index()
    if fut.empty:
        return ReplaySignalOutcome(signal.signal_id, signal.signal_type, signal.entry_time, signal.entry_price, signal.stop_price, signal.target_price, signal.target_line_name, "NO_HIT", None, float('nan'), float('nan'), None, "No future candles.")
    outcome="NO_HIT"; out_time=None; bars=None
    for i,(ts,row) in enumerate(fut.iterrows(),start=1):
        if signal.signal_type=="CALL":
            t = (not pd.isna(signal.target_price)) and row['High']>=signal.target_price
            st = row['Low']<=signal.stop_price
        else:
            t = (not pd.isna(signal.target_price)) and row['Low']<=signal.target_price
            st = row['High']>=signal.stop_price
        if t and st: outcome="AMBIGUOUS_SAME_CANDLE"; out_time=ts; bars=i; break
        if t: outcome="TARGET_FIRST"; out_time=ts; bars=i; break
        if st: outcome="STOP_FIRST"; out_time=ts; bars=i; break
    if signal.signal_type=="CALL":
        max_fav = (fut['High']-signal.entry_price).max(); max_adv = (fut['Low']-signal.entry_price).min()
    else:
        max_fav = (signal.entry_price-fut['Low']).max(); max_adv = (signal.entry_price-fut['High']).min()
    return ReplaySignalOutcome(signal.signal_id, signal.signal_type, signal.entry_time, signal.entry_price, signal.stop_price, signal.target_price, signal.target_line_name, outcome, out_time, float(max_fav), float(max_adv), bars, "Hourly replay outcome.")


def get_latest_active_signal(signals: list[TradeSignal], candles_df: pd.DataFrame) -> TradeSignal | None:
    for signal in reversed(signals or []):
        if signal.status == "PENDING_CONFIRMATION":
            return signal
        outcome = evaluate_signal_outcome(signal, candles_df)
        if outcome.outcome == "NO_HIT":
            return signal
    return None


def build_replay_state(full_df: pd.DataFrame, replay_date, replay_time=None, slope_per_hour=DEFAULT_SLOPE_PER_HOUR, include_future_outcomes=True) -> ReplayState:
    warns=[]
    if full_df is None or full_df.empty:
        return ReplayState(replay_date, replay_time, None, None, None, [], [], None, [], {}, {}, None, "No data.", ["NO_DATA"])
    day_df = filter_replay_day(full_df, replay_date)
    if replay_time is not None:
        day_visible = day_df[day_df.index <= replay_time]
    else:
        day_visible = day_df
    prior = get_prior_trading_day(full_df, pd.Timestamp(replay_date).to_pydatetime())
    if prior is None:
        return ReplayState(replay_date, replay_time, None, None, None, [], [], None, [], {}, {}, None, "No prior trading day.", ["NO_PRIOR_TRADING_DAY"])
    prior_rth = filter_rth_session(full_df, prior)
    piv = find_primary_pivots(prior_rth) if not prior_rth.empty else {"high": None, "low": None}
    secs = find_secondary_pivots(prior_rth) if not prior_rth.empty else []
    primary_lines = build_primary_lines(piv['high'], piv['low'], slope_per_hour) if piv['high'] and piv['low'] else []
    secondary_lines = build_secondary_lines(secs, slope_per_hour)
    latest_price = float(day_visible['Close'].iloc[-1]) if not day_visible.empty else float('nan')
    bias = determine_preopen_bias(primary_lines, latest_price, day_visible.index[-1]) if primary_lines and not day_visible.empty else None
    sigs = detect_rejection_signals(day_visible, primary_lines, secondary_lines) if not day_visible.empty else []
    quals = {sg.signal_id: score_signal_quality(sg) for sg in sigs}
    outcomes = {}
    if include_future_outcomes:
        for sg in sigs:
            outcomes[sg.signal_id] = evaluate_signal_outcome(sg, day_df)
    return ReplayState(replay_date, replay_time, prior, piv['high'] if piv else None, piv['low'] if piv else None, primary_lines, secondary_lines, bias, sigs, quals, outcomes, sigs[-1].signal_id if sigs else None, "Replay built.", warns)




def fmt_nan(value, fallback="-"):
    if value is None:
        return fallback
    try:
        if pd.isna(value) is True:
            return fallback
    except Exception:
        pass
    return value

def fmt_price(value, digits=2):
    v=fmt_nan(value,None)
    return "-" if v is None else f"{float(v):.{digits}f}"

def fmt_float(value, digits=2):
    v=fmt_nan(value,None)
    return "-" if v is None else f"{float(v):.{digits}f}"

def fmt_pct(value, digits=1):
    v=fmt_nan(value,None)
    return "-" if v is None else f"{float(v):.{digits}f}%"

def fmt_money_short(value):
    v = fmt_nan(value, None)
    if v is None:
        return "-"
    amount = float(v)
    sign = "-" if amount < 0 else ""
    amount = abs(amount)
    if amount >= 1_000_000_000:
        return f"{sign}${amount / 1_000_000_000:.1f}B"
    if amount >= 1_000_000:
        return f"{sign}${amount / 1_000_000:.1f}M"
    if amount >= 1_000:
        return f"{sign}${amount / 1_000:.0f}K"
    return f"{sign}${amount:.0f}"

def fmt_time(value):
    if value is None: return "-"
    ts=pd.Timestamp(value)
    ts = ts.tz_localize(get_central_tz()) if ts.tzinfo is None else ts.tz_convert(get_central_tz())
    return ts.strftime("%Y-%m-%d %H:%M %Z")


def fmt_clock_time(value):
    if value is None: return "-"
    ts = pd.Timestamp(value)
    ts = ts.tz_localize(get_central_tz()) if ts.tzinfo is None else ts.tz_convert(get_central_tz())
    return ts.strftime("%I:%M %p %Z").lstrip("0")


def rth_session_window_label() -> str:
    def compact_session_time(value: time) -> str:
        template = "%I:00" if value.minute == 0 else "%I:%M"
        return value.strftime(template).lstrip("0")

    start = compact_session_time(RTH_SESSION_START)
    end = compact_session_time(RTH_SESSION_END)
    return f"{start}-{end} CT"

def safe_to_dict(obj):
    if obj is None: return {}
    d = obj if isinstance(obj,dict) else asdict(obj) if hasattr(obj,'__dataclass_fields__') else {"value":str(obj)}
    for k in list(d.keys()):
        if any(x in str(k).lower() for x in ["client_secret","refresh_token","access_token","account"]):
            d[k] = "[REDACTED]"
    return d

def safe_json(obj):
    return json.dumps(safe_to_dict(obj), default=str)

def _fmt_num(v: float | None, nd: int = 2) -> str:
    return "N/A" if v is None or pd.isna(v) else f"{v:.{nd}f}"


def inject_global_css() -> None:
    st.markdown("""
    <style>
    :root {
      --bg:#080d12;--surface:#111821;--surface2:#151f2b;--surface3:#1a2633;
      --border:#243244;--border2:#314357;--text:#f4f7fb;--muted:#9aa7b5;
      --blue:#4ea8de;--green:#2ecc71;--red:#f45d75;--amber:#f5c451;
      --cyan:#28d2c2;--shadow:0 14px 34px rgba(0,0,0,.26);
      --ui-font:"Inter","Source Sans 3","Segoe UI",Roboto,system-ui,sans-serif;
      --mono-font:"IBM Plex Mono","Roboto Mono","JetBrains Mono",Consolas,monospace;
    }
    html,body,.stApp,[data-testid="stAppViewContainer"]{font-family:var(--ui-font);background:var(--bg);color:var(--text)}
    .stMarkdown,.stText,.stCaption,.stDataFrame,p,span,button,label,input,textarea,select,h1,h2,h3,h4,h5,h6{font-family:var(--ui-font)}
    .block-container{padding-top:2.25rem;max-width:1240px}
    [data-testid="stSidebar"]{background:#111722;border-right:1px solid #202c3f}
    [data-testid="stSidebar"] h2{font-size:1rem;letter-spacing:.02em}
    [data-testid="stSidebar"] button{border-radius:8px}
    div[data-testid="stButton"] button, div[data-testid="stDownloadButton"] button{border-radius:8px;border:1px solid var(--border2);background:var(--surface2);color:var(--text);box-shadow:none}
    div[data-testid="stButton"] button:hover, div[data-testid="stDownloadButton"] button:hover{border-color:var(--blue);color:var(--text)}
    textarea, input{font-family:var(--ui-font)}
    div[data-baseweb="tab-list"]{gap:10px;border-bottom:1px solid var(--border);padding-bottom:0}
    button[role="tab"]{padding:10px 0;border-bottom:2px solid transparent;color:var(--muted)}
    button[role="tab"][aria-selected="true"]{border-bottom-color:var(--green);color:var(--text)}
    .terminal-hero{border:1px solid var(--border2);border-radius:8px;background:linear-gradient(135deg,#101821,#111b26 58%,#0c1219);box-shadow:var(--shadow);padding:18px 20px;margin-bottom:14px}
    .terminal-top{display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid rgba(141,160,184,.16);padding-bottom:12px}
    .brand-row,.panel-head,.quote-head,.tile-head,.hero-price-row{display:flex;align-items:center;gap:12px}
    .brand-row{gap:14px}
    .panel-head,.quote-head,.tile-head{justify-content:space-between}
    .ui-icon{position:relative;display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;width:48px;height:48px;border-radius:8px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.035);overflow:hidden;isolation:isolate;box-shadow:none}
    .ui-icon svg{width:58%;height:58%;stroke:currentColor;fill:none;stroke-width:2.25;stroke-linecap:round;stroke-linejoin:round}
    .ui-icon.lg{width:64px;height:64px}.ui-icon.md{width:52px;height:52px}.ui-icon.sm{width:42px;height:42px}.ui-icon.mini{width:30px;height:30px}
    .brand-logo{position:relative;display:inline-flex;align-items:center;justify-content:center;flex:0 0 auto;width:82px;height:82px;border-radius:8px;border:1px solid rgba(78,168,222,.48);overflow:hidden;isolation:isolate;background:linear-gradient(135deg,#102335,#0d1723);box-shadow:none}
    .brand-logo::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 26% 18%,rgba(78,168,222,.36),transparent 48%);z-index:-1}
    .brand-logo svg{width:82%;height:82%;overflow:visible}.brand-grid{stroke:rgba(215,240,255,.16);stroke-width:.8}.brand-mono{fill:#f6fbff;font:900 9px var(--mono-font);letter-spacing:.4px}.brand-path{fill:none;stroke:var(--amber);stroke-width:2.2;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:34;animation:brandDraw 2.9s ease-in-out infinite}.brand-dot{fill:var(--green);animation:brandPulse 1.45s ease-in-out infinite}.brand-orbit{fill:none;stroke:rgba(246,251,255,.48);stroke-width:1.4;stroke-dasharray:4 4;animation:brandOrbit 7s linear infinite;transform-origin:24px 24px}.brand-scan{stroke:#9ed2ff;stroke-width:1.1;opacity:.72;animation:brandScan 2.2s ease-in-out infinite}
    .ui-icon.blue{color:var(--blue);border-color:rgba(78,168,222,.42);background:rgba(78,168,222,.10)}
    .ui-icon.green{color:var(--green);border-color:rgba(46,204,113,.42);background:rgba(46,204,113,.10)}
    .ui-icon.red{color:var(--red);border-color:rgba(244,93,117,.42);background:rgba(244,93,117,.10)}
    .ui-icon.amber{color:var(--amber);border-color:rgba(245,196,81,.42);background:rgba(245,196,81,.10)}
    .label-stack{min-width:0}
    .brand-title{font-size:2.25rem;font-weight:850;color:var(--text);line-height:1;letter-spacing:0}
    .brand-tagline{margin-top:8px;color:var(--blue);font-size:.95rem;font-weight:650;letter-spacing:.02em}
    .market-clock{text-align:right;color:var(--muted);font-size:.84rem}
    .hero-grid{display:grid;grid-template-columns:1.1fr 1.5fr .9fr;gap:16px;margin-top:16px;align-items:stretch}
    .hero-price-row{align-items:flex-start}
    .hero-price{font-family:var(--mono-font);font-size:2.85rem;font-weight:800;color:var(--text);line-height:1}
    .hero-label,.panel-label,.tile-label{font-size:.74rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .hero-sub{margin-top:8px;color:var(--muted);font-size:.86rem}
    .hero-intel{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:14px}
    .intel-mini{border:1px solid var(--border);border-radius:8px;background:rgba(255,255,255,.035);padding:9px;min-height:76px}
    .intel-mini.green{border-color:rgba(33,208,122,.48)} .intel-mini.red{border-color:rgba(255,95,124,.48)} .intel-mini.amber{border-color:rgba(244,199,107,.48)} .intel-mini.blue{border-color:rgba(103,183,255,.48)}
    .intel-head{display:flex;align-items:flex-start;justify-content:space-between;gap:8px}
    .intel-label{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .intel-value{font-size:1rem;font-weight:800;color:var(--text);margin-top:4px;line-height:1.2}
    .intel-mini.green .intel-value{color:var(--green)} .intel-mini.red .intel-value{color:var(--red)} .intel-mini.amber .intel-value{color:var(--amber)} .intel-mini.blue .intel-value{color:var(--blue)}
    .intel-copy{font-size:.76rem;color:var(--muted);margin-top:4px;line-height:1.25}
    .decision-plate{border:1px solid var(--border);border-radius:8px;background:rgba(7,10,15,.58);padding:14px}
    .decision-main{font-size:1.6rem;font-weight:850;line-height:1.12;color:var(--text);margin:5px 0}
    .decision-reason{color:var(--muted);font-size:.86rem}
    .wait-discipline{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px}
    .wait-gate{border:1px solid rgba(255,255,255,.08);border-radius:8px;background:rgba(255,255,255,.035);padding:9px;min-height:92px}
    .wait-gate-label{font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .wait-gate-value{font-size:1rem;font-weight:850;color:var(--text);margin-top:5px;line-height:1.18}
    .wait-gate-copy{font-size:.76rem;line-height:1.25;color:var(--muted);margin-top:5px}
    .pill-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
    .pill{border:1px solid var(--border);border-radius:999px;padding:4px 9px;color:var(--muted);font-size:.78rem;background:rgba(255,255,255,.03)}
    .pill.green{border-color:rgba(33,208,122,.55);color:var(--green)} .pill.red{border-color:rgba(255,95,124,.55);color:var(--red)} .pill.amber{border-color:rgba(244,199,107,.55);color:var(--amber)} .pill.blue{border-color:rgba(103,183,255,.55);color:var(--blue)}
    .quote-stack{display:grid;grid-template-columns:1fr;gap:10px}
    .quote-mini{border:1px solid var(--border);border-radius:8px;padding:12px;background:rgba(255,255,255,.035);display:flex;flex-direction:column;gap:10px}
    .quote-body{display:grid;gap:6px}
    .quote-eyebrow{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .quote-trigger-name{font-size:.98rem;font-weight:800;color:var(--text);line-height:1.2}
    .quote-trigger-price{font-family:var(--mono-font);font-size:1.75rem;font-weight:850;color:var(--blue);line-height:1}
    .quote-meta-row{display:flex;align-items:center;justify-content:space-between;gap:10px;border-top:1px solid rgba(141,160,184,.16);padding-top:8px;color:var(--muted);font-size:.78rem}
    .quote-meta-row strong{color:var(--text);font-weight:750;text-align:right}
    .strike-grid{display:grid;grid-template-columns:1fr 1fr;gap:8px}
    .strike-cell{border:1px solid rgba(141,160,184,.18);border-radius:8px;background:rgba(7,10,15,.35);padding:9px}
    .strike-cell.call{border-left:3px solid var(--green)} .strike-cell.put{border-left:3px solid var(--red)}
    .strike-label{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .strike-value{font-family:var(--mono-font);font-size:1.45rem;font-weight:850;color:var(--text);line-height:1.05;margin-top:4px}
    .terminal-section{margin-top:14px}
    .command-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px;align-items:stretch}
    .terminal-panel,.prophet-header,.metric-card,.prophet-card,.empty-state,.warning-panel{border:1px solid var(--border);border-radius:8px;background:var(--surface);box-shadow:none}
    .terminal-panel{padding:16px;min-height:184px;display:flex;flex-direction:column;gap:10px}
    .panel-head{min-width:0}
    .panel-head>div{min-width:0}
    .panel-title{font-size:1.05rem;font-weight:800;color:var(--text);margin-top:4px;line-height:1.22;overflow-wrap:anywhere}
    .panel-copy{color:var(--muted);font-size:.88rem;line-height:1.45;margin-top:0;flex:1;overflow-wrap:anywhere}
    .data-notice{border:1px solid rgba(78,168,222,.28);border-radius:8px;background:rgba(78,168,222,.08);padding:11px 13px;color:#b9dcfb;font-size:.9rem;margin:10px 0}
    .data-notice.warn{border-color:rgba(245,196,81,.34);background:rgba(245,196,81,.08);color:#f8dfa0}
    .option-quote-main{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:6px 0 8px}
    .option-quote-strike{font-family:var(--mono-font);font-size:1.55rem;font-weight:850;color:var(--text)}
    .option-quote-mark{font-family:var(--mono-font);font-size:1.35rem;font-weight:800;color:var(--blue);text-align:right}
    .option-quote-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-top:10px}
    .option-quote-cell{border:1px solid rgba(141,160,184,.16);border-radius:8px;background:rgba(255,255,255,.025);padding:7px}
    .option-quote-label{font-size:.64rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .option-quote-value{font-family:var(--mono-font);font-size:.95rem;color:var(--text);margin-top:3px}
    .structure-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:14px}
    .structure-note{display:inline-flex;align-items:center;gap:8px;margin-top:14px;border:1px solid rgba(103,183,255,.3);border-radius:8px;background:rgba(103,183,255,.08);padding:7px 10px;color:var(--blue);font-size:.82rem;font-weight:650}
    .structure-tile{border:1px solid var(--border);border-radius:8px;background:linear-gradient(180deg,rgba(22,34,53,.8),rgba(13,19,29,.95));padding:12px;min-height:122px}
    .structure-tile.closest{border-color:var(--blue);box-shadow:0 0 0 1px rgba(103,183,255,.3)}
    .tile-name{font-size:1.1rem;font-weight:800;color:var(--text)}
    .tile-value{font-family:var(--mono-font);font-size:1.65rem;font-weight:800;color:var(--text);margin-top:4px}
    .tile-meta{color:var(--muted);font-size:.78rem;margin-top:4px}
    .tile-call{border-left:3px solid var(--green)} .tile-put{border-left:3px solid var(--red)}
    .brief-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0 14px}
    .brief-card{border:1px solid var(--border);border-radius:8px;background:rgba(13,19,29,.92);padding:12px}
    .brief-label{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .brief-value{font-family:var(--mono-font);font-size:1.35rem;font-weight:800;color:var(--text);margin-top:4px}
    .brief-copy{color:var(--muted);font-size:.82rem;margin-top:4px;line-height:1.35}
    .replay-shell{border:1px solid var(--border2);border-radius:8px;background:linear-gradient(135deg,rgba(13,19,29,.92),rgba(16,27,43,.82));padding:14px;margin:10px 0 14px}
    .replay-title{font-size:1.15rem;font-weight:800;color:var(--text)}
    .replay-copy{font-size:.88rem;color:var(--muted);margin-top:6px;line-height:1.45}
    .outcome-row{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:12px}
    .outcome-card{border:1px solid var(--border);border-radius:8px;background:rgba(255,255,255,.035);padding:10px}
    .status-strip{display:flex;gap:14px;flex-wrap:wrap;padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:rgba(16,24,38,.7);font-size:.85rem;color:var(--muted);margin:14px 0}
    .status-strip b{color:var(--text);font-weight:600}
    .context-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:14px;margin-top:12px}
    .context-stack{display:grid;gap:14px}
    .learning-hero{border:1px solid var(--border2);border-radius:8px;background:linear-gradient(135deg,rgba(17,26,38,.96),rgba(10,17,25,.96));padding:16px}
    .learning-head,.feed-head,.calendar-head{display:flex;align-items:center;justify-content:space-between;gap:12px}
    .learning-title{font-size:1.18rem;font-weight:850;color:var(--text);line-height:1.15}
    .learning-copy{font-size:.9rem;color:var(--muted);line-height:1.45;margin-top:8px}
    .probability-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:14px}
    .prob-card{border:1px solid rgba(141,160,184,.16);border-radius:8px;background:rgba(255,255,255,.035);padding:10px}
    .prob-label{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .prob-value{font-family:var(--mono-font);font-size:1.35rem;font-weight:850;margin-top:4px;color:var(--text)}
    .prob-card.green .prob-value{color:var(--green)} .prob-card.red .prob-value{color:var(--red)} .prob-card.blue .prob-value{color:var(--blue)}
    .news-list,.calendar-list{display:grid;gap:9px;margin-top:10px}
    .news-card,.calendar-row{border:1px solid var(--border);border-radius:8px;background:rgba(255,255,255,.03);padding:10px}
    .news-title{font-weight:800;color:var(--text);line-height:1.3}
    .news-meta,.calendar-meta{display:flex;gap:8px;flex-wrap:wrap;color:var(--muted);font-size:.76rem;margin-top:6px}
    .news-summary,.calendar-notes{color:var(--muted);font-size:.82rem;line-height:1.35;margin-top:7px}
    .calendar-event{font-weight:800;color:var(--text);line-height:1.25}
    .calendar-impact{color:var(--amber);font-weight:750}
    .briefing-shell{border:1px solid var(--border2);border-radius:8px;background:linear-gradient(135deg,rgba(14,22,33,.98),rgba(8,13,18,.98));padding:16px;margin-top:12px}
    .briefing-head{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;border-bottom:1px solid rgba(141,160,184,.18);padding-bottom:12px}
    .briefing-title{font-size:1.45rem;font-weight:900;color:var(--text);line-height:1.12}
    .briefing-sub{color:var(--muted);font-size:.88rem;margin-top:6px;line-height:1.4}
    .briefing-body{white-space:pre-wrap;color:#dbe8f5;font-size:.95rem;line-height:1.55;margin-top:14px}
    .source-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:12px}
    .source-card{border:1px solid var(--border);border-radius:8px;background:rgba(255,255,255,.03);padding:9px;min-height:82px}
    .source-card.connected{border-color:rgba(46,204,113,.38)} .source-card.unavailable{border-color:rgba(245,196,81,.34)}
    .source-name{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .source-state{font-weight:850;margin-top:4px}.source-card.connected .source-state{color:var(--green)}.source-card.unavailable .source-state{color:var(--amber)}
    .source-detail{font-size:.76rem;color:var(--muted);line-height:1.3;margin-top:4px}
    .briefing-mini-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}
    .briefing-mini{border:1px solid var(--border);border-radius:8px;background:rgba(255,255,255,.035);padding:10px}
    .briefing-mini-label{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .briefing-mini-value{font-family:var(--mono-font);font-size:1.15rem;font-weight:850;color:var(--text);margin-top:4px}
    .briefing-mini-copy{font-size:.78rem;color:var(--muted);margin-top:4px;line-height:1.3}
    .morning-control{display:flex;align-items:center;justify-content:space-between;gap:14px;border:1px solid var(--border);border-radius:8px;background:rgba(16,24,38,.68);padding:10px 12px;margin:10px 0 14px}
    .morning-control-title{font-size:.82rem;font-weight:850;color:var(--text)}
    .morning-control-copy{font-size:.76rem;color:var(--muted);line-height:1.35;margin-top:3px}
    .morning-hero{position:relative;overflow:hidden;border:1px solid rgba(103,183,255,.34);border-radius:8px;background:radial-gradient(circle at 12% 12%,rgba(103,183,255,.22),transparent 32%),radial-gradient(circle at 92% 6%,rgba(46,204,113,.16),transparent 28%),linear-gradient(135deg,rgba(13,22,35,.98),rgba(7,11,17,.98));padding:18px;margin:12px 0 14px}
    .morning-hero:before{content:"";position:absolute;inset:0;background:linear-gradient(90deg,transparent,rgba(255,255,255,.055),transparent);transform:translateX(-100%);animation:brandScan 4.5s ease-in-out infinite;pointer-events:none}
    .morning-hero-inner{position:relative;display:grid;grid-template-columns:1.2fr .8fr;gap:18px;align-items:center}
    .morning-kicker{display:flex;align-items:center;gap:10px;color:var(--blue);font-size:.74rem;letter-spacing:.09em;text-transform:uppercase;font-weight:850}
    .morning-title{font-size:2rem;font-weight:950;color:var(--text);line-height:1.04;margin-top:9px}
    .morning-subtitle{color:var(--muted);font-size:.92rem;line-height:1.45;margin-top:8px;max-width:740px}
    .morning-hero-metrics{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:15px}
    .morning-hero-stat{border:1px solid rgba(141,160,184,.18);border-radius:8px;background:rgba(255,255,255,.045);padding:10px;min-height:82px}
    .morning-stat-label{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .morning-stat-value{font-family:var(--mono-font);font-size:1.1rem;font-weight:900;color:var(--text);margin-top:4px}
    .morning-stat-copy{font-size:.76rem;color:var(--muted);line-height:1.3;margin-top:4px}
    .morning-orb{display:grid;place-items:center;justify-self:end;width:188px;max-width:100%;aspect-ratio:1;border-radius:999px;background:conic-gradient(var(--ring-color) calc(var(--confidence)*1%),rgba(141,160,184,.14) 0);box-shadow:0 0 44px rgba(103,183,255,.18)}
    .morning-orb-core{display:grid;place-items:center;width:78%;height:78%;border:1px solid rgba(255,255,255,.12);border-radius:999px;background:linear-gradient(160deg,rgba(10,17,27,.98),rgba(20,31,46,.94));text-align:center;padding:14px}
    .morning-orb-value{font-family:var(--mono-font);font-size:2.1rem;font-weight:950;color:var(--text);line-height:1}
    .morning-orb-label{font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-top:7px}
    .morning-lines{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:12px 0}
    .morning-line-card{border:1px solid var(--border);border-radius:8px;background:linear-gradient(180deg,rgba(22,34,53,.86),rgba(11,17,26,.94));padding:12px;min-height:142px;position:relative;overflow:hidden}
    .morning-line-card:after{content:"";position:absolute;right:-28px;top:-36px;width:96px;height:96px;border-radius:999px;background:var(--wash);opacity:.52}
    .morning-line-top{position:relative;display:flex;align-items:center;justify-content:space-between;gap:10px}
    .morning-line-name{font-size:.82rem;font-weight:850;color:var(--text);line-height:1.25}
    .morning-line-role{font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-top:3px}
    .morning-line-value{position:relative;font-family:var(--mono-font);font-size:1.72rem;font-weight:950;color:var(--text);margin-top:14px}
    .morning-line-anchor{position:relative;font-size:.76rem;color:var(--muted);line-height:1.35;margin-top:6px}
    .morning-line-card.call{border-color:rgba(46,204,113,.32);--wash:rgba(46,204,113,.18)}
    .morning-line-card.put{border-color:rgba(255,95,124,.34);--wash:rgba(255,95,124,.18)}
    .morning-line-card.neutral{--wash:rgba(103,183,255,.16)}
    .morning-dashboard{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-top:12px}
    .morning-card{border:1px solid var(--border);border-radius:8px;background:linear-gradient(180deg,rgba(18,28,42,.9),rgba(9,14,21,.96));padding:14px;min-height:168px;display:flex;flex-direction:column}
    .morning-card.green{border-color:rgba(46,204,113,.34)}.morning-card.red{border-color:rgba(255,95,124,.34)}.morning-card.amber{border-color:rgba(245,196,81,.36)}.morning-card.blue{border-color:rgba(103,183,255,.34)}
    .morning-card-head{display:flex;align-items:center;gap:10px}
    .morning-card-title{font-size:.78rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:850}
    .morning-card-value{font-size:1.08rem;font-weight:900;color:var(--text);line-height:1.22;margin-top:10px}
    .morning-card-copy{font-size:.82rem;color:var(--muted);line-height:1.4;margin-top:7px;flex:1}
    .morning-chip-row{display:flex;gap:6px;flex-wrap:wrap;margin-top:10px}
    .morning-chip{border:1px solid rgba(141,160,184,.18);border-radius:999px;background:rgba(255,255,255,.045);padding:4px 8px;font-size:.72rem;color:var(--text)}
    .action-brief{border:1px solid rgba(46,204,113,.34);border-radius:8px;background:linear-gradient(135deg,rgba(46,204,113,.10),rgba(78,168,222,.08),rgba(8,13,18,.98));padding:15px;margin:12px 0}
    .action-brief.wait{border-color:rgba(245,196,81,.4);background:linear-gradient(135deg,rgba(245,196,81,.12),rgba(78,168,222,.07),rgba(8,13,18,.98))}
    .action-brief.put{border-color:rgba(244,93,117,.38);background:linear-gradient(135deg,rgba(244,93,117,.11),rgba(78,168,222,.06),rgba(8,13,18,.98))}
    .action-brief-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;border-bottom:1px solid rgba(141,160,184,.16);padding-bottom:12px;margin-bottom:12px}
    .action-kicker{font-size:.7rem;letter-spacing:.08em;text-transform:uppercase;color:var(--amber);font-weight:900}
    .action-headline{font-size:1.38rem;font-weight:950;color:var(--text);line-height:1.14;margin-top:5px}
    .action-summary{font-size:.86rem;color:var(--muted);line-height:1.4;margin-top:6px}
    .action-grid{display:grid;grid-template-columns:1.05fr .95fr;gap:10px}
    .action-ticket{border:1px solid rgba(141,160,184,.18);border-radius:8px;background:rgba(255,255,255,.04);padding:11px}
    .action-ticket-label{font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:850}
    .action-ticket-value{font-size:1.02rem;font-weight:900;color:var(--text);line-height:1.25;margin-top:5px}
    .action-ticket-copy{font-size:.78rem;color:var(--muted);line-height:1.35;margin-top:5px}
    .action-reasons{display:grid;gap:7px}
    .action-reason{display:flex;gap:8px;border:1px solid rgba(141,160,184,.14);border-radius:8px;background:rgba(255,255,255,.03);padding:8px;color:var(--muted);font-size:.8rem;line-height:1.33}
    .action-reason-dot{width:7px;height:7px;border-radius:99px;background:var(--green);flex:0 0 7px;margin-top:5px}
    .action-risk .action-reason-dot{background:var(--red)}
    .morning-action{border:1px solid rgba(245,196,81,.34);border-radius:8px;background:linear-gradient(135deg,rgba(245,196,81,.12),rgba(103,183,255,.08),rgba(8,13,18,.96));padding:14px;margin:12px 0}
    .morning-action-grid{display:grid;grid-template-columns:.82fr 1.18fr;gap:14px;align-items:center}
    .morning-action-label{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--amber);font-weight:850}
    .morning-action-title{font-size:1.35rem;font-weight:950;color:var(--text);line-height:1.15;margin-top:5px}
    .morning-action-copy{font-size:.88rem;color:var(--muted);line-height:1.45;margin-top:7px}
    .morning-action-list{display:grid;gap:8px}
    .morning-action-item{display:flex;align-items:flex-start;gap:9px;border:1px solid rgba(141,160,184,.16);border-radius:8px;background:rgba(255,255,255,.035);padding:9px;color:var(--muted);font-size:.82rem;line-height:1.35}
    .morning-action-dot{width:8px;height:8px;border-radius:99px;background:var(--blue);margin-top:5px;flex:0 0 8px}
    .ai-verify{border:1px solid rgba(46,204,113,.24);border-radius:8px;background:linear-gradient(135deg,rgba(46,204,113,.09),rgba(103,183,255,.055),rgba(8,13,18,.96));padding:13px;margin:12px 0}
    .ai-verify-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}
    .ai-verify-title{font-size:1.05rem;font-weight:950;color:var(--text)}
    .ai-verify-copy{font-size:.82rem;color:var(--muted);line-height:1.4;margin-top:3px}
    .ai-verify-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px}
    .ai-verify-card{border:1px solid rgba(141,160,184,.16);border-radius:8px;background:rgba(255,255,255,.035);padding:9px;min-height:94px}
    .ai-verify-card.good{border-color:rgba(46,204,113,.34)}.ai-verify-card.warn{border-color:rgba(245,196,81,.34)}.ai-verify-card.info{border-color:rgba(103,183,255,.28)}
    .ai-verify-label{font-size:.66rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:850}
    .ai-verify-value{font-size:.96rem;font-weight:900;color:var(--text);line-height:1.25;margin-top:6px}
    .ai-verify-note{font-size:.74rem;color:var(--muted);line-height:1.32;margin-top:5px}
    .morning-narrative{border:1px solid var(--border2);border-radius:8px;background:linear-gradient(135deg,rgba(14,22,33,.98),rgba(8,13,18,.98));padding:14px;margin-top:12px}
    .morning-narrative-head{display:flex;align-items:center;justify-content:space-between;gap:12px;border-bottom:1px solid rgba(141,160,184,.16);padding-bottom:10px;margin-bottom:10px}
    .morning-narrative-title{font-size:1.05rem;font-weight:900;color:var(--text)}
    .morning-narrative-body{white-space:pre-wrap;color:#dbe8f5;font-size:.9rem;line-height:1.55}
    .evidence-shell{border:1px solid rgba(103,183,255,.28);border-radius:8px;background:linear-gradient(135deg,rgba(12,20,31,.96),rgba(8,13,18,.98));padding:14px;margin:12px 0}
    .evidence-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:12px}
    .evidence-title{font-size:1.12rem;font-weight:950;color:var(--text);line-height:1.15}
    .evidence-copy{color:var(--muted);font-size:.84rem;line-height:1.4;margin-top:4px}
    .evidence-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}
    .evidence-card{border:1px solid rgba(141,160,184,.16);border-radius:8px;background:rgba(255,255,255,.035);padding:10px;min-height:128px}
    .evidence-card.connected{border-color:rgba(46,204,113,.3)}.evidence-card.watch{border-color:rgba(245,196,81,.34)}.evidence-card.internal{border-color:rgba(103,183,255,.32)}
    .evidence-label{font-size:.68rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);font-weight:850}
    .evidence-value{font-size:.98rem;font-weight:900;color:var(--text);line-height:1.25;margin-top:7px}
    .evidence-detail{font-size:.78rem;color:var(--muted);line-height:1.35;margin-top:6px}
    .evidence-asof{font-family:var(--mono-font);font-size:.72rem;color:var(--blue);margin-top:7px}
    .evidence-flow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin-top:12px}
    .evidence-step{border:1px solid rgba(141,160,184,.15);border-radius:8px;background:rgba(255,255,255,.03);padding:9px}
    .evidence-step-num{display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:999px;background:rgba(103,183,255,.14);color:var(--blue);font-family:var(--mono-font);font-weight:900;font-size:.72rem}
    .evidence-step-title{font-weight:850;color:var(--text);font-size:.82rem;margin-top:7px}
    .evidence-step-copy{font-size:.75rem;color:var(--muted);line-height:1.33;margin-top:4px}
    .source-ledger{border:1px solid rgba(141,160,184,.18);border-radius:8px;background:rgba(255,255,255,.025);padding:13px;margin:12px 0}
    .source-ledger-head{display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:10px}
    .source-ledger-title{font-size:1rem;font-weight:930;color:var(--text)}
    .source-ledger-copy{font-size:.82rem;color:var(--muted);line-height:1.4;margin-top:3px}
    .source-ledger-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
    .source-row{border:1px solid rgba(141,160,184,.14);border-radius:8px;background:rgba(255,255,255,.03);padding:9px}
    .source-row-name{font-weight:850;color:var(--text);font-size:.86rem;line-height:1.25}
    .source-row-meta{font-size:.76rem;color:var(--muted);line-height:1.35;margin-top:4px}
    .source-row.connected{border-color:rgba(46,204,113,.28)}.source-row.unavailable{border-color:rgba(245,196,81,.28)}.source-row.scout{border-color:rgba(103,183,255,.28)}
    .upgrade-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin-top:10px}
    .upgrade-card{border:1px solid rgba(103,183,255,.18);border-radius:8px;background:rgba(103,183,255,.055);padding:9px}
    .upgrade-name{font-size:.82rem;font-weight:900;color:var(--text)}
    .upgrade-meta{font-size:.75rem;color:var(--muted);line-height:1.35;margin-top:4px}
    .scout-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:12px 0}
    .scout-card,.citation-card{border:1px solid var(--border);border-radius:8px;background:rgba(255,255,255,.03);padding:10px}
    .scout-name,.citation-title{font-weight:850;color:var(--text);line-height:1.25}
    .scout-role,.citation-url{font-size:.78rem;color:var(--muted);line-height:1.35;margin-top:5px;overflow-wrap:anywhere}
    .citation-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:10px}
    .prophet-header{padding:0 0 12px;margin:14px 0 16px;border:0;border-bottom:1px solid var(--border);border-radius:0;background:transparent}.prophet-header h3{margin:0;font-size:1.45rem;font-weight:850}
    .metric-card,.prophet-card{padding:12px}.card-title{font-size:.76rem;color:var(--muted)} .card-value{font-size:1.4rem;font-family:var(--mono-font);color:var(--text)} .small-muted{color:var(--muted);font-size:.8rem}
    .zone-call{border-color:rgba(33,208,122,.55)} .zone-put{border-color:rgba(255,95,124,.55)} .zone-neutral{border-color:rgba(103,183,255,.55)}
    .signal-badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:.75rem;border:1px solid var(--border);margin-bottom:8px}.signal-call{background:rgba(33,208,122,.14)} .signal-put{background:rgba(255,95,124,.14)}
    .distance-wrap{height:7px;border-radius:99px;background:#1b2943}.distance-fill{height:7px;border-radius:99px;background:linear-gradient(90deg,var(--blue),var(--green))}
    @media (max-width: 1100px){.hero-grid,.command-grid,.brief-grid,.context-grid,.source-grid,.briefing-mini-grid,.scout-grid,.citation-grid,.morning-hero-inner,.morning-dashboard,.morning-action-grid,.action-grid,.ai-verify-grid,.evidence-grid,.evidence-flow,.source-ledger-grid,.upgrade-grid{grid-template-columns:1fr}.morning-lines{grid-template-columns:repeat(2,minmax(0,1fr))}.morning-orb{justify-self:start}.wait-discipline{grid-template-columns:1fr}.structure-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.outcome-row{grid-template-columns:repeat(2,minmax(0,1fr))}.option-quote-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
    @keyframes brandDraw{0%{stroke-dashoffset:34;opacity:.62}45%,70%{stroke-dashoffset:0;opacity:1}100%{stroke-dashoffset:-34;opacity:.62}}
    @keyframes brandPulse{0%,100%{r:1.8;opacity:.7}50%{r:3.1;opacity:1}}
    @keyframes brandOrbit{to{transform:rotate(360deg)}}
    @keyframes brandScan{0%,100%{transform:translateY(-5px);opacity:.18}50%{transform:translateY(5px);opacity:.78}}
    @media (max-width: 680px){.terminal-top{align-items:flex-start;flex-direction:column}.brand-title{font-size:2rem}.hero-price{font-size:2.45rem}.structure-grid,.morning-lines,.morning-hero-metrics{grid-template-columns:1fr}.morning-title{font-size:1.55rem}.morning-orb{width:150px}.ui-icon.lg{width:64px;height:64px}.ui-icon.md{width:54px;height:54px}.brand-logo{width:74px;height:74px}}
    </style>
    """, unsafe_allow_html=True)




def render_badge(text, kind="neutral"):
    return f"<span class='prophet-badge badge-{kind}'>{text}</span>"

def render_kpi_card(title, value, subtitle=None, kind="neutral", badge=None):
    b = render_badge(badge, kind) if badge else ""
    st.markdown(f"<div class='prophet-card prophet-kpi'><div class='prophet-kpi-label'>{title} {b}</div><div class='prophet-kpi-value'>{value}</div><div class='small-muted'>{subtitle or ''}</div></div>", unsafe_allow_html=True)

def render_glass_card(title, body_html, kind="neutral", footer=None):
    foot = f"<div class='small-muted'>{footer}</div>" if footer else ""
    st.markdown(f"<div class='prophet-card prophet-card-glass'><div class='card-title'>{title}</div>{body_html}{foot}</div>", unsafe_allow_html=True)

def render_empty_state(title, message, next_action=None, kind="neutral"):
    st.markdown(f"<div class='empty-state'><b>{title}</b><br>{message}<br><span class='small-muted'>{next_action or ''}</span></div>", unsafe_allow_html=True)

def render_panel_notice(title, message, kind="warning"):
    st.markdown(f"<div class='warning-panel'><b>{title}</b><br>{message}</div>", unsafe_allow_html=True)

def render_decision_panel(decision_state):
    if not decision_state or not decision_state.signal_quality:
        render_empty_state("Decision", "No decision state available yet.", "Wait for data/signal.")
        return
    q=decision_state.signal_quality; g=decision_state.guardrail_state
    body=f"<div class='card-value'>{decision_state.final_decision}</div><div class='small-muted'>Grade {q.grade} | Score {fmt_float(q.score)} | Action {q.action_label}</div><div class='small-muted'>Warning: {(q.warnings[0] if q.warnings else '-') }</div><div class='small-muted'>Chase {g.chase_status} | Structure {g.structure_status} | Retest {g.retest_status}</div>"
    render_glass_card("Decision State", body)

def render_section_title(title, subtitle=None, icon=None):
    st.markdown(f"<div class='prophet-header'><h3>{icon or ''} {title}</h3><div class='small-muted'>{subtitle or ''}</div></div>", unsafe_allow_html=True)


def render_metric_card(title, value, subtitle=None, accent="neutral", extra_html=None):
    z = "zone-call" if accent=="call" else "zone-put" if accent=="put" else "zone-neutral"
    st.markdown(f"<div class='metric-card glow-card {z}'><div class='card-title'>{title}</div><div class='card-value'>{value}</div><div class='small-muted'>{subtitle or ''}</div>{extra_html or ''}</div>", unsafe_allow_html=True)


def render_line_card(line_name, tradable_value, raw_value, distance, zone_type, direction, is_closest=False):
    accent = "call" if zone_type=="CALL_ZONE" else "put" if zone_type=="PUT_ZONE" else "neutral"
    render_metric_card(f"{line_name}{' *' if is_closest else ''}", _fmt_num(tradable_value), f"{zone_side_label(zone_type)} | {direction} | distance {_fmt_num(distance)}", accent=accent)


def render_bias_card(bias_state):
    render_metric_card("Bias", f"{bias_state.bias} ({_fmt_num(bias_state.strength_score)})", bias_state.explanation, accent="neutral")


def render_distance_bar(label, distance, max_distance=5.0, zone_type="neutral"):
    pct = 0 if distance is None or pd.isna(distance) else min(100, abs(distance)/max_distance*100)
    st.markdown(f"<div class='small-muted'>{label}: {_fmt_num(distance)}</div><div class='distance-wrap'><div class='distance-fill' style='width:{pct:.1f}%'></div></div>", unsafe_allow_html=True)


def render_signal_badge(text, kind="neutral"):
    cls = "signal-call" if kind=="call" else "signal-put" if kind=="put" else ""
    st.markdown(f"<span class='signal-badge {cls}'>{text}</span>", unsafe_allow_html=True)


def render_signal_card(signal):
    if signal is None:
        st.info("No confirmed rejection yet. Waiting for hourly candle rejection at primary structure.")
        return
    kind = "call" if signal.signal_type=="CALL" else "put"
    render_signal_badge(f"{signal.signal_type} {signal.status}", kind)
    render_metric_card("Signal", f"{display_line_name(signal.line_name)} @ {_fmt_num(signal.line_value_at_rejection)}", f"entry {_fmt_num(signal.entry_price)} | stop {_fmt_num(signal.stop_price)} | target {display_line_name(signal.target_line_name)} {_fmt_num(signal.target_price)} | RR {_fmt_num(signal.rr_ratio)}")


def render_header_ticker(current_price, bias_state, closest_line, latest_signal, selected_strikes, provider_status="TASTYTRADE"):
    txt = f"SPY {_fmt_num(current_price)} • BIAS {bias_state.bias if bias_state else 'N/A'} • CLOSEST {display_line_name(closest_line.name) if closest_line else 'N/A'} • SIG {(latest_signal.signal_type+' '+latest_signal.status) if latest_signal else 'NONE'} • C {selected_strikes.call_strike if selected_strikes else '-'} / P {selected_strikes.put_strike if selected_strikes else '-'} • PROVIDER {provider_status}"
    st.markdown(f"<div class='metric-card ticker-scroll'><div class='ticker-track'>{txt} &nbsp;&nbsp;&nbsp; {txt}</div></div>", unsafe_allow_html=True)


def render_warning_panel(message): st.warning(message)

def render_data_notice(message: str, tone: str = "info") -> None:
    cls = "warn" if tone == "warn" else "info"
    st.markdown(f"<div class='data-notice {cls}'>{escape(str(message))}</div>", unsafe_allow_html=True)

def render_debug_json(label, obj):
    st.write(label); st.json(obj)


def redact_structure_calibration(value):
    if isinstance(value, list):
        return [redact_structure_calibration(item) for item in value]
    if isinstance(value, dict):
        return {
            key: ("protected" if key in {"slope_per_hour", "Formula", "Slope / Hour"} else redact_structure_calibration(item))
            for key, item in value.items()
        }
    return value


def hide_structure_calibration_columns(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    hidden = {"slope_per_hour", "Slope / Hour", "Formula", "raw_projected_value"}
    return df.drop(columns=[col for col in df.columns if col in hidden], errors="ignore")


def render_status_strip(items) -> None:
    html = "".join(f"<span><b>{label}</b> {value if value is not None else '-'}</span>" for label, value in items)
    st.markdown(f"<div class='status-strip'>{html}</div>", unsafe_allow_html=True)


def _tone_for_text(value: str | None) -> str:
    text = (value or "").upper()
    if any(word in text for word in ["CALL", "BULL", "LIVE", "CONFIRMED", "GO", "VALID"]):
        return "green"
    if any(word in text for word in ["PUT", "BEAR", "ERROR", "STOP", "AVOID"]):
        return "red"
    if any(word in text for word in ["WAIT", "PENDING", "WARN", "FALLBACK"]):
        return "amber"
    return "blue"


def _humanize(value: str | None) -> str:
    if value is None:
        return "-"
    return str(value).replace("_", " ")


def display_state_label(value: str | None) -> str:
    text = _humanize(value)
    labels = {
        "CONNECTED": "Connected",
        "WAIT": "Wait",
        "WAIT FOR CONFIRMATION": "Wait for confirmation",
        "WAIT FOR RETEST": "Wait for retest",
        "TRADE ALLOWED": "Trade allowed",
        "NO TRADE": "No trade",
        "REGULAR SESSION": "Session watch",
        "YFINANCE FALLBACK": "Delayed yfinance quotes",
        "TASTYTRADE LIVE": "Tastytrade live",
        "YFINANCE DELAYED": "Delayed quotes",
        "UNAVAILABLE": "Needs data",
        "NOT USED": "Not used",
    }
    return labels.get(text.upper(), text.title() if text == text.upper() else text)


def display_line_name(name: str | None) -> str:
    if not name:
        return "-"
    normalized = str(name).strip().upper().replace(" ", "_")
    primary = {
        "UA": "Upper Put Trigger",
        "UD": "Upper Call Trigger",
        "LA": "Lower Put Trigger",
        "LD": "Lower Call Trigger",
    }
    if normalized in primary:
        return primary[normalized]
    if normalized.startswith("S_ASC"):
        return "Lower Target"
    if normalized.startswith("S_DESC"):
        return "Upper Target"
    return _humanize(name)


def display_line_description(name: str | None) -> str:
    descriptions = {
        "UA": "PUT watch from the prior-session high",
        "UD": "CALL watch from the prior-session high",
        "LA": "PUT watch from the prior-session low",
        "LD": "CALL watch from the prior-session low",
    }
    if not name:
        return "-"
    normalized = str(name).strip().upper().replace(" ", "_")
    if normalized in descriptions:
        return descriptions[normalized]
    if normalized.startswith("S_ASC") or normalized.startswith("S_DESC"):
        return "Target-only structure"
    return _humanize(name)


def display_anchor_source(line: DynamicLine | None) -> str:
    if line is None:
        return "-"
    source_name = "High pivot" if line.source == "PRIMARY_HIGH" else "Low pivot" if line.source == "PRIMARY_LOW" else _humanize(line.source)
    return f"{source_name} {fmt_price(line.anchor_price)}"


def display_line_list(names: list[str] | tuple[str, ...] | None) -> str:
    return ", ".join(display_line_name(name) for name in names or []) or "-"


def _pill(label: str, value: str | None, tone: str | None = None) -> str:
    return f"<span class='pill {tone or _tone_for_text(value)}'>{label}: {value or '-'}</span>"


def ui_icon(name: str, tone: str = "blue", size: str = "md") -> str:
    icons = {
        "spark": "<path d='M12 2v5'/><path d='M12 17v5'/><path d='M2 12h5'/><path d='M17 12h5'/><path d='m5 5 3.5 3.5'/><path d='m15.5 15.5L19 19'/><path d='m19 5-3.5 3.5'/><path d='m8.5 15.5L5 19'/>",
        "pulse": "<path d='M3 12h4l2-6 4 12 2-6h6'/><path d='M5 20h14'/>",
        "compass": "<circle cx='12' cy='12' r='9'/><path d='m15.5 8.5-2.2 4.8-4.8 2.2 2.2-4.8 4.8-2.2z'/>",
        "bolt": "<path d='M13 2 4 14h7l-1 8 10-13h-7l1-7z'/>",
        "target": "<circle cx='12' cy='12' r='9'/><circle cx='12' cy='12' r='5'/><path d='M12 7v10'/><path d='M7 12h10'/>",
        "contract": "<path d='M7 3h7l4 4v14H7z'/><path d='M14 3v5h4'/><path d='M9.5 12h5'/><path d='M9.5 16h5'/>",
        "shield": "<path d='M12 3 5 6v5c0 4.2 2.8 7.8 7 10 4.2-2.2 7-5.8 7-10V6z'/><path d='M9 12l2 2 4-4'/>",
        "call": "<path d='M4 17 17 4'/><path d='M9 4h8v8'/><path d='M4 21h16'/>",
        "put": "<path d='M4 7l13 13'/><path d='M17 12v8H9'/><path d='M4 3h16'/>",
        "gauge": "<path d='M5 15a7 7 0 0 1 14 0'/><path d='M12 15l4-5'/><path d='M7 18h10'/>",
        "clock": "<circle cx='12' cy='12' r='8'/><path d='M12 7v5l3 2'/>",
        "peak": "<path d='M3 18h18'/><path d='m5 16 5-9 3 5 2-3 4 7'/>",
        "valley": "<path d='M3 6h18'/><path d='m5 8 5 9 3-5 2 3 4-7'/>",
    }
    glyph = icons.get(name, icons["spark"])
    return f"<span class='ui-icon {tone} {size}' aria-hidden='true'><svg viewBox='0 0 24 24'>{glyph}</svg></span>"


def render_brand_logo() -> str:
    return (
        "<span class='brand-logo' aria-hidden='true'><svg viewBox='0 0 48 48'>"
        "<line class='brand-grid' x1='10' y1='34' x2='38' y2='34'/>"
        "<line class='brand-grid' x1='10' y1='25' x2='38' y2='25'/>"
        "<line class='brand-grid' x1='10' y1='16' x2='38' y2='16'/>"
        "<path class='brand-orbit' d='M10 24c5-9 23-9 28 0-5 9-23 9-28 0z'/>"
        "<text class='brand-mono' x='24' y='22' text-anchor='middle'>SPY</text>"
        "<path class='brand-path' d='M9 33 L17 29 L22 31 L29 18 L38 13'/>"
        "<line class='brand-scan' x1='9' y1='26' x2='39' y2='26'/>"
        "<circle class='brand-dot' cx='38' cy='13' r='2.4'/>"
        "</svg></span>"
    )


def _entry_stop_summary(signal) -> str:
    if signal is None:
        return ""
    pieces = [f"Status {_humanize(signal.status)}."]
    if signal.entry_price is not None and not pd.isna(signal.entry_price):
        pieces.append(f"Entry {fmt_price(signal.entry_price)}.")
    else:
        pieces.append("Entry waits for the next candle open.")
    if signal.stop_price is not None and not pd.isna(signal.stop_price):
        pieces.append(f"Stop {fmt_price(signal.stop_price)}.")
    if signal.target_line_name:
        pieces.append(f"Target {display_line_name(signal.target_line_name)} {fmt_price(signal.target_price)}.")
    return " ".join(pieces)


def market_read_label(bias_state) -> str:
    if not bias_state:
        return "Waiting for structure"
    labels = {
        "BULLISH": "Call-side watch",
        "BEARISH": "Put-side watch",
        "NEUTRAL": "Two-sided watch",
        "REGULAR_SESSION": "Session watch",
        "UNKNOWN": "Structure unavailable",
    }
    return labels.get(bias_state.bias, _humanize(bias_state.bias))


def market_read_copy(bias_state) -> str:
    if not bias_state:
        return "Load SPY candles to calculate the prior-session structure."
    if bias_state.bias == "NEUTRAL":
        return "SPY is between the upper call and put triggers. Wait for a clean hourly rejection before choosing calls or puts."
    if bias_state.bias == "BULLISH":
        return "SPY is above the upper structure. Calls are the primary watch if price rejects the Upper Call Trigger."
    if bias_state.bias == "BEARISH":
        return "SPY is below the upper structure. Puts are the primary watch if price rejects the Lower Put Trigger."
    return bias_state.explanation


def signal_setup_label(signal) -> str:
    if signal is None:
        return "No active setup"
    status = "forming" if signal.status == "PENDING_CONFIRMATION" else "confirmed"
    return f"{signal.signal_type} setup {status}"


def signal_setup_copy(signal) -> str:
    if signal is None:
        return "Waiting for an hourly candle to reject a trade trigger."
    level = display_line_name(signal.line_name)
    if signal.status == "PENDING_CONFIRMATION":
        return f"Price rejected {level}. No trade yet; wait for the next hourly candle open. Stop {fmt_price(signal.stop_price)}. Target {display_line_name(signal.target_line_name)} {fmt_price(signal.target_price)}."
    return f"Confirmed at {level}. Entry {fmt_price(signal.entry_price)}. Stop {fmt_price(signal.stop_price)}. Target {display_line_name(signal.target_line_name)} {fmt_price(signal.target_price)}."


def quality_label(quality) -> str:
    if quality is None:
        return "-"
    if str(quality.action_label).upper() in {"NO_TRADE", "WAIT_FOR_CONFIRMATION"}:
        return _humanize(quality.action_label)
    return _humanize(quality.grade)


def next_hourly_checkpoint(value) -> pd.Timestamp:
    ts = pd.Timestamp(value)
    ts = ts.tz_localize(get_central_tz()) if ts.tzinfo is None else ts.tz_convert(get_central_tz())
    floor = ts.replace(minute=0, second=0, microsecond=0, nanosecond=0)
    return floor if ts == floor else floor + pd.Timedelta(hours=1)


def build_wait_discipline_items(decision_state=None, latest_signal=None, closest_line=None, selected_strikes=None, now_ct=None) -> list[dict]:
    now = pd.Timestamp(now_ct) if now_ct is not None else pd.Timestamp.now(tz=get_central_tz())
    now = now.tz_localize(get_central_tz()) if now.tzinfo is None else now.tz_convert(get_central_tz())
    if latest_signal and latest_signal.status == "PENDING_CONFIRMATION":
        checkpoint = pd.Timestamp(latest_signal.rejection_time) + pd.Timedelta(hours=1)
        candle_value = f"Open {fmt_clock_time(checkpoint)}"
        candle_copy = "Entry is locked until the next hourly candle opens."
    elif latest_signal:
        candle_value = "Confirmed"
        candle_copy = "Manage the confirmed setup; do not add after the chase guard fails."
    else:
        candle_value = f"Next {fmt_clock_time(next_hourly_checkpoint(now))}"
        trigger = display_line_name(closest_line.name) if closest_line else "primary structure"
        candle_copy = f"Need an hourly rejection at {trigger} before any entry."

    guardrail = decision_state.guardrail_state if decision_state else None
    chase_status = str(guardrail.chase_status if guardrail else "NO_SIGNAL").upper()
    if chase_status == "MISSED_ENTRY":
        chase_value = "Retest only"
        chase_copy = "Price moved too far from entry; the first trade is gone."
    elif latest_signal and latest_signal.status == "PENDING_CONFIRMATION":
        chase_value = "No early entry"
        chase_copy = "Let confirmation print before pricing the contract."
    else:
        chase_value = "Max $0.30"
        chase_copy = "After confirmation, avoid entries beyond the chase limit."

    watch_type = get_watch_option_type(latest_signal, None)
    if watch_type == "CALL":
        contract_value = "Call OTM"
        contract_copy = f"Strike stays about ${TARGET_OTM_STRIKE_DISTANCE:.0f} above the entry reference."
    elif watch_type == "PUT":
        contract_value = "Put OTM"
        contract_copy = f"Strike stays about ${TARGET_OTM_STRIKE_DISTANCE:.0f} below the entry reference."
    elif selected_strikes:
        contract_value = "Two-sided OTM"
        contract_copy = "Keep the call above and put below the trigger reference."
    else:
        contract_value = "No contract"
        contract_copy = "Contracts appear after SPY and structure data are ready."

    return [
        {"label": "Candle Gate", "value": candle_value, "copy": candle_copy},
        {"label": "Chase Guard", "value": chase_value, "copy": chase_copy},
        {"label": "Contract Guard", "value": contract_value, "copy": contract_copy},
    ]


def render_wait_discipline_html(decision_state=None, latest_signal=None, closest_line=None, selected_strikes=None, now_ct=None) -> str:
    cards = []
    for item in build_wait_discipline_items(decision_state, latest_signal, closest_line, selected_strikes, now_ct):
        cards.append(
            "<div class='wait-gate'>"
            f"<div class='wait-gate-label'>{escape(item['label'])}</div>"
            f"<div class='wait-gate-value'>{escape(item['value'])}</div>"
            f"<div class='wait-gate-copy'>{escape(item['copy'])}</div>"
            "</div>"
        )
    return f"<div class='wait-discipline'>{''.join(cards)}</div>"


def _intel_tile(label: str, value: str, copy: str, tone: str = "blue", icon_name: str | None = None) -> str:
    icon_html = ui_icon(icon_name, tone, "mini") if icon_name else ""
    return (
        f"<div class='intel-mini {tone}'>"
        f"<div class='intel-head'><div class='intel-label'>{label}</div>{icon_html}</div>"
        f"<div class='intel-value'>{value}</div>"
        f"<div class='intel-copy'>{copy}</div>"
        "</div>"
    )


def render_terminal_hero(
    latest_price,
    bias_state,
    decision_state,
    closest_line,
    latest_signal,
    selected_strikes,
    provider_status: str,
    now_ct,
    df: pd.DataFrame,
    prior_day,
    market_context: MarketContext | None = None,
    primary_lines: list[DynamicLine] | None = None,
    structure_projection_time=None,
) -> None:
    latest_candle = fmt_time(df.index[-1]) if df is not None and not df.empty else "-"
    clock = pd.Timestamp(now_ct).strftime("%I:%M:%S %p CT")
    projection_time = structure_projection_time or now_ct
    decision = display_state_label(decision_state.final_decision if decision_state else "WAIT")
    wait_discipline_html = render_wait_discipline_html(decision_state, latest_signal, closest_line, selected_strikes, now_ct)
    if decision_state and decision_state.signal_quality:
        q = decision_state.signal_quality
        decision_reason = f"Grade {display_state_label(q.grade)} with score {fmt_float(q.score)}. {display_state_label(q.action_label)}."
    else:
        decision_reason = bias_state.explanation if bias_state else "Waiting for enough structure to form a read."
    grade = decision_state.signal_quality.grade if decision_state and decision_state.signal_quality else "-"
    action = display_state_label(decision_state.signal_quality.action_label) if decision_state and decision_state.signal_quality else "Monitor"
    signal_text = f"{latest_signal.signal_type} {display_state_label(latest_signal.status)}" if latest_signal else "No signal"
    closest_value = closest_line.tradable_value_at(projection_time) if closest_line else None
    closest_name = display_line_name(closest_line.name) if closest_line else "-"
    closest_price = fmt_price(closest_value)
    call_strike = selected_strikes.call_strike if selected_strikes else "-"
    put_strike = selected_strikes.put_strike if selected_strikes else "-"
    if market_context is None:
        market_context = build_market_context(df, latest_price, closest_line, now_ct, float("nan"))
    pressure_value = fmt_price(market_context.spy_pressure_value) if not pd.isna(market_context.spy_pressure_value) else "-"
    trigger_gap = fmt_price(market_context.trigger_gap) if not pd.isna(market_context.trigger_gap) else "-"
    vix_value = fmt_price(market_context.vix_price) if not pd.isna(market_context.vix_price) else "-"
    intel_html = "".join([
        _intel_tile("VIX Regime", f"{vix_value} {market_context.vix_label}", market_context.vix_copy, market_context.vix_tone, "gauge"),
        _intel_tile("SPY Pressure", market_context.spy_pressure, f"3-bar change {pressure_value}", market_context.spy_pressure_tone, "pulse"),
        _intel_tile("Trigger Gap", market_context.trigger_gap_label, f"Distance {trigger_gap}", market_context.trigger_gap_tone, "target"),
        _intel_tile("Pivot Window", rth_session_window_label(), "Prior-day RTH candles", "blue", "clock"),
    ])
    anchors = get_primary_anchor_summary(primary_lines)
    anchor_html = "".join([
        _intel_tile("High Anchor", fmt_time(anchors["high_time"]), f"High {fmt_price(anchors['high_price'])}", "blue", "peak"),
        _intel_tile("Low Anchor", fmt_time(anchors["low_time"]), f"Low {fmt_price(anchors['low_price'])}", "blue", "valley"),
    ])
    st.markdown(
        f"""
        <div class='terminal-hero'>
          <div class='terminal-top'>
            <div class='brand-row'>
              {render_brand_logo()}
              <div class='label-stack'>
                <div class='brand-title'>SPY Prophet</div>
                <div class='brand-tagline'>When structure determines foresight...</div>
              </div>
            </div>
            <div class='market-clock'>
              <div>{clock}</div>
              <div>Prior session: {prior_day or '-'}</div>
            </div>
          </div>
          <div class='hero-grid'>
            <div>
              <div class='hero-price-row'>
                {ui_icon('pulse', market_context.spy_pressure_tone, 'lg')}
                <div class='label-stack'>
                  <div class='hero-label'>SPY Last</div>
                  <div class='hero-price'>{fmt_price(latest_price)}</div>
                </div>
              </div>
              <div class='hero-sub'>Latest candle {latest_candle}</div>
              <div class='hero-intel'>{intel_html}</div>
              <div class='hero-intel'>{anchor_html}</div>
            </div>
            <div class='decision-plate'>
              <div class='panel-head'>
                <div>
                  <div class='hero-label'>Final Decision</div>
                  <div class='decision-main'>{decision}</div>
                </div>
                {ui_icon('compass', _tone_for_text(decision), 'lg')}
              </div>
              <div class='decision-reason'>{decision_reason}</div>
              <div class='pill-row'>
                {_pill('Bias', display_state_label(bias_state.bias) if bias_state else '-')}
                {_pill('Grade', display_state_label(grade))}
                {_pill('Action', action)}
                {_pill('Signal', signal_text)}
              </div>
              {wait_discipline_html}
            </div>
            <div class='quote-stack'>
              <div class='quote-mini'>
                <div class='quote-head'>
                  <div>
                    <div class='hero-label'>Nearest Trigger</div>
                    <div class='quote-eyebrow'>Structure watch</div>
                  </div>
                  {ui_icon('target', 'amber', 'sm')}
                </div>
                <div class='quote-body'>
                  <div class='quote-trigger-name'>{closest_name}</div>
                  <div class='quote-trigger-price'>{closest_price}</div>
                </div>
                <div class='quote-meta-row'><span>Projected</span><strong>{fmt_clock_time(projection_time)}</strong></div>
              </div>
              <div class='quote-mini'>
                <div class='quote-head'>
                  <div>
                    <div class='hero-label'>0DTE Watchlist</div>
                    <div class='quote-eyebrow'>OTM contracts</div>
                  </div>
                  {ui_icon('contract', 'green', 'sm')}
                </div>
                <div class='strike-grid'>
                  <div class='strike-cell call'>
                    <div class='strike-label'>Call</div>
                    <div class='strike-value'>{call_strike}</div>
                  </div>
                  <div class='strike-cell put'>
                    <div class='strike-label'>Put</div>
                    <div class='strike-value'>{put_strike}</div>
                  </div>
                </div>
                <div class='quote-meta-row'><span>Source</span><strong>{display_state_label(provider_status)}</strong></div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_live_command_center(
    bias_state,
    decision_state,
    latest_signal,
    selected_strikes,
    options_state,
    latest_price,
    options_intel: OptionsIntelligence | None = None,
) -> None:
    quality = decision_state.signal_quality if decision_state else None
    guardrail = decision_state.guardrail_state if decision_state else None
    watch_lines = []
    if bias_state:
        watch_lines = bias_state.watched_call_lines + bias_state.watched_put_lines
    signal_body = signal_setup_copy(latest_signal)
    signal_title = signal_setup_label(latest_signal)
    options_market_data = bool(options_state and provider_is_allowed_option_data(options_state.provider) and (quote_has_live_market_data(options_state.call_quote) or quote_has_live_market_data(options_state.put_quote)))
    options_live = bool(options_state and provider_is_live_tastytrade(options_state.provider) and options_market_data)
    call_mark = fmt_price(options_state.call_quote.mark) if options_market_data and options_state.call_quote else "-"
    put_mark = fmt_price(options_state.put_quote.mark) if options_market_data and options_state.put_quote else "-"
    projection = options_state.entry_target_projection if options_live and options_state else None
    projection_text = (
        f"Entry {display_line_name(projection.entry_line_name)} at {fmt_price(projection.entry_line_value)}; "
        f"target {display_line_name(projection.target_line_name)} {fmt_price(projection.target_line_value)}."
        if projection else "Live option premium projections appear when Tastytrade quotes include Greeks."
    )
    options_copy = (
        f"CALL mark {call_mark}. PUT mark {put_mark}. {projection_text}"
        if options_market_data
        else "Live Tastytrade quotes are not active in this session. Delayed yfinance prices appear when available."
    )
    provider_text = option_provider_label(options_state, {}) if options_state else "TASTYTRADE setup needed"
    direction_tone = _tone_for_text(bias_state.bias if bias_state else "WAIT")
    setup_tone = _tone_for_text(signal_title)
    options_tone = "green" if options_live else "amber"
    watch_side = get_watch_option_type(latest_signal, bias_state)
    flow_alignment = premium_flow_alignment(options_intel, watch_side)
    flow_tone = (
        "green" if flow_alignment.get("state") == "aligned"
        else "red" if flow_alignment.get("state") == "opposes"
        else "amber" if flow_alignment.get("state") == "neutral"
        else "blue"
    )

    st.markdown(
        f"""
        <div class='terminal-section command-grid'>
          <div class='terminal-panel'>
            <div class='panel-head'>
              <div>
                <div class='panel-label'>Direction</div>
                <div class='panel-title'>{market_read_label(bias_state)}</div>
              </div>
              {ui_icon('compass', direction_tone, 'md')}
            </div>
            <div class='panel-copy'>{market_read_copy(bias_state)}</div>
            <div class='pill-row'>
              {_pill('Confidence', fmt_float(bias_state.strength_score) if bias_state else '-')}
              {_pill('Triggers', display_line_list(watch_lines))}
              {_pill('Price', fmt_price(latest_price))}
            </div>
          </div>
          <div class='terminal-panel'>
            <div class='panel-head'>
              <div>
                <div class='panel-label'>Setup</div>
                <div class='panel-title'>{signal_title}</div>
              </div>
              {ui_icon('bolt', setup_tone, 'md')}
            </div>
            <div class='panel-copy'>{signal_body}</div>
            <div class='pill-row'>
              {_pill('Action', display_state_label(quality_label(quality)))}
              {_pill('Score', fmt_float(quality.score) if quality else '-')}
              {_pill('Retest', display_state_label(guardrail.retest_status) if guardrail else '-')}
            </div>
          </div>
          <div class='terminal-panel'>
            <div class='panel-head'>
              <div>
                <div class='panel-label'>Flow Pressure</div>
                <div class='panel-title'>{escape(str(flow_alignment.get('title') or 'Flow Pressure'))}</div>
              </div>
              {ui_icon('pulse', flow_tone, 'md')}
            </div>
            <div class='panel-copy'>{escape(str(flow_alignment.get('copy') or 'No current flow context is loaded yet.'))}</div>
            <div class='pill-row'>
              {_pill('Side', display_state_label(flow_alignment.get('side') or 'Neutral'))}
              {_pill('Tide', display_state_label(flow_alignment.get('tide') or '-'))}
            </div>
          </div>
          <div class='terminal-panel'>
            <div class='panel-head'>
              <div>
                <div class='panel-label'>Options Data</div>
                <div class='panel-title'>{format_watch_contract(selected_strikes, latest_signal, bias_state)}</div>
              </div>
              {ui_icon('shield', options_tone, 'md')}
            </div>
            <div class='panel-copy'>{options_copy}</div>
            <div class='pill-row'>
              {_pill('DTE', selected_strikes.dte_label if selected_strikes else '-')}
              {_pill('Data', display_state_label(provider_text))}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_structure_tiles(primary_lines, latest_price, projection_time, closest_line, structure_day=None) -> None:
    tiles = []
    for name in ["UA", "UD", "LA", "LD"]:
        line = get_line_by_name(primary_lines, name)
        if not line:
            continue
        value = line.tradable_value_at(projection_time)
        distance = line.distance_from_price(latest_price, projection_time) if latest_price is not None else float("nan")
        kind = "tile-call" if line.zone_type == "CALL_ZONE" else "tile-put" if line.zone_type == "PUT_ZONE" else ""
        icon_name = "call" if line.zone_type == "CALL_ZONE" else "put" if line.zone_type == "PUT_ZONE" else "target"
        icon_tone = "green" if line.zone_type == "CALL_ZONE" else "red" if line.zone_type == "PUT_ZONE" else "blue"
        closest_cls = " closest" if closest_line is not None and closest_line.name == name else ""
        tiles.append(
            f"<div class='structure-tile {kind}{closest_cls}'>"
            f"<div class='tile-head'>"
            f"<div class='label-stack'><div class='tile-label'>{zone_side_label(line.zone_type)}</div>"
            f"<div class='tile-name'>{display_line_name(name)}</div></div>"
            f"{ui_icon(icon_name, icon_tone, 'sm')}"
            f"</div>"
            f"<div class='tile-value'>{fmt_price(value)}</div>"
            f"<div class='tile-meta'>Distance from SPY {fmt_float(distance)}</div>"
            f"<div class='tile-meta'>{display_anchor_source(line)}</div>"
            f"<div class='tile-meta'>Anchor close {fmt_time(line.anchor_time)}</div>"
            "</div>"
        )
    if tiles:
        st.markdown(f"<div class='structure-note'>Trigger values projected for {fmt_clock_time(projection_time)}</div><div class='structure-grid'>{''.join(tiles)}</div>", unsafe_allow_html=True)


def fmt_news_time(value) -> str:
    if value is None:
        return "Freshness unknown"
    try:
        ts = pd.Timestamp(value)
        ts = ts.tz_localize("UTC") if ts.tzinfo is None else ts
        return ts.tz_convert(get_central_tz()).strftime("%b %d, %I:%M %p CT").replace(" 0", " ")
    except Exception:
        return "Freshness unknown"


def render_learning_profile(profile: StructureLearningProfile) -> None:
    st.markdown(
        f"""
        <div class='learning-hero'>
          <div class='learning-head'>
            <div>
              <div class='panel-label'>Structure Learning</div>
              <div class='learning-title'>{escape(profile.expected_direction)}</div>
            </div>
            {ui_icon('compass', 'green' if profile.target_first_rate >= profile.stop_first_rate else 'amber', 'lg')}
          </div>
          <div class='learning-copy'>
            {escape(profile.confidence_label)} from {profile.matching_sample_size} matching outcomes
            ({profile.sample_size} completed outcomes in memory). {escape(profile.caveat)}
          </div>
          <div class='probability-grid'>
            <div class='prob-card green'><div class='prob-label'>Target first</div><div class='prob-value'>{fmt_pct(profile.target_first_rate * 100, 0)}</div></div>
            <div class='prob-card red'><div class='prob-label'>Stop first</div><div class='prob-value'>{fmt_pct(profile.stop_first_rate * 100, 0)}</div></div>
            <div class='prob-card blue'><div class='prob-label'>No hit</div><div class='prob-value'>{fmt_pct(profile.no_hit_rate * 100, 0)}</div></div>
          </div>
          <div class='pill-row'>
            {_pill('Avg RR', fmt_float(profile.average_rr))}
            {_pill('Avg favorable move', fmt_price(profile.average_max_favorable_move))}
            {_pill('Avg adverse move', fmt_price(profile.average_max_adverse_move))}
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if profile.best_context:
        render_data_notice(profile.best_context)


def render_news_feed(news_items: list[NewsItem]) -> None:
    head = f"<div class='feed-head'><div><div class='panel-label'>Market Movers</div><div class='panel-title'>SPY/SPX catalysts only</div></div>{ui_icon('pulse','blue','md')}</div>"
    items_to_show = list(news_items or [])[:MARKET_MOVING_NEWS_LIMIT]
    if not items_to_show:
        st.markdown(f"<div class='terminal-panel'>{head}<div class='panel-copy'>No fresh SPY/SPX-moving headline passed the filter. Trade from structure, catalyst timing, flow, and risk controls.</div></div>", unsafe_allow_html=True)
        return
    cards = []
    for item in items_to_show:
        title = escape(item.title)
        title_html = f"<a href='{escape(item.link)}' target='_blank'>{title}</a>" if item.link else title
        summary = f"<div class='news-summary'>{escape(item.summary[:160])}</div>" if item.summary else ""
        cards.append(
            "<div class='news-card'>"
            f"<div class='news-title'>{title_html}</div>"
            f"<div class='news-meta'><span>{escape(item.relevance)}</span><span>{escape(fmt_news_time(item.published))}</span><span>{escape(item.source)}</span></div>"
            f"{summary}"
            "</div>"
        )
    st.markdown(f"<div class='terminal-panel'>{head}<div class='news-list'>{''.join(cards)}</div></div>", unsafe_allow_html=True)


def render_economic_calendar(events: list[EconomicEvent]) -> None:
    head = f"<div class='calendar-head'><div><div class='panel-label'>Economic Calendar</div><div class='panel-title'>Catalyst timing</div></div>{ui_icon('clock','amber','md')}</div>"
    rows = []
    for event in events:
        notes = f"<div class='calendar-notes'>{escape(event.notes)}</div>" if event.notes else ""
        rows.append(
            "<div class='calendar-row'>"
            f"<div class='calendar-event'>{escape(str(event.event))}</div>"
            f"<div class='calendar-meta'><span>{escape(str(event.event_date))}</span><span>{escape(event.time_label)}</span><span class='calendar-impact'>{escape(event.impact)}</span><span>{escape(event.source)}</span></div>"
            f"{notes}"
            "</div>"
        )
    if not rows:
        rows.append(
            "<div class='calendar-row'>"
            "<div class='calendar-event'>No timed catalyst loaded</div>"
            "<div class='calendar-meta'><span>Run Foresight or connect a structured calendar source</span></div>"
            "<div class='calendar-notes'>Only dated, sourced macro events appear here. The app will leave this blank before it invents CPI, Fed, or jobs timing.</div>"
            "</div>"
        )
    st.markdown(f"<div class='terminal-panel'>{head}<div class='calendar-list'>{''.join(rows)}</div></div>", unsafe_allow_html=True)


def render_market_context_tab(profile: StructureLearningProfile, news_items: list[NewsItem], economic_events: list[EconomicEvent], market_context: MarketContext | None, latest_price, closest_line, projection_time) -> None:
    render_section_title("Market Context", "News, calendar, and structure statistics")
    if market_context:
        render_status_strip([
            ("SPY", fmt_price(latest_price)),
            ("VIX", f"{fmt_price(market_context.vix_price)} {market_context.vix_label}"),
            ("Pressure", market_context.spy_pressure),
            ("Nearest trigger", f"{display_line_name(closest_line.name) if closest_line else '-'} {fmt_price(closest_line.tradable_value_at(projection_time)) if closest_line else '-'}"),
        ])
    left, right = st.columns([1.05, 0.95])
    with left:
        render_learning_profile(profile)
        render_economic_calendar(economic_events)
    with right:
        render_news_feed(news_items)


def render_source_statuses(statuses: list[SourceStatus]) -> None:
    cards = []
    for status in statuses:
        if status.status == "skipped":
            continue
        cls = "connected" if status.status == "connected" else "unavailable"
        cards.append(
            f"<div class='source-card {cls}'>"
            f"<div class='source-name'>{escape(status.name)}</div>"
            f"<div class='source-state'>{escape(display_state_label(status.status))}</div>"
            f"<div class='source-detail'>{escape(status.detail)}</div>"
            "</div>"
        )
    st.markdown(f"<div class='source-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def render_briefing_snapshot(bundle: MorningBriefingBundle) -> None:
    event = bundle.economic_events[0] if bundle.economic_events else None
    leader = bundle.sector_context[0] if bundle.sector_context else None
    laggard = bundle.sector_context[-1] if bundle.sector_context else None
    gamma_label = "Dealer GEX" if bundle.gamma_insight.provider_payload else "OI Magnet"
    gamma_copy = bundle.gamma_insight.notes[:80]
    quote = bundle.options_intelligence.selected_quotes[0] if bundle.options_intelligence.selected_quotes else None
    quote_value = f"{quote.get('type')} {quote.get('strike')}" if quote else "Waiting"
    quote_copy = f"{quote.get('provider')} mark {fmt_price(quote.get('mark'))} delta {fmt_float(quote.get('delta'))}" if quote else "Live Tastytrade or delayed yfinance"
    mini = [
        ("Macro Event", event.event if event else "None loaded", event.time_label if event else "Calendar connector"),
        ("Put/Call OI", fmt_float(bundle.options_intelligence.put_call_open_interest_ratio), "Delayed yfinance proxy"),
        (gamma_label, bundle.gamma_insight.dealer_tone, gamma_copy),
        ("Option Quote", quote_value, quote_copy),
        ("Sector Leader", leader.label if leader else "-", fmt_float(leader.change_pct) + "%" if leader else "-"),
        ("Sector Laggard", laggard.label if laggard else "-", fmt_float(laggard.change_pct) + "%" if laggard else "-"),
        ("Prior Close", fmt_price(bundle.technical_context.prior_close), f"Gap {fmt_price(bundle.technical_context.gap_from_prior_close)}"),
        ("Learning", bundle.learning_profile.confidence_label, f"Target first {fmt_pct(bundle.learning_profile.target_first_rate * 100, 0)}"),
    ]
    html = "".join(
        f"<div class='briefing-mini'><div class='briefing-mini-label'>{escape(label)}</div><div class='briefing-mini-value'>{escape(str(value))}</div><div class='briefing-mini-copy'>{escape(str(copy))}</div></div>"
        for label, value, copy in mini
    )
    st.markdown(f"<div class='briefing-mini-grid'>{html}</div>", unsafe_allow_html=True)


def _morning_confidence_tone(confidence: int | float | None) -> tuple[str, str]:
    value = 0 if confidence is None or pd.isna(confidence) else int(confidence)
    if value >= 70:
        return "green", "High conviction"
    if value >= 52:
        return "blue", "Balanced read"
    if value >= 35:
        return "amber", "Patience zone"
    return "red", "Defensive read"


def _first_high_impact_event(events: list[EconomicEvent]) -> EconomicEvent | None:
    high = [event for event in events or [] if str(event.impact).lower() == "high"]
    return high[0] if high else (events[0] if events else None)


def _line_tone(role: str | None) -> str:
    text = (role or "").lower()
    if "call" in text:
        return "call"
    if "put" in text:
        return "put"
    return "neutral"


def _first_quote_label(options: OptionsIntelligence) -> tuple[str, str, list[str]]:
    quotes = options.selected_quotes or []
    if not quotes:
        return "No contract loaded", "Tastytrade/yfinance quote will appear when the option chain is available.", []
    call_quote = next((quote for quote in quotes if str(quote.get("type") or "").upper() == "CALL"), None)
    put_quote = next((quote for quote in quotes if str(quote.get("type") or "").upper() == "PUT"), None)
    if call_quote and put_quote:
        value = f"CALL {fmt_price(call_quote.get('strike'), 0)} / PUT {fmt_price(put_quote.get('strike'), 0)}"
        copy = (
            f"CALL mark {fmt_price(call_quote.get('mark'))}; PUT mark {fmt_price(put_quote.get('mark'))}. "
            "Action Brief selects the active side."
        )
        chips = [
            f"CALL spread {fmt_price(call_quote.get('spread'))}",
            f"PUT spread {fmt_price(put_quote.get('spread'))}",
        ]
        return value, copy, chips
    primary = quotes[0]
    value = f"{str(primary.get('type') or '').upper()} {primary.get('strike')}"
    copy = (
        f"Mark {fmt_price(primary.get('mark'))}; bid/ask "
        f"{fmt_price(primary.get('bid'))}/{fmt_price(primary.get('ask'))}; "
        f"delta {fmt_float(primary.get('delta'))}."
    )
    chips = []
    for quote in quotes[:2]:
        chips.append(f"{str(quote.get('type') or '').upper()} {quote.get('strike')} spread {fmt_price(quote.get('spread'))}")
    return value, copy, chips


def _joined_moves(moves: list[MarketMove], limit: int = 3) -> str:
    if not moves:
        return "No live move loaded."
    return " | ".join(move_line(move) for move in moves[:limit])


def unusual_whales_card_data(options: OptionsIntelligence) -> tuple[str, str, list[str], str]:
    whales = options.unusual_whales or {}
    if not isinstance(whales, dict) or not whales:
        return "", "", [], "blue"
    flow = whales.get("flow_alerts") or {}
    recent_flow = whales.get("recent_flow") or {}
    tide = whales.get("market_tide") or {}
    net_premium = whales.get("net_premium_ticks") or {}
    darkpool = whales.get("darkpool") or {}
    volume = whales.get("options_volume") or {}
    bias = str(flow.get("flow_bias") or recent_flow.get("tone") or net_premium.get("tone") or tide.get("tone") or "Flow context loaded")
    net_pressure = flow.get("net_premium_pressure")
    if (net_pressure is None or pd.isna(_finite_float(net_pressure))) and isinstance(recent_flow, dict):
        net_pressure = recent_flow.get("net_pressure")
    value = f"{bias} {fmt_money_short(net_pressure)}" if net_pressure is not None and not pd.isna(_finite_float(net_pressure)) else bias
    key_strikes = flow.get("key_strikes") if isinstance(flow, dict) else []
    if not key_strikes and isinstance(recent_flow, dict):
        key_strikes = recent_flow.get("top_strikes") or []
    first_strike = key_strikes[0] if key_strikes else None
    copy = "SPY 0DTE flow, premium tape, and dealer context are being merged into the Action Brief."
    if isinstance(first_strike, dict) and first_strike.get("strike") is not None:
        side = "call" if _finite_float(first_strike.get("call_premium"), 0) >= _finite_float(first_strike.get("put_premium"), 0) else "put"
        copy = f"Most active nearby institutional strike: {fmt_price(first_strike.get('strike'), 0)} {side.upper()} pressure."
    elif darkpool:
        copy = f"Dark-pool prints loaded: {darkpool.get('print_count', 0)} prints, {fmt_money_short(darkpool.get('total_premium'))} notional."
    chips = []
    if isinstance(flow, dict) and flow.get("alert_count"):
        chips.append(f"{flow.get('alert_count')} flow alerts")
    if isinstance(recent_flow, dict) and recent_flow.get("trade_count"):
        chips.append(f"{recent_flow.get('trade_count')} tape prints")
    if isinstance(net_premium, dict) and net_premium.get("tone"):
        chips.append(str(net_premium.get("tone")))
    if isinstance(tide, dict) and tide.get("tone"):
        chips.append(str(tide.get("tone")))
    if isinstance(volume, dict) and not pd.isna(_finite_float(volume.get("put_call_volume_ratio"))):
        chips.append(f"Vol P/C {fmt_float(volume.get('put_call_volume_ratio'))}")
    if isinstance(darkpool, dict) and darkpool.get("key_levels"):
        level = darkpool["key_levels"][0]
        chips.append(f"DP level {fmt_price(level.get('price'))}")
    tone = "green" if "bull" in bias.lower() or "risk-on" in bias.lower() else "red" if "bear" in bias.lower() or "risk-off" in bias.lower() else "amber"
    return value, copy, chips[:4], tone


def unusual_whales_gex_card_data(options: OptionsIntelligence) -> tuple[str, str, list[str], str] | None:
    whales = options.unusual_whales or {}
    if not isinstance(whales, dict) or not whales:
        return None
    gex = whales.get("gex") or {}
    if not isinstance(gex, dict) or not (gex.get("levels") or gex.get("gamma_flip")):
        return None
    flip = gex.get("gamma_flip")
    value = f"Flip {fmt_price(flip)}" if flip is not None and not pd.isna(_finite_float(flip)) else str(gex.get("dealer_tone") or "GEX loaded")
    levels = [row for row in (gex.get("levels") or []) if isinstance(row, dict)]
    copy = "Dealer hedging context from spot GEX by strike."
    if levels:
        copy = "Largest GEX strike " + fmt_price(levels[0].get("strike"), 0) + "; use as magnet/volatility context."
    chips = [f"{fmt_price(row.get('strike'), 0)} {fmt_money_short(row.get('total_gex'))}" for row in levels[:3]]
    tone = "green" if _finite_float(gex.get("net_gex"), 0) > 0 else "red" if _finite_float(gex.get("net_gex"), 0) < 0 else "blue"
    return value, copy, chips, tone


def _morning_card_html(title: str, value: str, copy: str, icon: str, tone: str = "blue", chips: list[str] | None = None) -> str:
    chip_html = ""
    if chips:
        chip_html = "<div class='morning-chip-row'>" + "".join(f"<span class='morning-chip'>{escape(chip)}</span>" for chip in chips if chip) + "</div>"
    return (
        f"<div class='morning-card {tone}'>"
        f"<div class='morning-card-head'>{ui_icon(icon, tone, 'sm')}<div class='morning-card-title'>{escape(title)}</div></div>"
        f"<div class='morning-card-value'>{escape(value)}</div>"
        f"<div class='morning-card-copy'>{escape(copy)}</div>"
        f"{chip_html}</div>"
    )


def render_morning_briefing_hero(bundle: MorningBriefingBundle, result: MorningBriefingResult, ai_ready: bool) -> None:
    tone, label = _morning_confidence_tone(result.confidence)
    ring = {"green": "#2ecc71", "blue": "#67b7ff", "amber": "#f5c451", "red": "#ff5f7c"}.get(tone, "#67b7ff")
    event = _first_high_impact_event(bundle.economic_events)
    event_value = f"{event.event} at {event.time_label}" if event else "No timed catalyst loaded"
    decision = morning_decision_from_result(result) or fallback_morning_decision(bundle, result)
    trade = decision.get("primary_trade") if isinstance(decision.get("primary_trade"), dict) else {}
    stance = display_state_label(str(decision.get("stance") or "WAIT").upper())
    contract = str(trade.get("contract") or "Wait for setup")
    trigger = str(trade.get("trigger_line") or "No trigger selected")
    st.markdown(
        f"""
        <div class='morning-hero'>
          <div class='morning-hero-inner'>
            <div>
              <div class='morning-kicker'>{ui_icon('spark', tone, 'sm')} Foresight Command</div>
              <div class='morning-title'>SPY Prophet Foresight</div>
              <div class='morning-subtitle'>Only the trade plan, trigger lines, and filters that can change today's 0DTE decision.</div>
              <div class='morning-hero-metrics'>
                <div class='morning-hero-stat'><div class='morning-stat-label'>Action</div><div class='morning-stat-value'>{escape(stance)}</div><div class='morning-stat-copy'>{escape(trigger)}</div></div>
                <div class='morning-hero-stat'><div class='morning-stat-label'>Contract</div><div class='morning-stat-value'>{escape(contract)}</div><div class='morning-stat-copy'>Use only after confirmation.</div></div>
                <div class='morning-hero-stat'><div class='morning-stat-label'>Catalyst</div><div class='morning-stat-value'>{escape(event.impact if event else 'None loaded')}</div><div class='morning-stat-copy'>{escape(event_value)}</div></div>
                <div class='morning-hero-stat'><div class='morning-stat-label'>Timing</div><div class='morning-stat-value'>{escape(fmt_time(result.generated_at))}</div><div class='morning-stat-copy'>Refresh before trading.</div></div>
              </div>
            </div>
            <div class='morning-orb' style='--confidence:{max(0, min(100, int(result.confidence or 0)))};--ring-color:{ring}'>
              <div class='morning-orb-core'>
                {ui_icon('gauge', tone, 'md')}
                <div class='morning-orb-value'>{int(result.confidence or 0)}%</div>
                <div class='morning-orb-label'>{escape(label)}</div>
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_morning_lines_deck(bundle: MorningBriefingBundle) -> None:
    cards = []
    for line in bundle.lines:
        tone = _line_tone(line.get("role"))
        icon = "call" if tone == "call" else "put" if tone == "put" else "target"
        cards.append(
            f"<div class='morning-line-card {tone}'>"
            f"<div class='morning-line-top'><div><div class='morning-line-name'>{escape(line.get('name') or '-')}</div><div class='morning-line-role'>{escape(line.get('role') or '-')}</div></div>{ui_icon(icon, 'green' if tone == 'call' else 'red' if tone == 'put' else 'blue', 'sm')}</div>"
            f"<div class='morning-line-value'>{escape(fmt_price(line.get('value')))}</div>"
            f"<div class='morning-line-anchor'>Anchor {escape(fmt_price(line.get('anchor_price')))}<br>{escape(str(line.get('anchor_time') or '-'))}</div>"
            "</div>"
        )
    if not cards:
        cards.append("<div class='morning-line-card neutral'><div class='morning-line-name'>Structure lines unavailable</div><div class='morning-line-anchor'>Load SPY candles to calculate today's lines.</div></div>")
    st.markdown(f"<div class='morning-lines'>{''.join(cards)}</div>", unsafe_allow_html=True)


def render_morning_action_panel(bundle: MorningBriefingBundle, result: MorningBriefingResult) -> None:
    decision = morning_decision_from_result(result) or fallback_morning_decision(bundle, result)
    trade = decision.get("primary_trade") if isinstance(decision.get("primary_trade"), dict) else {}
    stance = str(decision.get("stance") or "WAIT").upper()
    tone = "put" if "PUT" in stance else "green" if "CALL" in stance else "wait" if stance == "WAIT" else "blue"
    headline = str(decision.get("headline") or "Wait for a confirmed structure trigger.")
    novice = str(decision.get("novice_summary") or "Let the structure line confirm before choosing direction.")
    confidence = trade.get("confidence", result.confidence)
    tickets = [
        ("Stance", display_state_label(stance), novice),
        ("Trigger", str(trade.get("trigger_line") or "-"), f"Trigger price {trade.get('trigger_price') or '-'}"),
        ("Contract", str(trade.get("contract") or "-"), "Use only the listed OTM contract after the entry rule confirms."),
        ("Entry Rule", str(trade.get("entry_timing") or "-"), str(trade.get("entry_rule") or "-")),
        ("Invalidation", str(trade.get("stop") or "-"), "If this happens, the setup is no longer valid."),
        ("Target", str(trade.get("target") or "-"), f"Confidence {fmt_float(confidence, 0)}%"),
    ]
    ticket_html = "".join(
        "<div class='action-ticket'>"
        f"<div class='action-ticket-label'>{escape(label)}</div>"
        f"<div class='action-ticket-value'>{escape(value)}</div>"
        f"<div class='action-ticket-copy'>{escape(copy)}</div>"
        "</div>"
        for label, value, copy in tickets
    )
    reasons = [str(item) for item in decision.get("why", []) if str(item).strip()][:5]
    risks = [str(item) for item in decision.get("risk_flags", []) if str(item).strip()][:4]
    avoid = []
    for row in decision.get("avoid", [])[:3]:
        if isinstance(row, dict):
            avoid.append(f"{row.get('label')}: {row.get('reason')}")
        else:
            avoid.append(str(row))
    reason_html = "".join(f"<div class='action-reason'><span class='action-reason-dot'></span><span>{escape(item)}</span></div>" for item in reasons or ["No extra reason supplied by the briefing agent."])
    risk_html = "".join(f"<div class='action-reason action-risk'><span class='action-reason-dot'></span><span>{escape(item)}</span></div>" for item in (risks + avoid)[:5] or ["No specific risk flag loaded beyond normal 0DTE discipline."])
    st.markdown(
        f"""
        <div class='action-brief {tone}'>
          <div class='action-brief-head'>
            <div>
              <div class='action-kicker'>Action Brief</div>
              <div class='action-headline'>{escape(headline)}</div>
              <div class='action-summary'>{escape(str(trade.get('label') or 'SPY Prophet structure plan'))}</div>
            </div>
            {ui_icon('compass', 'green' if tone == 'green' else 'red' if tone == 'put' else 'amber', 'md')}
          </div>
          <div class='action-grid'>
            <div class='action-grid'>{ticket_html}</div>
            <div>
              <div class='action-kicker'>Why This Matters</div>
              <div class='action-reasons'>{reason_html}</div>
              <div class='action-kicker' style='margin-top:10px'>Avoid / Risk</div>
              <div class='action-reasons'>{risk_html}</div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _ai_verify_card(label: str, value: str, note: str, state: str = "info") -> str:
    return (
        f"<div class='ai-verify-card {state}'>"
        f"<div class='ai-verify-label'>{escape(label)}</div>"
        f"<div class='ai-verify-value'>{escape(value)}</div>"
        f"<div class='ai-verify-note'>{escape(note)}</div>"
        "</div>"
    )


def render_ai_verification_panel(result: MorningBriefingResult, ai_ready: bool, use_ai: bool) -> None:
    used_openai = bool(result.model)
    web_enabled = openai_web_search_enabled()
    citation_count = len(merge_citations(result.citations, None))
    cards = [
        _ai_verify_card(
            "Synthesis",
            "Live" if ai_ready else "Offline",
            "Foresight synthesis can refresh the read." if ai_ready else "Connect the synthesis key to unlock live reasoning.",
            "good" if ai_ready else "warn",
        ),
        _ai_verify_card(
            "This Read",
            "Synthesized" if used_openai else "Rule-based",
            "The engine consolidated the loaded inputs." if used_openai else "Click Generate Foresight to run live synthesis.",
            "good" if used_openai else "warn",
        ),
        _ai_verify_card(
            "Reasoning Core",
            "Ready" if ai_ready else "Standby",
            "Used only when you generate a fresh Foresight read.",
            "info",
        ),
        _ai_verify_card(
            "Current Scan",
            "Enabled" if web_enabled else "Off",
            f"{citation_count} current source references returned in this run.",
            "good" if web_enabled and citation_count else "info" if web_enabled else "warn",
        ),
    ]
    st.markdown(
        f"""
        <div class='ai-verify'>
          <div class='ai-verify-head'>
            <div>
              <div class='ai-verify-title'>Foresight Health</div>
              <div class='ai-verify-copy'>A quiet check that the read was freshly synthesized from current structure, flow, macro, and market inputs.</div>
            </div>
            {ui_icon('spark', 'green' if used_openai else 'amber', 'md')}
          </div>
          <div class='ai-verify-grid'>{''.join(cards)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_morning_context_deck(bundle: MorningBriefingBundle) -> None:
    event = _first_high_impact_event(bundle.economic_events)
    event_value = f"{event.event} at {event.time_label}" if event else "No timed catalyst loaded"
    event_copy = f"{event.impact} impact event: avoid blind entries around this time." if event else "No dated macro event is loaded; structure and flow must do the work."
    options = bundle.options_intelligence
    quote_value, quote_copy, quote_chips = _first_quote_label(options)
    cards = []
    cards.append(_morning_card_html("Catalyst Clock", event_value, event_copy, "clock", "amber" if event and str(event.impact).lower() == "high" else "blue"))
    whale_value, whale_copy, whale_chips, whale_tone = unusual_whales_card_data(options)
    if whale_value:
        cards.append(_morning_card_html("Flow Pressure", whale_value, whale_copy, "bolt", whale_tone, whale_chips))
    gex_card = unusual_whales_gex_card_data(options)
    if gex_card:
        gex_value, gex_copy, gex_chips, gex_tone = gex_card
        cards.append(_morning_card_html("Dealer Gamma", gex_value, gex_copy, "gauge", gex_tone, gex_chips))
    cards.extend([
        _morning_card_html("Contract Watch", quote_value, quote_copy, "contract", "green", quote_chips),
        _morning_card_html(
            "Structure Learning",
            bundle.learning_profile.confidence_label,
            f"Matched history: target first {fmt_pct(bundle.learning_profile.target_first_rate * 100, 0)}, stop first {fmt_pct(bundle.learning_profile.stop_first_rate * 100, 0)}.",
            "shield",
            "green" if bundle.learning_profile.target_first_rate > bundle.learning_profile.stop_first_rate else "amber",
        ),
    ])
    st.markdown(f"<div class='morning-dashboard'>{''.join(cards[:4])}</div>", unsafe_allow_html=True)


def _evidence_time(value) -> str:
    if value is None:
        return "as-of: current session"
    try:
        return f"as-of: {fmt_time(value)}"
    except Exception:
        return f"as-of: {value}"


def _evidence_card(label: str, value: str, detail: str, as_of=None, state: str = "connected") -> str:
    return (
        f"<div class='evidence-card {state}'>"
        f"<div class='evidence-label'>{escape(label)}</div>"
        f"<div class='evidence-value'>{escape(value)}</div>"
        f"<div class='evidence-detail'>{escape(detail)}</div>"
        f"<div class='evidence-asof'>{escape(_evidence_time(as_of))}</div>"
        "</div>"
    )


def render_briefing_evidence_trail(bundle: MorningBriefingBundle, result: MorningBriefingResult) -> None:
    event = _first_high_impact_event(bundle.economic_events)
    event_source = "Macro Calendar" if event else "No timed catalyst loaded"
    event_detail = f"{event.event} at {event.time_label} ({event.impact})" if event else "No dated macro row is loaded for this run. Run Foresight to scan current calendar sources."
    event_state = "connected" if event else "watch"
    quote_providers = sorted({display_state_label(str(q.get("provider") or "quote")) for q in (bundle.options_intelligence.selected_quotes or [])})
    quote_detail = ", ".join(quote_providers) if quote_providers else "No selected contract quote loaded yet."
    options_detail = f"{bundle.options_intelligence.status.detail} Selected quote source: {quote_detail}"
    whales = bundle.options_intelligence.unusual_whales or {}
    whale_flow = whales.get("flow_alerts", {}) if isinstance(whales, dict) else {}
    whale_recent = whales.get("recent_flow", {}) if isinstance(whales, dict) else {}
    whale_premium = whales.get("net_premium_ticks", {}) if isinstance(whales, dict) else {}
    whale_detail = (
        f"{whale_flow.get('alert_count', 0)} SPY 0DTE OTM alerts; {whale_flow.get('flow_bias', 'flow loaded')}; net pressure {fmt_money_short(whale_flow.get('net_premium_pressure'))}."
        if whale_flow
        else f"Recent tape {whale_recent.get('tone')}; premium tape {whale_premium.get('tone')}."
        if whale_recent or whale_premium
        else "Premium order-flow feed was not loaded into this run."
    )
    news_asof = bundle.news_items[0].published if bundle.news_items else None
    global_asof = bundle.global_context[0].as_of if bundle.global_context else None
    ai_detail = (
        f"{result.provider}. Unique web citations returned: {len(merge_citations(result.citations, None))}. "
        f"Model: {result.model or 'rule-based engine'}."
    )
    cards = [
        _evidence_card("SPY Prophet Lines", f"{len(bundle.lines)} internal lines", "Generated from your pivot/structure engine and passed into the briefing JSON.", bundle.generated_at, "internal"),
        _evidence_card("Economic Calendar", event_source, event_detail, bundle.generated_at, event_state),
        _evidence_card("Options Data", bundle.options_intelligence.status.name, options_detail, bundle.options_intelligence.status.as_of, "connected" if bundle.options_intelligence.status.status == "connected" else "watch"),
        _evidence_card("Flow Pressure", "Connected" if whales else "Not used", whale_detail, bundle.options_intelligence.status.as_of, "connected" if whales else "watch"),
        _evidence_card("Global Context", f"{len(bundle.global_context)} yfinance instruments", _joined_moves(bundle.global_context, 3), global_asof, "connected" if bundle.global_context else "watch"),
        _evidence_card("SPY Technicals", bundle.technical_context.status.name, bundle.technical_context.status.detail, bundle.technical_context.status.as_of, "connected" if bundle.technical_context.status.status == "connected" else "watch"),
        _evidence_card("Headline Scan", bundle.sentiment.status.name, f"{len(bundle.news_items)} same-day/previous-day headlines checked in the background for current-source context.", news_asof, "connected" if bundle.news_items else "watch"),
        _evidence_card("Learning Stats", bundle.learning_profile.confidence_label, f"Target first {fmt_pct(bundle.learning_profile.target_first_rate * 100, 0)}; stop first {fmt_pct(bundle.learning_profile.stop_first_rate * 100, 0)}.", bundle.generated_at, "internal"),
        _evidence_card("Foresight Synthesis", "Live synthesis" if result.model else "Rule-based verified", ai_detail, result.generated_at, "connected" if result.model else "internal"),
    ]
    steps = [
        ("1", "Collect", "The app loads structure, options, technicals, news, macro, and learning stats."),
        ("2", "Package", "Those fields become the verified data bundle for the briefing agent."),
        ("3", "Scan", "When live synthesis is on, the engine can check current public sources."),
        ("4", "Merge", "The recommendation must tie external context back to the four SPY Prophet lines."),
    ]
    step_html = "".join(
        f"<div class='evidence-step'><span class='evidence-step-num'>{num}</span><div class='evidence-step-title'>{escape(title)}</div><div class='evidence-step-copy'>{escape(copy)}</div></div>"
        for num, title, copy in steps
    )
    st.markdown(
        f"""
        <div class='evidence-shell'>
          <div class='evidence-head'>
            <div>
              <div class='evidence-title'>Evidence Trail</div>
              <div class='evidence-copy'>Proof layer for the briefing: what was loaded, where it came from, and how it supports the trade read.</div>
            </div>
            {ui_icon('shield', 'blue', 'md')}
          </div>
          <div class='evidence-grid'>{''.join(cards)}</div>
          <div class='evidence-flow'>{step_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _source_row_html(name: str, status: str, detail: str, as_of=None, url: str | None = None, state: str | None = None) -> str:
    css_state = state or ("connected" if str(status).lower() == "connected" else "unavailable")
    link = f" | {url}" if url else ""
    return (
        f"<div class='source-row {css_state}'>"
        f"<div class='source-row-name'>{escape(name)} - {escape(display_state_label(status))}</div>"
        f"<div class='source-row-meta'>{escape(detail + link)}</div>"
        f"<div class='source-row-meta'>{escape(_evidence_time(as_of))}</div>"
        "</div>"
    )


def render_actual_source_ledger(bundle: MorningBriefingBundle, result: MorningBriefingResult) -> None:
    rows = [
        _source_row_html("SPY Prophet structure engine", "connected", f"{len(bundle.lines)} trigger lines calculated from the app's pivot engine.", bundle.generated_at, state="connected"),
    ]
    for status in bundle.source_statuses:
        rows.append(_source_row_html(status.name, status.status, status.detail, status.as_of, status.url))
    citations = merge_citations(result.citations, None)
    if citations:
        for citation in citations[:4]:
            rows.append(_source_row_html(citation_title(citation), "connected", "Current source scan referenced this page in the generated read.", result.generated_at, citation.get("url"), "scout"))
    else:
        rows.append(_source_row_html("Current source scan", "not used", "No current source references were returned for this run.", result.generated_at, state="scout"))
    upgrades = [
        ("Macro calendar", "Generate Foresight for current calendar scanning, or connect a structured calendar source for scheduled releases."),
        ("Flow pressure", "Connect the premium flow token for 0DTE alerts, recent tape, net premium, market tide, dark-pool, IV, Greeks, and GEX context."),
        ("Options depth", "Live broker data gives bid, ask, spread, and Greeks. Premium flow adds order-flow context; market data remains the delayed backup."),
        ("Current scan", "Keep live synthesis enabled so the engine can cite current public pages when accessible."),
    ]
    upgrade_html = "".join(
        f"<div class='upgrade-card'><div class='upgrade-name'>{escape(name)}</div><div class='upgrade-meta'>{escape(copy)}</div></div>"
        for name, copy in upgrades
    )
    st.markdown(
        f"""
        <div class='source-ledger'>
          <div class='source-ledger-head'>
            <div>
              <div class='source-ledger-title'>Inputs Behind The Read</div>
              <div class='source-ledger-copy'>A compact health layer for the data that fed this Foresight read.</div>
            </div>
            {ui_icon('compass', 'blue', 'md')}
          </div>
          <div class='source-ledger-grid'>{''.join(rows)}</div>
          <div class='source-ledger-title' style='margin-top:12px'>How To Add More Reliable Sources</div>
          <div class='upgrade-grid'>{upgrade_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_scout_sources() -> None:
    cards = []
    for source in CURATED_MORNING_SOURCES:
        cards.append(
            "<div class='scout-card'>"
            f"<div class='scout-name'>{escape(source['name'])}</div>"
            f"<div class='scout-role'>{escape(source['role'])}</div>"
            f"<div class='scout-role'>{escape(source['url'])}</div>"
            "</div>"
        )
    st.markdown(f"<div class='scout-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def render_briefing_citations(citations: list[dict] | None) -> None:
    citations = merge_citations(citations, None)
    if not citations:
        return
    cards = []
    for citation in citations[:6]:
        url = citation.get("url") or ""
        title = citation_title(citation)
        cards.append(
            "<div class='citation-card'>"
            f"<a class='citation-title' href='{escape(url)}' target='_blank'>{escape(title)}</a>"
            f"<div class='citation-url'>{escape(url)}</div>"
            "</div>"
        )
    st.markdown("**Key Current Sources**")
    st.markdown(f"<div class='citation-grid'>{''.join(cards)}</div>", unsafe_allow_html=True)


def render_morning_briefing_tab(bundle: MorningBriefingBundle) -> None:
    render_section_title("Prophet Foresight", "Actionable 0DTE plan for today's SPY Prophet lines")
    ai_ready = bool(get_secret_or_env("OPENAI_API_KEY"))
    active_bundle = st.session_state.get("morning_briefing_bundle")
    if not isinstance(active_bundle, MorningBriefingBundle) or pd.Timestamp(active_bundle.generated_at).date() != pd.Timestamp(bundle.generated_at).date():
        active_bundle = bundle
    if not ai_ready:
        render_data_notice("Live synthesis is not connected. A verified rule-based Foresight read is still available.", tone="warn")
    control_cols = st.columns([0.62, 0.38])
    with control_cols[0]:
        st.markdown(
            f"""
            <div class='morning-control'>
              <div>
                <div class='morning-control-title'>Foresight Engine</div>
                <div class='morning-control-copy'>{escape('Ready to refresh the trade plan.' if ai_ready else 'Rule-based read is active until live synthesis is connected.')}</div>
              </div>
              {ui_icon('spark' if ai_ready else 'shield', 'green' if ai_ready else 'amber', 'md')}
            </div>
            """,
            unsafe_allow_html=True,
        )
    with control_cols[1]:
        use_ai = st.toggle("Use live synthesis", value=ai_ready, disabled=not ai_ready, key="morning_briefing_use_ai")
        if st.button("Generate Foresight" if ai_ready else "Generate Foresight read", type="primary", key="generate_morning_briefing", use_container_width=True):
            working_bundle = bundle
            calendar_citations = []
            if use_ai and not working_bundle.economic_events:
                with st.spinner("Checking current macro calendar sources..."):
                    ai_events, calendar_citations, calendar_warning = call_openai_calendar_scout(working_bundle.generated_at, days=0)
                working_bundle = bundle_with_economic_events(working_bundle, ai_events, calendar_warning)
            result = generate_morning_briefing(working_bundle, use_ai=use_ai)
            if calendar_citations:
                result = result_with_extra_citations(result, calendar_citations)
            save_morning_briefing(result)
            st.session_state["morning_briefing_result"] = result
            st.session_state["morning_briefing_bundle"] = working_bundle
            active_bundle = working_bundle
    result = st.session_state.get("morning_briefing_result")
    if not isinstance(result, MorningBriefingResult) or pd.Timestamp(result.generated_at).date() != pd.Timestamp(active_bundle.generated_at).date():
        result = None
    if result is None:
        result = generate_morning_briefing(active_bundle, use_ai=False)
    render_morning_briefing_hero(active_bundle, result, ai_ready)
    render_morning_action_panel(active_bundle, result)
    render_morning_lines_deck(active_bundle)
    render_morning_context_deck(active_bundle)
    if is_admin_diagnostics_enabled():
        with st.expander("Foresight health and inputs"):
            render_ai_verification_panel(result, ai_ready, use_ai)
            render_briefing_evidence_trail(active_bundle, result)
            render_actual_source_ledger(active_bundle, result)
            render_briefing_citations(result.citations)
    return



def safe_ohlc_columns(df: pd.DataFrame) -> tuple[str,str,str,str]:
    cols = {c.lower(): c for c in df.columns}
    return cols.get('open','Open'), cols.get('high','High'), cols.get('low','Low'), cols.get('close','Close')


def select_secondary_lines_for_chart(secondary_lines: list[DynamicLine], current_price: float, current_dt: pd.Timestamp, mode: str):
    valid = [(line, line.tradable_value_at(current_dt)) for line in secondary_lines if not pd.isna(line.tradable_value_at(current_dt))]
    if mode == 'all':
        return [v[0] for v in valid]
    n = 6 if mode == 'nearest 6' else 12
    return [x[0] for x in sorted(valid, key=lambda z: abs(z[1]-current_price))[:n]]


def make_line_trace(line: DynamicLine, xvals, name: str, current_dt: pd.Timestamp, width=2, dash='solid', opacity=0.9):
    ys=[line.tradable_value_at(x) for x in xvals]
    raw=[line.raw_value_at(x) for x in xvals]
    color = '#2dd4bf' if line.zone_type=='CALL_ZONE' else '#fb7185' if line.zone_type=='PUT_ZONE' else '#94a3b8'
    label = display_line_name(name)
    return go.Scatter(x=xvals,y=ys,mode='lines',name=label,line=dict(color=color,width=width,dash=dash),opacity=opacity,customdata=raw,hovertemplate=f"{label}<br>Tradable=%{{y:.2f}}<br>Raw=%{{customdata:.3f}}<extra></extra>")


def make_glow_line_trace(line: DynamicLine, xvals, name: str):
    ys=[line.tradable_value_at(x) for x in xvals]
    color = 'rgba(45,212,191,0.25)' if line.zone_type=='CALL_ZONE' else 'rgba(251,113,133,0.25)'
    return go.Scatter(x=xvals,y=ys,mode='lines',name=f"{display_line_name(name)} glow",showlegend=False,line=dict(color=color,width=9),hoverinfo='skip')


def render_plotly_html(fig: go.Figure, height: int = 780, display_mode_bar: bool = True) -> None:
    html = fig.to_html(
        full_html=False,
        include_plotlyjs=True,
        config={"displayModeBar": display_mode_bar, "responsive": True},
    )
    components.html(html, height=height, scrolling=False)


def add_trade_overlay_for_signal(fig, signal: TradeSignal):
    if signal.entry_time is None or pd.isna(signal.entry_price):
        return
    fig.add_trace(go.Scatter(x=[signal.entry_time], y=[signal.entry_price], mode='markers+text', text=['ENTRY'], textposition='top center', marker=dict(symbol='diamond',color='#f8fafc',size=9), name='ENTRY'))
    if not pd.isna(signal.stop_price):
        fig.add_trace(go.Scatter(x=[signal.entry_time-pd.Timedelta(hours=0.5), signal.entry_time+pd.Timedelta(hours=0.5)], y=[signal.stop_price, signal.stop_price], mode='lines+text', text=['STOP',''], line=dict(color='#ef4444',dash='dash'), name='STOP'))
    if signal.target_line_name and not pd.isna(signal.target_price):
        fig.add_trace(go.Scatter(x=[signal.entry_time-pd.Timedelta(hours=0.5), signal.entry_time+pd.Timedelta(hours=0.5)], y=[signal.target_price, signal.target_price], mode='lines+text', text=['TARGET',''], line=dict(color='#f59e0b',dash='dash'), name='TARGET'))


def add_decision_overlay(fig, decision_state):
    txt = 'WAIT | No active rejection.'
    if decision_state and decision_state.signal_quality:
        w = decision_state.signal_quality.warnings[0] if decision_state.signal_quality.warnings else 'Clean rejection'
        txt = f"{decision_state.final_decision} | {decision_state.signal_quality.grade} | {decision_state.signal_quality.action_label} | {w}"
    fig.add_annotation(xref='paper', yref='paper', x=0.01, y=0.99, text=txt, showarrow=False, align='left', bgcolor='rgba(8,13,22,0.75)', bordercolor='#334155', font=dict(color='#e2e8f0',size=11))


def build_prophet_chart(candles_df, primary_lines, secondary_lines, high_pivot, low_pivot, secondary_pivots, signals, decision_state, current_price, current_dt, show_secondary=True, show_signals=True, show_trade_overlays=True, show_pivots=True, secondary_mode='nearest 12'):
    fig = go.Figure()
    if candles_df is None or candles_df.empty:
        fig.add_annotation(text='No candle data available.', x=0.5, y=0.5, xref='paper', yref='paper', showarrow=False)
        return fig
    df = candles_df.sort_index(); o,h,l,c = safe_ohlc_columns(df)
    xvals = list(df.index)
    if current_dt > xvals[-1]: xvals.append(pd.Timestamp(current_dt))
    fig.add_trace(go.Candlestick(x=df.index, open=df[o], high=df[h], low=df[l], close=df[c], name='SPY', increasing_line_color='#22c55e', decreasing_line_color='#f43f5e'))
    closest = get_closest_primary_line(primary_lines, current_dt, current_price) if current_price is not None and not pd.isna(current_price) else None
    for line in primary_lines:
        if closest and line.name==closest.name: fig.add_trace(make_glow_line_trace(line,xvals,line.name))
        fig.add_trace(make_line_trace(line,xvals,line.name,current_dt,width=4 if closest and line.name==closest.name else 2))
    plotted_secondary=[]
    if show_secondary:
        s_lines = select_secondary_lines_for_chart(secondary_lines, current_price if current_price is not None else float('nan'), pd.Timestamp(current_dt), secondary_mode)
        plotted_secondary=s_lines
        for line in s_lines:
            fig.add_trace(make_line_trace(line,xvals,f"{display_line_name(line.name)} target",current_dt,width=1,dash='dash',opacity=0.55))
    if show_pivots:
        if high_pivot and high_pivot.timestamp is not None and not pd.isna(high_pivot.price): fig.add_trace(go.Scatter(x=[high_pivot.timestamp],y=[high_pivot.price],mode='markers+text',text=['High Pivot'],textposition='top center',marker=dict(color='#f97316',size=9),name='High Pivot'))
        if low_pivot and low_pivot.timestamp is not None and not pd.isna(low_pivot.price): fig.add_trace(go.Scatter(x=[low_pivot.timestamp],y=[low_pivot.price],mode='markers+text',text=['Low Pivot'],textposition='bottom center',marker=dict(color='#38bdf8',size=9),name='Low Pivot'))
    if show_signals:
        for sg in signals:
            color = '#22c55e' if sg.signal_type=='CALL' else '#f43f5e'; sym='triangle-up' if sg.signal_type=='CALL' else 'triangle-down'
            if sg.status=='PENDING_CONFIRMATION':
                fig.add_trace(go.Scatter(x=[sg.rejection_time],y=[sg.rejection_low if sg.signal_type=='CALL' else sg.rejection_high],mode='markers+text',text=['PENDING'],marker=dict(symbol=sym,size=11,color='rgba(0,0,0,0)',line=dict(color=color,width=2)),name=f"{sg.signal_type} pending"))
            else:
                fig.add_trace(go.Scatter(x=[sg.rejection_time],y=[sg.rejection_low if sg.signal_type=='CALL' else sg.rejection_high],mode='markers+text',text=[sg.signal_type],marker=dict(symbol=sym,size=12,color=color),name=f"{sg.signal_type} signal"))
        if show_trade_overlays and signals:
            add_trade_overlay_for_signal(fig, signals[-1])
    if current_price is not None and not pd.isna(current_price):
        fig.add_hline(y=current_price,line_dash='dot',line_color='#cbd5e1',annotation_text=f"SPY {current_price:.2f}")
    if closest:
        cv = closest.tradable_value_at(current_dt); d = current_price-cv if current_price is not None and not pd.isna(cv) else float('nan')
        fig.add_annotation(xref='paper',yref='paper',x=0.99,y=0.99,text=f"Closest Structure: {display_line_name(closest.name)} @ {cv:.2f} (Δ {d:.2f})",showarrow=False,font=dict(color='#e2e8f0',size=11),align='right')
    add_decision_overlay(fig, decision_state)
    fig.update_layout(height=820, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='#0b1220', font=dict(color='#cbd5e1'), xaxis_title='Central Time', yaxis_title='SPY', hovermode='x unified', xaxis_rangeslider_visible=False, margin=dict(l=20,r=20,t=30,b=150), legend=dict(orientation='h', x=0, y=-0.18, xanchor='left', yanchor='top', font=dict(size=10), bgcolor='rgba(8,13,22,0.72)', bordercolor='rgba(148,163,184,0.25)', borderwidth=1))
    fig.update_xaxes(showgrid=True, gridcolor='rgba(148,163,184,0.12)'); fig.update_yaxes(showgrid=True, gridcolor='rgba(148,163,184,0.12)')
    if show_secondary and secondary_mode!='all' and len(secondary_lines)>len(plotted_secondary):
        fig.add_annotation(xref='paper',yref='paper',x=0.01,y=0.02,text='Showing nearest secondary target lines.',showarrow=False,font=dict(size=10,color='#94a3b8'))
    return fig


def _zone_fill_trace(xvals, line: DynamicLine, name: str, color: str):
    return go.Scatter(x=xvals, y=[line.tradable_value_at(x) for x in xvals], mode="lines", line=dict(width=0, color=color), hoverinfo="skip", showlegend=False, name=name)


def add_structure_channel(fig, xvals, lower_line, upper_line, name: str, color: str):
    if lower_line is None or upper_line is None:
        return
    fig.add_trace(_zone_fill_trace(xvals, lower_line, f"{name} low", color))
    fig.add_trace(go.Scatter(x=xvals, y=[upper_line.tradable_value_at(x) for x in xvals], mode="lines", line=dict(width=0, color=color), fill="tonexty", fillcolor=color, hoverinfo="skip", showlegend=True, name=name))


def build_structure_path_chart(candles_df, primary_lines, secondary_lines, signals, decision_state, current_price, current_dt, secondary_mode="nearest 6"):
    fig = go.Figure()
    if candles_df is None or candles_df.empty:
        fig.add_annotation(text="No price path available.", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
        return fig
    df = candles_df.sort_index()
    _, _, _, close_col = safe_ohlc_columns(df)
    xvals = list(df.index)
    if current_dt is not None and pd.Timestamp(current_dt) > xvals[-1]:
        xvals.append(pd.Timestamp(current_dt))
    add_structure_channel(fig, xvals, get_line_by_name(primary_lines, "UD"), get_line_by_name(primary_lines, "UA"), "Upper trade zone", "rgba(103,183,255,0.12)")
    add_structure_channel(fig, xvals, get_line_by_name(primary_lines, "LD"), get_line_by_name(primary_lines, "LA"), "Lower trade zone", "rgba(255,95,124,0.10)")
    fig.add_trace(go.Scatter(x=df.index, y=df[close_col], mode="lines+markers", line=dict(color="#f4f7fb", width=3), marker=dict(size=5, color="#f4f7fb"), name="SPY path", hovertemplate="SPY %{y:.2f}<br>%{x|%b %d %I:%M %p}<extra></extra>"))
    closest = get_closest_primary_line(primary_lines, current_dt, current_price) if current_price is not None and not pd.isna(current_price) else None
    for line in primary_lines:
        color = "#21d07a" if line.zone_type == "CALL_ZONE" else "#ff5f7c" if line.zone_type == "PUT_ZONE" else "#67b7ff"
        width = 4 if closest and closest.name == line.name else 2
        label = display_line_name(line.name)
        fig.add_trace(go.Scatter(x=xvals, y=[line.tradable_value_at(x) for x in xvals], mode="lines", line=dict(color=color, width=width), name=label, hovertemplate=f"{label}<br>%{{y:.2f}}<extra></extra>"))
    for line in select_secondary_lines_for_chart(secondary_lines, current_price if current_price is not None else float("nan"), pd.Timestamp(current_dt), secondary_mode):
        fig.add_trace(go.Scatter(x=xvals, y=[line.tradable_value_at(x) for x in xvals], mode="lines", line=dict(color="#8da0b8", width=1, dash="dot"), opacity=0.55, name=display_line_name(line.name), hovertemplate=f"{display_line_name(line.name)}<br>%{{y:.2f}}<extra></extra>"))
    active_signal = get_latest_active_signal(signals, df)
    if active_signal:
        color = "#21d07a" if active_signal.signal_type == "CALL" else "#ff5f7c"
        y = active_signal.rejection_low if active_signal.signal_type == "CALL" else active_signal.rejection_high
        fig.add_trace(go.Scatter(x=[active_signal.rejection_time], y=[y], mode="markers+text", text=[f"{active_signal.signal_type} watch"], textposition="top center", marker=dict(size=14, color=color, symbol="diamond"), name="Active setup"))
        if active_signal.status == "CONFIRMED" and active_signal.entry_time is not None and not pd.isna(active_signal.entry_price):
            fig.add_trace(go.Scatter(x=[active_signal.entry_time], y=[active_signal.entry_price], mode="markers+text", text=["Entry"], textposition="bottom center", marker=dict(size=10, color="#f4c76b"), name="Entry"))
        if not pd.isna(active_signal.stop_price):
            fig.add_hline(y=active_signal.stop_price, line_dash="dash", line_color="#ff5f7c", annotation_text="Stop")
        if active_signal.target_line_name and not pd.isna(active_signal.target_price):
            fig.add_hline(y=active_signal.target_price, line_dash="dash", line_color="#f4c76b", annotation_text="Target")
    if current_price is not None and not pd.isna(current_price):
        fig.add_hline(y=current_price, line_dash="dot", line_color="#f4f7fb", annotation_text=f"Now {current_price:.2f}")
    title = "Price path with decision zones"
    if decision_state:
        title = f"{_humanize(decision_state.final_decision)}: {title}"
    fig.update_layout(height=700, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0b1220", font=dict(color="#cbd5e1"), title=dict(text=title, x=0.01, font=dict(size=16)), margin=dict(l=20, r=20, t=48, b=135), hovermode="x unified", legend=dict(orientation="h", x=0, y=-0.18, xanchor="left", yanchor="top", font=dict(size=10), bgcolor="rgba(8,13,22,0.72)", bordercolor="rgba(148,163,184,0.25)", borderwidth=1), xaxis_title="Central Time", yaxis_title="SPY")
    fig.update_xaxes(showgrid=True, gridcolor="rgba(148,163,184,0.10)", rangeslider_visible=False)
    fig.update_yaxes(showgrid=True, gridcolor="rgba(148,163,184,0.10)")
    return fig


def _svg_polyline_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    return " ".join(("M" if i == 0 else "L") + f"{x:.2f},{y:.2f}" for i, (x, y) in enumerate(points))


def _svg_text(value: object) -> str:
    return escape(str(value if value is not None else "-"))


def build_structure_map_svg(candles_df, primary_lines, secondary_lines, signals, decision_state, current_price, current_dt, title="Structure Map", subtitle=None, secondary_mode="nearest 6") -> str:
    width, height = 1180, 720
    x0, x1, y0, y1 = 84, 1088, 72, 502
    if candles_df is None or candles_df.empty:
        return (
            "<div class='svg-map-shell'><svg viewBox='0 0 1180 420' role='img'>"
            "<rect width='1180' height='420' rx='24' fill='#0b1220'/>"
            "<text x='590' y='210' text-anchor='middle' fill='#dbeafe' font-size='24' font-weight='800'>No price path available</text>"
            "</svg></div>"
        )

    df = candles_df.sort_index()
    _, _, _, close_col = safe_ohlc_columns(df)
    times = list(df.index)
    current_ts = pd.Timestamp(current_dt)
    if current_dt is not None and current_ts > times[-1]:
        times.append(current_ts)

    close_values = [float(v) for v in df[close_col].dropna().tolist()]
    level_values = []
    relevant_lines = list(primary_lines or []) + select_secondary_lines_for_chart(secondary_lines or [], current_price if current_price is not None else float("nan"), current_ts, secondary_mode)
    for line in relevant_lines:
        for ts in times:
            v = line.tradable_value_at(ts)
            if not pd.isna(v):
                level_values.append(float(v))
    if current_price is not None and not pd.isna(current_price):
        level_values.append(float(current_price))
    for sg in signals or []:
        for v in [sg.entry_price, sg.stop_price, sg.target_price, sg.line_value_at_rejection]:
            if v is not None and not pd.isna(v):
                level_values.append(float(v))

    all_values = close_values + level_values
    lo, hi = min(all_values), max(all_values)
    span = max(hi - lo, 1.0)
    pad = max(span * 0.18, 1.5)
    lo -= pad
    hi += pad

    def x_for(ts):
        if len(times) <= 1:
            return (x0 + x1) / 2
        idx = times.index(pd.Timestamp(ts)) if pd.Timestamp(ts) in times else len(times) - 1
        return x0 + (idx / (len(times) - 1)) * (x1 - x0)

    def y_for(value):
        if value is None or pd.isna(value):
            return (y0 + y1) / 2
        return y1 - ((float(value) - lo) / (hi - lo)) * (y1 - y0)

    spy_points = [(x_for(ts), y_for(float(df.loc[ts, close_col]))) for ts in df.index if ts in df.index and not pd.isna(df.loc[ts, close_col])]
    spy_path = _svg_polyline_path(spy_points)
    active_signal = get_latest_active_signal(signals or [], df)
    closest = get_closest_primary_line(primary_lines or [], current_ts, current_price) if current_price is not None and not pd.isna(current_price) else None
    current_y = y_for(current_price)
    current_x = x_for(times[-1])

    def line_points(line):
        return [(x_for(ts), y_for(line.tradable_value_at(ts))) for ts in times if not pd.isna(line.tradable_value_at(ts))]

    rail_items = []
    for line in primary_lines or []:
        path = _svg_polyline_path(line_points(line))
        if not path:
            continue
        is_closest = closest is not None and closest.name == line.name
        color = "#31d0aa" if line.zone_type == "CALL_ZONE" else "#ff6b8a"
        rail_items.append((line, path, y_for(line.tradable_value_at(times[-1])) + 5, is_closest, color))

    rails = []
    last_label_y = -999.0
    for line, path, label_y, is_closest, color in sorted(rail_items, key=lambda item: item[2]):
        label_y = min(max(label_y, last_label_y + 22), y1 - 8)
        last_label_y = label_y
        rails.append(
            f"<path d='{path}' class='rail {'rail-hot' if is_closest else ''}' stroke='{color}'/>"
            f"<text x='{x0 + 14}' y='{label_y:.2f}' class='rail-label' fill='{color}'>{_svg_text(display_line_name(line.name))}</text>"
        )

    targets = []
    for line in select_secondary_lines_for_chart(secondary_lines or [], current_price if current_price is not None else float("nan"), current_ts, secondary_mode):
        path = _svg_polyline_path(line_points(line))
        if path:
            targets.append(f"<path d='{path}' class='target-rail'/>")

    def channel_polygon(low_name, high_name):
        low_line, high_line = get_line_by_name(primary_lines or [], low_name), get_line_by_name(primary_lines or [], high_name)
        if not low_line or not high_line:
            return ""
        lows = line_points(low_line)
        highs = line_points(high_line)
        if not lows or not highs:
            return ""
        pts = lows + list(reversed(highs))
        return " ".join(f"{x:.2f},{y:.2f}" for x, y in pts)

    upper_poly = channel_polygon("UD", "UA")
    lower_poly = channel_polygon("LD", "LA")
    signal_marker = ""
    signal_title = "No active setup"
    signal_copy = "Waiting for a clean rejection"
    if active_signal:
        sig_color = "#31d0aa" if active_signal.signal_type == "CALL" else "#ff6b8a"
        sig_y_value = active_signal.entry_price if active_signal.entry_price is not None and not pd.isna(active_signal.entry_price) else active_signal.line_value_at_rejection
        sig_x = x_for(active_signal.entry_time or active_signal.rejection_time)
        sig_y = y_for(sig_y_value)
        signal_title = f"{active_signal.signal_type} {_humanize(active_signal.status)}"
        signal_copy = display_line_name(active_signal.line_name)
        signal_marker = (
            f"<g class='signal-pulse' transform='translate({sig_x:.2f} {sig_y:.2f})'>"
            f"<circle r='18' fill='{sig_color}' opacity='.16'/><circle r='8' fill='{sig_color}'/>"
            f"<text x='18' y='5' class='marker-label' fill='{sig_color}'>{_svg_text(active_signal.signal_type)}</text></g>"
        )

    decision_title = _humanize(decision_state.final_decision) if decision_state else "Wait"
    closest_label = display_line_name(closest.name) if closest else "No trigger"
    closest_value = closest.tradable_value_at(current_ts) if closest else float("nan")
    subtitle = subtitle or f"SPY {fmt_price(current_price)} near {closest_label} {fmt_price(closest_value)}"
    grid = []
    for i in range(5):
        y = y0 + (i / 4) * (y1 - y0)
        val = hi - (i / 4) * (hi - lo)
        grid.append(f"<line x1='{x0}' y1='{y:.2f}' x2='{x1}' y2='{y:.2f}' class='grid-line'/><text x='32' y='{y + 4:.2f}' class='axis-label'>{val:.2f}</text>")

    latest_label = fmt_time(times[-1]) if times else "-"
    first_label = fmt_time(times[0]) if times else "-"
    cards = [
        ("Decision", decision_title, signal_copy),
        ("Closest Trigger", closest_label, fmt_price(closest_value)),
        ("Current SPY", fmt_price(current_price), latest_label),
        ("Active Setup", signal_title, "Signal engine"),
    ]
    card_html = "".join(
        f"<div class='svg-map-card'><div class='svg-card-label'>{_svg_text(k)}</div><div class='svg-card-value'>{_svg_text(v)}</div><div class='svg-card-copy'>{_svg_text(c)}</div></div>"
        for k, v, c in cards
    )

    return f"""
    <style>
      .svg-map-shell{{background:#111821;border:1px solid #243244;border-radius:8px;padding:16px 16px 12px;box-shadow:none;font-family:Inter,"Source Sans 3","Segoe UI",Roboto,system-ui,sans-serif;color:#f4f7fb}}
      .svg-map-shell svg{{display:block;width:100%;height:auto}}
      .svg-map-title{{display:flex;justify-content:space-between;gap:16px;align-items:flex-end;margin:2px 2px 12px}}
      .svg-map-title h3{{margin:0;font-size:20px;letter-spacing:0;font-weight:850;color:#f4f7fb}}
      .svg-map-title p{{margin:4px 0 0;color:#9aa7b5;font-size:13px}}
      .svg-map-badge{{border:1px solid #314357;border-radius:999px;padding:7px 11px;color:#b9dcfb;background:#151f2b;font-size:12px;font-weight:750;white-space:nowrap}}
      .grid-line{{stroke:#243244;stroke-width:1;opacity:.72}}
      .axis-label{{fill:#9aa7b5;font-size:12px;font-weight:650}}
      .zone-upper{{fill:#4ea8de;opacity:.10}}
      .zone-lower{{fill:#f45d75;opacity:.08}}
      .rail{{fill:none;stroke-width:2.5;stroke-linecap:round;stroke-dasharray:8 10;animation:railFlow 9s linear infinite}}
      .rail-hot{{stroke-width:4}}
      .target-rail{{fill:none;stroke:#9aa7b5;stroke-width:1.25;stroke-dasharray:3 7;opacity:.42}}
      .spy-path{{fill:none;stroke:url(#spyGradient);stroke-width:4.5;stroke-linecap:round;stroke-linejoin:round;stroke-dasharray:1400;stroke-dashoffset:1400;animation:drawPath 2.4s ease-out forwards}}
      .spy-shadow{{fill:none;stroke:#4ea8de;stroke-width:10;stroke-linecap:round;stroke-linejoin:round;opacity:.10}}
      .price-line{{stroke:#f8fbff;stroke-width:1.5;stroke-dasharray:7 9;opacity:.85}}
      .price-dot{{fill:#f8fbff;stroke:#4ea8de;stroke-width:4}}
      .rail-label,.marker-label{{font-size:12px;font-weight:850;letter-spacing:0}}
      .map-label{{fill:#d9ecff;font-size:13px;font-weight:800}}
      .map-muted{{fill:#8ba9c8;font-size:12px;font-weight:650}}
      .signal-pulse circle:first-child{{animation:pulse 2.2s ease-in-out infinite;transform-origin:center}}
      .svg-map-cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:10px;margin-top:12px;align-items:stretch}}
      .svg-map-card{{border:1px solid #243244;background:#151f2b;border-radius:8px;padding:11px 12px;min-height:92px;overflow:visible}}
      .svg-card-label{{font-size:11px;color:#9aa7b5;text-transform:uppercase;letter-spacing:.08em}}
      .svg-card-value{{font-size:18px;line-height:1.22;margin-top:5px;font-weight:850;color:#fbfdff;white-space:normal;overflow-wrap:anywhere}}
      .svg-card-copy{{font-size:12px;color:#95acc6;margin-top:6px;line-height:1.35;white-space:normal;overflow-wrap:anywhere}}
      @keyframes drawPath{{to{{stroke-dashoffset:0}}}}
      @keyframes railFlow{{to{{stroke-dashoffset:-120}}}}
      @keyframes pulse{{0%,100%{{transform:scale(.85);opacity:.16}}50%{{transform:scale(1.4);opacity:.32}}}}
      @media (max-width:760px){{.svg-map-title{{display:block}}.svg-map-badge{{display:inline-block;margin-top:10px}}.svg-map-cards{{grid-template-columns:1fr}}}}
    </style>
    <div class='svg-map-shell'>
      <div class='svg-map-title'><div><h3>{_svg_text(title)}</h3><p>{_svg_text(subtitle)}</p></div><div class='svg-map-badge'>Animated structure map</div></div>
      <svg viewBox='0 0 {width} {height}' role='img' aria-label='{_svg_text(title)}'>
        <defs>
          <linearGradient id='spyGradient' x1='0' x2='1'><stop offset='0%' stop-color='#9bdcff'/><stop offset='48%' stop-color='#ffffff'/><stop offset='100%' stop-color='#f4c76b'/></linearGradient>
          <filter id='softGlow'><feGaussianBlur stdDeviation='4' result='blur'/><feMerge><feMergeNode in='blur'/><feMergeNode in='SourceGraphic'/></feMerge></filter>
        </defs>
        <rect x='0' y='0' width='{width}' height='{height - 96}' rx='8' fill='#0d131d'/>
        <rect x='{x0}' y='{y0}' width='{x1 - x0}' height='{y1 - y0}' rx='8' fill='#111821' stroke='#243244'/>
        {''.join(grid)}
        {"<polygon points='" + upper_poly + "' class='zone-upper'/>" if upper_poly else ""}
        {"<polygon points='" + lower_poly + "' class='zone-lower'/>" if lower_poly else ""}
        {''.join(targets)}
        {''.join(rails)}
        <path d='{spy_path}' class='spy-shadow'/>
        <path id='spyPath' d='{spy_path}' class='spy-path'/>
        <line x1='{x0}' y1='{current_y:.2f}' x2='{x1}' y2='{current_y:.2f}' class='price-line'/>
        <circle class='price-dot' cx='{current_x:.2f}' cy='{current_y:.2f}' r='7'/>
        <text x='{x1 - 4}' y='{current_y - 12:.2f}' text-anchor='end' class='map-label'>SPY {fmt_price(current_price)}</text>
        {signal_marker}
        <text x='{x0}' y='{height - 132}' class='map-muted'>{_svg_text(first_label)}</text>
        <text x='{x1}' y='{height - 132}' text-anchor='end' class='map-muted'>{_svg_text(latest_label)}</text>
        <circle r='5' fill='#f4c76b'><animateMotion dur='7s' repeatCount='indefinite' path='{spy_path}'/></circle>
      </svg>
      <div class='svg-map-cards'>{card_html}</div>
    </div>
    """


def render_structure_map_svg(*args, height: int = 940, **kwargs) -> None:
    components.html(build_structure_map_svg(*args, **kwargs), height=height, scrolling=False)


def render_chart_brief(current_price, closest_line, active_signal, decision_state, current_dt):
    closest_value = closest_line.tradable_value_at(current_dt) if closest_line else None
    signal_text = f"{active_signal.signal_type} {_humanize(active_signal.status)}" if active_signal else "No active signal"
    cards = [
        ("Current SPY", fmt_price(current_price), "Live price context"),
        ("Closest Structure", f"{display_line_name(closest_line.name)} {fmt_price(closest_value)}" if closest_line else "-", display_line_description(closest_line.name) if closest_line else "Waiting"),
        ("Signal State", signal_text, display_line_name(active_signal.line_name) if active_signal else "Waiting for rejection"),
        ("Decision", _humanize(decision_state.final_decision) if decision_state else "WAIT", _humanize(decision_state.signal_quality.grade) if decision_state and decision_state.signal_quality else "No grade yet"),
    ]
    html = "".join(f"<div class='brief-card'><div class='brief-label'>{label}</div><div class='brief-value'>{value}</div><div class='brief-copy'>{copy}</div></div>" for label, value, copy in cards)
    st.markdown(f"<div class='brief-grid'>{html}</div>", unsafe_allow_html=True)


def render_replay_story(rs: ReplayState, replay_candles: pd.DataFrame, mode: str):
    latest_price = float(replay_candles["Close"].iloc[-1]) if replay_candles is not None and not replay_candles.empty else float("nan")
    active = get_latest_active_signal(rs.signals, replay_candles) if replay_candles is not None and not replay_candles.empty else None
    story = "No active setup at this replay point."
    if active:
        story = f"{active.signal_type} setup at {display_line_name(active.line_name)}. Status: {_humanize(active.status)}."
    html = (
        "<div class='replay-shell'>"
        f"<div class='replay-title'>{mode}: {rs.replay_date}</div>"
        f"<div class='replay-copy'>Structure came from {rs.prior_trading_day}. Replay price is {fmt_price(latest_price)}. {story}</div>"
        "<div class='outcome-row'>"
        f"<div class='outcome-card'><div class='brief-label'>Signals</div><div class='brief-value'>{len(rs.signals)}</div></div>"
        f"<div class='outcome-card'><div class='brief-label'>Confirmed</div><div class='brief-value'>{len([x for x in rs.signals if x.status=='CONFIRMED'])}</div></div>"
        f"<div class='outcome-card'><div class='brief-label'>Pending</div><div class='brief-value'>{len([x for x in rs.signals if x.status=='PENDING_CONFIRMATION'])}</div></div>"
        f"<div class='outcome-card'><div class='brief-label'>Targets</div><div class='brief-value'>{len([o for o in rs.outcomes.values() if o.outcome=='TARGET_FIRST'])}</div></div>"
        f"<div class='outcome-card'><div class='brief-label'>Stops</div><div class='brief-value'>{len([o for o in rs.outcomes.values() if o.outcome=='STOP_FIRST'])}</div></div>"
        f"<div class='outcome-card'><div class='brief-label'>No Hit</div><div class='brief-value'>{len([o for o in rs.outcomes.values() if o.outcome=='NO_HIT'])}</div></div>"
        "</div></div>"
    )
    st.markdown(html, unsafe_allow_html=True)
    return active



@dataclass(frozen=True)
class OptionQuote:
    symbol: str; underlying: str; expiration: object; strike: int; option_type: str
    bid: float; ask: float; mark: float; spread: float; delta: float; gamma: float; theta: float; vega: float; iv: float
    provider: str; timestamp: pd.Timestamp | None; warning: str | None

@dataclass(frozen=True)
class OptionsScenario:
    option_type: str; strike: int; current_mark: float; underlying_move: float; estimated_mark: float; estimated_pnl_per_contract: float; explanation: str

@dataclass(frozen=True)
class EntryTargetOptionProjection:
    option_type: str; strike: int; option_symbol: str; current_underlying_price: float; current_option_mark: float; option_delta: float
    entry_line_name: str; entry_line_value: float; entry_projection_time: pd.Timestamp; underlying_move_to_entry: float; estimated_entry_mark: float
    target_line_name: str | None; target_line_value: float; target_projection_time: pd.Timestamp | None; underlying_move_entry_to_target: float; estimated_target_mark: float
    estimated_profit_per_contract: float; estimated_return_pct: float; warning: str | None; explanation: str

@dataclass(frozen=True)
class OptionsCockpitState:
    provider: str; underlying_price: float; expiration: object; call_quote: OptionQuote | None; put_quote: OptionQuote | None; selected_trade_quote: OptionQuote | None
    scenarios: list[OptionsScenario]; entry_target_projection: EntryTargetOptionProjection | None; warning: str | None; explanation: str


class YFinanceOptionProvider:
    provider_name = "YFINANCE_DELAYED"

    def get_selected_quotes(self, underlying_price, expiration_date, call_strike, put_strike):
        return fetch_yfinance_option_quotes(expiration_date, call_strike, put_strike)


def is_mock_option_provider_name(name: str | None) -> bool:
    text = str(name or "").upper()
    return "MOCK" in text or text == "MOC"


def provider_is_live_tastytrade(name: str | None) -> bool:
    text = str(name or "").upper()
    return "TASTYTRADE" in text and not is_mock_option_provider_name(text)


def provider_is_yfinance_delayed(name: str | None) -> bool:
    return "YFINANCE" in str(name or "").upper()


def provider_is_allowed_option_data(name: str | None) -> bool:
    return provider_is_live_tastytrade(name) or provider_is_yfinance_delayed(name)


def quote_has_live_market_data(quote: OptionQuote | None) -> bool:
    if quote is None:
        return False
    values = [quote.bid, quote.ask, quote.mark, quote.delta]
    return any(value is not None and not pd.isna(value) for value in values)


def quote_has_projection_inputs(quote: OptionQuote | None) -> bool:
    return bool(quote and quote.mark is not None and not pd.isna(quote.mark) and quote.delta is not None and not pd.isna(quote.delta))


def _finite_float(value, default: float = float("nan")) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out


def option_mark_from_bid_ask_or_last(bid: float, ask: float, last_price: float) -> float:
    if not pd.isna(bid) and not pd.isna(ask) and bid > 0 and ask > 0:
        return round((bid + ask) / 2, 2)
    if not pd.isna(last_price) and last_price > 0:
        return round(last_price, 2)
    return float("nan")


def _quote_from_yfinance_row(row, option_type: str, expiration_date) -> dict:
    bid = _finite_float(row.get("bid"))
    ask = _finite_float(row.get("ask"))
    last_price = _finite_float(row.get("lastPrice"))
    mark = option_mark_from_bid_ask_or_last(bid, ask, last_price)
    spread = round(ask - bid, 2) if not pd.isna(bid) and not pd.isna(ask) else float("nan")
    return {
        "symbol": str(row.get("contractSymbol") or row.get("symbol") or ""),
        "underlying": SYMBOL,
        "expiration": expiration_date,
        "strike": int(float(row.get("strike", 0))),
        "option_type": option_type,
        "bid": bid,
        "ask": ask,
        "mark": mark,
        "spread": spread,
        "delta": float("nan"),
        "gamma": float("nan"),
        "theta": float("nan"),
        "vega": float("nan"),
        "iv": _finite_float(row.get("impliedVolatility")),
        "provider": "YFINANCE_DELAYED",
        "timestamp": pd.Timestamp.now(tz=get_central_tz()),
        "warning": "Delayed yfinance quote. Mark uses bid/ask midpoint when available, otherwise last traded price.",
    }


def _select_yfinance_option_row(df: pd.DataFrame, strike: int):
    if df is None or df.empty or "strike" not in df:
        return None
    rows = df.copy()
    rows["strike_distance"] = (rows["strike"].astype(float) - float(strike)).abs()
    return rows.sort_values("strike_distance").iloc[0]


@st.cache_data(ttl=120, show_spinner=False)
def fetch_yfinance_option_quotes(expiration_date, call_strike: int, put_strike: int) -> dict:
    try:
        ticker = yf.Ticker(SYMBOL)
        expiration = str(expiration_date)
        chain = ticker.option_chain(expiration)
        call_row = _select_yfinance_option_row(chain.calls, call_strike)
        put_row = _select_yfinance_option_row(chain.puts, put_strike)
        call_quote = _quote_from_yfinance_row(call_row, "CALL", expiration) if call_row is not None else None
        put_quote = _quote_from_yfinance_row(put_row, "PUT", expiration) if put_row is not None else None
        warning = "Delayed yfinance option quotes are active for this session."
        return {"CALL": call_quote, "PUT": put_quote, "warning": warning}
    except Exception as e:
        return {"CALL": None, "PUT": None, "warning": f"Delayed yfinance option quotes could not load: {type(e).__name__}"}


def simulate_option_scenarios(quote: OptionQuote, moves=None) -> list[OptionsScenario]:
    moves = moves or [0.5,-0.5]; out=[]
    for mv in moves:
        em=max(0.01, round(quote.mark + (quote.delta*mv),2)); pnl=round((em-quote.mark)*100,2)
        out.append(OptionsScenario(quote.option_type, quote.strike, quote.mark, mv, em, pnl, 'Delta-only estimate; ignores gamma, IV, spread changes, and decay.'))
    return out

def get_default_projection_time(current_dt, hour=9, minute=0) -> pd.Timestamp:
    dt=pd.Timestamp(current_dt); ct=get_central_tz(); dt=dt.tz_localize(ct) if dt.tzinfo is None else dt.tz_convert(ct)
    return pd.Timestamp(dt.date(), tz=ct)+pd.Timedelta(hours=hour, minutes=minute)

def resolve_entry_target_lines(all_lines, latest_signal=None, bias_state=None, option_type=None, entry_line_name=None, target_line_name=None, current_price=None, current_dt=None):
    dt = pd.Timestamp(current_dt) if current_dt is not None else pd.Timestamp.now(tz=get_central_tz())
    entry = get_line_by_name(all_lines, entry_line_name) if entry_line_name else None
    target = get_line_by_name(all_lines, target_line_name) if target_line_name else None
    if entry is None and latest_signal is not None: entry = get_line_by_name(all_lines, latest_signal.line_name)
    if target is None and latest_signal is not None and latest_signal.target_line_name: target = get_line_by_name(all_lines, latest_signal.target_line_name)
    if entry is None and bias_state is not None:
        watch = bias_state.watched_call_lines if option_type=='CALL' else bias_state.watched_put_lines
        if watch: entry = get_line_by_name(all_lines, watch[0])
    if entry and target is None:
        ev=entry.tradable_value_at(dt); cand=[]
        for l in all_lines:
            if l.name==entry.name: continue
            v=l.tradable_value_at(dt)
            if pd.isna(v): continue
            if option_type=='CALL' and v>ev: cand.append((v-ev,l))
            if option_type=='PUT' and v<ev: cand.append((ev-v,l))
        if cand: target=min(cand,key=lambda x:x[0])[1]
    return entry,target

def project_option_entry_to_target(quote, current_underlying_price, entry_line, target_line=None, entry_projection_time=None, target_projection_time=None):
    ept = pd.Timestamp(entry_projection_time) if entry_projection_time is not None else pd.Timestamp.now(tz=get_central_tz())
    etv = entry_line.tradable_value_at(ept); move_e = etv-current_underlying_price; est_entry=max(0.01, round(quote.mark + quote.delta*move_e,2))
    warn=None
    if target_line is None:
        return EntryTargetOptionProjection(quote.option_type,quote.strike,quote.symbol,current_underlying_price,quote.mark,quote.delta,entry_line.name,etv,ept,move_e,est_entry,None,float('nan'),None,float('nan'),float('nan'),float('nan'),float('nan'),'No target line selected.','Delta-only estimate. It ignores gamma, IV changes, theta decay, liquidity, and bid/ask spread. Actual 0DTE prices may change faster than this estimate.')
    tpt = pd.Timestamp(target_projection_time) if target_projection_time is not None else ept
    ttv = target_line.tradable_value_at(tpt); move_t = ttv-etv; est_target=max(0.01, round(est_entry + quote.delta*move_t,2)); prof=round((est_target-est_entry)*100,2); ret=round(((est_target-est_entry)/est_entry)*100,2) if est_entry>0 else float('nan')
    return EntryTargetOptionProjection(quote.option_type,quote.strike,quote.symbol,current_underlying_price,quote.mark,quote.delta,entry_line.name,etv,ept,move_e,est_entry,target_line.name,ttv,tpt,move_t,est_target,prof,ret,warn,'Delta-only estimate. It ignores gamma, IV changes, theta decay, liquidity, and bid/ask spread. Actual 0DTE prices may change faster than this estimate.')

def build_options_cockpit_state(selected_strikes, latest_signal=None, decision_state=None, provider=None, current_dt=None, all_lines=None, entry_line_name=None, target_line_name=None, projection_time=None, option_type_override=None):
    now=pd.Timestamp(current_dt) if current_dt is not None else pd.Timestamp.now(tz=get_central_tz())
    provider_name = getattr(provider, "provider_name", "TASTYTRADE")
    if selected_strikes is None or pd.isna(selected_strikes.underlying_price):
        return OptionsCockpitState(provider_name,float('nan'),None,None,None,None,[],None,'Invalid/missing strikes or underlying.', 'No options cockpit available.')
    if provider is None:
        return OptionsCockpitState(provider_name, selected_strikes.underlying_price, selected_strikes.expiration_date, None, None, None, [], None, 'Tastytrade quotes unavailable. Check credentials or provider connection.', 'No live options provider available.')
    try:
        q = provider.get_selected_quotes(selected_strikes.underlying_price, selected_strikes.expiration_date, selected_strikes.call_strike, selected_strikes.put_strike)
    except Exception as e:
        return OptionsCockpitState(provider_name, selected_strikes.underlying_price, selected_strikes.expiration_date, None, None, None, [], None, f'Tastytrade provider error: {type(e).__name__}', 'Live options provider failed.')
    call_q = q.get('call') or q.get('CALL')
    put_q = q.get('put') or q.get('PUT')
    if isinstance(call_q, dict): call_q = OptionQuote(**call_q)
    if isinstance(put_q, dict): put_q = OptionQuote(**put_q)
    if call_q and getattr(call_q, "provider", None):
        provider_name = call_q.provider
    provider_names = [provider_name, getattr(call_q, "provider", None), getattr(put_q, "provider", None)]
    if any(is_mock_option_provider_name(name) for name in provider_names):
        return OptionsCockpitState("TASTYTRADE", selected_strikes.underlying_price, selected_strikes.expiration_date, None, None, None, [], None, 'Mock option quotes are disabled. Configure live Tastytrade credentials for options data.', 'No live options provider available.')
    if (call_q or put_q) and not any(provider_is_allowed_option_data(name) for name in provider_names):
        return OptionsCockpitState("TASTYTRADE", selected_strikes.underlying_price, selected_strikes.expiration_date, None, None, None, [], None, 'Unsupported option quote provider. Use live Tastytrade or delayed yfinance data.', 'No supported options provider available.')
    missing_market_data = (call_q or put_q) and not (quote_has_live_market_data(call_q) or quote_has_live_market_data(put_q))
    opt_type = option_type_override or (latest_signal.signal_type if latest_signal else None)
    sel = call_q if opt_type=='CALL' else put_q if opt_type=='PUT' else None
    scenarios = simulate_option_scenarios(sel) if quote_has_projection_inputs(sel) else []
    proj=None; warning=q.get("warning")
    if missing_market_data:
        warning = q.get("warning") or 'Tastytrade found the contracts, but Live quote streaming has not returned bid/ask/Greeks yet.'
    if sel and all_lines:
        entry,target = resolve_entry_target_lines(all_lines, latest_signal=latest_signal, option_type=opt_type, entry_line_name=entry_line_name, target_line_name=target_line_name, current_price=selected_strikes.underlying_price, current_dt=now)
        if entry and quote_has_projection_inputs(sel):
            proj = project_option_entry_to_target(sel, selected_strikes.underlying_price, entry, target, entry_projection_time=projection_time or get_default_projection_time(now), target_projection_time=projection_time or get_default_projection_time(now))
        elif entry is None:
            warning = 'Could not resolve entry line; projection unavailable.'
    return OptionsCockpitState(provider_name, selected_strikes.underlying_price, selected_strikes.expiration_date, call_q, put_q, sel, scenarios, proj, warning, f'{provider_name} options cockpit state.')


def option_state_has_market_data(state: OptionsCockpitState | None) -> bool:
    return bool(state and (quote_has_live_market_data(state.call_quote) or quote_has_live_market_data(state.put_quote)))


def build_options_cockpit_state_with_fallback(selected_strikes, latest_signal=None, decision_state=None, provider=None, current_dt=None, all_lines=None, projection_time=None):
    state = build_options_cockpit_state(
        selected_strikes,
        latest_signal=latest_signal,
        decision_state=decision_state,
        provider=provider,
        current_dt=current_dt,
        all_lines=all_lines or [],
        projection_time=projection_time,
    )
    if option_state_has_market_data(state):
        return state
    yfinance_state = build_options_cockpit_state(
        selected_strikes,
        latest_signal=latest_signal,
        decision_state=decision_state,
        provider=YFinanceOptionProvider(),
        current_dt=current_dt,
        all_lines=all_lines or [],
        projection_time=projection_time,
    )
    return yfinance_state if option_state_has_market_data(yfinance_state) else state


def get_tastytrade_option_provider():
    missing = get_missing_tastytrade_secrets()
    if missing:
        return None, {"provider":"TASTYTRADE","connected":False,"quotes_ok":False,"missing_secrets":missing}
    try:
        env=st.secrets.get("TASTYTRADE_ENVIRONMENT","production")
        provider = TastytradeProvider(st.secrets["TASTYTRADE_CLIENT_ID"], st.secrets["TASTYTRADE_CLIENT_SECRET"], st.secrets["TASTYTRADE_REFRESH_TOKEN"], env)
        return provider, {"provider":"TASTYTRADE","connected":True,"quotes_ok":None,"missing_secrets":[]}
    except Exception as e:
        return None, {"provider":"TASTYTRADE","connected":False,"quotes_ok":False,"missing_secrets":[],"last_error":type(e).__name__}


def option_provider_label(state: OptionsCockpitState | None, provider_status: dict | None = None) -> str:
    provider_status = provider_status or {}
    if state and is_mock_option_provider_name(state.provider):
        return "TASTYTRADE unavailable"
    if state and provider_is_yfinance_delayed(state.provider):
        return "YFINANCE delayed"
    if state and (state.call_quote or state.put_quote):
        return state.provider
    if provider_status.get("missing_secrets"):
        return "TASTYTRADE setup needed"
    if provider_status.get("last_error") or (state and state.warning):
        return "TASTYTRADE unavailable"
    return provider_status.get("provider") or "TASTYTRADE"


def friendly_provider_error(error: str | None) -> str:
    text = str(error or "").strip()
    if not text:
        return ""
    lowered = text.lower()
    if "404" in lowered or "chain failed" in lowered:
        return "Tastytrade could not return that option chain. Delayed yfinance quotes will be used when available."
    if "timeout" in lowered:
        return "Tastytrade took too long to respond. Refresh once or continue with delayed quote context."
    if "auth" in lowered or "unauthorized" in lowered or "forbidden" in lowered:
        return "Tastytrade sign-in needs attention. Check the app secrets for the live quote connection."
    return "Tastytrade live quotes are not active for this run. Delayed quote context remains available when yfinance has the chain."


def option_quote_card_html(quote: OptionQuote | None, fallback_strike: int | None = None, warning: str | None = None) -> str:
    strike = quote.strike if quote else fallback_strike
    bid = fmt_price(quote.bid if quote else None)
    ask = fmt_price(quote.ask if quote else None)
    spread = fmt_price(quote.spread if quote else None)
    delta = fmt_float(quote.delta if quote else None)
    if quote_has_live_market_data(quote):
        status = "Delayed yfinance price; mark is midpoint when bid/ask exist, otherwise last trade." if provider_is_yfinance_delayed(quote.provider) else "Live bid/ask and Greeks from Tastytrade."
    elif quote:
        status = "Contract found, but live bid/ask/delta are not available yet."
    else:
        status = warning or "Waiting for Tastytrade to return a live option quote."
    return (
        "<div class='option-quote-main'>"
        f"<div><div class='option-quote-label'>Strike</div><div class='option-quote-strike'>{strike if strike else '-'}</div></div>"
        f"<div><div class='option-quote-label'>Mark</div><div class='option-quote-mark'>{fmt_price(quote.mark if quote else None)}</div></div>"
        "</div>"
        "<div class='option-quote-grid'>"
        f"<div class='option-quote-cell'><div class='option-quote-label'>Bid</div><div class='option-quote-value'>{bid}</div></div>"
        f"<div class='option-quote-cell'><div class='option-quote-label'>Ask</div><div class='option-quote-value'>{ask}</div></div>"
        f"<div class='option-quote-cell'><div class='option-quote-label'>Spread</div><div class='option-quote-value'>{spread}</div></div>"
        f"<div class='option-quote-cell'><div class='option-quote-label'>Delta</div><div class='option-quote-value'>{delta}</div></div>"
        "</div>"
        f"<div class='small-muted' style='margin-top:10px'>{status}</div>"
    )

@dataclass(frozen=True)
class JournalEntry:
    journal_id: str; created_at: pd.Timestamp; updated_at: pd.Timestamp | None; trade_date: object; source: str
    signal_id: str | None; signal_type: str | None; signal_status: str | None; line_name: str | None; line_zone_type: str | None; bias: str | None
    quality_grade: str | None; quality_score: float; final_decision: str | None; action_label: str | None
    rejection_time: pd.Timestamp | None; entry_time: pd.Timestamp | None; entry_price: float; stop_price: float; target_line_name: str | None; target_price: float; rr_ratio: float
    outcome: str | None; outcome_time: pd.Timestamp | None; max_favorable_move: float; max_adverse_move: float; bars_to_outcome: int | None
    selected_option_type: str | None; selected_option_strike: int | None; estimated_entry_mark: float; estimated_target_mark: float; estimated_profit_per_contract: float
    provider_used: str | None; notes: str | None; tags: list[str]

@dataclass(frozen=True)
class JournalAnalytics:
    total_entries: int; total_confirmed: int; target_first_count: int; stop_first_count: int; no_hit_count: int; ambiguous_count: int; pending_count: int; unknown_count: int
    win_rate: float; average_rr: float; average_max_favorable_move: float; average_max_adverse_move: float; average_estimated_profit_per_contract: float; expectancy_per_contract: float
    by_line: dict; by_signal_type: dict; by_quality_grade: dict; by_bias: dict; by_hour: dict; by_source: dict; warnings: list[str]

@dataclass(frozen=True)
class StructureLearningProfile:
    sample_size: int
    matching_sample_size: int
    expected_direction: str
    confidence_label: str
    target_first_rate: float
    stop_first_rate: float
    no_hit_rate: float
    average_rr: float
    average_max_favorable_move: float
    average_max_adverse_move: float
    best_context: str | None
    caveat: str

@dataclass(frozen=True)
class AutoJournalStatus:
    enabled: bool; saved_count: int; updated_count: int; skipped_duplicate_count: int; latest_saved_signal_id: str | None; warnings: list[str]; explanation: str

def ensure_data_dir(path='data'):
    Path(path).mkdir(parents=True, exist_ok=True)

def journal_entry_to_dict(entry: JournalEntry) -> dict:
    d=asdict(entry)
    for k,v in list(d.items()):
        if isinstance(v,pd.Timestamp): d[k]=v.isoformat()
    return d

def journal_entry_from_dict(d: dict) -> JournalEntry:
    dd=d.copy()
    for k in ['created_at','updated_at','rejection_time','entry_time','outcome_time']:
        if dd.get(k): dd[k]=pd.Timestamp(dd[k])
    return JournalEntry(**dd)

def load_signal_journal(path='data/signal_journal.json'):
    ensure_data_dir(Path(path).parent)
    p=Path(path)
    if not p.exists(): return []
    try:
        arr=json.loads(p.read_text())
        return [journal_entry_from_dict(x) for x in arr]
    except Exception:
        backup=Path(path).with_name(f"signal_journal.corrupt.{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.json")
        p.replace(backup)
        return []

def save_signal_journal(entries, path='data/signal_journal.json'):
    ensure_data_dir(Path(path).parent)
    temp=Path(str(path)+'.tmp')
    temp.write_text(json.dumps([journal_entry_to_dict(e) for e in entries], indent=2, default=str))
    temp.replace(path)

def make_journal_id(entry: JournalEntry) -> str:
    key=f"{entry.trade_date}|{entry.signal_id}|{entry.source}|{entry.line_name}|{entry.entry_time}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]

def get_journal_signal_key(entry: JournalEntry) -> str:
    if entry.signal_id: return f"sig:{entry.signal_id}"
    return f"{entry.trade_date}|{entry.signal_type}|{entry.line_name}|{entry.rejection_time}|{entry.entry_time}"

def entry_is_more_complete(new_entry, old_entry):
    checks=[(new_entry.outcome, old_entry.outcome),(new_entry.estimated_entry_mark, old_entry.estimated_entry_mark),(new_entry.quality_grade, old_entry.quality_grade),(new_entry.notes, old_entry.notes),(new_entry.tags, old_entry.tags),(new_entry.final_decision, old_entry.final_decision)]
    for n,o in checks:
        if (o in [None,[],float('nan')] or (isinstance(o,float) and pd.isna(o))) and (n not in [None,[],float('nan')] and not (isinstance(n,float) and pd.isna(n))):
            return True
    return False

def upsert_journal_entry(entries, new_entry):
    nk=get_journal_signal_key(new_entry)
    for i,e in enumerate(entries):
        if get_journal_signal_key(e)==nk:
            if entry_is_more_complete(new_entry,e):
                entries[i]=new_entry; return entries,'updated'
            return entries,'skipped'
    entries.append(new_entry); return entries,'inserted'

def build_journal_entry_from_live_state(latest_signal, decision_state, bias_state, options_cockpit_state, outcome=None, source='LIVE_MANUAL', notes=None, tags=None):
    if latest_signal is None: return None
    q=decision_state.signal_quality if decision_state and decision_state.signal_quality else None
    proj=options_cockpit_state.entry_target_projection if options_cockpit_state and options_cockpit_state.entry_target_projection else None
    e=JournalEntry('',pd.Timestamp.now(tz=get_central_tz()),None,latest_signal.rejection_time.date(),source,latest_signal.signal_id,latest_signal.signal_type,latest_signal.status,latest_signal.line_name,None,bias_state.bias if bias_state else None,q.grade if q else None,q.score if q else float('nan'),decision_state.final_decision if decision_state else None,q.action_label if q else None,latest_signal.rejection_time,latest_signal.entry_time,latest_signal.entry_price,latest_signal.stop_price,latest_signal.target_line_name,latest_signal.target_price,latest_signal.rr_ratio,outcome.outcome if outcome else None,outcome.outcome_time if outcome else None,outcome.max_favorable_move if outcome else float('nan'),outcome.max_adverse_move if outcome else float('nan'),outcome.bars_to_outcome if outcome else None,proj.option_type if proj else None,proj.strike if proj else None,proj.estimated_entry_mark if proj else float('nan'),proj.estimated_target_mark if proj else float('nan'),proj.estimated_profit_per_contract if proj else float('nan'),options_cockpit_state.provider if options_cockpit_state else None,notes,tags or [])
    return e.__class__(make_journal_id(e), *list(asdict(e).values())[1:])

def build_journal_entries_from_replay_state(replay_state):
    out=[]
    for sg in replay_state.signals:
        o = replay_state.outcomes.get(sg.signal_id) if replay_state.outcomes else None
        q = replay_state.signal_qualities.get(sg.signal_id) if replay_state.signal_qualities else None
        e=JournalEntry('',pd.Timestamp.now(tz=get_central_tz()),None,replay_state.replay_date,'REPLAY',sg.signal_id,sg.signal_type,sg.status,sg.line_name,None,replay_state.bias_state.bias if replay_state.bias_state else None,q.grade if q else None,q.score if q else float('nan'),None,q.action_label if q else None,sg.rejection_time,sg.entry_time,sg.entry_price,sg.stop_price,sg.target_line_name,sg.target_price,sg.rr_ratio,o.outcome if o else None,o.outcome_time if o else None,o.max_favorable_move if o else float('nan'),o.max_adverse_move if o else float('nan'),o.bars_to_outcome if o else None,None,None,float('nan'),float('nan'),float('nan'),None,None,[])
        out.append(e.__class__(make_journal_id(e), *list(asdict(e).values())[1:]))
    return out

def compute_journal_analytics(entries):
    n=len(entries); conf=[e for e in entries if e.signal_status=='CONFIRMED']; wins=[e for e in entries if e.outcome=='TARGET_FIRST']; losses=[e for e in entries if e.outcome=='STOP_FIRST']
    wr=(len(wins)/(len(wins)+len(losses))) if (len(wins)+len(losses))>0 else float('nan')
    def grp(key):
        d={}
        for e in entries:
            k=getattr(e,key) if key!='hour' else (e.entry_time.hour if e.entry_time else None)
            d.setdefault(k,[]).append(e)
        out={}
        for k,v in d.items():
            w=len([x for x in v if x.outcome=='TARGET_FIRST']); l=len([x for x in v if x.outcome=='STOP_FIRST'])
            out[str(k)]={"count":len(v),"wins":w,"losses":l,"win_rate":(w/(w+l) if (w+l)>0 else float('nan')),"average_rr":float(pd.Series([x.rr_ratio for x in v]).mean()),"average_estimated_profit_per_contract":float(pd.Series([x.estimated_profit_per_contract for x in v]).mean()),"small_sample":len(v)<5}
        return out
    return JournalAnalytics(n,len(conf),len([e for e in entries if e.outcome=='TARGET_FIRST']),len([e for e in entries if e.outcome=='STOP_FIRST']),len([e for e in entries if e.outcome=='NO_HIT']),len([e for e in entries if e.outcome=='AMBIGUOUS_SAME_CANDLE']),len([e for e in entries if e.outcome in ['PENDING','PENDING_OUTCOME']]),len([e for e in entries if e.outcome in [None,'UNKNOWN']]),wr,float(pd.Series([e.rr_ratio for e in entries]).mean()),float(pd.Series([e.max_favorable_move for e in entries]).mean()),float(pd.Series([e.max_adverse_move for e in entries]).mean()),float(pd.Series([e.estimated_profit_per_contract for e in entries]).mean()),float(pd.Series([e.estimated_profit_per_contract for e in wins+losses]).mean()) if wins or losses else float('nan'),grp('line_name'),grp('signal_type'),grp('quality_grade'),grp('bias'),grp('hour'),grp('source'),[])

def build_replay_learning_entries(df: pd.DataFrame, max_days: int = REPLAY_LEARNING_DAYS, slope_per_hour: float = DEFAULT_SLOPE_PER_HOUR) -> list[JournalEntry]:
    if df is None or df.empty:
        return []
    dates = get_available_replay_dates(df)[-max_days:]
    entries: list[JournalEntry] = []
    for replay_date in dates:
        rs = build_replay_state(df, replay_date, slope_per_hour=slope_per_hour, include_future_outcomes=True)
        if rs.warnings and "NO_PRIOR_TRADING_DAY" in rs.warnings:
            continue
        entries.extend(build_journal_entries_from_replay_state(rs))
    return entries


def dedupe_learning_entries(entries: list[JournalEntry]) -> list[JournalEntry]:
    out: list[JournalEntry] = []
    seen: set[str] = set()
    for entry in entries:
        key = get_journal_signal_key(entry)
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    return out


def completed_learning_entries(entries: list[JournalEntry]) -> list[JournalEntry]:
    complete = {"TARGET_FIRST", "STOP_FIRST", "NO_HIT", "AMBIGUOUS_SAME_CANDLE"}
    return [entry for entry in entries if entry.outcome in complete]


def infer_current_learning_filter(active_signal=None, bias_state=None, closest_line=None) -> tuple[str | None, str | None, str]:
    signal_type = get_watch_option_type(active_signal, bias_state)
    line_name = active_signal.line_name if active_signal else closest_line.name if closest_line else None
    if active_signal:
        direction = f"{active_signal.signal_type} setup at {display_line_name(active_signal.line_name)}"
    elif signal_type:
        direction = f"{signal_type} watch from current structure"
    else:
        direction = "No directional edge yet"
    return signal_type, line_name, direction


def confidence_from_sample_size(sample_size: int) -> str:
    if sample_size >= 30:
        return "Higher confidence"
    if sample_size >= 12:
        return "Moderate confidence"
    if sample_size >= 5:
        return "Early read"
    if sample_size > 0:
        return "Tiny sample"
    return "No sample"


def best_learning_context(entries: list[JournalEntry]) -> str | None:
    analytics = compute_journal_analytics(entries)
    candidates = []
    for label, groups in [("trigger", analytics.by_line), ("direction", analytics.by_signal_type), ("quality", analytics.by_quality_grade)]:
        for key, value in groups.items():
            if value.get("count", 0) < 3 or pd.isna(value.get("win_rate", float("nan"))):
                continue
            candidates.append((value["win_rate"], value["count"], label, key))
    if not candidates:
        return None
    win_rate, count, label, key = sorted(candidates, reverse=True)[0]
    display_key = display_line_name(key) if label == "trigger" else display_state_label(key)
    return f"Best {label}: {display_key} ({fmt_pct(win_rate * 100, 0)} target-first across {count} samples)"


def build_structure_learning_profile(entries: list[JournalEntry], active_signal=None, bias_state=None, closest_line=None, flow_tags: list[str] | None = None) -> StructureLearningProfile:
    all_complete = completed_learning_entries(dedupe_learning_entries(entries))
    signal_type, line_name, direction = infer_current_learning_filter(active_signal, bias_state, closest_line)
    matching = all_complete
    if signal_type:
        matching = [entry for entry in matching if entry.signal_type == signal_type]
    if line_name:
        same_line = [entry for entry in matching if entry.line_name == line_name]
        if same_line:
            matching = same_line
    if flow_tags:
        flow_tag_set = set(flow_tags)
        same_flow = [entry for entry in matching if flow_tag_set.intersection(set(entry.tags or []))]
        if len(same_flow) >= 5:
            matching = same_flow
            direction = f"{direction} with current flow pressure"
    sample = matching or all_complete
    n = len(sample)
    if n == 0:
        return StructureLearningProfile(0, 0, direction, "No sample", float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), float("nan"), None, "The app needs completed replay or journal outcomes before it can form a statistical read.")
    target = len([entry for entry in sample if entry.outcome == "TARGET_FIRST"])
    stop = len([entry for entry in sample if entry.outcome == "STOP_FIRST"])
    no_hit = len([entry for entry in sample if entry.outcome == "NO_HIT"])
    caveat = "This is a historical tendency from completed outcomes, not a guarantee of the next candle or day."
    return StructureLearningProfile(
        len(all_complete),
        len(matching),
        direction,
        confidence_from_sample_size(n),
        target / n,
        stop / n,
        no_hit / n,
        float(pd.Series([entry.rr_ratio for entry in sample]).mean()),
        float(pd.Series([entry.max_favorable_move for entry in sample]).mean()),
        float(pd.Series([entry.max_adverse_move for entry in sample]).mean()),
        best_learning_context(all_complete),
        caveat,
    )


def generate_journal_insights(a):
    out=[]
    if a.total_entries==0: return ["No journal history yet."]
    for name,grp in [('line',a.by_line),('quality',a.by_quality_grade),('hour',a.by_hour)]:
        if grp:
            best=max(grp.items(), key=lambda kv: kv[1]['win_rate'] if kv[1]['win_rate']==kv[1]['win_rate'] else -1)
            note='small sample' if best[1]['small_sample'] else 'sample adequate'
            out.append(f"Best {name} so far: {best[0]} (win_rate={best[1]['win_rate']:.2f}, {note}).")
    return out

def auto_journal_live_signals(signals, decision_state, bias_state, options_cockpit_state, existing_entries, path='data/signal_journal.json', enabled=False, flow_tags=None):
    if not enabled: return existing_entries, AutoJournalStatus(False,0,0,0,None,[],"Auto-journal disabled.")
    saved=updated=skipped=0; latest=None
    entries=list(existing_entries)
    for sg in signals or []:
        entry=build_journal_entry_from_live_state(sg,decision_state,bias_state,options_cockpit_state,source='LIVE_AUTO',tags=flow_tags or [])
        entries,act=upsert_journal_entry(entries,entry)
        if act=='inserted': saved+=1; latest=sg.signal_id
        elif act=='updated': updated+=1; latest=sg.signal_id
        else: skipped+=1
    save_signal_journal(entries,path)
    return entries, AutoJournalStatus(True,saved,updated,skipped,latest,[],"Auto-journal processed live signals.")


def main() -> None:
    st.set_page_config(page_title="SPY Prophet", page_icon="SPY", layout="wide", initial_sidebar_state="expanded")
    inject_global_css()
    real_now_ct = datetime.now(tz=get_central_tz())

    st.sidebar.header("SPY Prophet Controls")
    st.sidebar.button("Refresh data")
    admin_mode = is_admin_diagnostics_enabled()
    show_debug = st.sidebar.toggle("Advanced diagnostics", value=False) if admin_mode else False
    auto_journal_on = st.sidebar.toggle("Auto-journal live signals", value=False)
    slope = get_structure_calibration()
    provider = "TASTYTRADE"
    df = fetch_spy_hourly(period="60d")
    available_session_days = get_available_trading_days(df)
    preview_max_day = next_session_after(real_now_ct.date())
    date_min = available_session_days[0] if available_session_days else (real_now_ct - pd.Timedelta(days=60)).date()
    date_max = max([preview_max_day, real_now_ct.date()] + available_session_days) if available_session_days else preview_max_day
    selected_session_day = st.sidebar.date_input(
        "Session date",
        value=default_session_date(df, real_now_ct),
        min_value=date_min,
        max_value=date_max,
        help="Choose the trading session to preview. Future sessions use the most recent completed session as structure until new candles arrive.",
    )
    selected_session_day = pd.Timestamp(selected_session_day).date()
    now_ct = resolve_session_clock(df, selected_session_day, real_now_ct).to_pydatetime()
    structure_projection_time = get_structure_projection_time(now_ct)
    session_has_candles = selected_session_day in available_session_days
    is_live_session = selected_session_day == real_now_ct.date()
    st.sidebar.caption("Provider: TASTYTRADE")
    st.sidebar.caption("Structure calibration: Protected")
    st.sidebar.caption(f"Actual CT: {real_now_ct.strftime('%H:%M:%S %Z')}")
    st.sidebar.caption(f"Session clock: {pd.Timestamp(now_ct).strftime('%Y-%m-%d %H:%M %Z')}")
    st.sidebar.caption(f"Structure projection: {fmt_clock_time(structure_projection_time)}")
    if not session_has_candles:
        st.sidebar.caption("Preview mode: waiting for session candles.")
    elif not is_live_session:
        st.sidebar.caption("Historical session preview.")

    latest_price = None
    prior_day = None
    signal_day = None
    rth_df = pd.DataFrame(); signal_rth_df = pd.DataFrame(); ext_df = pd.DataFrame(); pivots={}; secondary_pivots=[]; primary_lines=[]; secondary_lines=[]; signals=[]
    bias = None; strikes = None; closest=None; proj_df=pd.DataFrame(); decision_state=None; active_signal=None; market_context=None
    option_provider, provider_status = get_tastytrade_option_provider()
    option_state = None
    if df.empty:
        st.warning("No SPY data loaded. Click refresh or check yfinance availability.")
    if not df.empty:
        latest_price = latest_price_for_session(df, selected_session_day, now_ct)
        signal_day = get_live_signal_day(df, now_ct)
        prior_day = get_prior_trading_day(df, pd.Timestamp(signal_day).to_pydatetime()) if signal_day is not None else None
        if prior_day is not None:
            rth_df = filter_rth_session(df, prior_day)
            signal_rth_df = filter_rth_session(df, signal_day) if signal_day is not None else pd.DataFrame()
            ext_df = filter_extended_session(df, signal_day) if signal_day is not None else pd.DataFrame()
            if not rth_df.empty:
                pivots = find_primary_pivots(rth_df)
                secondary_pivots = find_secondary_pivots(rth_df)
                primary_lines = build_primary_lines(pivots["high"], pivots["low"], slope)
                secondary_lines = build_secondary_lines(secondary_pivots, slope)
                proj_df = project_lines(primary_lines + secondary_lines, structure_projection_time, latest_price)
                bias = determine_preopen_bias(primary_lines, latest_price if latest_price is not None else float("nan"), now_ct)
                signals = detect_rejection_signals(signal_rth_df, primary_lines, secondary_lines)
                active_signal = get_latest_active_signal(signals, signal_rth_df)
                strikes = select_watch_contracts(latest_price if latest_price is not None else float("nan"), now_ct, active_signal, primary_lines+secondary_lines)
                closest = get_closest_primary_line(primary_lines, structure_projection_time, latest_price) if latest_price is not None else None
                latest_signal_candle = signal_rth_df.iloc[-1] if not signal_rth_df.empty else None
                decision_state = build_decision_state(active_signal, primary_lines+secondary_lines, latest_price if latest_price is not None else float("nan"), pd.Timestamp(now_ct), latest_signal_candle, signals_today=signals)
                option_state = build_options_cockpit_state_with_fallback(strikes, latest_signal=active_signal, decision_state=decision_state, provider=option_provider, current_dt=now_ct, all_lines=primary_lines+secondary_lines if primary_lines else [], projection_time=get_default_projection_time(now_ct))
                market_context = build_market_context(df, latest_price, closest, structure_projection_time)

    journal_path='data/signal_journal.json'
    journal_entries = load_signal_journal(journal_path)
    replay_learning_entries = build_replay_learning_entries(df, max_days=REPLAY_LEARNING_DAYS, slope_per_hour=slope)
    learning_profile = build_structure_learning_profile(journal_entries + replay_learning_entries, active_signal, bias, closest)
    news_items = fetch_market_news(limit=MARKET_MOVING_NEWS_LIMIT)
    economic_events = get_upcoming_economic_events(now_ct, days=0)
    morning_bundle = build_morning_briefing_bundle(primary_lines, structure_projection_time, economic_events, news_items, learning_profile, latest_price, strikes, option_state)
    flow_tags_for_learning = premium_flow_tags(morning_bundle.options_intelligence)
    if flow_tags_for_learning:
        flow_learning_profile = build_structure_learning_profile(journal_entries + replay_learning_entries, active_signal, bias, closest, flow_tags_for_learning)
        if flow_learning_profile.matching_sample_size != learning_profile.matching_sample_size or flow_learning_profile.expected_direction != learning_profile.expected_direction:
            learning_profile = flow_learning_profile
            morning_bundle = build_morning_briefing_bundle(primary_lines, structure_projection_time, economic_events, news_items, learning_profile, latest_price, strikes, option_state)
    if strikes and morning_bundle.options_intelligence.status.status != "skipped":
        flow_strikes = select_flow_aware_watch_contracts(
            latest_price if latest_price is not None else float("nan"),
            now_ct,
            active_signal,
            primary_lines + secondary_lines if primary_lines else [],
            morning_bundle.options_intelligence,
        )
        if flow_strikes and (flow_strikes.call_strike != strikes.call_strike or flow_strikes.put_strike != strikes.put_strike):
            strikes = flow_strikes
            option_state = build_options_cockpit_state_with_fallback(
                strikes,
                latest_signal=active_signal,
                decision_state=decision_state,
                provider=option_provider,
                current_dt=now_ct,
                all_lines=primary_lines + secondary_lines if primary_lines else [],
                projection_time=get_default_projection_time(now_ct),
            )
            morning_bundle = build_morning_briefing_bundle(primary_lines, structure_projection_time, economic_events, news_items, learning_profile, latest_price, strikes, option_state)

    if show_debug:
        st.sidebar.caption(f"Data loaded: {not df.empty}")
        st.sidebar.caption(f"Latest candle: {df.index[-1] if not df.empty else 'N/A'}")
        st.sidebar.caption(f"Structure day: {prior_day}")
        st.sidebar.caption(f"Signal day: {signal_day}")

    tab_names = ["Live Terminal", "Prophet Foresight", "Market Context", "Prophet Chart", "Replay Lab", "Options", "Journal"]
    if show_debug:
        tab_names += ["Structure Details", "Signal Details", "Diagnostics"]
    tabs = dict(zip(tab_names, st.tabs(tab_names)))

    with tabs["Live Terminal"]:
        if not session_has_candles:
            render_data_notice(f"{selected_session_day} is in preview mode. SPY Prophet is projecting the next session from the latest completed market data; entries will appear after that session's candles print.")
        elif not is_live_session:
            render_data_notice(f"Viewing historical session {selected_session_day}. Use Replay Lab for strict candle-by-candle review.")
        render_terminal_hero(
            latest_price,
            bias,
            decision_state,
            closest,
            active_signal,
            strikes,
            option_provider_label(option_state, provider_status),
            now_ct,
            df,
            prior_day,
            market_context,
            primary_lines,
            structure_projection_time,
        )
        render_live_command_center(
            bias,
            decision_state,
            active_signal,
            strikes,
            option_state,
            latest_price,
            morning_bundle.options_intelligence,
        )
        render_status_strip([
            ("Learning", learning_profile.confidence_label),
            ("Matching outcomes", learning_profile.matching_sample_size),
            ("Target first", fmt_pct(learning_profile.target_first_rate * 100, 0)),
            ("Stop first", fmt_pct(learning_profile.stop_first_rate * 100, 0)),
        ])
        render_structure_tiles(primary_lines, latest_price, structure_projection_time, closest, prior_day)
        if option_state:
            if option_state.entry_target_projection:
                render_status_strip([
                    ("Entry premium", fmt_price(option_state.entry_target_projection.estimated_entry_mark)),
                    ("Target premium", fmt_price(option_state.entry_target_projection.estimated_target_mark)),
                    ("Est. P/L", fmt_price(option_state.entry_target_projection.estimated_profit_per_contract)),
                ])

    with tabs["Market Context"]:
        render_market_context_tab(learning_profile, news_items, economic_events, market_context, latest_price, closest, structure_projection_time)

    with tabs["Prophet Foresight"]:
        render_morning_briefing_tab(morning_bundle)

    with tabs["Prophet Chart"]:
        render_section_title("Prophet Chart", "Decision map and technical candle views")
        chart_df = signal_rth_df if not signal_rth_df.empty else (rth_df if not rth_df.empty else df)
        render_chart_brief(latest_price, closest, active_signal, decision_state, pd.Timestamp(now_ct))
        cc1,cc2=st.columns([1.1,1])
        chart_mode = cc1.selectbox("View", ["Decision Map", "Technical Candles"], index=0, key="chart_view_mode")
        secondary_mode = cc2.selectbox("Targets", ["nearest 6","nearest 12","all"], index=0, key="chart_target_density")
        show_secondary = True
        show_signals = True
        show_overlays = True
        try:
            hp = pivots["high"] if 'pivots' in locals() else None
            lp = pivots["low"] if 'pivots' in locals() else None
            if chart_mode == "Decision Map":
                render_structure_map_svg(chart_df, primary_lines, secondary_lines, signals, decision_state, latest_price if latest_price is not None else float('nan'), pd.Timestamp(now_ct), title="SPY Structure Map", subtitle=f"Prior session {prior_day}; signal day {signal_day}", secondary_mode=secondary_mode)
            else:
                fig = build_prophet_chart(chart_df, primary_lines, secondary_lines, hp, lp, secondary_pivots, signals, decision_state, latest_price if latest_price is not None else float('nan'), pd.Timestamp(now_ct), show_secondary=show_secondary, show_signals=show_signals, show_trade_overlays=show_overlays, show_pivots=True, secondary_mode=secondary_mode)
                render_plotly_html(fig)
                st.caption("Advanced view: candlesticks, all selected structure rails, signal markers, and trade overlays.")
        except Exception as e:
            render_warning_panel(f"Chart build failed: {e}")

    with tabs["Replay Lab"]:
        render_section_title("Replay Lab", "Replay a session against prior-day structure")
        dates = get_available_replay_dates(df)
        if not dates:
            render_data_notice("No replay dates available.")
        else:
            rca,rcb,rcc=st.columns([1,1,1])
            rdate = rca.selectbox("Replay date", dates, index=max(0,len(dates)-1), key="replay_date")
            mode = rcb.selectbox("Mode", ["Full Day Review","Step Replay"], key="replay_mode")
            replay_view = rcc.selectbox("View", ["Decision Map", "Technical Candles"], index=0, key="replay_view_mode")
            day_df = filter_replay_day(df, rdate)
            rtime = None
            if mode=="Step Replay" and not day_df.empty:
                rtime = st.selectbox("Replay time", list(day_df.index), index=len(day_df)-1, key="replay_time")
                st.caption("Step Replay hides future candles and signals by default to avoid look-ahead bias.")
            include_out = st.toggle("Show future outcome overlays", value=(mode=="Full Day Review"), key="replay_include_outcomes")
            show_sec_replay = st.toggle("Show secondary target lines", value=True, key="replay_show_secondary")
            rs = build_replay_state(df, rdate, replay_time=rtime, slope_per_hour=slope, include_future_outcomes=include_out)
            replay_candles = day_df if mode=="Full Day Review" or rtime is None else day_df[day_df.index<=rtime]
            replay_active = render_replay_story(rs, replay_candles, mode)
            replay_dt = replay_candles.index[-1] if not replay_candles.empty else pd.Timestamp(now_ct)
            replay_price = float(replay_candles['Close'].iloc[-1]) if not replay_candles.empty else float('nan')
            replay_decision = build_decision_state(replay_active, rs.primary_lines+rs.secondary_lines, replay_price, replay_dt, replay_candles.iloc[-1] if not replay_candles.empty else None, signals_today=rs.signals)
            if include_out:
                render_data_notice("Outcome review is visible for this replay.")
            else:
                render_data_notice("Future outcomes are hidden for this replay point.")
            if replay_view == "Decision Map":
                render_structure_map_svg(replay_candles, rs.primary_lines, rs.secondary_lines if show_sec_replay else [], rs.signals, replay_decision, replay_price, replay_dt, title=f"Replay Map: {rdate}", subtitle=f"Structure from {rs.prior_trading_day}; mode {_humanize(mode)}")
            else:
                rfig = build_prophet_chart(replay_candles, rs.primary_lines, rs.secondary_lines if show_sec_replay else [], rs.high_pivot, rs.low_pivot, [], rs.signals, replay_decision, replay_price, replay_dt, show_secondary=show_sec_replay)
                render_plotly_html(rfig)
            table=[]
            for sg in rs.signals:
                q=rs.signal_qualities.get(sg.signal_id); o=rs.outcomes.get(sg.signal_id)
                table.append({"type":sg.signal_type,"status":_humanize(sg.status),"line":display_line_name(sg.line_name),"rejection_time":sg.rejection_time,"entry":fmt_price(sg.entry_price),"stop":fmt_price(sg.stop_price),"target":display_line_name(sg.target_line_name),"target_price":fmt_price(sg.target_price),"grade":_humanize(q.grade) if q else None,"score":fmt_float(q.score) if q else None,"outcome":_humanize(o.outcome) if o else None,"bars":o.bars_to_outcome if o else None})
            if table:
                st.dataframe(pd.DataFrame(table), use_container_width=True)
            if table:
                st.caption((f"As of {fmt_time(rtime)}," if mode=="Step Replay" and rtime is not None else "For the full replay day,") + f" prior-day structure from {rs.prior_trading_day} produced {len(table)} signals.")

    with tabs["Options"]:
        render_section_title("Options Cockpit", "0DTE quote and projection console")
        if strikes:
            state = option_state or build_options_cockpit_state_with_fallback(strikes, latest_signal=active_signal, decision_state=decision_state, provider=option_provider, current_dt=now_ct, all_lines=primary_lines+secondary_lines if primary_lines else [], projection_time=get_default_projection_time(now_ct))
            render_status_strip([
                ("Provider", display_state_label(option_provider_label(state, provider_status))),
                ("Connection", "Live" if provider_is_live_tastytrade(state.provider) and (state.call_quote or state.put_quote) else "Delayed" if provider_is_yfinance_delayed(state.provider) and (state.call_quote or state.put_quote) else "Unavailable"),
                ("Mode", "Tastytrade live" if provider_is_live_tastytrade(state.provider) else "Delayed yfinance quotes" if provider_is_yfinance_delayed(state.provider) else "Tastytrade"),
            ])
            if provider_status.get("missing_secrets"): render_data_notice("Live Tastytrade is not active in this session. Delayed quotes can still support mark-only review.")
            if provider_status.get("last_error"): render_data_notice(friendly_provider_error(provider_status.get('last_error')), tone="warn")
            if state.warning:
                if provider_is_yfinance_delayed(state.provider):
                    render_data_notice("Delayed yfinance quotes are active. Bid, ask, and mark can display; Greeks require live Tastytrade.")
                else:
                    render_data_notice(friendly_provider_error(state.warning), tone="warn")
            c1,c2=st.columns(2)
            with c1:
                cq=state.call_quote
                render_glass_card("CALL Quote", option_quote_card_html(cq, strikes.call_strike, state.warning))
            with c2:
                pq=state.put_quote
                render_glass_card("PUT Quote", option_quote_card_html(pq, strikes.put_strike, state.warning))
            if state.selected_trade_quote:
                render_status_strip([
                    ("Active contract", f"{state.selected_trade_quote.option_type} {state.selected_trade_quote.strike}"),
                    ("Mark", fmt_price(state.selected_trade_quote.mark)),
                ])
            else:
                render_data_notice("No active options setup. Waiting for confirmed or pending SPY rejection signal.")
            if state.entry_target_projection:
                p = state.entry_target_projection
                render_status_strip([
                    ("Entry premium", fmt_price(p.estimated_entry_mark)),
                    ("Target premium", fmt_price(p.estimated_target_mark)),
                    ("Est. P/L", fmt_price(p.estimated_profit_per_contract)),
                    ("Return", f"{p.estimated_return_pct}%"),
                ])
                if p.option_type=='CALL' and p.entry_line_value < state.underlying_price: st.caption("CALL premium expected to depreciate into entry.")
                if p.option_type=='PUT' and p.entry_line_value > state.underlying_price: st.caption("PUT premium expected to depreciate into entry.")
            if state.scenarios:
                st.dataframe(pd.DataFrame([asdict(x) for x in state.scenarios]))

    with tabs["Journal"]:
        render_section_title("Journal Analytics", "Self-learning signal memory")
        journal_path='data/signal_journal.json'
        entries = load_signal_journal(journal_path)
        auto_status = AutoJournalStatus(False,0,0,0,None,[],"Auto-journal disabled.")
        opt_state = option_state if strikes else None
        current_flow_tags = premium_flow_tags(morning_bundle.options_intelligence)
        entries, auto_status = auto_journal_live_signals(signals, decision_state, bias, opt_state, entries, journal_path, enabled=auto_journal_on and is_live_session, flow_tags=current_flow_tags)
        render_status_strip([
            ("Auto journal", "On" if auto_status.enabled else "Off"),
            ("Saved", auto_status.saved_count),
            ("Updated", auto_status.updated_count),
            ("Skipped", auto_status.skipped_duplicate_count),
        ])
        notes = st.text_area("Notes for latest live signal", "")
        tags_text = st.text_input("Tags (comma-separated)", "")
        cja,cjb,cjc,cjd,cje=st.columns([1.35,1.35,.85,1.1,1.1])
        if cja.button("Save live signal") and active_signal and is_live_session:
            user_tags=[t.strip() for t in tags_text.split(',') if t.strip()]
            e=build_journal_entry_from_live_state(active_signal, decision_state, bias, opt_state, source='LIVE_MANUAL', notes=notes, tags=sorted(set(user_tags + current_flow_tags)))
            entries, _ = upsert_journal_entry(entries, e); save_signal_journal(entries,journal_path)
        elif not is_live_session:
            st.caption("Live signal journaling is only enabled for the actual current session. Use replay saves for historical sessions.")
        if cjb.button("Save replay signals") and 'rs' in locals():
            for e in build_journal_entries_from_replay_state(rs): entries,_=upsert_journal_entry(entries,e)
            save_signal_journal(entries,journal_path)
        if cjc.button("Reload journal"): entries=load_signal_journal(journal_path)
        cjd.download_button("Export journal JSON", data=json.dumps([journal_entry_to_dict(x) for x in entries], indent=2), file_name="signal_journal.json")
        cje.download_button("Export journal CSV", data=pd.DataFrame([journal_entry_to_dict(x) for x in entries]).to_csv(index=False), file_name="signal_journal.csv")
        a=compute_journal_analytics(entries)
        render_status_strip([
            ("Entries", a.total_entries),
            ("Confirmed", a.total_confirmed),
            ("Win rate", fmt_pct(a.win_rate * 100, 0) if not pd.isna(a.win_rate) else "-"),
            ("Avg RR", fmt_float(a.average_rr)),
            ("Expectancy", fmt_price(a.expectancy_per_contract)),
        ])
        journal_view = pd.DataFrame([journal_entry_to_dict(x) for x in entries]).tail(50)
        if not journal_view.empty:
            if "line_name" in journal_view.columns:
                journal_view["trigger"] = journal_view["line_name"].map(display_line_name)
                journal_view = journal_view.drop(columns=["line_name"])
            if "target_line_name" in journal_view.columns:
                journal_view["target"] = journal_view["target_line_name"].map(display_line_name)
                journal_view = journal_view.drop(columns=["target_line_name"])
        if journal_view.empty:
            render_data_notice("No journal history yet.")
        else:
            st.dataframe(journal_view, use_container_width=True)
        if show_debug:
            st.write("By line", a.by_line); st.write("By signal type", a.by_signal_type); st.write("By quality grade", a.by_quality_grade); st.write("By bias", a.by_bias); st.write("By hour", a.by_hour); st.write("By source", a.by_source)
        if a.total_entries > 0:
            for ins in generate_journal_insights(a): render_data_notice(ins)

    if show_debug:
        with tabs["Structure Details"]:
            st.caption("Advanced structure table for validating Yahoo candle inputs and calculated trigger levels.")
            render_section_title("Structure Details", "Yahoo pivots and calculated trigger levels")
            if not proj_df.empty:
                st.markdown("**Yahoo Pivot Source**")
                st.dataframe(build_pivot_source_table(rth_df), use_container_width=True)
                st.markdown("**Calculated Trigger Levels**")
                st.dataframe(build_structure_projection_table(primary_lines, now_ct, latest_price, prior_day, signal_day), use_container_width=True)
                secondary_view = proj_df[proj_df['is_primary']==False][["level","tradable_value","distance","role","direction","anchor_price","anchor_time"]].rename(columns={"level":"level_name"})
                if not secondary_view.empty:
                    st.markdown("**Intermediate Targets**")
                    st.dataframe(secondary_view, use_container_width=True)
            else:
                st.info("No projected structure available yet.")

        with tabs["Signal Details"]:
            st.caption("Advanced signal diagnostics for checking rejection quality.")
            render_section_title("Signal Details", "Hourly rejection diagnostics")
            render_signal_card(active_signal)
            if decision_state and decision_state.signal_quality:
                q = decision_state.signal_quality
                render_status_strip([
                    ("Quality", q.grade),
                    ("Score", f"{q.score:.1f}"),
                    ("Close dist", f"{q.close_distance:.2f}"),
                    ("Wick ratio", f"{q.wick_rejection_ratio:.2f}"),
                    ("Action", q.action_label),
                ])
                if q.warnings:
                    st.warning(", ".join(q.warnings).replace("_", " ").title())
                if q.strengths:
                    st.success(", ".join(q.strengths).replace("_", " ").title())
            if signals:
                signal_rows = []
                for sg in signals[-5:]:
                    signal_rows.append({
                        "type": sg.signal_type,
                        "status": _humanize(sg.status),
                        "trigger": display_line_name(sg.line_name),
                        "rejection_time": sg.rejection_time,
                        "entry_time": sg.entry_time,
                        "entry_price": sg.entry_price,
                        "stop_price": sg.stop_price,
                        "target": display_line_name(sg.target_line_name),
                        "target_price": sg.target_price,
                        "rr_ratio": sg.rr_ratio,
                    })
                st.dataframe(pd.DataFrame(signal_rows), use_container_width=True)
            else:
                st.info("No current-session rejection signals.")

        with tabs["Diagnostics"]:
            st.caption("Raw object inspection for development and support.")
            render_debug_json("Primary lines", redact_structure_calibration([asdict(x) for x in primary_lines]))
            st.dataframe(df.tail(20) if not df.empty else pd.DataFrame())
            st.dataframe(rth_df.tail(20) if not rth_df.empty else pd.DataFrame())
            st.dataframe(signal_rth_df.tail(20) if not signal_rth_df.empty else pd.DataFrame())
            st.dataframe(ext_df.tail(20) if not ext_df.empty else pd.DataFrame())
            render_debug_json("Secondary pivots", [asdict(x) for x in secondary_pivots])
            st.dataframe(hide_structure_calibration_columns(proj_df))
            render_debug_json("Bias", asdict(bias) if bias else {})
            render_debug_json("Strikes", asdict(strikes) if strikes else {})
            render_debug_json("Signals", [asdict(x) for x in signals])
            if strikes:
                dbg_opt = option_state or build_options_cockpit_state(strikes, latest_signal=active_signal, provider=option_provider, current_dt=now_ct, all_lines=primary_lines+secondary_lines if primary_lines else [])
                render_debug_json("OptionsCockpitState", asdict(dbg_opt))
                render_debug_json("ProviderStatus", provider_status if "provider_status" in locals() else {})
                render_debug_json("OptionsScenario", [asdict(x) for x in dbg_opt.scenarios])
                render_debug_json("EntryTargetOptionProjection", asdict(dbg_opt.entry_target_projection) if dbg_opt.entry_target_projection else {})
            render_debug_json("SignalQuality", asdict(decision_state.signal_quality) if decision_state and decision_state.signal_quality else {})
            render_debug_json("RiskGuardrailState", asdict(decision_state.guardrail_state) if decision_state else {})
            render_debug_json("DecisionState", asdict(decision_state) if decision_state else {})
            st.write({"current_ts": str(now_ct), "latest_price": latest_price, "structure_day": str(prior_day), "signal_day": str(signal_day), "candles_plotted": len(signal_rth_df if not signal_rth_df.empty else rth_df if not rth_df.empty else df), "num_primary_lines": len(primary_lines), "num_secondary_lines_available": len(secondary_lines), "num_signals": len(signals), "active_signal_id": active_signal.signal_id if active_signal else None})
            j_entries = load_signal_journal("data/signal_journal.json")
            render_debug_json("Journal path", {"path":"data/signal_journal.json","count":len(j_entries),"auto_journal":auto_journal_on})
            render_debug_json("Last 3 journal entries", [journal_entry_to_dict(x) for x in j_entries[-3:]])


if __name__ == "__main__":
    main()
