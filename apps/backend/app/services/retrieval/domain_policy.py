"""Trusted and excluded domain policies for retrieval."""

from __future__ import annotations


TRUSTED_DOMAINS = {
    "news_general": [
        "ansa.it",
        "reuters.com",
        "apnews.com",
        "bbc.com",
        "corriere.it",
    ],
    "finance_statistical": [
        "ilsole24ore.com",
        "bloomberg.com",
        "ft.com",
        "wsj.com",
        "bancaditalia.it",
        "istat.it",
    ],
    "fact_checking": [
        "pagellapolitica.it",
        "facta.news",
        "snopes.com",
        "politifact.com",
    ],
    "institutional": [
        "governo.it",
        "gazzettaufficiale.it",
        "europa.eu",
    ],
}

TIER1_DOMAINS = list(
    dict.fromkeys(domain for domains in TRUSTED_DOMAINS.values() for domain in domains)
)

BLACKLIST_DOMAINS = [
    "reddit.com",
    "quora.com",
    "medium.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
    "pinterest.com",
    "youtube.com",
    "linkedin.com",
    "tumblr.com",
    "wikipedia.org",
    "amazon.com",
    "ebay.com",
    "alibaba.com",
    "blogspot.com",
    "wordpress.com",
]
