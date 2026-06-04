"""Shared helpers for provider adapters.

The core idea: a provider tries its live implementation and, on *any* failure
(missing key, network error, rate limit, bad response), gracefully falls back
to a deterministic mock so the product never hard-crashes on a missing key.
"""
from __future__ import annotations

import hashlib
import logging
import random
from typing import Any, Callable

log = logging.getLogger("trendforge.providers")


def stable_seed(*parts: Any) -> int:
    """Deterministic integer seed derived from arbitrary inputs.

    Lets mock data look "alive" yet stay reproducible for a given prompt, so a
    user re-running the same request sees consistent (not random-flickering)
    output — important for things like trend scores and demo screenshots.
    """
    joined = "::".join(str(p) for p in parts)
    digest = hashlib.sha256(joined.encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def seeded_rng(*parts: Any) -> random.Random:
    return random.Random(stable_seed(*parts))


def with_fallback(live: Callable, mock: Callable, *, label: str):
    """Run ``live`` and fall back to ``mock`` on any exception.

    Returns a tuple ``(result, used_mock: bool)``.
    """
    try:
        result = live()
        if result is None:
            raise ValueError("live provider returned no result")
        return result, False
    except Exception as exc:  # noqa: BLE001 - intentional broad guard
        log.info("provider '%s' falling back to mock: %s", label, exc)
        return mock(), True


class ProviderResult(dict):
    """Dict subclass that also remembers whether a mock was used."""

    @property
    def is_mock(self) -> bool:
        return bool(self.get("_mock", False))
