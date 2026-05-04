from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    service: str = "spyprophet-api"
    version: str = "0.1.0"
    tastytrade_configured: bool


class OptionQuote(BaseModel):
    symbol: str
    underlying: str
    expiration: str | None
    strike: int
    option_type: Literal["CALL", "PUT"]
    bid: float | None
    ask: float | None
    mark: float | None
    spread: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None
    iv: float | None
    provider: str
    warning: str | None = None


class QuotePairResponse(BaseModel):
    underlying: str
    underlying_price: float | None
    expiration: str
    call: OptionQuote | None
    put: OptionQuote | None
    provider_status: dict
    warning: str | None = None


class SpotSnapshot(BaseModel):
    price: float | None = Field(None, description="Most recent SPY mark.")
    change: float | None = Field(None, description="Absolute change since prior session close.")
    change_pct: float | None = Field(None, description="Percent change since prior session close.")


class VixSnapshot(BaseModel):
    value: float | None
    regime: str | None = Field(None, description="Plain-language regime label, e.g. 'Calm'.")
    regime_tone: Literal["green", "amber", "red"] | None = None


class WatchStrikes(BaseModel):
    call: int | None
    put: int | None


class LiveSnapshot(BaseModel):
    spot: SpotSnapshot
    vix: VixSnapshot
    watch: WatchStrikes
    decision_label: str
    last_update: str
    # Fields below stay optional — populated incrementally as the briefing
    # composer is wired through. Live page renders gracefully without them.
    bias: dict | None = None
    signal: dict | None = None
    trigger: dict | None = None
    target: dict | None = None
    stop: float | None = None
    guardrails: list[dict] | None = None
    intel: list[dict] | None = None
