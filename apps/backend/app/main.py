"""
Truth Engine – FastAPI application entry point.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, load_settings
from app.api.routes_health import router as health_router
from app.api.routes_verify import router as verify_router
from app.api.routes_benchmark import router as benchmark_router
from app.api.routes_debug import router as debug_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory."""
    settings = settings or load_settings()

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        # Startup: store settings in app state for DI
        _app.state.settings = settings
        yield
        # Shutdown: cleanup if needed

    app = FastAPI(
        title="Truth Engine",
        version="0.1.0",
        description="Explainable, source-traced fact-checking system",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(health_router, prefix="/api")
    app.include_router(verify_router, prefix="/api")
    app.include_router(benchmark_router, prefix="/api/benchmark")
    app.include_router(debug_router, prefix="/api/debug")

    return app


app = create_app()
