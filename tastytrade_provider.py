from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import math
import requests
from zoneinfo import ZoneInfo


@dataclass
class TastytradeProviderStatus:
    provider: str = "TASTYTRADE"
    connected: bool = False
    using_live_quotes: bool = False
    environment: str = "production"
    last_error: str | None = None
    last_update: object | None = None
    missing_secrets: list[str] = None
    auth_ok: bool = False
    chain_ok: bool = False
    quotes_ok: bool = False
    fallback_used: bool = False

    def __post_init__(self):
        if self.missing_secrets is None:
            self.missing_secrets = []


class TastytradeProvider:
    def __init__(self, client_id: str, client_secret: str, refresh_token: str, environment: str = "production"):
        self.client_id = client_id
        self.client_secret = client_secret
        self.refresh_token = refresh_token
        self.environment = environment
        self.access_token = None
        self.status = TastytradeProviderStatus(environment=environment)
        self.base = "https://api.tastytrade.com" if environment == "production" else "https://api.cert.tastytrade.com"

    def authenticate(self):
        try:
            resp = requests.post(f"{self.base}/oauth/token", data={"grant_type":"refresh_token","client_id":self.client_id,"client_secret":self.client_secret,"refresh_token":self.refresh_token}, timeout=10)
            if resp.status_code >= 400:
                self.status.last_error = f"Auth failed: {resp.status_code}"
                self.status.auth_ok = False
                return False
            data = resp.json()
            self.access_token = data.get("access_token")
            self.status.auth_ok = bool(self.access_token)
            self.status.connected = self.status.auth_ok
            return self.status.auth_ok
        except Exception as e:
            self.status.last_error = f"Auth exception: {type(e).__name__}"
            self.status.auth_ok = False
            return False

    def get_access_token(self):
        if not self.access_token:
            self.authenticate()
        return self.access_token

    def get_nested_option_chain(self, symbol, expiration_date):
        token = self.get_access_token()
        if not token:
            return None
        try:
            r = requests.get(f"{self.base}/instruments/equities/{symbol}/nested-option-chain", headers={"Authorization":f"Bearer {token}"}, timeout=10)
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
        if exp is None:
            self.status.chain_ok = False
            return None, None, "Expiration unavailable"

        def choose(side, strike):
            arr = exp.get(side, [])
            if not arr:
                return None, False
            exact = [x for x in arr if int(float(x.get("strike-price", 0))) == int(strike)]
            if exact:
                return exact[0], True
            nearest = min(arr, key=lambda x: abs(float(x.get("strike-price", 0)) - strike))
            return nearest, False

        c, ce = choose("calls", call_strike)
        p, pe = choose("puts", put_strike)
        warn = None if (ce and pe) else "Exact strike unavailable; nearest strike selected."
        return c, p, warn

    def _to_quote_dict(self, contract, option_type, underlying_price):
        strike = int(float(contract.get("strike-price", 0)))
        bid = float(contract.get("bid", math.nan)) if contract.get("bid") is not None else math.nan
        ask = float(contract.get("ask", math.nan)) if contract.get("ask") is not None else math.nan
        mark = float(contract.get("mark", math.nan)) if contract.get("mark") is not None else ((bid + ask) / 2 if not math.isnan(bid) and not math.isnan(ask) else math.nan)
        spread = ask - bid if not math.isnan(ask) and not math.isnan(bid) else math.nan
        now = datetime.now(tz=ZoneInfo("US/Central"))
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
            "delta": float(contract.get("delta", math.nan)) if contract.get("delta") is not None else math.nan,
            "gamma": float(contract.get("gamma", math.nan)) if contract.get("gamma") is not None else math.nan,
            "theta": float(contract.get("theta", math.nan)) if contract.get("theta") is not None else math.nan,
            "vega": float(contract.get("vega", math.nan)) if contract.get("vega") is not None else math.nan,
            "iv": float(contract.get("iv", math.nan)) if contract.get("iv") is not None else math.nan,
            "provider": "TASTYTRADE_LIVE",
            "timestamp": now,
            "warning": None,
        }

    def get_selected_quotes(self, underlying_price, expiration_date, call_strike, put_strike):
        c,p,w = self.select_contracts("SPY", expiration_date, call_strike, put_strike)
        if not c or not p:
            self.status.fallback_used = True
            self.status.quotes_ok = False
            return {"CALL": None, "PUT": None, "status": asdict(self.status), "warning": w or "Contract selection failed."}
        self.status.quotes_ok = True
        self.status.using_live_quotes = True
        self.status.connected = True
        self.status.last_update = datetime.now(tz=ZoneInfo("US/Central"))
        return {"CALL": self._to_quote_dict(c, "CALL", underlying_price), "PUT": self._to_quote_dict(p, "PUT", underlying_price), "status": asdict(self.status), "warning": w}

    def get_status(self):
        return asdict(self.status)
