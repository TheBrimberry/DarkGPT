"""Trend / social-intelligence adapter.

Live mode calls LunarCrush (social listening across X, TikTok, YouTube, Reddit
for topics & creators). Without a key, it returns a rich deterministic mock so
the intelligence dashboard is fully populated and demoable.
"""
from __future__ import annotations

import datetime as dt
from typing import Any

import requests

from ..config import settings
from .base import seeded_rng, with_fallback

CATEGORIES = [
    "entertainment", "politics", "tiktok", "influencers", "music", "tech",
    "sports", "gaming", "finance", "lifestyle", "news", "ai",
]

# Seed vocabulary used to synthesize believable trending topics per category.
_SEED_TOPICS: dict[str, list[str]] = {
    "entertainment": ["new blockbuster trailer", "celebrity feud", "awards season picks",
                       "streaming wars", "reboot announcement", "surprise album"],
    "politics": ["election polling shift", "policy debate", "viral campaign clip",
                 "town hall moment", "new bill reaction", "debate fact-check"],
    "tiktok": ["new dance challenge", "POV trend", "audio remix", "transition trick",
               "storytime format", "day-in-my-life vlogs"],
    "influencers": ["creator collab", "podcast drama", "brand-deal callout",
                    "subscriber milestone", "apology video", "morning routine"],
    "music": ["genre revival", "viral snippet", "festival lineup", "producer beef",
              "lyric trend", "slowed + reverb edit"],
    "tech": ["new AI model", "phone leak", "app shutdown", "gadget review",
             "privacy update", "open-source release"],
    "sports": ["upset victory", "trade rumor", "highlight reel", "rookie breakout",
               "coach decision", "playoff race"],
    "gaming": ["surprise drop", "patch backlash", "speedrun record", "esports upset",
               "remaster reveal", "crossover event"],
    "finance": ["market swing", "memecoin mania", "side-hustle trend", "rate decision",
                "budgeting hack", "layoff wave"],
    "lifestyle": ["wellness routine", "minimalist trend", "recipe hack", "travel hotspot",
                  "thrift haul", "productivity system"],
    "news": ["breaking update", "weather extreme", "human-interest story",
             "viral rescue", "local hero", "policy fallout"],
    "ai": ["agent demo", "image model update", "AI music tool", "deepfake debate",
           "coding copilot", "AI regulation"],
}


class TrendsProvider:
    def __init__(self) -> None:
        self.s = settings

    def trending(self, category: str = "all", limit: int = 12) -> dict:
        result, mocked = with_fallback(
            lambda: self._live(category, limit),
            lambda: self._mock(category, limit),
            label="trends",
        )
        result["_mock"] = mocked
        result["provider"] = self.s.provider_status()["trends"]
        return result

    def topic_detail(self, topic: str) -> dict:
        result, mocked = with_fallback(
            lambda: self._live_topic(topic),
            lambda: self._mock_topic(topic),
            label="trends.topic",
        )
        result["_mock"] = mocked
        return result

    # ── live (LunarCrush) ────────────────────────────────────────────────
    def _live(self, category: str, limit: int) -> dict:
        if not self.s.lunarcrush_api_key:
            raise RuntimeError("no lunarcrush key")
        headers = {"Authorization": f"Bearer {self.s.lunarcrush_api_key}"}
        r = requests.get(
            "https://lunarcrush.com/api4/public/topics/list/v1",
            headers=headers, timeout=self.s.request_timeout,
        )
        r.raise_for_status()
        rows = (r.json() or {}).get("data", [])[:limit]
        items = []
        for row in rows:
            items.append({
                "topic": row.get("topic") or row.get("title", "unknown"),
                "category": category,
                "interactions_24h": row.get("interactions_24h", 0),
                "sentiment": round(float(row.get("types_sentiment", {}).get("tweet", 60)) / 100, 2)
                if isinstance(row.get("types_sentiment"), dict) else 0.6,
                "momentum": _bucket(row.get("social_dominance", 1)),
                "velocity_pct": round(float(row.get("percent_change_24h", 0)), 1),
            })
        return {"category": category, "items": items, "source": "lunarcrush"}

    def _live_topic(self, topic: str) -> dict:
        if not self.s.lunarcrush_api_key:
            raise RuntimeError("no lunarcrush key")
        headers = {"Authorization": f"Bearer {self.s.lunarcrush_api_key}"}
        slug = topic.lower().strip().replace(" ", "-")
        r = requests.get(
            f"https://lunarcrush.com/api4/public/topic/{slug}/v1",
            headers=headers, timeout=self.s.request_timeout,
        )
        r.raise_for_status()
        d = (r.json() or {}).get("data", {})
        return {
            "topic": topic,
            "interactions_24h": d.get("interactions_24h", 0),
            "contributors": d.get("num_contributors", 0),
            "sentiment": 0.6,
            "source": "lunarcrush",
        }

    # ── mock ─────────────────────────────────────────────────────────────
    def _mock(self, category: str, limit: int) -> dict:
        cats = CATEGORIES if category in ("all", "", None) else [category]
        rng = seeded_rng("trending", category, _today())
        items: list[dict] = []
        for cat in cats:
            seeds = _SEED_TOPICS.get(cat, ["trending moment"])
            for seed in seeds:
                items.append(self._mk_item(cat, seed, rng))
        rng.shuffle(items)
        items.sort(key=lambda x: x["heat_score"], reverse=True)
        return {"category": category, "items": items[:limit], "source": "mock"}

    def _mk_item(self, category: str, seed: str, rng) -> dict:
        velocity = round(rng.uniform(-8, 95), 1)
        heat = max(1, min(100, int(50 + velocity * 0.4 + rng.uniform(-10, 25))))
        return {
            "topic": seed,
            "category": category,
            "heat_score": heat,
            "interactions_24h": rng.randint(40_000, 9_500_000),
            "creators_posting": rng.randint(120, 48_000),
            "sentiment": round(rng.uniform(0.35, 0.92), 2),
            "velocity_pct": velocity,
            "momentum": _bucket(heat / 25),
            "audience": rng.choice(["Gen Z", "Millennials", "Gen Z + Millennials", "Broad"]),
            "platforms": rng.sample(["TikTok", "Reels", "Shorts", "X", "YouTube"], k=3),
        }

    def _mock_topic(self, topic: str) -> dict:
        rng = seeded_rng("topic", topic.lower(), _today())
        velocity = round(rng.uniform(-5, 88), 1)
        return {
            "topic": topic,
            "heat_score": max(1, min(100, int(55 + velocity * 0.3))),
            "interactions_24h": rng.randint(50_000, 8_000_000),
            "contributors": rng.randint(200, 60_000),
            "sentiment": round(rng.uniform(0.4, 0.9), 2),
            "velocity_pct": velocity,
            "momentum": _bucket(velocity / 20),
            "related": rng.sample(
                ["explained", "reaction", "tier list", "predictions", "behind the scenes",
                 "vs", "tutorial", "tea", "ranked", "deep dive"], k=5),
            "top_formats": rng.sample(
                ["talking head", "green screen react", "voiceover b-roll",
                 "text-on-screen", "duet", "skit", "listicle"], k=3),
            "source": "mock",
        }


def _bucket(x: float) -> str:
    if x >= 3.5:
        return "exploding"
    if x >= 2:
        return "rising"
    if x >= 1:
        return "steady"
    return "cooling"


def _today() -> str:
    return dt.date.today().isoformat()
