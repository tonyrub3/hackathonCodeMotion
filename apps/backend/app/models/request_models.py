"""Request models for the Truth Engine API."""

from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Literal


class VerifyRequest(BaseModel):
    """POST /api/verify request body."""

    input_type: Literal["text", "url"] = Field(
        default="text",
        description="Whether the content is plain text or a URL to fetch.",
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=50_000,
        description="The text to verify or the URL to analyse.",
    )
    language: str = Field(default="en", description="ISO-639-1 language code.")
    country: str = Field(default="", description="ISO-3166-1 alpha-2 country code.")
    topic: str = Field(
        default="",
        description="Optional topic hint (economy, politics, defense, …).",
    )
    mode: Literal["live", "benchmark"] = Field(
        default="live",
        description="Pipeline mode.",
    )
