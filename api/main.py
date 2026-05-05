from __future__ import annotations

import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import health as health_routes
from api.routes import journal as journal_routes
from api.routes import live as live_routes
from api.routes import options as options_routes
from api.routes import quotes as quotes_routes

logging.basicConfig(
    level=os.getenv("SPYPROPHET_LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("spyprophet.api")

_DEFAULT_ORIGINS = (
    "https://app.spyprophet.app",
    "https://spyprophet.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def _allowed_origins() -> list[str]:
    raw = os.getenv("SPYPROPHET_API_ALLOWED_ORIGINS", "").strip()
    if not raw:
        return list(_DEFAULT_ORIGINS)
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def create_app() -> FastAPI:
    app = FastAPI(
        title="SPY Prophet API",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_allowed_origins(),
        allow_credentials=False,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    app.include_router(health_routes.router, prefix="/api")
    app.include_router(quotes_routes.router, prefix="/api")
    app.include_router(live_routes.router, prefix="/api")
    app.include_router(options_routes.router, prefix="/api")
    app.include_router(journal_routes.router, prefix="/api")

    @app.get("/", include_in_schema=False)
    def root():
        return {"service": "spyprophet-api", "docs": "/api/docs"}

    return app


app = create_app()
