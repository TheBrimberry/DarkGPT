"""Voiceover / TTS adapter — ElevenLabs when keyed, plan-only mock otherwise."""
from __future__ import annotations

import requests

from ..config import settings
from .base import seeded_rng, with_fallback

VOICES = [
    {"id": "narrator_warm", "name": "Atlas", "style": "warm documentary", "gender": "m"},
    {"id": "creator_hype", "name": "Nova", "style": "high-energy creator", "gender": "f"},
    {"id": "calm_explainer", "name": "Sage", "style": "calm explainer", "gender": "n"},
    {"id": "news_anchor", "name": "Reed", "style": "authoritative news", "gender": "m"},
    {"id": "gen_z", "name": "Remi", "style": "casual gen-z", "gender": "f"},
]


class VoiceProvider:
    def __init__(self) -> None:
        self.s = settings

    def voices(self) -> list[dict]:
        return VOICES

    def synthesize(self, *, text: str, voice: str = "creator_hype", out_path: str | None = None) -> dict:
        result, mocked = with_fallback(
            lambda: self._live(text, voice, out_path),
            lambda: self._mock(text, voice),
            label="voice",
        )
        result["_mock"] = mocked
        result["provider"] = self.s.provider_status()["voice"]
        return result

    def _live(self, text, voice, out_path) -> dict:
        if not self.s.elevenlabs_api_key:
            raise RuntimeError("no tts key")
        r = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice}",
            headers={"xi-api-key": self.s.elevenlabs_api_key, "Content-Type": "application/json"},
            json={"text": text, "model_id": "eleven_multilingual_v2"},
            timeout=self.s.request_timeout,
        )
        r.raise_for_status()
        if out_path:
            with open(out_path, "wb") as fh:
                fh.write(r.content)
        return {"status": "ready", "audio": out_path, "voice": voice, "source": "elevenlabs"}

    def _mock(self, text, voice) -> dict:
        rng = seeded_rng("tts", voice, text[:40])
        words = max(1, len(text.split()))
        return {
            "status": "preview_ready",
            "voice": voice,
            "estimated_seconds": round(words / 2.6, 1),  # ~155 wpm
            "word_count": words,
            "waveform_seed": rng.randint(1000, 9999),
            "note": "Mock voiceover. Add ELEVENLABS_API_KEY for real audio.",
            "source": "mock",
        }
