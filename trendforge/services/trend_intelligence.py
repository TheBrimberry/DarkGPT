"""Trend intelligence: what's hot now across social / entertainment / politics /
TikTok / influencers, plus a deeper drill-down and content angles per topic.
"""
from __future__ import annotations

from ..providers import TrendsProvider, LLMProvider


class TrendIntelligence:
    def __init__(self) -> None:
        self.trends = TrendsProvider()
        self.llm = LLMProvider()

    def dashboard(self, category: str = "all", limit: int = 12) -> dict:
        data = self.trends.trending(category=category, limit=limit)
        items = data["items"]
        if items:
            avg_heat = round(sum(i.get("heat_score", 0) for i in items) / len(items), 1)
            exploding = [i for i in items if i.get("momentum") == "exploding"]
        else:
            avg_heat, exploding = 0, []
        return {
            "category": category,
            "generated_for": "now",
            "summary": {
                "tracked": len(items),
                "avg_heat": avg_heat,
                "exploding_now": [i["topic"] for i in exploding[:5]],
                "data_source": data.get("source"),
            },
            "items": items,
            "_mock": data.get("_mock", False),
        }

    def analyze_topic(self, topic: str) -> dict:
        detail = self.trends.topic_detail(topic)
        angles = self.llm.json(
            f"Give 5 short-form video angles (caption package) for the topic '{topic}'. "
            "Include caption, hashtags, hooks, best_post_time, thumbnail_text.",
            system="You are a viral short-form content strategist.",
        )
        return {
            "topic": topic,
            "metrics": detail,
            "angles": angles["data"],
            "_mock": detail.get("_mock", False) or angles.get("_mock", False),
        }
