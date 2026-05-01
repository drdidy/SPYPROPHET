from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time
from html import escape
from typing import Optional

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf
import plotly.graph_objects as go
from tastytrade_provider import TastytradeProvider, TastytradeProviderStatus
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

SYMBOL = "SPY"
CENTRAL_TZ_NAME = "America/Chicago"
CENTRAL_TZ_ALIASES = (CENTRAL_TZ_NAME, "US/Central")
DEFAULT_SLOPE_PER_HOUR = 0.103
TARGET_OTM_STRIKE_DISTANCE = 2.0
SPY_STRIKE_INCREMENT = 1
EXPECTED_OHLCV_COLUMNS = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
TASTYTRADE_SECRET_KEYS = ["TASTYTRADE_CLIENT_ID", "TASTYTRADE_CLIENT_SECRET", "TASTYTRADE_REFRESH_TOKEN"]


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
        return (cur - anc).total_seconds() / 3600.0

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


def filter_rth_session(df: pd.DataFrame, trading_day: date) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    session = df[df.index.date == trading_day].sort_index()
    rth = session.between_time(time(8, 30), time(15, 0), inclusive="both")
    diffs = session.index.to_series().diff().dropna()
    if not diffs.empty and diffs.median() >= pd.Timedelta(minutes=30):
        rth = rth[rth.index.time < time(15, 0)]
    return rth


def filter_extended_session(df: pd.DataFrame, trading_day: date) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    return df[df.index.date == trading_day].between_time(time(3, 0), time(19, 0), inclusive="both")


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
        raw = line.raw_value_at(current_dt)
        tradable = line.tradable_value_at(current_dt)
        distance = line.distance_from_price(current_price, current_dt) if current_price is not None else float("nan")
        sign = "+" if line.direction == "ascending" else "-"
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
            "Hours From Pivot": hours,
            "Slope / Hour": line.slope_per_hour,
            "Formula": f"{line.anchor_price:.2f} {sign} ({line.slope_per_hour:.3f} x {hours:.2f}h)" if not pd.isna(hours) and not pd.isna(line.anchor_price) else "-",
            "Projected SPY Level": tradable,
            "Raw Projection": raw,
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
    return fallback if value is None or (isinstance(value,float) and pd.isna(value)) else value

def fmt_price(value, digits=2):
    v=fmt_nan(value,None)
    return "-" if v is None else f"{float(v):.{digits}f}"

def fmt_float(value, digits=2):
    v=fmt_nan(value,None)
    return "-" if v is None else f"{float(v):.{digits}f}"

def fmt_pct(value, digits=1):
    v=fmt_nan(value,None)
    return "-" if v is None else f"{float(v):.{digits}f}%"

def fmt_time(value):
    if value is None: return "-"
    ts=pd.Timestamp(value)
    ts = ts.tz_localize(get_central_tz()) if ts.tzinfo is None else ts.tz_convert(get_central_tz())
    return ts.strftime("%Y-%m-%d %H:%M %Z")

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
      --bg:#070a0f;--surface:#0d131d;--surface2:#111a28;--surface3:#162235;
      --border:#26364d;--border2:#355174;--text:#f4f7fb;--muted:#8da0b8;
      --blue:#67b7ff;--green:#21d07a;--red:#ff5f7c;--amber:#f4c76b;
      --cyan:#28d2c2;--shadow:0 18px 50px rgba(0,0,0,.35);
    }
    .block-container{padding-top:3rem;max-width:1240px}
    [data-testid="stSidebar"]{background:#111722;border-right:1px solid #202c3f}
    [data-testid="stSidebar"] h2{font-size:1rem;letter-spacing:.02em}
    [data-testid="stSidebar"] button{border-radius:8px}
    div[data-baseweb="tab-list"]{gap:10px;border-bottom:1px solid var(--border);padding-bottom:0}
    button[role="tab"]{padding:10px 0;border-bottom:2px solid transparent;color:var(--muted)}
    button[role="tab"][aria-selected="true"]{border-bottom-color:var(--green);color:var(--text)}
    .terminal-hero{border:1px solid var(--border2);border-radius:8px;background:linear-gradient(135deg,#0c1421,#101b2b 58%,#0b1019);box-shadow:var(--shadow);padding:18px 20px;margin-bottom:14px}
    .terminal-top{display:flex;align-items:center;justify-content:space-between;gap:16px;border-bottom:1px solid rgba(141,160,184,.16);padding-bottom:12px}
    .brand-mark{font-size:.72rem;letter-spacing:.18em;color:var(--blue);text-transform:uppercase}
    .brand-title{font-size:1.8rem;font-weight:800;color:var(--text);line-height:1.1;margin-top:4px}
    .market-clock{text-align:right;color:var(--muted);font-size:.84rem}
    .hero-grid{display:grid;grid-template-columns:1.1fr 1.5fr .9fr;gap:14px;margin-top:16px}
    .hero-price{font-family:Consolas,monospace;font-size:3rem;font-weight:800;color:var(--text);line-height:1}
    .hero-label,.panel-label,.tile-label{font-size:.74rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .hero-sub{margin-top:8px;color:var(--muted);font-size:.86rem}
    .decision-plate{border:1px solid var(--border);border-radius:8px;background:rgba(7,10,15,.58);padding:14px}
    .decision-main{font-size:1.45rem;font-weight:800;line-height:1.15;color:var(--text);margin:5px 0}
    .decision-reason{color:var(--muted);font-size:.86rem}
    .pill-row{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
    .pill{border:1px solid var(--border);border-radius:999px;padding:4px 9px;color:var(--muted);font-size:.78rem;background:rgba(255,255,255,.03)}
    .pill.green{border-color:rgba(33,208,122,.55);color:var(--green)} .pill.red{border-color:rgba(255,95,124,.55);color:var(--red)} .pill.amber{border-color:rgba(244,199,107,.55);color:var(--amber)} .pill.blue{border-color:rgba(103,183,255,.55);color:var(--blue)}
    .quote-stack{display:grid;grid-template-columns:1fr;gap:8px}
    .quote-mini{border:1px solid var(--border);border-radius:8px;padding:10px;background:rgba(255,255,255,.035)}
    .quote-value{font-family:Consolas,monospace;font-size:1.35rem;font-weight:800;color:var(--text)}
    .quote-level{display:block;font-family:system-ui,-apple-system,Segoe UI,sans-serif;font-size:1rem;line-height:1.2;white-space:normal}
    .terminal-section{margin-top:14px}
    .command-grid{display:grid;grid-template-columns:1.15fr .95fr .9fr;gap:14px}
    .terminal-panel,.prophet-header,.metric-card,.prophet-card,.empty-state,.warning-panel{border:1px solid var(--border);border-radius:8px;background:var(--surface);box-shadow:0 10px 30px rgba(0,0,0,.18)}
    .terminal-panel{padding:14px}
    .panel-title{font-size:1.05rem;font-weight:800;color:var(--text);margin-top:4px}
    .panel-copy{color:var(--muted);font-size:.88rem;line-height:1.45;margin-top:8px}
    .structure-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:14px}
    .structure-tile{border:1px solid var(--border);border-radius:8px;background:linear-gradient(180deg,rgba(22,34,53,.8),rgba(13,19,29,.95));padding:12px;min-height:122px}
    .structure-tile.closest{border-color:var(--blue);box-shadow:0 0 0 1px rgba(103,183,255,.3)}
    .tile-name{font-size:1.1rem;font-weight:800;color:var(--text)}
    .tile-value{font-family:Consolas,monospace;font-size:1.65rem;font-weight:800;color:var(--text);margin-top:4px}
    .tile-meta{color:var(--muted);font-size:.78rem;margin-top:4px}
    .tile-call{border-left:3px solid var(--green)} .tile-put{border-left:3px solid var(--red)}
    .brief-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:10px 0 14px}
    .brief-card{border:1px solid var(--border);border-radius:8px;background:rgba(13,19,29,.92);padding:12px}
    .brief-label{font-size:.72rem;letter-spacing:.08em;text-transform:uppercase;color:var(--muted)}
    .brief-value{font-family:Consolas,monospace;font-size:1.35rem;font-weight:800;color:var(--text);margin-top:4px}
    .brief-copy{color:var(--muted);font-size:.82rem;margin-top:4px;line-height:1.35}
    .replay-shell{border:1px solid var(--border2);border-radius:8px;background:linear-gradient(135deg,rgba(13,19,29,.92),rgba(16,27,43,.82));padding:14px;margin:10px 0 14px}
    .replay-title{font-size:1.15rem;font-weight:800;color:var(--text)}
    .replay-copy{font-size:.88rem;color:var(--muted);margin-top:6px;line-height:1.45}
    .outcome-row{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin-top:12px}
    .outcome-card{border:1px solid var(--border);border-radius:8px;background:rgba(255,255,255,.035);padding:10px}
    .status-strip{display:flex;gap:14px;flex-wrap:wrap;padding:8px 10px;border:1px solid var(--border);border-radius:8px;background:rgba(16,24,38,.7);font-size:.85rem;color:var(--muted)}
    .status-strip b{color:var(--text);font-weight:600}
    .prophet-header{padding:16px;margin-bottom:12px}.prophet-header h3{margin:0;font-size:1.5rem}
    .metric-card,.prophet-card{padding:12px}.card-title{font-size:.76rem;color:var(--muted)} .card-value{font-size:1.4rem;font-family:Consolas,monospace;color:var(--text)} .small-muted{color:var(--muted);font-size:.8rem}
    .zone-call{border-color:rgba(33,208,122,.55)} .zone-put{border-color:rgba(255,95,124,.55)} .zone-neutral{border-color:rgba(103,183,255,.55)}
    .signal-badge{display:inline-block;padding:3px 10px;border-radius:999px;font-size:.75rem;border:1px solid var(--border);margin-bottom:8px}.signal-call{background:rgba(33,208,122,.14)} .signal-put{background:rgba(255,95,124,.14)}
    .distance-wrap{height:7px;border-radius:99px;background:#1b2943}.distance-fill{height:7px;border-radius:99px;background:linear-gradient(90deg,var(--blue),var(--green))}
    @media (max-width: 1100px){.hero-grid,.command-grid,.brief-grid{grid-template-columns:1fr}.structure-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.outcome-row{grid-template-columns:repeat(2,minmax(0,1fr))}}
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

def render_warning_panel(title, message, kind="warning"):
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

def render_debug_json(label, obj):
    st.write(label); st.json(obj)


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


def display_line_list(names: list[str] | tuple[str, ...] | None) -> str:
    return ", ".join(display_line_name(name) for name in names or []) or "-"


def _pill(label: str, value: str | None, tone: str | None = None) -> str:
    return f"<span class='pill {tone or _tone_for_text(value)}'>{label}: {value or '-'}</span>"


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
) -> None:
    latest_candle = fmt_time(df.index[-1]) if df is not None and not df.empty else "-"
    clock = pd.Timestamp(now_ct).strftime("%I:%M:%S %p CT")
    decision = _humanize(decision_state.final_decision if decision_state else "WAIT")
    if decision_state and decision_state.signal_quality:
        q = decision_state.signal_quality
        decision_reason = f"Grade {_humanize(q.grade)} with score {fmt_float(q.score)}. {_humanize(q.action_label)}."
    else:
        decision_reason = bias_state.explanation if bias_state else "Waiting for enough structure to form a read."
    grade = decision_state.signal_quality.grade if decision_state and decision_state.signal_quality else "-"
    action = _humanize(decision_state.signal_quality.action_label) if decision_state and decision_state.signal_quality else "Monitor"
    signal_text = f"{latest_signal.signal_type} {_humanize(latest_signal.status)}" if latest_signal else "No signal"
    closest_value = closest_line.tradable_value_at(now_ct) if closest_line else None
    closest_text = f"<span class='quote-level'>{display_line_name(closest_line.name)}</span>{fmt_price(closest_value)}" if closest_line else "-"
    contract_text = format_watch_contract_short(selected_strikes, latest_signal, bias_state)
    st.markdown(
        f"""
        <div class='terminal-hero'>
          <div class='terminal-top'>
            <div>
              <div class='brand-mark'>SPY Prophet</div>
              <div class='brand-title'>0DTE Structure Terminal</div>
            </div>
            <div class='market-clock'>
              <div>{clock}</div>
              <div>Prior session: {prior_day or '-'}</div>
            </div>
          </div>
          <div class='hero-grid'>
            <div>
              <div class='hero-label'>SPY Last</div>
              <div class='hero-price'>{fmt_price(latest_price)}</div>
              <div class='hero-sub'>Latest candle {latest_candle}</div>
            </div>
            <div class='decision-plate'>
              <div class='hero-label'>Final Decision</div>
              <div class='decision-main'>{decision}</div>
              <div class='decision-reason'>{decision_reason}</div>
              <div class='pill-row'>
                {_pill('Bias', bias_state.bias if bias_state else '-')}
                {_pill('Grade', _humanize(grade))}
                {_pill('Action', action)}
                {_pill('Signal', signal_text)}
              </div>
            </div>
            <div class='quote-stack'>
              <div class='quote-mini'>
                <div class='hero-label'>Closest</div>
                <div class='quote-value'>{closest_text}</div>
                <div class='hero-sub'>Primary structure</div>
              </div>
              <div class='quote-mini'>
                <div class='hero-label'>0DTE</div>
                <div class='quote-value'>{contract_text}</div>
                <div class='hero-sub'>{provider_status}</div>
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
) -> None:
    quality = decision_state.signal_quality if decision_state else None
    guardrail = decision_state.guardrail_state if decision_state else None
    watch_lines = []
    if bias_state:
        watch_lines = bias_state.watched_call_lines + bias_state.watched_put_lines
    signal_body = signal_setup_copy(latest_signal)
    signal_title = signal_setup_label(latest_signal)
    options_live = bool(options_state and (options_state.call_quote or options_state.put_quote) and provider_is_live_tastytrade(options_state.provider))
    call_mark = fmt_price(options_state.call_quote.mark) if options_live and options_state.call_quote else "-"
    put_mark = fmt_price(options_state.put_quote.mark) if options_live and options_state.put_quote else "-"
    projection = options_state.entry_target_projection if options_live and options_state else None
    projection_text = (
        f"Entry {display_line_name(projection.entry_line_name)} at {fmt_price(projection.entry_line_value)}; "
        f"target {display_line_name(projection.target_line_name)} {fmt_price(projection.target_line_value)}."
        if projection else "Live option premiums appear after Tastytrade is connected and a setup resolves."
    )
    options_copy = (
        f"CALL mark {call_mark}. PUT mark {put_mark}. {projection_text}"
        if options_live
        else "Live Tastytrade premiums are not connected yet. Strikes are shown, but no option prices are displayed until quotes are live."
    )
    provider_text = option_provider_label(options_state, {}) if options_state else "TASTYTRADE setup needed"

    st.markdown(
        f"""
        <div class='terminal-section command-grid'>
          <div class='terminal-panel'>
            <div class='panel-label'>Direction</div>
            <div class='panel-title'>{market_read_label(bias_state)}</div>
            <div class='panel-copy'>{market_read_copy(bias_state)}</div>
            <div class='pill-row'>
              {_pill('Confidence', fmt_float(bias_state.strength_score) if bias_state else '-')}
              {_pill('Triggers', display_line_list(watch_lines))}
              {_pill('Price', fmt_price(latest_price))}
            </div>
          </div>
          <div class='terminal-panel'>
            <div class='panel-label'>Setup</div>
            <div class='panel-title'>{signal_title}</div>
            <div class='panel-copy'>{signal_body}</div>
            <div class='pill-row'>
              {_pill('Action', quality_label(quality))}
              {_pill('Score', fmt_float(quality.score) if quality else '-')}
              {_pill('Retest', _humanize(guardrail.retest_status) if guardrail else '-')}
            </div>
          </div>
          <div class='terminal-panel'>
            <div class='panel-label'>Options Data</div>
            <div class='panel-title'>{format_watch_contract(selected_strikes, latest_signal, bias_state)}</div>
            <div class='panel-copy'>{options_copy}</div>
            <div class='pill-row'>
              {_pill('DTE', selected_strikes.dte_label if selected_strikes else '-')}
              {_pill('Provider', provider_text)}
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_structure_tiles(primary_lines, latest_price, now_ct, closest_line, structure_day=None) -> None:
    tiles = []
    for name in ["UA", "UD", "LA", "LD"]:
        line = get_line_by_name(primary_lines, name)
        if not line:
            continue
        value = line.tradable_value_at(now_ct)
        distance = line.distance_from_price(latest_price, now_ct) if latest_price is not None else float("nan")
        kind = "tile-call" if line.zone_type == "CALL_ZONE" else "tile-put" if line.zone_type == "PUT_ZONE" else ""
        closest_cls = " closest" if closest_line is not None and closest_line.name == name else ""
        tiles.append(
            f"<div class='structure-tile {kind}{closest_cls}'>"
            f"<div class='tile-label'>{zone_side_label(line.zone_type)}</div>"
            f"<div class='tile-name'>{display_line_name(name)}</div>"
            f"<div class='tile-value'>{fmt_price(value)}</div>"
            f"<div class='tile-meta'>Distance from SPY {fmt_float(distance)}</div>"
            f"<div class='tile-meta'>Yahoo structure day {structure_day or '-'}</div>"
            "</div>"
        )
    if tiles:
        st.markdown(f"<div class='structure-grid'>{''.join(tiles)}</div>", unsafe_allow_html=True)



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
    fig.update_layout(height=780, paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='#0b1220', font=dict(color='#cbd5e1'), xaxis_title='Central Time', yaxis_title='SPY', hovermode='x unified', xaxis_rangeslider_visible=False, margin=dict(l=20,r=20,t=30,b=20), legend=dict(orientation='h'))
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
    fig.update_layout(height=620, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#0b1220", font=dict(color="#cbd5e1"), title=dict(text=title, x=0.01, font=dict(size=16)), margin=dict(l=20, r=20, t=48, b=20), hovermode="x unified", legend=dict(orientation="h", y=-0.12), xaxis_title="Central Time", yaxis_title="SPY")
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
      .svg-map-shell{{background:linear-gradient(180deg,#101927 0%,#0b111d 100%);border:1px solid #274060;border-radius:18px;padding:18px 18px 14px;box-shadow:0 20px 60px rgba(0,0,0,.28);font-family:Inter,Segoe UI,system-ui,sans-serif;color:#e7eefb}}
      .svg-map-title{{display:flex;justify-content:space-between;gap:16px;align-items:flex-end;margin:2px 2px 12px}}
      .svg-map-title h3{{margin:0;font-size:22px;letter-spacing:0;font-weight:850;color:#f8fbff}}
      .svg-map-title p{{margin:4px 0 0;color:#9cc7f5;font-size:13px}}
      .svg-map-badge{{border:1px solid #2c79bd;border-radius:999px;padding:7px 11px;color:#9dd7ff;background:#0c2238;font-size:12px;font-weight:750;white-space:nowrap}}
      .grid-line{{stroke:#263b56;stroke-width:1;opacity:.72}}
      .axis-label{{fill:#7f9ab7;font-size:12px;font-weight:650}}
      .zone-upper{{fill:#1c78b8;opacity:.14}}
      .zone-lower{{fill:#e85b7b;opacity:.10}}
      .rail{{fill:none;stroke-width:3;stroke-linecap:round;stroke-dasharray:10 10;animation:railFlow 9s linear infinite}}
      .rail-hot{{stroke-width:5;filter:url(#softGlow)}}
      .target-rail{{fill:none;stroke:#8fa4bd;stroke-width:1.5;stroke-dasharray:3 7;opacity:.55}}
      .spy-path{{fill:none;stroke:url(#spyGradient);stroke-width:6;stroke-linecap:round;stroke-linejoin:round;filter:url(#softGlow);stroke-dasharray:1400;stroke-dashoffset:1400;animation:drawPath 2.4s ease-out forwards}}
      .spy-shadow{{fill:none;stroke:#1c6eb8;stroke-width:16;stroke-linecap:round;stroke-linejoin:round;opacity:.18;filter:blur(5px)}}
      .price-line{{stroke:#f8fbff;stroke-width:1.5;stroke-dasharray:7 9;opacity:.85}}
      .price-dot{{fill:#f8fbff;stroke:#50b7ff;stroke-width:5;filter:url(#softGlow)}}
      .rail-label,.marker-label{{font-size:12px;font-weight:850;letter-spacing:0}}
      .map-label{{fill:#d9ecff;font-size:13px;font-weight:800}}
      .map-muted{{fill:#8ba9c8;font-size:12px;font-weight:650}}
      .signal-pulse circle:first-child{{animation:pulse 2.2s ease-in-out infinite;transform-origin:center}}
      .svg-map-cards{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:12px}}
      .svg-map-card{{border:1px solid #263e5b;background:#0d1726;border-radius:8px;padding:11px 12px;min-height:72px}}
      .svg-card-label{{font-size:11px;color:#7db9ef;text-transform:uppercase;letter-spacing:.08em}}
      .svg-card-value{{font-size:19px;line-height:1.2;margin-top:5px;font-weight:850;color:#fbfdff}}
      .svg-card-copy{{font-size:12px;color:#95acc6;margin-top:6px}}
      @keyframes drawPath{{to{{stroke-dashoffset:0}}}}
      @keyframes railFlow{{to{{stroke-dashoffset:-120}}}}
      @keyframes pulse{{0%,100%{{transform:scale(.85);opacity:.16}}50%{{transform:scale(1.4);opacity:.32}}}}
      @media (max-width:760px){{.svg-map-title{{display:block}}.svg-map-badge{{display:inline-block;margin-top:10px}}.svg-map-cards{{grid-template-columns:repeat(2,minmax(0,1fr))}}}}
    </style>
    <div class='svg-map-shell'>
      <div class='svg-map-title'><div><h3>{_svg_text(title)}</h3><p>{_svg_text(subtitle)}</p></div><div class='svg-map-badge'>Animated structure map</div></div>
      <svg viewBox='0 0 {width} {height}' role='img' aria-label='{_svg_text(title)}'>
        <defs>
          <linearGradient id='spyGradient' x1='0' x2='1'><stop offset='0%' stop-color='#9bdcff'/><stop offset='48%' stop-color='#ffffff'/><stop offset='100%' stop-color='#f4c76b'/></linearGradient>
          <filter id='softGlow'><feGaussianBlur stdDeviation='4' result='blur'/><feMerge><feMergeNode in='blur'/><feMergeNode in='SourceGraphic'/></feMerge></filter>
        </defs>
        <rect x='0' y='0' width='{width}' height='{height - 96}' rx='18' fill='#0a1321'/>
        <rect x='{x0}' y='{y0}' width='{x1 - x0}' height='{y1 - y0}' rx='14' fill='#0d1828' stroke='#203a58'/>
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


def render_structure_map_svg(*args, height: int = 820, **kwargs) -> None:
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

def is_mock_option_provider_name(name: str | None) -> bool:
    text = str(name or "").upper()
    return "MOCK" in text or text == "MOC"


def provider_is_live_tastytrade(name: str | None) -> bool:
    text = str(name or "").upper()
    return "TASTYTRADE" in text and not is_mock_option_provider_name(text)


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
    if (call_q or put_q) and not any(provider_is_live_tastytrade(name) for name in provider_names):
        return OptionsCockpitState("TASTYTRADE", selected_strikes.underlying_price, selected_strikes.expiration_date, None, None, None, [], None, 'Non-Tastytrade option quotes are disabled. Configure live Tastytrade credentials for options data.', 'No live options provider available.')
    opt_type = option_type_override or (latest_signal.signal_type if latest_signal else None)
    sel = call_q if opt_type=='CALL' else put_q if opt_type=='PUT' else None
    scenarios = simulate_option_scenarios(sel) if sel else []
    proj=None; warning=q.get("warning")
    if sel and all_lines:
        entry,target = resolve_entry_target_lines(all_lines, latest_signal=latest_signal, option_type=opt_type, entry_line_name=entry_line_name, target_line_name=target_line_name, current_price=selected_strikes.underlying_price, current_dt=now)
        if entry:
            proj = project_option_entry_to_target(sel, selected_strikes.underlying_price, entry, target, entry_projection_time=projection_time or get_default_projection_time(now), target_projection_time=projection_time or get_default_projection_time(now))
        else:
            warning = 'Could not resolve entry line; projection unavailable.'
    return OptionsCockpitState(provider_name, selected_strikes.underlying_price, selected_strikes.expiration_date, call_q, put_q, sel, scenarios, proj, warning, f'{provider_name} options cockpit state.')


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
    if state and (state.call_quote or state.put_quote):
        return state.provider
    if provider_status.get("missing_secrets"):
        return "TASTYTRADE setup needed"
    if provider_status.get("last_error") or (state and state.warning):
        return "TASTYTRADE unavailable"
    return provider_status.get("provider") or "TASTYTRADE"



import os, json, hashlib
from pathlib import Path

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

def generate_journal_insights(a):
    out=[]
    if a.total_entries==0: return ["No journal history yet."]
    for name,grp in [('line',a.by_line),('quality',a.by_quality_grade),('hour',a.by_hour)]:
        if grp:
            best=max(grp.items(), key=lambda kv: kv[1]['win_rate'] if kv[1]['win_rate']==kv[1]['win_rate'] else -1)
            note='small sample' if best[1]['small_sample'] else 'sample adequate'
            out.append(f"Best {name} so far: {best[0]} (win_rate={best[1]['win_rate']:.2f}, {note}).")
    return out

def auto_journal_live_signals(signals, decision_state, bias_state, options_cockpit_state, existing_entries, path='data/signal_journal.json', enabled=False):
    if not enabled: return existing_entries, AutoJournalStatus(False,0,0,0,None,[],"Auto-journal disabled.")
    saved=updated=skipped=0; latest=None
    entries=list(existing_entries)
    for sg in signals or []:
        entry=build_journal_entry_from_live_state(sg,decision_state,bias_state,options_cockpit_state,source='LIVE_AUTO')
        entries,act=upsert_journal_entry(entries,entry)
        if act=='inserted': saved+=1; latest=sg.signal_id
        elif act=='updated': updated+=1; latest=sg.signal_id
        else: skipped+=1
    save_signal_journal(entries,path)
    return entries, AutoJournalStatus(True,saved,updated,skipped,latest,[],"Auto-journal processed live signals.")


def main() -> None:
    st.set_page_config(page_title="SPY Prophet", page_icon="SPY", layout="wide", initial_sidebar_state="expanded")
    inject_global_css()
    now_ct = datetime.now(tz=get_central_tz())

    st.sidebar.header("SPY Prophet Controls")
    st.sidebar.button("Refresh data")
    show_debug = st.sidebar.toggle("Advanced diagnostics", value=False)
    auto_journal_on = st.sidebar.toggle("Auto-journal live signals", value=False)
    slope = DEFAULT_SLOPE_PER_HOUR
    if show_debug:
        slope = st.sidebar.number_input("Slope per hour", min_value=0.050, max_value=0.200, value=DEFAULT_SLOPE_PER_HOUR, step=0.001, format="%.3f")
    provider = "TASTYTRADE"
    st.sidebar.caption("Provider: TASTYTRADE")
    st.sidebar.caption(f"Current CT: {now_ct.strftime('%H:%M:%S %Z')}")

    df = fetch_spy_hourly(period="10d")
    latest_price = None
    prior_day = None
    signal_day = None
    rth_df = pd.DataFrame(); signal_rth_df = pd.DataFrame(); ext_df = pd.DataFrame(); pivots={}; secondary_pivots=[]; primary_lines=[]; secondary_lines=[]; signals=[]
    bias = None; strikes = None; closest=None; proj_df=pd.DataFrame(); decision_state=None; active_signal=None
    option_provider, provider_status = get_tastytrade_option_provider()
    option_state = None
    if df.empty:
        st.warning("No SPY data loaded. Click refresh or check yfinance availability.")
    if not df.empty:
        close_series = df.get("Close", pd.Series(dtype="float64")).dropna()
        latest_price = float(close_series.iloc[-1]) if not close_series.empty else None
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
                proj_df = project_lines(primary_lines + secondary_lines, now_ct, latest_price)
                bias = determine_preopen_bias(primary_lines, latest_price if latest_price is not None else float("nan"), now_ct)
                signals = detect_rejection_signals(signal_rth_df, primary_lines, secondary_lines)
                active_signal = get_latest_active_signal(signals, signal_rth_df)
                strikes = select_watch_contracts(latest_price if latest_price is not None else float("nan"), now_ct, active_signal, primary_lines+secondary_lines)
                closest = get_closest_primary_line(primary_lines, now_ct, latest_price) if latest_price is not None else None
                latest_signal_candle = signal_rth_df.iloc[-1] if not signal_rth_df.empty else None
                decision_state = build_decision_state(active_signal, primary_lines+secondary_lines, latest_price if latest_price is not None else float("nan"), pd.Timestamp(now_ct), latest_signal_candle, signals_today=signals)
                option_state = build_options_cockpit_state(strikes, latest_signal=active_signal, decision_state=decision_state, provider=option_provider, current_dt=now_ct, all_lines=primary_lines+secondary_lines if primary_lines else [], projection_time=get_default_projection_time(now_ct))

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
    )
    if show_debug:
        st.sidebar.caption(f"Data loaded: {not df.empty}")
        st.sidebar.caption(f"Latest candle: {df.index[-1] if not df.empty else 'N/A'}")
        st.sidebar.caption(f"Structure day: {prior_day}")
        st.sidebar.caption(f"Signal day: {signal_day}")

    tab_names = ["Live Terminal", "Prophet Chart", "Replay Lab", "Options", "Journal"]
    if show_debug:
        tab_names += ["Structure Details", "Signal Details", "Diagnostics"]
    tabs = dict(zip(tab_names, st.tabs(tab_names)))

    with tabs["Live Terminal"]:
        render_live_command_center(
            bias,
            decision_state,
            active_signal,
            strikes,
            option_state,
            latest_price,
        )
        render_structure_tiles(primary_lines, latest_price, now_ct, closest, prior_day)
        if option_state:
            if option_state.entry_target_projection:
                render_status_strip([
                    ("Entry premium", fmt_price(option_state.entry_target_projection.estimated_entry_mark)),
                    ("Target premium", fmt_price(option_state.entry_target_projection.estimated_target_mark)),
                    ("Est. P/L", fmt_price(option_state.entry_target_projection.estimated_profit_per_contract)),
                ])

    with tabs["Prophet Chart"]:
        render_section_title("Prophet Chart", "Animated decision map")
        chart_df = signal_rth_df if not signal_rth_df.empty else (rth_df if not rth_df.empty else df)
        render_chart_brief(latest_price, closest, active_signal, decision_state, pd.Timestamp(now_ct))
        cc1,cc2=st.columns([1.1,1])
        chart_mode = cc1.selectbox("View", ["Animated Map", "Advanced Candles"], index=0, key="chart_view_mode")
        secondary_mode = cc2.selectbox("Targets", ["nearest 6","nearest 12","all"], index=0, key="chart_target_density")
        show_secondary = True
        show_signals = True
        show_overlays = True
        try:
            hp = pivots["high"] if 'pivots' in locals() else None
            lp = pivots["low"] if 'pivots' in locals() else None
            if chart_mode == "Animated Map":
                render_structure_map_svg(chart_df, primary_lines, secondary_lines, signals, decision_state, latest_price if latest_price is not None else float('nan'), pd.Timestamp(now_ct), title="SPY Structure Map", subtitle=f"Prior session {prior_day}; signal day {signal_day}", secondary_mode=secondary_mode)
            else:
                fig = build_prophet_chart(chart_df, primary_lines, secondary_lines, hp, lp, secondary_pivots, signals, decision_state, latest_price if latest_price is not None else float('nan'), pd.Timestamp(now_ct), show_secondary=show_secondary, show_signals=show_signals, show_trade_overlays=show_overlays, show_pivots=True, secondary_mode=secondary_mode)
                render_plotly_html(fig)
                st.caption("Advanced view: candlesticks, all selected structure rails, signal markers, and trade overlays.")
        except Exception as e:
            render_warning_panel(f"Chart build failed: {e}")

    with tabs["Replay Lab"]:
        st.caption("Historical replay as a decision story.")
        render_section_title("Replay Lab", "Replay a session against prior-day structure")
        dates = get_available_replay_dates(df)
        if not dates:
            st.info("No replay dates available.")
        else:
            rca,rcb,rcc=st.columns([1,1,1])
            rdate = rca.selectbox("Replay date", dates, index=max(0,len(dates)-1), key="replay_date")
            mode = rcb.selectbox("Mode", ["Full Day Review","Step Replay"], key="replay_mode")
            replay_view = rcc.selectbox("View", ["Animated Map", "Advanced Candles"], index=0, key="replay_view_mode")
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
                st.info("Outcome review is visible for this replay.")
            else:
                st.info("Future outcomes are hidden for this replay point.")
            if replay_view == "Animated Map":
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
        st.caption("Live Tastytrade option quotes for the selected 0DTE strikes.")
        render_section_title("Options Cockpit", "Quote and projection console")
        if strikes:
            state = option_state or build_options_cockpit_state(strikes, latest_signal=active_signal, decision_state=decision_state, provider=option_provider, current_dt=now_ct, all_lines=primary_lines+secondary_lines if primary_lines else [], projection_time=get_default_projection_time(now_ct))
            render_status_strip([
                ("Provider", option_provider_label(state, provider_status)),
                ("Connection", "Live" if state.call_quote or state.put_quote else "Unavailable"),
                ("Mode", "TASTYTRADE"),
            ])
            if provider_status.get("missing_secrets"): st.warning(f"Missing secrets: {provider_status.get('missing_secrets')}")
            if provider_status.get("last_error"): st.warning(f"Provider error: {provider_status.get('last_error')}")
            if state.warning: st.warning(state.warning)
            c1,c2=st.columns(2)
            with c1:
                cq=state.call_quote
                render_glass_card("CALL Quote", f"<div class='card-value'>Strike {cq.strike if cq else '-'} | Mark {fmt_price(cq.mark if cq else None)}</div><div class='small-muted'>Bid {fmt_price(cq.bid if cq else None)} Ask {fmt_price(cq.ask if cq else None)} Spread {fmt_price(cq.spread if cq else None)} Delta {fmt_float(cq.delta if cq else None)}</div>")
            with c2:
                pq=state.put_quote
                render_glass_card("PUT Quote", f"<div class='card-value'>Strike {pq.strike if pq else '-'} | Mark {fmt_price(pq.mark if pq else None)}</div><div class='small-muted'>Bid {fmt_price(pq.bid if pq else None)} Ask {fmt_price(pq.ask if pq else None)} Spread {fmt_price(pq.spread if pq else None)} Delta {fmt_float(pq.delta if pq else None)}</div>")
            if state.selected_trade_quote:
                render_status_strip([
                    ("Active contract", f"{state.selected_trade_quote.option_type} {state.selected_trade_quote.strike}"),
                    ("Mark", fmt_price(state.selected_trade_quote.mark)),
                ])
            else:
                st.info("No active options setup. Waiting for confirmed or pending SPY rejection signal.")
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
        st.caption("Signal memory, outcomes, and expectancy analytics.")
        render_section_title("Journal Analytics", "Self-learning signal memory")
        journal_path='data/signal_journal.json'
        entries = load_signal_journal(journal_path)
        auto_status = AutoJournalStatus(False,0,0,0,None,[],"Auto-journal disabled.")
        opt_state = option_state if strikes else None
        entries, auto_status = auto_journal_live_signals(signals, decision_state, bias, opt_state, entries, journal_path, enabled=auto_journal_on)
        render_status_strip([
            ("Auto journal", "On" if auto_status.enabled else "Off"),
            ("Saved", auto_status.saved_count),
            ("Updated", auto_status.updated_count),
            ("Skipped", auto_status.skipped_duplicate_count),
        ])
        notes = st.text_area("Notes for latest live signal", "")
        tags_text = st.text_input("Tags (comma-separated)", "")
        cja,cjb,cjc,cjd=st.columns(4)
        if cja.button("Save latest live signal to journal") and active_signal:
            e=build_journal_entry_from_live_state(active_signal, decision_state, bias, opt_state, source='LIVE_MANUAL', notes=notes, tags=[t.strip() for t in tags_text.split(',') if t.strip()])
            entries, _ = upsert_journal_entry(entries, e); save_signal_journal(entries,journal_path)
        if cjb.button("Save replay signals to journal") and 'rs' in locals():
            for e in build_journal_entries_from_replay_state(rs): entries,_=upsert_journal_entry(entries,e)
            save_signal_journal(entries,journal_path)
        if cjc.button("Reload journal"): entries=load_signal_journal(journal_path)
        cjd.download_button("Export journal JSON", data=json.dumps([journal_entry_to_dict(x) for x in entries], indent=2), file_name="signal_journal.json")
        st.download_button("Export journal CSV", data=pd.DataFrame([journal_entry_to_dict(x) for x in entries]).to_csv(index=False), file_name="signal_journal.csv")
        a=compute_journal_analytics(entries)
        render_status_strip([
            ("Entries", a.total_entries),
            ("Confirmed", a.total_confirmed),
            ("Win rate", a.win_rate),
            ("Avg RR", a.average_rr),
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
        st.dataframe(journal_view, use_container_width=True)
        if show_debug:
            st.write("By line", a.by_line); st.write("By signal type", a.by_signal_type); st.write("By quality grade", a.by_quality_grade); st.write("By bias", a.by_bias); st.write("By hour", a.by_hour); st.write("By source", a.by_source)
        for ins in generate_journal_insights(a): st.info(ins)

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
            render_debug_json("Primary lines", [asdict(x) for x in primary_lines])
            st.dataframe(df.tail(20) if not df.empty else pd.DataFrame())
            st.dataframe(rth_df.tail(20) if not rth_df.empty else pd.DataFrame())
            st.dataframe(signal_rth_df.tail(20) if not signal_rth_df.empty else pd.DataFrame())
            st.dataframe(ext_df.tail(20) if not ext_df.empty else pd.DataFrame())
            render_debug_json("Secondary pivots", [asdict(x) for x in secondary_pivots])
            st.dataframe(proj_df)
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
