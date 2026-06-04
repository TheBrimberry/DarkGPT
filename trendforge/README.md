# 🔥 TrendForge — AI Trend Intelligence + Ultimate Video Generator

TrendForge analyzes what's trending across social / entertainment / politics /
TikTok / influencers, **forecasts what's likely to trend next**, and turns a few
words, an article link, or an existing video link into a **highly "trendable"
video** — complete with storyboard, AI voiceover, music, captions, hashtags and
an explainable **trend score**.

> **Runs with zero API keys.** Every external capability is built behind a
> provider interface that activates a real API when a key is present and
> otherwise falls back to rich, deterministic *smart mocks* — so the whole app
> works end-to-end out of the box. Add keys in `.env` to go fully live.

---

## ✨ What it does

| Module | What you give it | What you get |
|---|---|---|
| 🔥 **Trends** | a category | live-style ranked topics with heat, velocity, sentiment, audience & platforms |
| 🔮 **Forecast** | a category + horizon | topics projected to climb, with confidence, peak window & first‑mover picks |
| ✍️ **Prompt → Video** | a few words | full video project: storyboard, voiceover, music, captions, hashtags, trend score |
| ♻️ **Remake a Link** | a video URL | a fresh remixed version of an existing video |
| 📰 **Article → Video** | any article/news/info URL | an explainer video built from the page's content |
| 🎵 **Music Video / Song** | a topic | a structured song (genre, BPM, key, lyrics) + synced music‑video storyboard |
| 🎓 **Educational** | a topic | a structured lesson / instructional video with an outline |
| 📊 **Trend Score** | any hook/caption/length | an explainable 0–100 virality score with concrete fixes |
| 🖼️ **My Videos** | — | a saved gallery of every project (SQLite), re‑openable & remixable |

Best-in-class features borrowed from tools like CapCut, InVideo, Opus, Pika,
Runway, Synthesia and Suno: aspect-ratio presets per platform (TikTok/Reels/
Shorts/YouTube), hook & hashtag generators, best-post-time, multiple AI voices,
auto storyboards, repurpose-from-link, and a virality predictor.

---

## 🚀 Quick start

```bash
pip install -r trendforge/requirements.txt
python run_trendforge.py
# open http://localhost:5050
```

No configuration needed. To go live, copy the env template and add any keys:

```bash
cp trendforge/.env.example .env
# fill in only the providers you want (OpenAI/Groq, LunarCrush, Replicate, Suno, ElevenLabs)
```

The header pills show which capabilities are **live** vs **mock** in real time.

---

## 🔌 Providers (all optional)

| Capability | Live provider | Env key | Mock fallback |
|---|---|---|---|
| LLM (scripts/analysis) | OpenAI or Groq | `OPENAI_API_KEY` / `GROQ_API_KEY` | heuristic script & JSON generator |
| Trends / social | LunarCrush | `LUNARCRUSH_API_KEY` | seeded trending feed |
| Video render | Replicate / Runway / Pika | `REPLICATE_API_TOKEN` … | render plan + generated SVG poster |
| Music / song | Suno | `SUNO_API_KEY` | full song spec + structured lyrics |
| Voiceover | ElevenLabs | `ELEVENLABS_API_KEY` | timed voiceover plan |
| Link/article scrape | live HTTP fetch | (none) | structured content mock |

If a key is missing **or** a live call fails, the provider degrades to its mock
automatically — the product never hard-crashes on a missing key.

---

## 🧠 Architecture

```
trendforge/
├── config.py              # env-driven settings + provider status
├── app.py                 # Flask app factory
├── providers/             # pluggable adapters (live API ↔ smart mock)
│   ├── base.py            #   with_fallback(): live → mock on any error
│   ├── llm.py  trends.py  video.py  music.py  tts.py  scraper.py
├── services/
│   ├── trend_intelligence.py   # "what's trending now"
│   ├── trend_forecast.py       # "what's likely next" (velocity + sub-peak model)
│   ├── scoring.py              # explainable virality engine
│   ├── storyboard.py           # topic → scenes/script/package
│   ├── video_studio.py         # orchestrates all 5 generation modes
│   └── project_store.py        # SQLite gallery (stdlib only)
├── api/routes.py          # JSON endpoints under /api
├── templates/index.html   # single-page dashboard
└── static/                # css + vanilla-JS controller
```

## 📡 API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/status` | providers, categories, voices, stats |
| `GET` | `/api/trends?category=&limit=` | trending now |
| `GET` | `/api/trends/topic?q=` | deep-dive on a topic + content angles |
| `GET` | `/api/forecast?category=&weeks=&limit=` | predicted upcoming trends |
| `POST` | `/api/generate` | prompt → video (`{prompt, aspect, ...}`) |
| `POST` | `/api/remake` | remake a video URL (`{url, ...}`) |
| `POST` | `/api/from-article` | article URL → video (`{url, ...}`) |
| `POST` | `/api/music-video` | song / music video (`{topic, genre, ...}`) |
| `POST` | `/api/educational` | lesson video (`{topic, level, ...}`) |
| `POST` | `/api/score` | score any content for virality |
| `GET/DELETE` | `/api/projects[/<id>]` | gallery CRUD |

---

## ⚠️ Notes & honesty

- The **trend score** and **forecast** are transparent heuristic models, not a
  guarantee of real-world virality — they're decision aids with explainable
  factors and concrete suggested fixes.
- In mock mode, video "renders" produce a storyboard + a generated SVG poster
  (a real, viewable artifact), not an MP4. Wire a `VIDEO_PROVIDER` key for full
  video, `SUNO_API_KEY` for audio, and `ELEVENLABS_API_KEY` for voice.
