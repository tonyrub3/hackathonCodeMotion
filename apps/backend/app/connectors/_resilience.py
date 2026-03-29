"""Shared resilience utilities for connector calls."""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any


_CACHE: dict[str, tuple[float, Any]] = {}


def _stable_serialize(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def build_cache_key(namespace: str, payload: dict[str, Any]) -> str:
    raw = f"{namespace}:{_stable_serialize(payload)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"{namespace}:{digest}"


def cache_get(cache_key: str) -> Any | None:
    now = time.time()
    entry = _CACHE.get(cache_key)
    if not entry:
        return None
    expires_at, value = entry
    if expires_at <= now:
        _CACHE.pop(cache_key, None)
        return None
    return value


def cache_set(cache_key: str, value: Any, ttl_seconds: int) -> None:
    if ttl_seconds <= 0:
        return
    _CACHE[cache_key] = (time.time() + ttl_seconds, value)


@dataclass
class CircuitBreaker:
    """Simple in-memory circuit breaker for flaky external providers."""

    name: str
    failure_threshold: int = 3
    recovery_timeout_seconds: int = 60
    failures: int = 0
    opened_at: float | None = None

    def is_open(self) -> bool:
        if self.opened_at is None:
            return False
        if time.time() - self.opened_at >= self.recovery_timeout_seconds:
            # Half-open state: allow one probe request.
            self.opened_at = None
            self.failures = 0
            return False
        return True

    def record_success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def record_failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_threshold:
            self.opened_at = time.time()
