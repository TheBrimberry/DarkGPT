"""Trend forecasting: which topics are likely to trend in the near future.

Combines current velocity signals from the trends provider with a momentum
model to project topics 1-4 weeks out, each with a confidence band, an expected
peak window, and a ready-to-shoot content angle. Explainable by design.
"""
from __future__ import annotations

import datetime as dt

from ..providers import TrendsProvider, LLMProvider
from ..providers.base import seeded_rng


class TrendForecast:
    def __init__(self) -> None:
        self.trends = TrendsProvider()
        self.llm = LLMProvider()

    def forecast(self, category: str = "all", horizon_weeks: int = 4, limit: int = 10) -> dict:
        snapshot = self.trends.trending(category=category, limit=max(limit * 2, 16))
        items = snapshot["items"]
        rng = seeded_rng("forecast", category, dt.date.today().isoformat())

        predictions = []
        for it in items:
            velocity = it.get("velocity_pct", 0)
            heat = it.get("heat_score", 50)
            # Projected trajectory: rising velocity + sub-peak heat = best upside.
            upside = velocity * 0.5 + (70 - min(heat, 70)) * 0.4 + rng.uniform(-8, 12)
            projected_heat = max(1, min(100, int(heat + upside)))
            confidence = max(0.25, min(0.95, 0.45 + velocity / 200 + rng.uniform(-0.1, 0.15)))
            weeks_out = max(1, min(horizon_weeks, int(round((100 - heat) / 25)) or 1))
            peak = dt.date.today() + dt.timedelta(weeks=weeks_out)
            if projected_heat <= heat:
                continue  # only surface topics expected to climb
            predictions.append({
                "topic": it["topic"],
                "category": it.get("category", category),
                "current_heat": heat,
                "projected_heat": projected_heat,
                "lift": projected_heat - heat,
                "confidence": round(confidence, 2),
                "trajectory": _traj(upside),
                "peak_window": peak.isoformat(),
                "weeks_out": weeks_out,
                "why": _why(velocity, heat),
                "content_angle": _angle(it["topic"]),
                "first_mover": projected_heat - heat > 18 and heat < 55,
            })

        predictions.sort(key=lambda p: (p["confidence"] * p["lift"]), reverse=True)
        predictions = predictions[:limit]
        return {
            "category": category,
            "horizon_weeks": horizon_weeks,
            "generated_at": dt.datetime.now().isoformat(timespec="minutes"),
            "predictions": predictions,
            "first_mover_picks": [p["topic"] for p in predictions if p["first_mover"]][:5],
            "_mock": snapshot.get("_mock", False),
            "method": "velocity + sub-peak heat momentum model",
        }


def _traj(upside: float) -> str:
    if upside > 22:
        return "breakout"
    if upside > 10:
        return "climbing"
    return "early"


def _why(velocity: float, heat: int) -> str:
    bits = []
    if velocity > 30:
        bits.append("fast 24h velocity")
    elif velocity > 0:
        bits.append("steady positive velocity")
    if heat < 55:
        bits.append("still pre-peak (room to grow)")
    else:
        bits.append("already warm")
    return ", ".join(bits) or "early signal"


def _angle(topic: str) -> str:
    return f"Be first: a 'what's coming with {topic}' explainer before it peaks."
