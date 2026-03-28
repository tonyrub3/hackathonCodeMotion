"""Sentence splitter – breaks text into sentences."""

from __future__ import annotations

import re


def split_sentences(text: str) -> list[str]:
    """Split text into sentences using regex heuristics.

    Handles common abbreviations and decimal numbers to avoid
    false splits.
    """
    if not text:
        return []

    # Protect common abbreviations
    protected = text
    abbreviations = [
        "Mr.",
        "Mrs.",
        "Dr.",
        "Prof.",
        "Inc.",
        "Ltd.",
        "Sr.",
        "Jr.",
        "vs.",
        "etc.",
        "e.g.",
        "i.e.",
        "Dott.",
        "Dott.ssa.",
        "Sig.",
        "Sig.ra.",
        "Ing.",
        "Avv.",
        "On.",
        "S.p.A.",
    ]
    for abbr in abbreviations:
        protected = protected.replace(abbr, abbr.replace(".", "<DOT>"))

    # Protect decimal numbers (e.g., 3.14)
    protected = re.sub(r"(\d)\.([\d])", r"\1<DOT>\2", protected)

    # Split on sentence-ending punctuation followed by space + uppercase or newline
    parts = re.split(r'(?<=[.!?])\s+(?=[A-Z\u00C0-\u024F"])|(?<=\n)\s*(?=\S)', protected)

    # Restore dots
    sentences = [p.replace("<DOT>", ".").strip() for p in parts if p.strip()]
    return sentences
