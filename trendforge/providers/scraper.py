"""Link / article / video extraction adapter.

Given any URL (news article, blog, or video page) it returns a normalized
content object: title, text, and detected media type. Live mode does a real
HTTP fetch + lightweight HTML parsing; on failure it returns a structured mock
so the "video from link" features always have something to work with.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

import requests

from ..config import settings
from .base import seeded_rng, with_fallback

_VIDEO_HOSTS = ("youtube.com", "youtu.be", "tiktok.com", "instagram.com",
                "vimeo.com", "twitter.com", "x.com", "facebook.com")


class ScraperProvider:
    def __init__(self) -> None:
        self.s = settings

    def extract(self, url: str) -> dict:
        result, mocked = with_fallback(
            lambda: self._live(url),
            lambda: self._mock(url),
            label="scraper",
        )
        result["_mock"] = mocked
        return result

    def kind(self, url: str) -> str:
        host = urlparse(url).netloc.lower()
        return "video" if any(h in host for h in _VIDEO_HOSTS) else "article"

    def _live(self, url: str) -> dict:
        host = urlparse(url).netloc.lower()
        if not host:
            raise ValueError("invalid url")
        r = requests.get(url, timeout=self.s.request_timeout,
                         headers={"User-Agent": "Mozilla/5.0 (TrendForge/1.0)"})
        r.raise_for_status()
        html = r.text
        title = _first(re.findall(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)) or host
        og_title = _meta(html, "og:title")
        og_desc = _meta(html, "og:description")
        # crude readable-text extraction
        body = re.sub(r"<script.*?</script>|<style.*?</style>", " ", html, flags=re.I | re.S)
        body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body).strip()
        return {
            "url": url,
            "kind": self.kind(url),
            "title": _clean(og_title or title),
            "description": _clean(og_desc),
            "text": body[:6000],
            "host": host,
            "source": "live",
        }

    def _mock(self, url: str) -> dict:
        rng = seeded_rng("scrape", url)
        host = urlparse(url).netloc.lower() or "example.com"
        kind = self.kind(url)
        slug = urlparse(url).path.strip("/").replace("-", " ").replace("/", " ")[:60]
        topic = slug or rng.choice(["a breaking story", "a trending update", "a how-to guide"])
        if kind == "video":
            title = f"{topic.title()} (original video)"
            text = (f"This {host} video covers {topic}. Key beats: a strong hook, three "
                    f"main points, and a call to action. It performed well with short-form "
                    f"audiences and is a good candidate to remix into vertical clips.")
        else:
            title = topic.title()
            text = (f"{topic.title()} — according to {host}, this story explains the what, "
                    f"why and how. It includes background context, a few key data points, "
                    f"expert reactions, and what is likely to happen next. " * 3)
        return {
            "url": url,
            "kind": kind,
            "title": title,
            "description": f"Auto-summary of {host} content about {topic}.",
            "text": text,
            "host": host,
            "note": "Mock extraction (fetch unavailable). Connect outbound network for live scraping.",
            "source": "mock",
        }


def _meta(html: str, prop: str) -> str:
    m = re.search(rf'<meta[^>]+(?:property|name)=["\']{re.escape(prop)}["\'][^>]+content=["\']([^"\']+)', html, re.I)
    return m.group(1) if m else ""


def _first(lst):
    return lst[0] if lst else ""


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "")).strip()
