"""FEVER benchmark models."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FeverClaim(BaseModel):
    """A single FEVER dataset entry."""

    id: int
    claim: str
    label: str = ""  # SUPPORTS, REFUTES, NOT ENOUGH INFO
    evidence_sentence_ids: list[list] = Field(default_factory=list)
    evidence_page: str = ""


class FeverBenchmarkResult(BaseModel):
    """Evaluation result for a FEVER run."""

    total_claims: int = 0
    label_accuracy: float = 0.0
    evidence_recall: float = 0.0
    evidence_precision: float = 0.0
    partial_hit_rate: float = 0.0
    confusion_matrix: dict[str, dict[str, int]] = Field(default_factory=dict)
