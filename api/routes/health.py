from __future__ import annotations

from fastapi import APIRouter

from api.deps import tastytrade_configured
from api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    return HealthResponse(tastytrade_configured=tastytrade_configured())
