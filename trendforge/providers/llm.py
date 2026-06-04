"""LLM adapter — OpenAI or Groq when configured, deterministic mock otherwise.

Exposes a single ``complete()`` that returns text and a ``json()`` helper that
coaxes structured output. The mock is intentionally capable: it can produce
believable scripts, hooks, captions and outlines so downstream features work.
"""
from __future__ import annotations

import json
import re
from typing import Any

from ..config import settings
from .base import seeded_rng, with_fallback


class LLMProvider:
    def __init__(self) -> None:
        self.s = settings

    # ── public API ───────────────────────────────────────────────────────
    def complete(self, prompt: str, *, system: str = "", max_tokens: int = 900,
                 temperature: float = 0.7) -> dict:
        result, mocked = with_fallback(
            lambda: self._live(prompt, system, max_tokens, temperature),
            lambda: self._mock(prompt, system),
            label="llm",
        )
        return {"text": result, "_mock": mocked, "provider": self.s.provider_status()["llm"]}

    def json(self, prompt: str, *, system: str = "", max_tokens: int = 1200) -> dict:
        out = self.complete(
            prompt + "\n\nRespond ONLY with valid minified JSON, no prose.",
            system=system or "You are a precise assistant that returns strict JSON.",
            max_tokens=max_tokens,
            temperature=0.4,
        )
        parsed = _extract_json(out["text"])
        return {"data": parsed, "_mock": out["_mock"], "provider": out["provider"]}

    # ── live implementations ─────────────────────────────────────────────
    def _live(self, prompt: str, system: str, max_tokens: int, temperature: float) -> str:
        provider = self.s.provider_status()["llm"]
        if provider == "mock":
            raise RuntimeError("no llm key configured")

        if provider == "openai":
            from openai import OpenAI

            client = OpenAI(api_key=self.s.openai_api_key)
            resp = client.chat.completions.create(
                model=self.s.openai_model,
                messages=[
                    {"role": "system", "content": system or "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return resp.choices[0].message.content or ""

        # groq is OpenAI-compatible
        from openai import OpenAI

        client = OpenAI(api_key=self.s.groq_api_key, base_url="https://api.groq.com/openai/v1")
        resp = client.chat.completions.create(
            model=self.s.groq_model,
            messages=[
                {"role": "system", "content": system or "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=max_tokens,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""

    # ── mock implementation ──────────────────────────────────────────────
    def _mock(self, prompt: str, system: str) -> str:
        """Heuristic generator that emits the structured JSON our services ask
        for, or a readable script when free text is requested."""
        rng = seeded_rng(prompt, system)
        low = prompt.lower()

        if "json" in low or "respond only with" in low:
            return self._mock_json(prompt, rng)

        # Free-text script-style fallback.
        topic = _guess_topic(prompt)
        hooks = [
            f"Nobody is talking about {topic} the right way…",
            f"This {topic} secret changes everything.",
            f"I tried {topic} for 30 days. Here's what happened.",
            f"Stop scrolling — {topic} is about to blow up.",
        ]
        lines = [
            rng.choice(hooks),
            f"Here's why {topic} matters more than you think.",
            f"Most people get {topic} completely wrong, and it's costing them.",
            f"Here are the 3 things you actually need to know about {topic}.",
            "Save this, share it, and follow for part two.",
        ]
        return "\n".join(lines)

    def _mock_json(self, prompt: str, rng) -> str:
        """Return JSON shaped to whatever the caller hinted it wants."""
        topic = _guess_topic(prompt)
        low = prompt.lower()

        if "storyboard" in low or "scenes" in low or "shot list" in low:
            n = 5
            scenes = []
            beats = [
                ("Hook", f"Punchy on-screen text about {topic}", "fast zoom, bold caption"),
                ("Context", f"Quick explainer of why {topic} is trending", "b-roll montage"),
                ("Insight 1", f"First surprising fact about {topic}", "talking-head + caption"),
                ("Insight 2", f"Second insight with a visual payoff on {topic}", "split screen"),
                ("CTA", "Tell viewers to follow, save and comment", "logo sting + text"),
            ]
            for i in range(n):
                title, narration, visual = beats[i]
                scenes.append({
                    "index": i + 1,
                    "title": title,
                    "narration": narration,
                    "on_screen_text": title.upper() if i == 0 else narration[:48],
                    "visual": visual,
                    "duration_sec": rng.choice([3, 4, 5, 6]),
                })
            return json.dumps({"scenes": scenes})

        if "hashtag" in low or "caption" in low or "package" in low:
            return json.dumps({
                "caption": f"The truth about {topic} that nobody tells you 👀 #fyp",
                "hashtags": _hashtags(topic, rng),
                "hooks": [
                    f"Nobody is talking about {topic} like this",
                    f"{topic.title()} is changing fast — here's how",
                    f"Watch this before you ignore {topic}",
                ],
                "best_post_time": rng.choice(["7:30 PM", "8:00 PM", "12:30 PM", "9:00 PM"]),
                "thumbnail_text": topic.title(),
            })

        if "outline" in low or "lesson" in low or "educational" in low:
            return json.dumps({
                "title": f"{topic.title()} Explained Simply",
                "sections": [
                    {"heading": "What it is", "points": [f"Plain-English definition of {topic}", "Why it exists"]},
                    {"heading": "Why it matters", "points": ["Real-world impact", "Common misconceptions"]},
                    {"heading": "How it works", "points": ["Step-by-step breakdown", "A simple analogy"]},
                    {"heading": "Try it yourself", "points": ["One practical action", "A resource to go deeper"]},
                ],
            })

        # generic key/value fallback
        return json.dumps({"summary": f"Analysis of {topic}", "topic": topic})


# ── helpers ─────────────────────────────────────────────────────────────
def _guess_topic(prompt: str) -> str:
    # 1. Prefer explicitly quoted subject — most reliable signal.
    q = re.search(r"['\"]([A-Za-z0-9 ,\-]{3,60})['\"]", prompt)
    if q:
        return q.group(1).strip().rstrip(".,")
    # 2. Then an "about <subject>" phrase (word-bounded so it won't match
    #    "on" inside "instructional").
    m = re.search(r"\babout\b\s+([A-Za-z0-9 ,\-]{3,50})", prompt, re.I)
    if m:
        return _trim_topic(m.group(1))
    # 3. Fall back to the first few meaningful words.
    words = re.findall(r"[A-Za-z][A-Za-z0-9\-]{2,}", prompt)
    skip = {"json", "respond", "only", "with", "valid", "the", "make", "create",
            "video", "about", "give", "short", "form", "create"}
    picked = [w for w in words if w.lower() not in skip][:4]
    return " ".join(picked) or "this topic"


def _trim_topic(text: str) -> str:
    text = text.strip().rstrip(".,")
    # stop at obvious clause boundaries
    text = re.split(r"\b(?:for|that|with|to|and|in a|including)\b", text, 1)[0]
    return text.strip().rstrip(".,") or text.strip()


def _hashtags(topic: str, rng) -> list[str]:
    base = re.sub(r"[^a-z0-9]+", "", topic.lower())[:18] or "trending"
    pool = ["fyp", "viral", "trending", "foryou", base, base + "tok", "explained",
            "2026", "mustwatch", "reels", "shorts", "creators"]
    rng.shuffle(pool)
    return ["#" + t for t in pool[:8]]


def _extract_json(text: str) -> Any:
    text = text.strip()
    # strip code fences if present
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.M).strip()
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"[\{\[].*[\}\]]", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return {"raw": text}
