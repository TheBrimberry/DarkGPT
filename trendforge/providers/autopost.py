"""Auto-posting / distribution adapter.

Publishes (or schedules) a finished video to multiple social platforms through
a single call. Live mode targets Ayrshare (one API for TikTok, Instagram Reels,
YouTube Shorts, X, Facebook, LinkedIn, etc.); without a key it returns a
realistic mock so the publish flow is fully demoable end-to-end.
"""
from __future__ import annotations

import datetime as dt

import requests

from ..config import settings
from .base import seeded_rng, with_fallback

# Platforms we expose in the UI -> Ayrshare platform identifiers.
PLATFORMS = {
    "TikTok": "tiktok",
    "Reels": "instagram",
    "Shorts": "youtube",
    "Instagram": "instagram",
    "YouTube": "youtube",
    "X": "twitter",
    "Facebook": "facebook",
    "LinkedIn": "linkedin",
}

# Rough "best time to post" heuristics (local time) per platform.
_BEST_TIMES = {
    "TikTok": ["7:00 PM", "9:00 PM", "12:00 PM"],
    "Reels": ["11:00 AM", "7:30 PM", "9:00 PM"],
    "Instagram": ["11:00 AM", "7:30 PM"],
    "Shorts": ["3:00 PM", "8:00 PM"],
    "YouTube": ["2:00 PM", "8:00 PM"],
    "X": ["9:00 AM", "12:00 PM", "6:00 PM"],
    "Facebook": ["1:00 PM", "8:00 PM"],
    "LinkedIn": ["8:00 AM", "12:00 PM"],
}


class AutoPostProvider:
    def __init__(self) -> None:
        self.s = settings

    def platforms(self) -> list[str]:
        return list(PLATFORMS.keys())

    def best_time(self, platform: str) -> str:
        return (_BEST_TIMES.get(platform) or ["7:00 PM"])[0]

    def post(self, *, caption: str, platforms: list[str], media_url: str | None = None,
             schedule_time: str | None = None, project_id: str = "") -> dict:
        platforms = [p for p in platforms if p in PLATFORMS] or ["TikTok"]
        result, mocked = with_fallback(
            lambda: self._live(caption, platforms, media_url, schedule_time),
            lambda: self._mock(caption, platforms, media_url, schedule_time, project_id),
            label="autopost",
        )
        result["_mock"] = mocked
        result["provider"] = self.s.provider_status()["autopost"]
        return result

    # ── live (Ayrshare) ──────────────────────────────────────────────────
    def _live(self, caption, platforms, media_url, schedule_time) -> dict:
        if not self.s.ayrshare_api_key:
            raise RuntimeError("no autopost key")
        payload: dict = {
            "post": caption,
            "platforms": [PLATFORMS[p] for p in platforms],
        }
        if media_url:
            payload["mediaUrls"] = [media_url]
        if schedule_time:
            payload["scheduleDate"] = schedule_time  # ISO 8601
        r = requests.post(
            "https://app.ayrshare.com/api/post",
            headers={"Authorization": f"Bearer {self.s.ayrshare_api_key}",
                     "Content-Type": "application/json"},
            json=payload, timeout=self.s.request_timeout,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "status": "scheduled" if schedule_time else "published",
            "ref_id": data.get("id"),
            "platforms": platforms,
            "schedule_time": schedule_time,
            "results": data.get("postIds", data),
            "source": "ayrshare",
        }

    # ── mock ─────────────────────────────────────────────────────────────
    def _mock(self, caption, platforms, media_url, schedule_time, project_id) -> dict:
        rng = seeded_rng("post", project_id, caption[:40], schedule_time or "now")
        status = "scheduled" if schedule_time else "published"
        results = []
        for p in platforms:
            pid = f"{p.lower()}_{rng.randint(10**9, 10**10)}"
            results.append({
                "platform": p,
                "status": status,
                "post_id": pid,
                "permalink": f"https://{PLATFORMS[p]}.example/p/{pid}",
                "suggested_time": self.best_time(p),
            })
        return {
            "status": status,
            "ref_id": f"mock_{rng.randint(10000, 99999)}",
            "platforms": platforms,
            "schedule_time": schedule_time,
            "results": results,
            "media_attached": bool(media_url),
            "note": "Mock publish. Add AYRSHARE_API_KEY to post for real.",
            "source": "mock",
        }


def suggest_schedule(platform: str, days_ahead: int = 0) -> str:
    """Return an ISO datetime at the platform's next best posting slot."""
    best = (_BEST_TIMES.get(platform) or ["19:00"])[0]
    # parse "7:00 PM" -> hour/min
    try:
        t = dt.datetime.strptime(best, "%I:%M %p")
        hour, minute = t.hour, t.minute
    except Exception:
        hour, minute = 19, 0
    when = dt.datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    if days_ahead:
        when += dt.timedelta(days=days_ahead)
    elif when <= dt.datetime.now():
        when += dt.timedelta(days=1)
    return when.isoformat(timespec="minutes")
