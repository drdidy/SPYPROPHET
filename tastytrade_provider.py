from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
import math
import requests
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TASTYTRADE_API_VERSION = "20251101"
ACCESS_TOKEN_EXPIRY_SAFETY_SECONDS = 60

logger = logging.getLogger("spyprophet.tastytrade")


def _central_now():
    try:
        tz = ZoneInfo("America/Chicago")
    except ZoneInfoNotFoundError:
        tz = ZoneInfo("UTC")
    return datetime.now(tz=tz)


@dataclass
class TastytradeProviderStatus:
    provider: str = "TASTYTRADE"
    connected: bool = False
    using_live_quotes: bool = False
    environment: str = "production"
    last_error: str | None = None
    last_update: object | None = None
    missing_secrets: list[str] = field(default_factory=list)
    auth_ok: bool = False
    chain_ok: bool = False
    quotes_ok: bool = False


class TastytradeProvider:
    provider_name = "TASTYTRADE"

    def __init__(self, client_id: str, client_secret: str, refresh_token: str, environment: str = "production"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.environment = environment
        self.access_token = None
        self.access_token_expires_at: datetime | None = None
        self.refresh_token_rotated = False
        self.status = TastytradeProviderStatus(environment=environment)
        self.base = "https://api.tastytrade.com" if environment == "production" else "https://api.cert.tastytrade.com"
        self.live_quote_timeout_seconds = 4.0
        self.api_headers = {"Accept": "application/json"}
        if environment == "production":
            self.api_headers["Accept-Version"] = TASTYTRADE_API_VERSION

    def _token_request_headers(self) -> dict:
        # Token endpoint must not echo any Authorization header from prior calls.
        return {"Accept": "application/json"}

    def _token_is_fresh(self) -> bool:
        if not self.access_token:
            return False
        # No expiry known (legacy path or token set directly): trust it.
        # Real OAuth flows always populate expires_at; this branch only
        # matters for tests / direct assignment.
        if self.access_token_expires_at is None:
            return True
        safety = timedelta(seconds=ACCESS_TOKEN_EXPIRY_SAFETY_SECONDS)
        return datetime.utcnow() + safety < self.access_token_expires_at

    def authenticate(self):
        try:
            resp = requests.post(
                f"{self.base}/oauth/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "refresh_token": self.refresh_token,
                },
                headers=self._token_request_headers(),
                timeout=10,
            )
            if resp.status_code >= 400:
                self.status.last_error = f"Auth failed: {resp.status_code}"
                self.status.auth_ok = False
                self.access_token = None
                self.access_token_expires_at = None
                return False
            data = resp.json()
            self.access_token = data.get("access_token")
            try:
                expires_in = int(data.get("expires_in") or 0)
            except (TypeError, ValueError):
                expires_in = 0
            if expires_in > 0:
                self.access_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
            else:
                self.access_token_expires_at = None
            rotated = data.get("refresh_token")
            if rotated and rotated != self.refresh_token:
                self.refresh_token = rotated
                self.refresh_token_rotated = True
                logger.warning(
                    "Tastytrade refresh token rotated; update the secret store with the new value to avoid stale tokens."
                )
            self.status.auth_ok = bool(self.access_token)
            self.status.connected = self.status.auth_ok
            return self.status.auth_ok
        except Exception as e:
            self.status.last_error = f"Auth exception: {type(e).__name__}"
            self.status.auth_ok = False
            self.access_token = None
            self.access_token_expires_at = None
            return False

    def get_access_token(self):
        if not self._token_is_fresh():
            self.authenticate()
        return self.access_token

    def get_nested_option_chain(self, symbol, expiration_date):
        token = self.get_access_token()
        if not token:
            return None
        try:
            headers = {**self.api_headers, "Authorization": f"Bearer {token}"}
            r = requests.get(f"{self.base}/option-chains/{symbol}/nested", headers=headers, timeout=10)
            if r.status_code >= 400:
                self.status.last_error = f"Chain failed: {r.status_code}"
                return None
            self.status.chain_ok = True
            return r.json()
        except Exception as e:
            self.status.last_error = f"Chain exception: {type(e).__name__}"
            return None

    def select_contracts(self, symbol, expiration_date, call_strike, put_strike):
        chain = self.get_nested_option_chain(symbol, expiration_date)
        if not chain:
            self.status.chain_ok = False
            return None, None, "Expiration unavailable"
        items = chain.get("data", {}).get("items", []) if isinstance(chain, dict) else []
        exp = None
        for it in items:
            if str(it.get("expiration-date")) == str(expiration_date):
                exp = it
                break
            for candidate in it.get("expirations", []) or []:
                if str(candidate.get("expiration-date")) == str(expiration_date):
                    exp = candidate
                    break
            if exp is not None:
                break
        if exp is None:
            self.status.chain_ok = False
            return None, None, "Expiration unavailable"

        def choose(option_type, strike):
            side = "calls" if option_type == "CALL" else "puts"
            symbol_key = "call" if option_type == "CALL" else "put"
            arr = exp.get(side)
            if arr is None:
                arr = [
                    {**x, "symbol": x.get(symbol_key)}
                    for x in exp.get("strikes", []) or []
                    if x.get(symbol_key)
                ]
            if not arr:
                return None, False
            def normalize_contract(raw):
                contract = dict(raw)
                contract.setdefault("symbol", contract.get(symbol_key))
                contract.setdefault("streamer-symbol", contract.get(f"{symbol_key}-streamer-symbol"))
                contract.setdefault("expiration-date", exp.get("expiration-date"))
                return contract
            exact = [x for x in arr if int(float(x.get("strike-price", 0))) == int(strike)]
            if exact:
                return normalize_contract(exact[0]), True
            nearest = min(arr, key=lambda x: abs(float(x.get("strike-price", 0)) - strike))
            return normalize_contract(nearest), False

        c, ce = choose("CALL", call_strike)
        p, pe = choose("PUT", put_strike)
        warn = None if (ce and pe) else "Exact strike unavailable; nearest strike selected."
        return c, p, warn

    @staticmethod
    def _safe_float(value):
        if value is None:
            return math.nan
        try:
            return float(value)
        except (TypeError, ValueError):
            return math.nan

    @staticmethod
    def _contract_streamer_symbol(contract):
        return (
            contract.get("streamer-symbol")
            or contract.get("streamer_symbol")
            or contract.get("dx-symbol")
            or contract.get("dx_symbol")
            or contract.get("symbol")
        )

    @staticmethod
    def _has_market_data(quote):
        fields = ("bid", "ask", "mark", "delta", "gamma", "theta", "vega", "iv")
        for field in fields:
            value = quote.get(field)
            if value is not None and not math.isnan(value):
                return True
        return False

    @classmethod
    def _stream_returned_market_data(cls, market_data):
        return any(cls._has_market_data(values) for values in market_data.values())

    @staticmethod
    def _run_async_blocking(coro):
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coro)

        with ThreadPoolExecutor(max_workers=1) as executor:
            return executor.submit(lambda: asyncio.run(coro)).result()

    async def _fetch_live_market_data_async(self, streamer_symbols, timeout_seconds):
        from tastytrade.session import Session
        from tastytrade.streamer import DXLinkStreamer, Greeks, Quote

        wanted = {symbol for symbol in streamer_symbols if symbol}
        if not wanted:
            return {}

        out = {symbol: {} for symbol in wanted}
        is_test = self.environment != "production"

        async with Session(
            provider_secret=self.client_secret,
            refresh_token=self.refresh_token,
            is_test=is_test,
            timeout=timeout_seconds,
        ) as session:
            async with DXLinkStreamer(session) as streamer:
                await streamer.subscribe(Quote, wanted)
                await streamer.subscribe(Greeks, wanted)

                quote_task = asyncio.create_task(streamer.get_event(Quote))
                greeks_task = asyncio.create_task(streamer.get_event(Greeks))
                tasks = {quote_task: Quote, greeks_task: Greeks}
                deadline = asyncio.get_running_loop().time() + timeout_seconds

                try:
                    while tasks and asyncio.get_running_loop().time() < deadline:
                        remaining = max(0.05, deadline - asyncio.get_running_loop().time())
                        done, pending = await asyncio.wait(
                            tasks.keys(),
                            timeout=remaining,
                            return_when=asyncio.FIRST_COMPLETED,
                        )
                        if not done:
                            break
                        for task in done:
                            event_class = tasks.pop(task)
                            event = task.result()
                            symbol = getattr(event, "event_symbol", None)
                            if symbol in out:
                                if event_class is Quote:
                                    bid = self._safe_float(getattr(event, "bid_price", None))
                                    ask = self._safe_float(getattr(event, "ask_price", None))
                                    out[symbol].update(
                                        {
                                            "bid": bid,
                                            "ask": ask,
                                            "mark": (bid + ask) / 2
                                            if not math.isnan(bid) and not math.isnan(ask)
                                            else math.nan,
                                            "spread": ask - bid
                                            if not math.isnan(bid) and not math.isnan(ask)
                                            else math.nan,
                                            "bid_size": self._safe_float(getattr(event, "bid_size", None)),
                                            "ask_size": self._safe_float(getattr(event, "ask_size", None)),
                                        }
                                    )
                                else:
                                    out[symbol].update(
                                        {
                                            "delta": self._safe_float(getattr(event, "delta", None)),
                                            "gamma": self._safe_float(getattr(event, "gamma", None)),
                                            "theta": self._safe_float(getattr(event, "theta", None)),
                                            "vega": self._safe_float(getattr(event, "vega", None)),
                                            "iv": self._safe_float(getattr(event, "volatility", None)),
                                        }
                                    )
                            tasks[asyncio.create_task(streamer.get_event(event_class))] = event_class

                            if all(out[s].get("bid") is not None and out[s].get("delta") is not None for s in wanted):
                                return out
                finally:
                    for task in tasks:
                        task.cancel()
                    if tasks:
                        await asyncio.gather(*tasks.keys(), return_exceptions=True)

        return out

    def _fetch_live_market_data(self, streamer_symbols):
        return self._run_async_blocking(
            self._fetch_live_market_data_async(streamer_symbols, self.live_quote_timeout_seconds)
        )

    def _apply_live_market_data(self, contract, market_data):
        streamer_symbol = self._contract_streamer_symbol(contract)
        if not streamer_symbol or streamer_symbol not in market_data:
            return dict(contract)
        merged = dict(contract)
        for key, value in market_data.get(streamer_symbol, {}).items():
            merged[key] = value
        return merged

    def _to_quote_dict(self, contract, option_type, underlying_price, provider="TASTYTRADE_CHAIN"):
        strike = int(float(contract.get("strike-price", 0)))
        bid = self._safe_float(contract.get("bid"))
        ask = self._safe_float(contract.get("ask"))
        mark_raw = contract.get("mark")
        mark = self._safe_float(mark_raw) if mark_raw is not None else (
            (bid + ask) / 2 if not math.isnan(bid) and not math.isnan(ask) else math.nan
        )
        spread = ask - bid if not math.isnan(ask) and not math.isnan(bid) else math.nan
        # An illiquid 0-DTE contract often returns 0/0 quotes. Treat that as
        # missing market data rather than a real $0.00 mark — otherwise the
        # downstream projection silently displays "guaranteed pennies" P/L.
        warning = None
        bid_zero = (not math.isnan(bid)) and bid <= 0.0
        ask_zero = (not math.isnan(ask)) and ask <= 0.0
        if bid_zero and ask_zero:
            mark = math.nan
            spread = math.nan
            warning = "No bid/ask available — strike may be illiquid."
        now = _central_now()
        return {
            "symbol": contract.get("symbol", f"SPY-{strike}-{option_type[0]}"),
            "underlying": "SPY",
            "expiration": contract.get("expiration-date"),
            "strike": strike,
            "option_type": option_type,
            "bid": bid,
            "ask": ask,
            "mark": mark,
            "spread": spread,
            "delta": self._safe_float(contract.get("delta")),
            "gamma": self._safe_float(contract.get("gamma")),
            "theta": self._safe_float(contract.get("theta")),
            "vega": self._safe_float(contract.get("vega")),
            "iv": self._safe_float(contract.get("iv")),
            "provider": provider,
            "timestamp": now,
            "warning": warning,
        }

    def get_selected_quotes(self, underlying_price, expiration_date, call_strike, put_strike):
        c,p,w = self.select_contracts("SPY", expiration_date, call_strike, put_strike)
        if not c or not p:
            self.status.quotes_ok = False
            return {"CALL": None, "PUT": None, "status": asdict(self.status), "warning": w or "Contract selection failed."}

        try:
            streamer_symbols = [self._contract_streamer_symbol(c), self._contract_streamer_symbol(p)]
            market_data = self._fetch_live_market_data(streamer_symbols)
            c = self._apply_live_market_data(c, market_data)
            p = self._apply_live_market_data(p, market_data)
        except Exception as e:
            market_data = {}
            self.status.last_error = f"Live quote stream failed: {type(e).__name__}"

        call_quote = self._to_quote_dict(c, "CALL", underlying_price)
        put_quote = self._to_quote_dict(p, "PUT", underlying_price)
        has_live_data = self._stream_returned_market_data(market_data)
        if has_live_data:
            call_quote["provider"] = "TASTYTRADE_LIVE"
            put_quote["provider"] = "TASTYTRADE_LIVE"

        self.status.quotes_ok = has_live_data
        self.status.using_live_quotes = has_live_data
        if has_live_data and self.status.last_error and self.status.last_error.startswith("Live quote stream failed:"):
            self.status.last_error = None
        self.status.connected = True
        self.status.last_update = _central_now()
        warning = w
        if not has_live_data:
            warning = "Contracts were found, but Tastytrade live bid/ask/Greek streaming did not return data yet."
        elif w:
            warning = w
        return {"CALL": call_quote, "PUT": put_quote, "status": asdict(self.status), "warning": warning}

    def get_status(self):
        return asdict(self.status)
