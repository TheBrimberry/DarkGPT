"""Asset providers for the render worker.

  * stock_clip(): fetch a vertical stock video from Pexels (optional key)
  * synth_voice(): free TTS via edge-tts, with word timings for captions
Both degrade gracefully so a render always succeeds, even with no keys and no
network (a gradient background + silent narration of the right length).
"""
from __future__ import annotations

import asyncio
import os
import tempfile

import requests

PEXELS_KEY = os.environ.get("PEXELS_API_KEY", "").strip()
DEFAULT_VOICE = os.environ.get("TTS_VOICE", "en-US-AriaNeural")
HTTP_TIMEOUT = int(os.environ.get("HTTP_TIMEOUT", "25") or 25)


# ── stock footage ─────────────────────────────────────────────────────────
def stock_clip(keyword: str, workdir: str, idx: int, want_vertical: bool = True) -> str | None:
    """Download one stock video for a keyword; return local path or None."""
    if not PEXELS_KEY:
        return None
    try:
        r = requests.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_KEY},
            params={"query": keyword or "abstract", "per_page": 5,
                    "orientation": "portrait" if want_vertical else "landscape"},
            timeout=HTTP_TIMEOUT,
        )
        r.raise_for_status()
        vids = r.json().get("videos", [])
        if not vids:
            return None
        # pick a reasonably sized mp4 file from the first result
        files = sorted(vids[0].get("video_files", []),
                       key=lambda f: (f.get("height") or 0), reverse=True)
        url = None
        for f in files:
            if (f.get("file_type") == "video/mp4") and (f.get("height") or 0) >= 900:
                url = f["link"]; break
        url = url or (files[0]["link"] if files else None)
        if not url:
            return None
        path = os.path.join(workdir, f"stock_{idx}.mp4")
        with requests.get(url, stream=True, timeout=HTTP_TIMEOUT) as resp:
            resp.raise_for_status()
            with open(path, "wb") as fh:
                for chunk in resp.iter_content(1 << 16):
                    fh.write(chunk)
        return path
    except Exception as exc:  # noqa: BLE001
        print("stock_clip fallback:", exc)
        return None


# ── voiceover (edge-tts, free) ────────────────────────────────────────────
def synth_voice(text: str, workdir: str, idx: int, voice: str = "") -> tuple[str | None, list, float]:
    """Return (mp3_path|None, word_timings, duration_sec).

    word_timings: list of {"word","start","end"} seconds for caption sync.
    """
    text = (text or "").strip()
    if not text:
        return None, [], 0.0
    voice = voice or DEFAULT_VOICE
    out = os.path.join(workdir, f"voice_{idx}.mp3")
    try:
        import edge_tts

        words: list[dict] = []

        async def _run():
            comm = edge_tts.Communicate(text, voice)
            with open(out, "wb") as fh:
                async for chunk in comm.stream():
                    if chunk["type"] == "audio":
                        fh.write(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start = chunk["offset"] / 1e7
                        dur = chunk["duration"] / 1e7
                        words.append({"word": chunk["text"], "start": start, "end": start + dur})

        asyncio.run(_run())
        dur = words[-1]["end"] if words else _probe_duration(out)
        return out, words, max(dur, 1.0)
    except Exception as exc:  # noqa: BLE001
        print("synth_voice fallback (silent):", exc)
        # estimate duration ~155 wpm so the scene still has sensible length
        n = max(1, len(text.split()))
        return None, [], max(2.0, n / 2.6)


def _probe_duration(path: str) -> float:
    try:
        from moviepy import AudioFileClip
        a = AudioFileClip(path); d = a.duration; a.close()
        return float(d or 2.0)
    except Exception:
        return 3.0
