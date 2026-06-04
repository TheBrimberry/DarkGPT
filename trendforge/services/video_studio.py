"""The Studio — orchestrates every generation mode into finished video projects.

Modes:
  * generate_from_prompt   — a few words → a highly trendable video
  * remake_from_link       — an existing video URL → fresh remixed version
  * from_article           — an article/news URL → explainer video
  * music_video            — topic → song + music-video storyboard
  * educational            — topic → structured lesson / instructional video

Each mode produces a unified "project spec": storyboard, voiceover plan, music,
render plan, publish package and an explainable trend score. Everything degrades
gracefully to mock output so it works with zero API keys.
"""
from __future__ import annotations

import os

from ..config import settings
from ..providers import VideoProvider, MusicProvider, VoiceProvider, ScraperProvider, LLMProvider
from .storyboard import Storyboard
from .scoring import score_content
from .project_store import ProjectStore
from .trend_intelligence import TrendIntelligence

POSTER_DIR = os.path.join(settings.data_dir, "renders")


class VideoStudio:
    def __init__(self, store: ProjectStore | None = None) -> None:
        self.story = Storyboard()
        self.video = VideoProvider()
        self.music = MusicProvider()
        self.voice = VoiceProvider()
        self.scraper = ScraperProvider()
        self.llm = LLMProvider()
        self.intel = TrendIntelligence()
        self.store = store or ProjectStore()

    # ── 1. prompt → video ────────────────────────────────────────────────
    def generate_from_prompt(self, *, prompt: str, aspect: str = "9:16", tone: str = "energetic",
                             target_sec: int = 24, voice: str = "creator_hype",
                             style: str = "vibrant", platform: str = "TikTok",
                             want_music: bool = True) -> dict:
        heat = self._topic_heat(prompt)
        board = self.story.build(brief=prompt, tone=tone, target_sec=target_sec, aspect=aspect)
        return self._assemble(kind="prompt", title=_title(prompt),
                              prompt=prompt, board=board, aspect=aspect, style=style, voice=voice,
                              platform=platform, want_music=want_music, topic_heat=heat)

    # ── 2. remake an existing video from a link ──────────────────────────
    def remake_from_link(self, *, url: str, aspect: str = "9:16", tone: str = "energetic",
                         target_sec: int = 24, voice: str = "creator_hype",
                         style: str = "vibrant", platform: str = "TikTok",
                         angle: str = "fresh remix") -> dict:
        extracted = self.scraper.extract(url)
        brief = (f"Remake/remix this existing video as a NEW {angle}. "
                 f"Original title: {extracted.get('title')}. "
                 f"Original gist: {extracted.get('text', '')[:1200]}")
        heat = self._topic_heat(extracted.get("title", url))
        board = self.story.build(brief=brief, tone=tone, target_sec=target_sec, aspect=aspect)
        spec = self._assemble(kind="remake", title=f"Remake — {extracted.get('title', url)[:40]}",
                              prompt=angle, source_url=url, board=board, aspect=aspect, style=style,
                              voice=voice, platform=platform, want_music=True, topic_heat=heat)
        spec["spec"]["source"] = extracted
        return spec

    # ── 3. article / any info link → video ───────────────────────────────
    def from_article(self, *, url: str, aspect: str = "9:16", tone: str = "informative",
                     target_sec: int = 30, voice: str = "narrator_warm",
                     style: str = "clean", platform: str = "Reels") -> dict:
        extracted = self.scraper.extract(url)
        summary = self.llm.complete(
            f"Summarize this into a tight, punchy short-form video script with a hook, "
            f"3 key points and a CTA:\n\nTitle: {extracted.get('title')}\n\n{extracted.get('text', '')[:4000]}",
            system="You distill articles into viral short-form scripts.", max_tokens=500,
        )["text"]
        brief = f"Article explainer: {extracted.get('title')}. Script basis: {summary}"
        heat = self._topic_heat(extracted.get("title", url))
        board = self.story.build(brief=brief, tone=tone, target_sec=target_sec, aspect=aspect)
        spec = self._assemble(kind="article", title=extracted.get("title", url)[:50],
                              prompt=url, source_url=url, board=board, aspect=aspect, style=style,
                              voice=voice, platform=platform, want_music=False, topic_heat=heat)
        spec["spec"]["source"] = extracted
        spec["spec"]["article_summary"] = summary
        return spec

    # ── 4. music video / song ────────────────────────────────────────────
    def music_video(self, *, topic: str, genre: str = "auto", mood: str = "auto",
                   aspect: str = "9:16", target_sec: int = 60, style: str = "neon",
                   platform: str = "TikTok", song_only: bool = False) -> dict:
        song = self.music.compose(topic=topic, genre=genre, mood=mood,
                                  lyrics_theme=topic, duration_sec=target_sec)
        heat = self._topic_heat(topic)
        if song_only:
            score = score_content(hook=song.get("title", topic), caption=f"New track about {topic}",
                                  hashtags=["#newmusic", "#song", "#fyp"], duration_sec=target_sec,
                                  aspect=aspect, platform=platform, topic_heat=heat)
            spec = {"mode": "song", "song": song, "trend": score}
            saved = self.store.create(kind="song", spec=spec, title=song.get("title", topic),
                                      prompt=topic, trend_score=score["trend_score"])
            return saved
        brief = (f"Music video for a {song.get('genre')} {song.get('mood')} song titled "
                 f"'{song.get('title')}' about {topic}. Sync visuals to the song structure.")
        board = self.story.build(brief=brief, tone="cinematic", target_sec=target_sec, aspect=aspect)
        spec = self._assemble(kind="music_video", title=song.get("title", topic), prompt=topic,
                              board=board, aspect=aspect, style=style, voice="", platform=platform,
                              want_music=False, topic_heat=heat, attach_music=song)
        return spec

    # ── 5. educational / instructional ───────────────────────────────────
    def educational(self, *, topic: str, aspect: str = "16:9", target_sec: int = 90,
                   voice: str = "calm_explainer", style: str = "clean",
                   platform: str = "YouTube", level: str = "beginner") -> dict:
        outline = self.llm.json(
            f"Create an educational/instructional lesson outline about '{topic}' for a "
            f"{level} audience. Include title and sections with headings and points.",
            system="You are a master teacher who makes complex topics simple.",
        )["data"]
        brief = f"Educational explainer on {topic} ({level}). Outline: {outline}"
        heat = self._topic_heat(topic)
        board = self.story.build(brief=brief, tone="informative", target_sec=target_sec, aspect=aspect)
        otitle = outline.get("title") if isinstance(outline, dict) else None
        spec = self._assemble(kind="educational", title=otitle or _title(topic), prompt=topic,
                              board=board, aspect=aspect, style=style, voice=voice, platform=platform,
                              want_music=False, topic_heat=heat)
        spec["spec"]["lesson_outline"] = outline
        return spec

    # ── shared assembly ──────────────────────────────────────────────────
    def _assemble(self, *, kind, title, board, aspect, style, voice, platform,
                  want_music, topic_heat, prompt="", source_url="", attach_music=None) -> dict:
        scenes = board["scenes"]
        render = self.video.render(scenes=scenes, aspect=aspect, style=style,
                                   job_id=_jid(title), out_dir=POSTER_DIR)
        voiceover = None
        if voice:
            voiceover = self.voice.synthesize(text=board["script"], voice=voice)
        music = attach_music
        if want_music and music is None:
            music = self.music.compose(topic=title, genre="auto", mood="auto",
                                       lyrics_theme="", duration_sec=board["target_sec"])

        pkg = board.get("package", {})
        hook = board.get("hook", "")
        hashtags = pkg.get("hashtags", []) if isinstance(pkg, dict) else []
        caption = pkg.get("caption", "") if isinstance(pkg, dict) else ""
        score = score_content(hook=hook, caption=caption, hashtags=hashtags,
                              duration_sec=board["target_sec"], aspect=aspect,
                              platform=platform, topic_heat=topic_heat)

        spec = {
            "kind": kind,
            "aspect": aspect,
            "style": style,
            "platform": platform,
            "storyboard": board,
            "render": render,
            "voiceover": voiceover,
            "music": music,
            "publish": pkg,
            "trend": score,
            "poster_url": f"/renders/{render.get('poster')}" if render.get("poster") else None,
            "mock_notice": any([
                render.get("_mock"), (voiceover or {}).get("_mock"),
                (music or {}).get("_mock"),
            ]),
        }
        return self.store.create(kind=kind, spec=spec, title=title, prompt=prompt,
                                 source_url=source_url, trend_score=score["trend_score"])

    def _topic_heat(self, text: str) -> int:
        try:
            d = self.intel.trends.topic_detail(text)
            return int(d.get("heat_score", 55))
        except Exception:
            return 55


def _title(text: str) -> str:
    """A clean, human title derived from the user's own words."""
    import re
    t = re.sub(r"\s+", " ", (text or "").strip())
    t = t[:60].rstrip(" ,.-")
    return (t[:1].upper() + t[1:]) if t else "Untitled video"


def _jid(title: str) -> str:
    import re
    import uuid
    slug = re.sub(r"[^a-z0-9]+", "-", (title or "video").lower()).strip("-")[:24]
    return f"{slug or 'video'}-{uuid.uuid4().hex[:6]}"
