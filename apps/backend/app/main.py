"""
Truth Engine – FastAPI application entry point.
"""

from __future__ import annotations

from pathlib import Path
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[3] / ".env")  # Load from project root

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings, load_settings
from app.utils.logger import setup_logging
from app.api.routes_health import router as health_router
from app.api.routes_verify import router as verify_router
from app.api.routes_benchmark import router as benchmark_router
from app.api.routes_debug import router as debug_router

import logging
logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Application factory."""
    setup_logging("DEBUG")
    settings = settings or load_settings()

    logger.info("=" * 60)
    logger.info("TRUTH ENGINE starting up")
    logger.info("=" * 60)
    logger.info("Regolo model:     %s", settings.regolo_model)
    logger.info("Query model:      %s", settings.regolo_query_model or settings.regolo_model)
    logger.info("Claim model:      %s", settings.regolo_claim_model or settings.regolo_model)
    logger.info("Crosscheck model: %s", settings.regolo_crosscheck_model or settings.regolo_model)
    logger.info("Scoring model:    %s", settings.regolo_scoring_model or settings.regolo_model)
    logger.info("Embedding model:  %s", settings.regolo_embedding_model)
    logger.info("Regolo API key:   %s", "SET" if settings.regolo_api_key else "MISSING")
    logger.info("Embed API key:    %s", "SET" if settings.regolo_embedding_api_key else "MISSING")
    logger.info("Google FC key:    %s", "SET" if settings.google_factcheck_api_key else "MISSING")
    logger.info("CORS origins:     %s", settings.cors_origins)
    logger.info("=" * 60)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        _app.state.settings = settings
        logger.info("Application ready – accepting requests")
        yield
        logger.info("Application shutting down")

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
