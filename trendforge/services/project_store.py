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
