"""Video render adapter.

Live mode targets text/image-to-video APIs (Replicate, Runway, Pika). Without
keys it produces a deterministic "render plan" + a generated SVG poster so the
UI can show a real, viewable preview artifact for every job.
"""
from __future__ import annotations

import os
from typing import Any

import requests

from ..config import settings
from .base import seeded_rng, with_fallback

ASPECTS = {
    "9:16": (1080, 1920),   # TikTok / Reels / Shorts
    "16:9": (1920, 1080),   # YouTube / landscape
    "1:1": (1080, 1080),    # feed square
    "4:5": (1080, 1350),    # IG portrait
}


class VideoProvider:
    def __init__(self) -> None:
        self.s = settings

    def render(self, *, scenes: list[dict], aspect: str = "9:16", style: str = "cinematic",
               job_id: str = "job", out_dir: str | None = None) -> dict:
        result, mocked = with_fallback(
            lambda: self._live(scenes, aspect, style, job_id),
            lambda: self._mock(scenes, aspect, style, job_id, out_dir),
            label="video",
        )
        result["_mock"] = mocked
        result["provider"] = self.s.provider_status()["video"]
        return result

    # ── live ─────────────────────────────────────────────────────────────
    def _live(self, scenes, aspect, style, job_id) -> dict:
        token = self.s.replicate_api_token
        if not token:
            raise RuntimeError("no video key")
        prompt = " | ".join(s.get("visual", s.get("narration", "")) for s in scenes)[:1500]
        w, h = ASPECTS.get(aspect, ASPECTS["9:16"])
        # Replicate prediction (model id is illustrative & swappable via env later)
        r = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers={"Authorization": f"Token {token}", "Content-Type": "application/json"},
            json={
                "version": os.environ.get("REPLICATE_VIDEO_MODEL", "stability-ai/stable-video-diffusion"),
                "input": {"prompt": f"{style} style. {prompt}", "width": w, "height": h},
            },
            timeout=self.s.request_timeout,
        )
        r.raise_for_status()
        data = r.json()
        return {
            "status": "processing",
            "render_id": data.get("id"),
            "poll_url": (data.get("urls") or {}).get("get"),
            "aspect": aspect,
            "style": style,
            "source": "replicate",
        }

    # ── mock ─────────────────────────────────────────────────────────────
    def _mock(self, scenes, aspect, style, job_id, out_dir) -> dict:
        rng = seeded_rng(job_id, aspect, style, len(scenes))
        w, h = ASPECTS.get(aspect, ASPECTS["9:16"])
        duration = sum(int(s.get("duration_sec", 4)) for s in scenes) or 18
        poster_rel = None
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
            poster_path = os.path.join(out_dir, f"{job_id}.svg")
            _write_poster(poster_path, scenes, style, w, h, rng)
            poster_rel = os.path.basename(poster_path)
        return {
            "status": "preview_ready",
            "render_id": f"mock_{job_id}",
            "aspect": aspect,
            "dimensions": {"width": w, "height": h},
            "style": style,
            "duration_sec": duration,
            "scene_count": len(scenes),
            "poster": poster_rel,
            "note": "Mock render: storyboard + poster generated. Add a VIDEO_PROVIDER key for full MP4 output.",
            "source": "mock",
        }


_PALETTES = {
    "cinematic": ["#0f0c29", "#302b63", "#24243e"],
    "vibrant": ["#ff0844", "#ffb199", "#ff6a00"],
    "clean": ["#e0eafc", "#cfdef3", "#a1c4fd"],
    "neon": ["#000000", "#7928ca", "#ff0080"],
    "documentary": ["#232526", "#414345", "#1c1c1c"],
}


def _write_poster(path: str, scenes: list[dict], style: str, w: int, h: int, rng) -> None:
    pal = _PALETTES.get(style, _PALETTES["cinematic"])
    title = (scenes[0].get("on_screen_text") if scenes else "") or "TRENDFORGE"
    vw, vh = 1080, int(1080 * h / w)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{vw}" height="{vh}">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="{pal[0]}"/>
      <stop offset="50%" stop-color="{pal[1]}"/>
      <stop offset="100%" stop-color="{pal[2]}"/>
    </linearGradient>
  </defs>
  <rect width="{vw}" height="{vh}" fill="url(#g)"/>
  <circle cx="{rng.randint(100, vw)}" cy="{rng.randint(100, vh)}" r="220" fill="#ffffff" opacity="0.06"/>
  <circle cx="{rng.randint(100, vw)}" cy="{rng.randint(100, vh)}" r="320" fill="#ffffff" opacity="0.05"/>
  <text x="50%" y="46%" fill="#ffffff" font-family="Arial Black, Arial, sans-serif"
        font-size="78" font-weight="900" text-anchor="middle">{_esc(title[:22])}</text>
  <text x="50%" y="54%" fill="#ffffff" opacity="0.85" font-family="Arial" font-size="34"
        text-anchor="middle">{_esc(style.title())} • {len(scenes)} scenes</text>
  <text x="50%" y="95%" fill="#ffffff" opacity="0.7" font-family="Arial" font-size="26"
        text-anchor="middle">TrendForge preview</text>
</svg>'''
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(svg)


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
