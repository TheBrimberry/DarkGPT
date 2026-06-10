"""Brainrot mode — generates absurd, hyper-stimulating short-form clips and an
endless feed of them. This is the classic "brainrot" format: a punchy AI hook,
rapid bouncing captions, a hype voice, a meme sound, and chaotic visuals.

All flavor lives here so the rest of the studio stays generic.
"""
from __future__ import annotations

from .scoring import score_content
from ..providers.base import seeded_rng

# Brainrot-flavored subjects (meme canon + the absurd "did you know" energy).
TOPICS = [
    "skibidi toilet lore explained", "why everyone has so much rizz now",
    "the Ohio final boss", "sigma male morning routine", "mewing for 24 hours straight",
    "gyatt physics in real life", "Tralalero Tralala backstory", "Bombardiro Crocodilo origin",
    "fanum tax explained by AI", "the gravity of Ohio", "level 9999 gyatt",
    "is the griddy a martial art", "AI ranks the brainrot characters",
    "what your favorite brainrot says about you", "the lore of the Ohio sky",
    "scientists discover new rizz particle", "speedrunning the alphabet (brainrot edition)",
    "did you know capybaras have max aura", "the forbidden sigma grindset",
    "POV you unlocked infinite aura", "ranking sounds by how much brainrot they cause",
]

HOOKS = [
    "POV: you just unlocked", "Nobody is ready for", "They don't want you to know about",
    "Wait for it…", "This is actually insane —", "Scientists are SHOOK by",
    "Only sigmas understand", "The lore behind", "Bro really said", "Day 1 of explaining",
]

SOUNDS = [
    "original sound - brainrotcentral", "skibidi remix (sped up)", "phonk house x rizz",
    "subway surfers gameplay audio", "Italian brainrot anthem", "sigma boy (slowed)",
    "ohio background music", "amen break + rizz", "epic gaming montage sound",
]

OVERLAYS = ["Subway Surfers gameplay", "Minecraft parkour", "GTA ramp clips",
            "Temple Run", "satisfying soap cutting", "marble race"]


def pick_topic(rng) -> str:
    return rng.choice(TOPICS)


def brainrot_brief(topic: str, rng) -> str:
    hook = rng.choice(HOOKS)
    overlay = rng.choice(OVERLAYS)
    return (
        f"Make an absurd, hyper-stimulating BRAINROT short-form video about '{topic}'. "
        f"Open with the hook '{hook} {topic}'. Use a fast, chaotic, gen-z, meme tone with "
        f"rapid bouncing on-screen captions, lots of emojis, and a satisfying "
        f"'{overlay}' background on the bottom half of the screen. Keep every line punchy "
        f"and unhinged. End on a 'follow for more lore' call to action."
    )


def feed_meta(topic: str, rng) -> dict:
    base = topic.split()[0].lower()
    tags = ["#brainrot", "#fyp", "#skibidi", "#sigma", "#rizz", "#ohio", "#viral",
            "#" + base, "#foryou", "#lore", "#npc", "#aura"]
    rng.shuffle(tags)
    likes = rng.randint(12_000, 4_200_000)
    return {
        "sound": rng.choice(SOUNDS),
        "caption": f"{rng.choice(HOOKS)} {topic} {rng.choice(['💀', '🔥', '🤯', '😭', '🗿'])}",
        "hashtags": tags[:7],
        "likes": likes,
        "comments": int(likes * rng.uniform(0.01, 0.05)),
        "shares": int(likes * rng.uniform(0.02, 0.08)),
        "overlay": rng.choice(OVERLAYS),
    }


def brainrot_score(topic: str, meta: dict, target_sec: int) -> dict:
    # Brainrot rides extreme novelty + perfect short-form length -> high heat.
    return score_content(
        hook=meta["caption"], caption=" ".join(meta["hashtags"]),
        hashtags=meta["hashtags"], duration_sec=target_sec, aspect="9:16",
        platform="TikTok", topic_heat=92, sentiment=0.85,
    )
