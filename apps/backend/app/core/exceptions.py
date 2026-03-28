"""Custom exceptions for the Truth Engine pipeline."""

from __future__ import annotations


class TruthEngineError(Exception):
    """Base exception."""


class InputValidationError(TruthEngineError):
    """Raised when input fails validation."""


class PipelineStepError(TruthEngineError):
    """Raised when an individual pipeline step fails."""

    def __init__(self, step: str, message: str) -> None:
        self.step = step
        super().__init__(f"[{step}] {message}")


class ExternalServiceError(TruthEngineError):
    """Raised when an external API call fails."""

    def __init__(self, service: str, message: str) -> None:
        self.service = service
        super().__init__(f"External service '{service}': {message}")
