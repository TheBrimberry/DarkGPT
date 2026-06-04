"""Music / song adapter — Suno-style when keyed, structured mock otherwise.

The mock returns a full song spec (style, BPM, key, structured lyrics) so the
music-video and song features produce usable creative output with no key.
"""
from __future__ import annotations

import requests

from ..config import settings
from .base import seeded_rng, with_fallback

_GENRES = ["pop", "hip-hop", "lo-fi", "afrobeats", "synthwave", "trap", "indie",
           "edm", "r&b", "drill", "country", "phonk"]
_MOODS = ["uplifting", "dark", "dreamy", "energetic", "emotional", "chill", "epic"]


class MusicProvider:
    def __init__(self) -> None:
        self.s = settings

    def compose(self, *, topic: str, genre: str = "auto", mood: str = "auto",
                lyrics_theme: str = "", duration_sec: int = 60) -> dict:
        result, mocked = with_fallback(
            lambda: self._live(topic, genre, mood, lyrics_theme, duration_sec),
            lambda: self._mock(topic, genre, mood, lyrics_theme, duration_sec),
            label="music",
        )
        result["_mock"] = mocked
        result["provider"] = self.s.provider_status()["music"]
        return result

    def _live(self, topic, genre, mood, lyrics_theme, duration_sec) -> dict:
        if not self.s.suno_api_key:
            raise RuntimeError("no music key")
        r = requests.post(
            "https://api.suno.ai/v1/generate",
            headers={"Authorization": f"Bearer {self.s.suno_api_key}"},
            json={"prompt": f"{genre} {mood} song about {topic}: {lyrics_theme}",
                  "duration": duration_sec},
            timeout=self.s.request_timeout,
        )
        r.raise_for_status()
        d = r.json()
        return {"status": "processing", "track_id": d.get("id"), "source": "suno"}

    def _mock(self, topic, genre, mood, lyrics_theme, duration_sec) -> dict:
        rng = seeded_rng("song", topic, genre, mood, lyrics_theme)
        g = genre if genre not in ("auto", "", None) else rng.choice(_GENRES)
        m = mood if mood not in ("auto", "", None) else rng.choice(_MOODS)
        theme = lyrics_theme or topic
        hook = f"{theme.title()} — we don't stop, we don't fall"
        lyrics = {
            "intro": f"(soft pads, building {g} groove)",
            "verse_1": [
                f"Started with a thought about {theme.lower()}",
                "Now it's everything I am, everything I sought",
                "Lights down low but the feeling's getting loud",
                "Every single move, yeah, I'm doing it proud",
            ],
            "chorus": [hook, f"All about {theme.lower()}, can't tell me nothing at all",
                       hook, "Run it back, run it back, here we go"],
            "verse_2": [
                f"They said {theme.lower()} was a phase, it would fade",
                "Look at me now, every promise that I made",
                "Turning up the tempo, feel it in your chest",
                "This the kind of moment that they never could test",
            ],
            "bridge": [f"Even when it's quiet, {theme.lower()} stays alive", "Hold on tight"],
            "outro": "(beat fades, vocal chops)",
        }
        return {
            "status": "preview_ready",
            "track_id": f"mock_{rng.randint(10000, 99999)}",
            "title": f"{theme.title()} (Anthem)",
            "genre": g,
            "mood": m,
            "bpm": rng.choice([90, 100, 120, 128, 140, 150]),
            "key": rng.choice(["A minor", "C major", "F# minor", "G major", "E minor"]),
            "duration_sec": duration_sec,
            "structure": ["intro", "verse 1", "chorus", "verse 2", "chorus", "bridge", "chorus", "outro"],
            "lyrics": lyrics,
            "note": "Mock composition. Add SUNO_API_KEY for rendered audio.",
            "source": "mock",
        }
