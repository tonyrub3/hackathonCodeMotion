"""
Configuration module for Truth Engine backend.
Loads settings from environment variables with sensible defaults.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """Application-wide settings loaded from environment."""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # Regolo / LLM
    regolo_api_key: str = ""
    regolo_base_url: str = "https://api.regolo.ai/v1"
    regolo_model: str = "regolo/regolo-default"
    regolo_query_model: str = ""
    regolo_claim_model: str = ""
    regolo_crosscheck_model: str = ""
    regolo_scoring_model: str = ""
    regolo_embedding_api_key: str = ""
    regolo_embedding_model: str = "regolo/embedding-default"

    # Google Fact Check
    google_factcheck_api_key: str = ""
    google_factcheck_base_url: str = "https://factchecktools.googleapis.com/v1alpha1"

    # GDELT
    gdelt_doc_api_url: str = "https://api.gdeltproject.org/api/v2/doc/doc"
    gdelt_context_api_url: str = "https://api.gdeltproject.org/api/v2/context/context"

    # FEVER
    fever_data_dir: str = "data/fever"

    # Pipeline
    max_claims_per_request: int = 20
    max_evidence_per_claim: int = 10
    request_timeout_seconds: int = 0
    use_alethea_mvp_discovery: bool = True

    # CORS
    cors_origins: list[str] = field(default_factory=lambda: ["http://localhost:3000"])


def load_settings() -> Settings:
    """Build Settings from environment variables."""
    return Settings(
        host=os.getenv("TE_HOST", "0.0.0.0"),
        port=int(os.getenv("TE_PORT", "8000")),
        debug=os.getenv("TE_DEBUG", "true").lower() == "true",
        regolo_api_key=os.getenv("REGOLO_API_KEY", ""),
        regolo_base_url=os.getenv("REGOLO_BASE_URL", "https://api.regolo.ai/v1"),
        regolo_model=os.getenv("REGOLO_MODEL", "regolo/regolo-default"),
        regolo_query_model=os.getenv("REGOLO_QUERY_MODEL", ""),
        regolo_claim_model=os.getenv("REGOLO_CLAIM_MODEL", ""),
        regolo_crosscheck_model=os.getenv("REGOLO_CROSSCHECK_MODEL", ""),
        regolo_scoring_model=os.getenv("REGOLO_SCORING_MODEL", ""),
        regolo_embedding_api_key=os.getenv("REGOLO_EMBEDDING_API_KEY", ""),
        regolo_embedding_model=os.getenv("REGOLO_EMBEDDING_MODEL", "regolo/embedding-default"),
        google_factcheck_api_key=os.getenv("GOOGLE_FACTCHECK_API_KEY", ""),
        gdelt_doc_api_url=os.getenv("GDELT_DOC_API_URL", "https://api.gdeltproject.org/api/v2/doc/doc"),
        gdelt_context_api_url=os.getenv("GDELT_CONTEXT_API_URL", "https://api.gdeltproject.org/api/v2/context/context"),
        fever_data_dir=os.getenv("FEVER_DATA_DIR", "data/fever"),
        max_claims_per_request=int(os.getenv("TE_MAX_CLAIMS", "20")),
        max_evidence_per_claim=int(os.getenv("TE_MAX_EVIDENCE", "10")),
        request_timeout_seconds=int(os.getenv("TE_TIMEOUT", "0")),
        use_alethea_mvp_discovery=os.getenv("TE_USE_ALETHEA_MVP_DISCOVERY", "true").lower() == "true",
        cors_origins=os.getenv("TE_CORS_ORIGINS", "http://localhost:3000").split(","),
    )
