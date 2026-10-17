"""Video assembly: scenes -> a real vertical MP4.

Pipeline per scene: stock b-roll (or an animated gradient fallback) +
voiceover (edge-tts) + a bold headline + moving chunked captions. Scenes are
concatenated and encoded to H.264/AAC with FFmpeg via MoviePy.
"""
from __future__ import annotations

import math
import os

from PIL import Image, ImageDraw, ImageFont

from providers import stock_clip, synth_voice

FONT_PATH = os.path.join(os.path.dirname(__file__), "assets", "font.ttf")

ASPECTS = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}
PALETTES = {
    "vibrant": [(255, 8, 68), (255, 106, 0)], "cinematic": [(15, 12, 41), (48, 43, 99)],
    "clean": [(26, 35, 64), (58, 90, 154)], "neon": [(121, 40, 202), (255, 0, 128)],
    "documentary": [(35, 37, 38), (65, 67, 69)], "brainrot": [(255, 0, 212), (0, 255, 136)],
}


# ── Pillow helpers ─────────────────────────────────────────────────────────
def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def _wrap(draw, text, font, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=font) > max_w and cur:
            lines.append(cur); cur = w
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines


def gradient_bg(w, h, colors, out_path):
    top, bot = colors
    img = Image.new("RGB", (w, h))
    px = img.load()
    for y in range(h):
        f = y / max(1, h - 1)
        px_row = tuple(int(top[i] + (bot[i] - top[i]) * f) for i in range(3))
        for x in range(w):
            px[x, y] = px_row
    img.save(out_path)
    return out_path


def text_png(text, w, font_size, out_path, *, stroke=8, pad=24, align_h="center"):
    text = (text or "").upper() if font_size >= 60 else (text or "")
    font = _font(font_size)
    scratch = Image.new("RGBA", (10, 10))
    d = ImageDraw.Draw(scratch)
    lines = _wrap(d, text, font, w - 2 * pad)
    lh = int(font_size * 1.18)
    H = lh * len(lines) + 2 * pad
    img = Image.new("RGBA", (w, max(H, 1)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = pad
    for ln in lines:
        tw = d.textlength(ln, font=font)
        x = (w - tw) / 2 if align_h == "center" else pad
        d.text((x, y), ln, font=font, fill="white",
               stroke_width=stroke, stroke_fill="black")
        y += lh
    img.save(out_path)
    return out_path, img.size


# ── caption timing ─────────────────────────────────────────────────────────
def caption_segments(text, word_timings, d, chunk=3):
    words = (text or "").split()
    if not words:
        return []
    segs = []
    if word_timings and len(word_timings) >= len(words) * 0.5:
        for i in range(0, len(word_timings), chunk):
            grp = word_timings[i:i + chunk]
            segs.append((" ".join(w["word"] for w in grp), grp[0]["start"], grp[-1]["end"]))
    else:
        n = math.ceil(len(words) / chunk)
        per = d / max(1, n)
        for k in range(n):
            grp = words[k * chunk:(k + 1) * chunk]
            segs.append((" ".join(grp), k * per, min(d, (k + 1) * per)))
    return segs


# ── main render ────────────────────────────────────────────────────────────
def render_job(spec: dict, out_path: str, workdir: str, progress=None) -> dict:
    from moviepy import (ImageClip, AudioFileClip, CompositeVideoClip,
                         concatenate_videoclips, VideoFileClip)

    aspect = spec.get("aspect", "9:16")
    W, H = ASPECTS.get(aspect, ASPECTS["9:16"])
    # keep render light by default; callers can request full res
    scale = float(spec.get("scale", 0.5))
    W, H = int(W * scale) // 2 * 2, int(H * scale) // 2 * 2
    fps = int(spec.get("fps", 30))
    style = spec.get("style", "vibrant")
    colors = PALETTES.get(style, PALETTES["vibrant"])
    voice = spec.get("voice", "")
    scenes_in = spec.get("scenes") or [{"headline": spec.get("title", "TrendForge"), "narration": ""}]

    os.makedirs(workdir, exist_ok=True)
    scene_clips = []
    total_scenes = len(scenes_in)

    for i, sc in enumerate(scenes_in):
        if progress:
            progress(f"scene {i + 1}/{total_scenes}", int(i / total_scenes * 85))
        headline = str(sc.get("headline") or sc.get("on_screen_text") or sc.get("title") or "")
        narration = str(sc.get("narration") or headline)
        keyword = str(sc.get("keyword") or headline or narration)[:60]

        voice_path, words, dur = synth_voice(narration, workdir, i, voice)
        dur = max(float(sc.get("duration") or dur or 3.0), 1.5)

        # background: stock clip (cover+crop+loop) or gradient
        bg = None
        stock = stock_clip(keyword, workdir, i)
        if stock:
            try:
                clip = VideoFileClip(stock, audio=False)
                sc_ratio = max(W / clip.w, H / clip.h)
                clip = clip.resized(sc_ratio)
                clip = clip.cropped(x_center=clip.w / 2, y_center=clip.h / 2, width=W, height=H)
                if clip.duration < dur:
                    reps = math.ceil(dur / clip.duration)
                    clip = concatenate_videoclips([clip] * reps)
                bg = clip.subclipped(0, dur)
            except Exception as exc:  # noqa: BLE001
                print("stock use failed, gradient:", exc); bg = None
        if bg is None:
            gpath = os.path.join(workdir, f"bg_{i}.png")
            gradient_bg(W, H, colors, gpath)
            bg = ImageClip(gpath).with_duration(dur)

        layers = [bg.with_duration(dur)]

        # headline (top-center, held whole scene)
        if headline:
            hp, (hw, hh) = text_png(headline, int(W * 0.92), int(W * 0.11),
                                    os.path.join(workdir, f"head_{i}.png"),
                                    stroke=max(4, int(W * 0.012)))
            layers.append(ImageClip(hp, transparent=True).with_duration(dur)
                          .with_position(("center", int(H * 0.30))))

        # moving chunked captions (bottom)
        for j, (txt, s, e) in enumerate(caption_segments(narration, words, dur)):
            if not txt.strip():
                continue
            cp, _ = text_png(txt, int(W * 0.9), int(W * 0.062),
                             os.path.join(workdir, f"cap_{i}_{j}.png"),
                             stroke=max(3, int(W * 0.008)))
            layers.append(ImageClip(cp, transparent=True)
                          .with_start(s).with_duration(max(0.3, e - s))
                          .with_position(("center", int(H * 0.72))))

        scene = CompositeVideoClip(layers, size=(W, H)).with_duration(dur)
        if voice_path and os.path.exists(voice_path):
            try:
                scene = scene.with_audio(AudioFileClip(voice_path))
            except Exception as exc:  # noqa: BLE001
                print("audio attach failed:", exc)
        scene_clips.append(scene)

    if progress:
        progress("encoding", 88)
    final = concatenate_videoclips(scene_clips, method="compose")
    final.write_videofile(
        out_path, fps=fps, codec="libx264", audio_codec="aac",
        preset="veryfast", threads=4, logger=None,
        temp_audiofile=os.path.join(workdir, "tmp_audio.m4a"),
    )
    dur_total = float(final.duration)
    try:
        final.close()
        for c in scene_clips:
            c.close()
    except Exception:
        pass
    if progress:
        progress("done", 100)
    return {"path": out_path, "duration": round(dur_total, 2),
            "width": W, "height": H, "scenes": total_scenes}
