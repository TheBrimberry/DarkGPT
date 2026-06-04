"""Central configuration and feature-flag resolution for TrendForge.

Reads everything from environment variables (loaded from a local .env when
python-dotenv is available). No key is *required*: when a provider's key is
absent the corresponding adapter transparently uses its mock implementation.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

try:  # optional, never fatal
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - dotenv is optional
    pass


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _flag(name: str, default: bool = False) -> bool:
    val = _env(name, str(default)).lower()
    return val in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    # ── Server ────────────────────────────────────────────────────────────
    host: str = field(default_factory=lambda: _env("TF_HOST", "0.0.0.0"))
    port: int = field(default_factory=lambda: int(_env("TF_PORT", "5050") or 5050))
    debug: bool = field(default_factory=lambda: _flag("TF_DEBUG", True))
    secret_key: str = field(default_factory=lambda: _env("TF_SECRET_KEY", "trendforge-dev-secret"))
    data_dir: str = field(default_factory=lambda: _env("TF_DATA_DIR", os.path.join(os.path.dirname(__file__), "data")))

    # ── LLM (text / scripts / analysis) ──────────────────────────────────
    llm_provider: str = field(default_factory=lambda: _env("LLM_PROVIDER", "auto"))
    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-4o-mini"))
    groq_api_key: str = field(default_factory=lambda: _env("GROQ_API_KEY"))
    groq_model: str = field(default_factory=lambda: _env("GROQ_MODEL", "llama-3.3-70b-versatile"))

    # ── Trend / social intelligence ──────────────────────────────────────
    lunarcrush_api_key: str = field(default_factory=lambda: _env("LUNARCRUSH_API_KEY"))
    youtube_api_key: str = field(default_factory=lambda: _env("YOUTUBE_API_KEY"))

    # ── Video render ─────────────────────────────────────────────────────
    video_provider: str = field(default_factory=lambda: _env("VIDEO_PROVIDER", "auto"))
    replicate_api_token: str = field(default_factory=lambda: _env("REPLICATE_API_TOKEN"))
    runway_api_key: str = field(default_factory=lambda: _env("RUNWAY_API_KEY"))
    pika_api_key: str = field(default_factory=lambda: _env("PIKA_API_KEY"))

    # ── Music / song ─────────────────────────────────────────────────────
    music_provider: str = field(default_factory=lambda: _env("MUSIC_PROVIDER", "auto"))
    suno_api_key: str = field(default_factory=lambda: _env("SUNO_API_KEY"))

    # ── Voiceover / TTS ──────────────────────────────────────────────────
    tts_provider: str = field(default_factory=lambda: _env("TTS_PROVIDER", "auto"))
    elevenlabs_api_key: str = field(default_factory=lambda: _env("ELEVENLABS_API_KEY"))

    # ── Misc ─────────────────────────────────────────────────────────────
    request_timeout: int = field(default_factory=lambda: int(_env("TF_HTTP_TIMEOUT", "20") or 20))

    def provider_status(self) -> dict:
        """A human-readable map of which capabilities are live vs mocked."""
        return {
            "llm": "openai" if self.openai_api_key else ("groq" if self.groq_api_key else "mock"),
            "trends": "lunarcrush" if self.lunarcrush_api_key else "mock",
            "video": "replicate" if self.replicate_api_token else (
                "runway" if self.runway_api_key else ("pika" if self.pika_api_key else "mock")
            ),
            "music": "suno" if self.suno_api_key else "mock",
            "voice": "elevenlabs" if self.elevenlabs_api_key else "mock",
        }


settings = Settings()
