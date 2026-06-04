"""Trendability / virality scoring engine.

A transparent, explainable heuristic model that scores a piece of content (its
hook, length, format, topic heat, hashtags, posting time, platform fit) for how
likely it is to trend. Real virality is noisy, but a clear rubric is genuinely
useful for guiding creators — and it makes the "make it highly trendable"
feature actionable with concrete suggestions instead of a black box.
"""
from __future__ import annotations

import re

# Words/structures known to boost short-form retention.
_HOOK_SIGNALS = [
    "nobody", "stop", "secret", "truth", "why", "how", "never", "what happens",
    "this is", "watch", "before", "everyone", "nobody tells", "the real", "vs",
    "i tried", "ranked", "tier list", "exposed", "finally", "you've been",
]
_POWER_EMOJIS = ["👀", "🔥", "😳", "🤯", "💀", "‼️"]

_IDEAL_DURATION = {"9:16": (15, 34), "1:1": (20, 45), "4:5": (20, 45), "16:9": (45, 180)}
_PLATFORM_FIT = {
    "9:16": {"TikTok": 1.0, "Reels": 1.0, "Shorts": 1.0, "X": 0.5, "YouTube": 0.4},
    "1:1": {"X": 0.9, "Reels": 0.7, "TikTok": 0.5, "YouTube": 0.4, "Shorts": 0.4},
    "4:5": {"Reels": 0.9, "TikTok": 0.6, "X": 0.6, "YouTube": 0.4, "Shorts": 0.4},
    "16:9": {"YouTube": 1.0, "X": 0.7, "TikTok": 0.2, "Reels": 0.2, "Shorts": 0.2},
}


def score_content(*, hook: str = "", caption: str = "", hashtags: list[str] | None = None,
                  duration_sec: int = 24, aspect: str = "9:16", platform: str = "TikTok",
                  topic_heat: int = 55, sentiment: float = 0.6) -> dict:
    """Return a 0-100 trend score with a per-factor breakdown and fixes."""
    hashtags = hashtags or []
    factors: dict[str, dict] = {}

    # 1. Hook strength (30%)
    hook_l = hook.lower()
    hits = sum(1 for s in _HOOK_SIGNALS if s in hook_l)
    hook_len_ok = 4 <= len(hook.split()) <= 12
    hook_score = min(1.0, 0.25 + hits * 0.22 + (0.2 if hook_len_ok else 0))
    factors["hook"] = _f(hook_score, 0.30,
                         "Strong curiosity hook" if hook_score > 0.7 else "Hook is weak/generic",
                         None if hook_score > 0.7 else "Open with tension: 'Nobody is telling you…' or 'Stop scrolling if…'")

    # 2. Topic heat (25%) — how hot the subject already is
    heat = max(0, min(100, topic_heat)) / 100
    factors["topic_heat"] = _f(heat, 0.25,
                               "Riding a hot topic" if heat > 0.6 else "Topic is lukewarm",
                               None if heat > 0.6 else "Tie the idea to a currently exploding trend or sound.")

    # 3. Length fit (15%)
    lo, hi = _IDEAL_DURATION.get(aspect, (15, 34))
    if lo <= duration_sec <= hi:
        len_score = 1.0
        len_note, len_fix = "Ideal length for the format", None
    else:
        over = duration_sec - hi if duration_sec > hi else lo - duration_sec
        len_score = max(0.2, 1 - over / max(hi, 1))
        len_note = "Too long — retention will drop" if duration_sec > hi else "Too short to land the point"
        len_fix = f"Aim for {lo}-{hi}s on a {aspect} clip."
    factors["length"] = _f(len_score, 0.15, len_note, len_fix)

    # 4. Platform fit (15%)
    fit = _PLATFORM_FIT.get(aspect, {}).get(platform, 0.5)
    factors["platform_fit"] = _f(fit, 0.15,
                                 f"{aspect} fits {platform} well" if fit > 0.7 else f"{aspect} is a poor fit for {platform}",
                                 None if fit > 0.7 else f"Switch to 9:16 for {platform}, or post to YouTube for 16:9.")

    # 5. Caption + hashtags (10%)
    n_tags = len(hashtags)
    tag_ok = 3 <= n_tags <= 8
    has_cta = bool(re.search(r"follow|save|comment|share|link|part \d", caption.lower()))
    emoji_bonus = 0.1 if any(e in caption for e in _POWER_EMOJIS) else 0
    cap_score = min(1.0, (0.4 if tag_ok else 0.1) + (0.4 if has_cta else 0) + 0.1 + emoji_bonus)
    factors["caption"] = _f(cap_score, 0.10,
                            "Caption has tags + CTA" if cap_score > 0.7 else "Caption missing tags or CTA",
                            None if cap_score > 0.7 else "Use 3-8 hashtags and a clear CTA (follow / save / comment).")

    # 6. Sentiment polarity (5%) — strong emotion (either way) travels further
    polarity = abs(sentiment - 0.5) * 2
    factors["emotion"] = _f(min(1.0, 0.4 + polarity), 0.05,
                            "Emotionally charged" if polarity > 0.4 else "Emotionally flat",
                            None if polarity > 0.4 else "Lean into a strong emotion: awe, outrage, or delight.")

    total = round(sum(f["weighted"] for f in factors.values()) * 100)
    grade = _grade(total)
    fixes = [f["fix"] for f in factors.values() if f["fix"]]
    return {
        "trend_score": total,
        "grade": grade,
        "verdict": _verdict(total),
        "factors": factors,
        "top_fixes": fixes[:3],
    }


def _f(score: float, weight: float, note: str, fix: str | None) -> dict:
    score = max(0.0, min(1.0, score))
    return {"score": round(score * 100), "weight": weight,
            "weighted": score * weight, "note": note, "fix": fix}


def _grade(total: int) -> str:
    if total >= 85:
        return "A+"
    if total >= 75:
        return "A"
    if total >= 65:
        return "B"
    if total >= 50:
        return "C"
    return "D"


def _verdict(total: int) -> str:
    if total >= 80:
        return "High viral potential — ship it."
    if total >= 65:
        return "Solid. A couple tweaks could push it over the top."
    if total >= 50:
        return "Mixed. Apply the fixes before posting."
    return "Low potential as-is. Rework the hook and topic fit."
