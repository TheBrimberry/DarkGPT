"""TrendForge — AI Trend Intelligence + Ultimate Video Generator.

A pluggable platform that:
  * analyzes social / trending / political / entertainment / TikTok / influencer topics
  * forecasts which topics are likely to trend next
  * turns a few words, an article link, or an existing video link into a
    highly "trendable" video, music video, song, or educational/instructional clip

Every external capability (LLM, trend data, video render, music, voiceover,
web scraping) is built behind a provider interface that activates real APIs
when keys are present and otherwise falls back to rich, deterministic mock
data so the whole app runs end-to-end with zero configuration.
"""

__version__ = "1.0.0"
__appname__ = "TrendForge"
