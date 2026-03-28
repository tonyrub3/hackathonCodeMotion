"""Source summary builder – human-readable summary of source trust decisions."""

from __future__ import annotations

from typing import Any


def build_source_summary(sources_used: list[dict[str, Any]], language: str = "en") -> list[str]:
    """Produce a list of human-readable explanations for each source's trust level."""
    summaries: list[str] = []
    language_key = _language_key(language)

    for src in sources_used:
        name = src.get("source_name", "Unknown")
        tier = src.get("tier", "C")
        score = src.get("source_reliability_score", 0.5)
        src_type = src.get("source_type", "news")

        tier_label = _tier_label(tier, language_key)
        source_label = _source_type_label(src_type, language_key)
        trust_note = _trust_note(score, language_key)

        if language_key == "it":
            summaries.append(
                f"{name} ({source_label}, livello {tier} - {tier_label}): "
                f"affidabilita {score:.2f} ({trust_note})"
            )
        else:
            summaries.append(
                f"{name} ({source_label}, tier {tier} - {tier_label}): "
                f"reliability {score:.2f} ({trust_note})"
            )

    return summaries


def _language_key(language: str) -> str:
    """Normalize the requested language to a supported key."""
    return "it" if (language or "").lower().startswith("it") else "en"


def _tier_label(tier: str, language_key: str) -> str:
    """Human-readable tier label."""
    labels = {
        "A": {"en": "primary/official", "it": "primaria/ufficiale"},
        "B": {"en": "trusted secondary", "it": "secondaria affidabile"},
        "C": {"en": "weak/indirect", "it": "debole/indiretta"},
    }
    return labels.get(tier, {"en": "unclassified", "it": "non classificata"}).get(language_key, "unclassified")


def _source_type_label(source_type: str, language_key: str) -> str:
    """Human-readable source type label."""
    labels = {
        "official": {"en": "official", "it": "ufficiale"},
        "factcheck": {"en": "fact-check", "it": "fact-check"},
        "news": {"en": "news", "it": "giornalistico"},
        "document": {"en": "document", "it": "documento"},
        "social_official": {"en": "official social", "it": "social ufficiale"},
    }
    return labels.get(source_type, {"en": source_type, "it": source_type}).get(language_key, source_type)


def _trust_note(score: float, language_key: str) -> str:
    """Human-readable reliability label."""
    if score >= 0.75:
        return "alta affidabilita" if language_key == "it" else "high reliability"
    if score >= 0.50:
        return "affidabilita moderata" if language_key == "it" else "moderate reliability"
    return "bassa affidabilita" if language_key == "it" else "low reliability"
