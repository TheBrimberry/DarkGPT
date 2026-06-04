#!/usr/bin/env python3
"""Entry point: launch the TrendForge web app.

    python run_trendforge.py

Then open http://localhost:5050  (no API keys required — runs on smart mocks).
"""
from trendforge.app import app
from trendforge.config import settings

if __name__ == "__main__":
    banner = f"""
  ┌────────────────────────────────────────────────┐
  │   TrendForge — AI Trend Intelligence + Studio   │
  │   http://localhost:{settings.port:<5}                        │
  └────────────────────────────────────────────────┘
  Providers: {settings.provider_status()}
"""
    print(banner)
    app.run(host=settings.host, port=settings.port, debug=settings.debug)
