# 🎞️ tf-render — TrendForge real-MP4 render worker

A small FFmpeg/MoviePy service that turns a TrendForge storyboard into an
**actual vertical MP4** (not a canvas preview): stock b-roll + AI voiceover +
moving captions, assembled and encoded to H.264/AAC.

It runs as a separate worker because heavy video rendering **cannot run on
Vercel** (no FFmpeg, short timeouts, read-only disk). Deploy it on Render /
Railway / Fly / any Docker host, then point TrendForge at it with
`RENDER_WORKER_URL`.

## What it does (inspired by MoneyPrinterTurbo / RedditVideoMakerBot)
- **b-roll**: pulls a stock clip per scene from **Pexels** (free API key) and
  cover-crops it to vertical; falls back to a styled gradient if no key.
- **voiceover**: free **edge-tts** (Microsoft voices), with word timings.
- **captions**: a bold headline + moving word-chunk captions, synced to the
  voice, burned into the frame.
- **assembly**: MoviePy + FFmpeg → `H.264/AAC` vertical MP4.

## API
| Method | Path | Body / notes |
|---|---|---|
| `POST` | `/render` | `{scenes:[{headline,narration,keyword,duration}], aspect, style, voice, title, scale}` → `{job_id}` |
| `GET` | `/jobs/<id>` | `{status, progress, message, video_url?, meta?}` (poll until `done`) |
| `GET` | `/files/<id>.mp4` | the finished video |
| `GET` | `/healthz` | liveness + whether a Pexels key is set |

`scale` (0–1) trades quality for speed (default `0.5` ≈ 540×960; set `1` for 1080×1920).

## Run locally
```bash
pip install -r requirements.txt       # needs ffmpeg on PATH (brew/apt install ffmpeg)
python app.py                         # http://localhost:8080
```

## Deploy (Render, recommended)
1. Push this repo (already done).
2. Render dashboard → **New + → Blueprint** → pick this repo (it reads `tf-render/render.yaml`).
3. (Optional) set `PEXELS_API_KEY` for real footage — get a free key at pexels.com/api.
4. You get a URL like `https://tf-render-xxx.onrender.com`.
5. In Vercel → the `viddeck` project → **Environment Variables**, add
   `RENDER_WORKER_URL = https://tf-render-xxx.onrender.com`, then redeploy.
   TrendForge's **🎞️ Render real MP4** button then uses it.

## Notes
- Starter instance or larger — FFmpeg needs the RAM/CPU; the free tier may OOM
  on 1080p.
- Rendering a ~20s clip takes roughly 15–60s depending on plan and `scale`.
- edge-tts needs outbound network; if it's blocked the clip still renders with
  silent narration of the right length.
