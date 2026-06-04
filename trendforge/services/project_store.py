"""SQLite-backed persistence for generated video projects.

Stores every job (prompt-to-video, remake, article, music video, educational)
with its full spec so the gallery, re-generation and "remake" features work.
Uses only the stdlib so there are no extra dependencies.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid
from typing import Any

from ..config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    title       TEXT,
    prompt      TEXT,
    source_url  TEXT,
    status      TEXT DEFAULT 'ready',
    trend_score INTEGER DEFAULT 0,
    spec        TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_projects_created ON projects(created_at DESC);

CREATE TABLE IF NOT EXISTS posts (
    id            TEXT PRIMARY KEY,
    project_id    TEXT,
    platforms     TEXT NOT NULL,
    caption       TEXT,
    status        TEXT DEFAULT 'published',
    schedule_time TEXT,
    provider      TEXT,
    results       TEXT,
    created_at    REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_posts_created ON posts(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_posts_project ON posts(project_id);
"""


class ProjectStore:
    def __init__(self, db_path: str | None = None) -> None:
        os.makedirs(settings.data_dir, exist_ok=True)
        self.db_path = db_path or os.path.join(settings.data_dir, "trendforge.db")
        self._init()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init(self) -> None:
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    def create(self, *, kind: str, spec: dict, title: str = "", prompt: str = "",
               source_url: str = "", trend_score: int = 0, status: str = "ready") -> dict:
        pid = uuid.uuid4().hex[:12]
        row = {
            "id": pid,
            "kind": kind,
            "title": title or spec.get("title", "Untitled"),
            "prompt": prompt,
            "source_url": source_url,
            "status": status,
            "trend_score": trend_score,
            "spec": json.dumps(spec),
            "created_at": time.time(),
        }
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO projects (id, kind, title, prompt, source_url, status, "
                "trend_score, spec, created_at) VALUES (:id,:kind,:title,:prompt,"
                ":source_url,:status,:trend_score,:spec,:created_at)", row)
        return self.get(pid)

    def get(self, pid: str) -> dict | None:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
        return _hydrate(r) if r else None

    def list(self, *, kind: str = "", limit: int = 50) -> list[dict]:
        q = "SELECT * FROM projects"
        params: list[Any] = []
        if kind:
            q += " WHERE kind=?"
            params.append(kind)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(q, params).fetchall()
        return [_hydrate(r) for r in rows]

    def delete(self, pid: str) -> bool:
        with self._conn() as conn:
            cur = conn.execute("DELETE FROM projects WHERE id=?", (pid,))
        return cur.rowcount > 0

    # ── posts ────────────────────────────────────────────────────────────
    def create_post(self, *, project_id: str, platforms: list, caption: str,
                    status: str, schedule_time: str | None, provider: str,
                    results: Any) -> dict:
        pid = uuid.uuid4().hex[:12]
        row = {
            "id": pid,
            "project_id": project_id,
            "platforms": json.dumps(platforms),
            "caption": caption,
            "status": status,
            "schedule_time": schedule_time,
            "provider": provider,
            "results": json.dumps(results),
            "created_at": time.time(),
        }
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO posts (id, project_id, platforms, caption, status, "
                "schedule_time, provider, results, created_at) VALUES (:id,:project_id,"
                ":platforms,:caption,:status,:schedule_time,:provider,:results,:created_at)", row)
        return self.get_post(pid)

    def get_post(self, pid: str) -> dict | None:
        with self._conn() as conn:
            r = conn.execute("SELECT * FROM posts WHERE id=?", (pid,)).fetchone()
        return _hydrate_post(r) if r else None

    def list_posts(self, *, project_id: str = "", limit: int = 100) -> list[dict]:
        q = "SELECT * FROM posts"
        params: list[Any] = []
        if project_id:
            q += " WHERE project_id=?"
            params.append(project_id)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._conn() as conn:
            rows = conn.execute(q, params).fetchall()
        return [_hydrate_post(r) for r in rows]

    def post_stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM posts").fetchone()["c"]
            scheduled = conn.execute(
                "SELECT COUNT(*) c FROM posts WHERE status='scheduled'").fetchone()["c"]
        return {"total_posts": total, "scheduled": scheduled}

    def stats(self) -> dict:
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"]
            by_kind = conn.execute(
                "SELECT kind, COUNT(*) c FROM projects GROUP BY kind").fetchall()
            avg = conn.execute(
                "SELECT AVG(trend_score) a FROM projects").fetchone()["a"] or 0
        return {
            "total": total,
            "by_kind": {r["kind"]: r["c"] for r in by_kind},
            "avg_trend_score": round(avg, 1),
        }


def _hydrate(row: sqlite3.Row) -> dict:
    d = dict(row)
    try:
        d["spec"] = json.loads(d["spec"])
    except Exception:
        d["spec"] = {}
    return d


def _hydrate_post(row: sqlite3.Row) -> dict:
    d = dict(row)
    for k in ("platforms", "results"):
        try:
            d[k] = json.loads(d[k]) if d[k] else None
        except Exception:
            pass
    return d
