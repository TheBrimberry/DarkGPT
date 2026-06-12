"""Vercel serverless entry point for the TrendForge web app.

Vercel's @vercel/python runtime detects the module-level ``app`` (a WSGI app)
and serves it. All routes (/, /api/*, /static/*) are handled by Flask.
"""
import os
import sys

# Make the repo root importable so `trendforge` resolves on Vercel.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Serverless filesystem is read-only except /tmp; never run the debug reloader.
os.environ.setdefault("TF_DATA_DIR", "/tmp/trendforge")
os.environ.setdefault("TF_DEBUG", "false")

from trendforge.app import app  # noqa: E402

# Vercel looks for `app` (WSGI) — also expose `handler` for safety.
handler = app
