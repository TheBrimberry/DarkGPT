"""All JSON endpoints for TrendForge, grouped under /api."""
from __future__ import annotations

from flask import Blueprint, jsonify, request

from ..config import settings
from ..providers import VoiceProvider
from ..providers.trends import CATEGORIES
from ..providers.video import ASPECTS
from ..services.project_store import ProjectStore
from ..services.scoring import score_content
from ..services.trend_intelligence import TrendIntelligence
from ..services.trend_forecast import TrendForecast
from ..services.video_studio import VideoStudio

api = Blueprint("api", __name__)

_store = ProjectStore()
_intel = TrendIntelligence()
_forecast = TrendForecast()
_studio = VideoStudio(store=_store)
_voice = VoiceProvider()


def _body() -> dict:
    return request.get_json(silent=True) or {}


# ── meta ─────────────────────────────────────────────────────────────────
@api.get("/status")
def status():
    return jsonify({
        "app": "TrendForge",
        "version": "1.0.0",
        "providers": settings.provider_status(),
        "categories": CATEGORIES,
        "aspects": list(ASPECTS.keys()),
        "voices": _voice.voices(),
        "stats": _store.stats(),
    })


# ── trend intelligence ────────────────────────────────────────────────────
@api.get("/trends")
def trends():
    category = request.args.get("category", "all")
    limit = int(request.args.get("limit", 12))
    return jsonify(_intel.dashboard(category=category, limit=limit))


@api.get("/trends/topic")
def trend_topic():
    topic = request.args.get("q", "").strip()
    if not topic:
        return jsonify({"error": "missing ?q=topic"}), 400
    return jsonify(_intel.analyze_topic(topic))


@api.get("/forecast")
def forecast():
    category = request.args.get("category", "all")
    weeks = int(request.args.get("weeks", 4))
    limit = int(request.args.get("limit", 10))
    return jsonify(_forecast.forecast(category=category, horizon_weeks=weeks, limit=limit))


# ── video studio ──────────────────────────────────────────────────────────
@api.post("/generate")
def generate():
    b = _body()
    prompt = (b.get("prompt") or "").strip()
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    return jsonify(_studio.generate_from_prompt(
        prompt=prompt,
        aspect=b.get("aspect", "9:16"),
        tone=b.get("tone", "energetic"),
        target_sec=int(b.get("target_sec", 24)),
        voice=b.get("voice", "creator_hype"),
        style=b.get("style", "vibrant"),
        platform=b.get("platform", "TikTok"),
        want_music=bool(b.get("want_music", True)),
    ))


@api.post("/remake")
def remake():
    b = _body()
    url = (b.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    return jsonify(_studio.remake_from_link(
        url=url, aspect=b.get("aspect", "9:16"), tone=b.get("tone", "energetic"),
        target_sec=int(b.get("target_sec", 24)), voice=b.get("voice", "creator_hype"),
        style=b.get("style", "vibrant"), platform=b.get("platform", "TikTok"),
        angle=b.get("angle", "fresh remix"),
    ))


@api.post("/from-article")
def from_article():
    b = _body()
    url = (b.get("url") or "").strip()
    if not url:
        return jsonify({"error": "url is required"}), 400
    return jsonify(_studio.from_article(
        url=url, aspect=b.get("aspect", "9:16"), tone=b.get("tone", "informative"),
        target_sec=int(b.get("target_sec", 30)), voice=b.get("voice", "narrator_warm"),
        style=b.get("style", "clean"), platform=b.get("platform", "Reels"),
    ))


@api.post("/music-video")
def music_video():
    b = _body()
    topic = (b.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "topic is required"}), 400
    return jsonify(_studio.music_video(
        topic=topic, genre=b.get("genre", "auto"), mood=b.get("mood", "auto"),
        aspect=b.get("aspect", "9:16"), target_sec=int(b.get("target_sec", 60)),
        style=b.get("style", "neon"), platform=b.get("platform", "TikTok"),
        song_only=bool(b.get("song_only", False)),
    ))


@api.post("/educational")
def educational():
    b = _body()
    topic = (b.get("topic") or "").strip()
    if not topic:
        return jsonify({"error": "topic is required"}), 400
    return jsonify(_studio.educational(
        topic=topic, aspect=b.get("aspect", "16:9"), target_sec=int(b.get("target_sec", 90)),
        voice=b.get("voice", "calm_explainer"), style=b.get("style", "clean"),
        platform=b.get("platform", "YouTube"), level=b.get("level", "beginner"),
    ))


@api.post("/score")
def score():
    b = _body()
    return jsonify(score_content(
        hook=b.get("hook", ""), caption=b.get("caption", ""),
        hashtags=b.get("hashtags", []), duration_sec=int(b.get("duration_sec", 24)),
        aspect=b.get("aspect", "9:16"), platform=b.get("platform", "TikTok"),
        topic_heat=int(b.get("topic_heat", 55)), sentiment=float(b.get("sentiment", 0.6)),
    ))


# ── projects gallery ──────────────────────────────────────────────────────
@api.get("/projects")
def projects():
    kind = request.args.get("kind", "")
    limit = int(request.args.get("limit", 50))
    return jsonify({"projects": _store.list(kind=kind, limit=limit), "stats": _store.stats()})


@api.get("/projects/<pid>")
def project(pid):
    p = _store.get(pid)
    if not p:
        return jsonify({"error": "not found"}), 404
    return jsonify(p)


@api.delete("/projects/<pid>")
def delete_project(pid):
    return jsonify({"deleted": _store.delete(pid)})
