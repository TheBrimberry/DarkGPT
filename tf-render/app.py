"""TrendForge render worker — turns a job spec into a real vertical MP4.

POST /render       {scenes:[{headline,narration,keyword,duration}], aspect, style, voice, title, scale}
                   -> {job_id}
GET  /jobs/<id>    -> {status, progress, message, video_url?, meta?}
GET  /files/<id>.mp4
GET  /healthz

Rendering is heavy (FFmpeg/MoviePy), so it runs in a background thread and the
caller polls /jobs/<id>. CORS is open so the TrendForge frontend can call it.
"""
from __future__ import annotations

import os
import threading
import traceback
import uuid

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from renderer import render_job

app = Flask(__name__)
CORS(app)

BASE = os.path.dirname(os.path.abspath(__file__))
RENDERS = os.path.join(BASE, "renders")
os.makedirs(RENDERS, exist_ok=True)

JOBS: dict[str, dict] = {}
_LOCK = threading.Lock()
MAX_SCENES = int(os.environ.get("MAX_SCENES", "8"))


def _set(job_id, **kw):
    with _LOCK:
        JOBS.setdefault(job_id, {}).update(kw)


def _worker(job_id: str, spec: dict):
    workdir = os.path.join(RENDERS, job_id + "_work")
    out_path = os.path.join(RENDERS, job_id + ".mp4")
    try:
        _set(job_id, status="rendering", progress=2, message="starting")

        def progress(msg, pct):
            _set(job_id, message=msg, progress=pct)

        meta = render_job(spec, out_path, workdir, progress=progress)
        _set(job_id, status="done", progress=100, message="done",
             video_url=f"/files/{job_id}.mp4", meta=meta)
    except Exception as exc:  # noqa: BLE001
        traceback.print_exc()
        _set(job_id, status="error", message=str(exc))
    finally:
        try:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)
        except Exception:
            pass


@app.post("/render")
def render():
    spec = request.get_json(silent=True) or {}
    scenes = spec.get("scenes") or []
    if len(scenes) > MAX_SCENES:
        spec["scenes"] = scenes[:MAX_SCENES]
    job_id = uuid.uuid4().hex[:12]
    _set(job_id, status="queued", progress=0, message="queued")
    threading.Thread(target=_worker, args=(job_id, spec), daemon=True).start()
    return jsonify({"job_id": job_id, "status": "queued"})


@app.get("/jobs/<job_id>")
def job(job_id):
    with _LOCK:
        j = JOBS.get(job_id)
    if not j:
        return jsonify({"error": "not found"}), 404
    return jsonify({"job_id": job_id, **j})


@app.get("/files/<path:filename>")
def files(filename):
    return send_from_directory(RENDERS, filename, mimetype="video/mp4")


@app.get("/healthz")
def healthz():
    return {"ok": True, "pexels": bool(os.environ.get("PEXELS_API_KEY")),
            "jobs": len(JOBS)}


@app.get("/")
def index():
    return {"service": "tf-render", "endpoints": ["/render", "/jobs/<id>", "/files/<id>.mp4", "/healthz"]}


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "8080")))
