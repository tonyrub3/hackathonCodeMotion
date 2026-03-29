"""Helpers for readable per-layer pipeline logging."""

from __future__ import annotations


LAYER_LABELS = {
    "input": "INPUT",
    "claims": "CLAIMS",
    "query": "QUERY",
    "retrieval": "RETRIEVAL",
    "scoring": "SCORING",
    "analysis": "ANALYSIS",
    "assembly": "ASSEMBLY",
    "pipeline": "PIPELINE",
}


def layer_tag(layer: str) -> str:
    """Return a stable ASCII tag for a pipeline layer."""
    label = LAYER_LABELS.get(layer.lower(), layer.upper())
    return f"[{label}]"
