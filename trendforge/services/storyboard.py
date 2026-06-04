"""Turns a topic/brief into a structured storyboard: hook, scenes, narration,
on-screen text, captions and hashtags. Powered by the LLM provider (mock-safe).
"""
from __future__ import annotations

from ..providers import LLMProvider


class Storyboard:
    def __init__(self) -> None:
        self.llm = LLMProvider()

    def build(self, *, brief: str, tone: str = "energetic", target_sec: int = 24,
              aspect: str = "9:16") -> dict:
        scenes = self.llm.json(
            f"Create a short-form video storyboard (shot list / scenes) for a {target_sec}s "
            f"{aspect} video. Brief: {brief}. Tone: {tone}. "
            "Each scene needs: index, title, narration, on_screen_text, visual, duration_sec.",
            system="You are an award-winning short-form video director.",
        )["data"]

        pkg = self.llm.json(
            f"Create the publish package (caption, hashtags, hooks, best_post_time, "
            f"thumbnail_text) for a short video about: {brief}.",
            system="You are a viral content strategist.",
        )["data"]

        scene_list = scenes.get("scenes") if isinstance(scenes, dict) else scenes
        if not isinstance(scene_list, list) or not scene_list:
            scene_list = self._fallback_scenes(brief, target_sec)

        return {
            "brief": brief,
            "tone": tone,
            "aspect": aspect,
            "target_sec": target_sec,
            "scenes": scene_list,
            "package": pkg,
            "hook": (scene_list[0].get("narration") if scene_list else "") or pkg.get("hooks", [""])[0],
            "script": "\n".join(s.get("narration", "") for s in scene_list),
        }

    def _fallback_scenes(self, brief: str, target_sec: int) -> list[dict]:
        per = max(3, target_sec // 5)
        beats = [
            ("Hook", f"Here's what nobody tells you about {brief}."),
            ("Setup", f"Quick context on {brief} and why it matters now."),
            ("Payoff 1", f"The first thing you need to know about {brief}."),
            ("Payoff 2", f"And the part that actually surprises people about {brief}."),
            ("CTA", "Follow for part two — and save this so you don't forget."),
        ]
        return [
            {"index": i + 1, "title": t, "narration": n,
             "on_screen_text": t.upper() if i == 0 else n[:48],
             "visual": "dynamic b-roll + bold captions", "duration_sec": per}
            for i, (t, n) in enumerate(beats)
        ]
