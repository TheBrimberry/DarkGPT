"""Publisher service — posts or schedules a saved project to social platforms.

Builds the caption from the project's publish package (caption + hashtags),
attaches the rendered media, picks a smart schedule slot when asked, hands off
to the auto-post provider, and records every post in history.
"""
from __future__ import annotations

from urllib.parse import urljoin

from ..config import settings
from ..providers import AutoPostProvider
from ..providers.autopost import suggest_schedule
from .project_store import ProjectStore


class Publisher:
    def __init__(self, store: ProjectStore | None = None) -> None:
        self.poster = AutoPostProvider()
        self.store = store or ProjectStore()

    def platforms(self) -> list[str]:
        return self.poster.platforms()

    def build_caption(self, project: dict, override: str = "") -> str:
        if override.strip():
            return override.strip()
        spec = project.get("spec", {})
        pkg = spec.get("publish") or (spec.get("storyboard") or {}).get("package") or {}
        caption = pkg.get("caption") or project.get("title", "")
        tags = pkg.get("hashtags") or []
        tag_str = " ".join(tags)
        full = f"{caption}\n\n{tag_str}".strip()
        return full

    def publish(self, *, project_id: str, platforms: list[str], caption: str = "",
                when: str = "now", base_url: str = "") -> dict:
        project = self.store.get(project_id)
        if not project:
            return {"error": "project not found"}

        platforms = [p for p in platforms if p] or [project.get("spec", {}).get("platform", "TikTok")]
        text = self.build_caption(project, caption)

        # Resolve media: turn the relative poster path into an absolute URL the
        # social API can fetch. (In mock mode this is informational only.)
        media_url = None
        poster = project.get("spec", {}).get("poster_url")
        if poster:
            media_url = urljoin(base_url, poster) if base_url else poster

        # Resolve schedule: "now" | "best" | explicit ISO datetime.
        schedule_time = None
        if when and when not in ("now", ""):
            schedule_time = suggest_schedule(platforms[0]) if when == "best" else when

        result = self.poster.post(
            caption=text, platforms=platforms, media_url=media_url,
            schedule_time=schedule_time, project_id=project_id,
        )

        record = self.store.create_post(
            project_id=project_id, platforms=platforms, caption=text,
            status=result.get("status", "published"), schedule_time=schedule_time,
            provider=result.get("provider", "mock"), results=result.get("results"),
        )
        return {
            "post": record,
            "result": result,
            "mock": result.get("_mock", False),
            "scheduled": bool(schedule_time),
        }

    def history(self, *, project_id: str = "", limit: int = 100) -> dict:
        return {
            "posts": self.store.list_posts(project_id=project_id, limit=limit),
            "stats": self.store.post_stats(),
            "provider": settings.provider_status()["autopost"],
        }
