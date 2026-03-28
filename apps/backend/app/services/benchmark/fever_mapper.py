"""FEVER label mapper – maps between FEVER labels and Truth Engine verdicts."""

from __future__ import annotations

# FEVER → Truth Engine
FEVER_TO_VERDICT: dict[str, str] = {
    "SUPPORTS": "verified",
    "REFUTES": "disputed",
    "NOT ENOUGH INFO": "insufficient_evidence",
}

# Truth Engine → FEVER (for evaluation)
VERDICT_TO_FEVER: dict[str, str] = {
    "verified": "SUPPORTS",
    "mostly_verified": "SUPPORTS",
    "mixed": "NOT ENOUGH INFO",
    "misleading": "REFUTES",
    "decontextualized": "NOT ENOUGH INFO",
    "insufficient_evidence": "NOT ENOUGH INFO",
    "mostly_false": "REFUTES",
    "false": "REFUTES",
}


def fever_label_to_verdict(fever_label: str) -> str:
    """Map a FEVER label to a Truth Engine verdict."""
    return FEVER_TO_VERDICT.get(fever_label, "insufficient_evidence")


def verdict_to_fever_label(verdict: str) -> str:
    """Map a Truth Engine verdict to a FEVER label."""
    return VERDICT_TO_FEVER.get(verdict, "NOT ENOUGH INFO")
