"""Video render adapter.

Live mode targets text/image-to-video APIs (Replicate, Runway, Pika). Without
keys it produces a deterministic "render plan" + a generated SVG poster so the
UI can show a real, viewable preview artifact for every job.
"""
from __future__ import annotations

import base64
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
        # Self-contained data-URI poster: renders anywhere (incl. read-only /
        # ephemeral serverless filesystems) with no file to serve.
        svg = _build_svg(scenes, style, w, h, rng)
        poster = "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return {
            "status": "preview_ready",
            "render_id": f"mock_{job_id}",
            "aspect": aspect,
            "dimensions": {"width": w, "height": h},
            "style": style,
            "duration_sec": duration,
            "scene_count": len(scenes),
            "poster": poster,
            "note": "Mock render: storyboard + poster generated. Add a VIDEO_PROVIDER key for full MP4 output.",
            "source": "mock",
        }


_PALETTES = {
    "cinematic": ["#0f0c29", "#302b63", "#24243e"],
    "vibrant": ["#ff0844", "#ffb199", "#ff6a00"],
    "clean": ["#e0eafc", "#cfdef3", "#a1c4fd"],
    "neon": ["#000000", "#7928ca", "#ff0080"],
    "documentary": ["#232526", "#414345", "#1c1c1c"],
    "brainrot": ["#1a0033", "#ff00d4", "#00ff88"],
}


def _build_svg(scenes: list[dict], style: str, w: int, h: int, rng) -> str:
    title = (scenes[0].get("on_screen_text") if scenes else "") or "TRENDFORGE"
    vw, vh = 1080, int(1080 * h / w)
    if style == "brainrot":
        return _brainrot_svg(title, vw, vh, rng)
    return _standard_svg(title, style, len(scenes), vw, vh, rng)


def _standard_svg(title: str, style: str, n_scenes: int, vw: int, vh: int, rng) -> str:
    pal = _PALETTES.get(style, _PALETTES["cinematic"])
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{vw}" height="{vh}">
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
        text-anchor="middle">{_esc(style.title())} • {n_scenes} scenes</text>
  <text x="50%" y="95%" fill="#ffffff" opacity="0.7" font-family="Arial" font-size="26"
        text-anchor="middle">TrendForge preview</text>
</svg>'''


def _brainrot_svg(title: str, vw: int, vh: int, rng) -> str:
    """The classic brainrot split-screen look: chaotic top half + 'gameplay'
    bottom half, with a giant impact caption and scattered emojis."""
    mid = vh // 2
    emojis = "".join(
        f'<text x="{rng.randint(60, vw-60)}" y="{rng.randint(120, vh-120)}" '
        f'font-size="{rng.randint(48, 110)}" opacity="0.85">{e}</text>'
        for e in rng.sample(["💀", "🔥", "😭", "🤯", "🗿", "💯", "🧠", "👹", "⁉️", "✨"], 6)
    )
    # word-wrap the caption into up to 3 punchy lines
    words = (title or "BRAINROT").upper().split()
    lines, cur = [], ""
    for wd in words:
        if len(cur + " " + wd) > 14 and cur:
            lines.append(cur); cur = wd
        else:
            cur = (cur + " " + wd).strip()
    if cur:
        lines.append(cur)
    lines = lines[:3] or ["BRAINROT"]
    fs = 96 if max(len(l) for l in lines) <= 10 else 74
    y0 = mid - (len(lines) - 1) * fs / 2
    caption = "".join(
        f'<text x="50%" y="{y0 + i*fs}" fill="#ffffff" stroke="#000000" stroke-width="9" '
        f'paint-order="stroke" font-family="Arial Black, Impact, sans-serif" font-size="{fs}" '
        f'font-weight="900" text-anchor="middle">{_esc(l)}</text>'
        for i, l in enumerate(lines)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{vw}" height="{vh}">
  <defs>
    <linearGradient id="top" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1a0033"/><stop offset="50%" stop-color="#ff00d4"/>
      <stop offset="100%" stop-color="#7928ca"/>
    </linearGradient>
    <linearGradient id="bot" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#00ff88"/><stop offset="50%" stop-color="#0066ff"/>
      <stop offset="100%" stop-color="#00ffcc"/>
    </linearGradient>
  </defs>
  <rect width="{vw}" height="{mid}" fill="url(#top)"/>
  <rect y="{mid}" width="{vw}" height="{vh-mid}" fill="url(#bot)"/>
  <!-- fake 'gameplay' lanes in the bottom half -->
  <g opacity="0.25">
    <rect x="{vw*0.25}" y="{mid}" width="6" height="{vh-mid}" fill="#fff"/>
    <rect x="{vw*0.5}" y="{mid}" width="6" height="{vh-mid}" fill="#fff"/>
    <rect x="{vw*0.75}" y="{mid}" width="6" height="{vh-mid}" fill="#fff"/>
  </g>
  <rect x="{vw*0.42}" y="{mid+120}" width="{vw*0.16}" height="{vw*0.16}" rx="20" fill="#ffeb3b" opacity="0.9"/>
  {emojis}
  {caption}
  <text x="50%" y="{vh-70}" fill="#000" stroke="#fff" stroke-width="5" paint-order="stroke"
        font-family="Arial Black, sans-serif" font-size="34" font-weight="900"
        text-anchor="middle">🔊 original sound - trendforge</text>
</svg>'''


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
