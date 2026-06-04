"""Flask application factory for TrendForge."""
from __future__ import annotations

import os

from flask import Flask, render_template, send_from_directory

from .config import settings
from .api.routes import api

POSTER_DIR = os.path.join(settings.data_dir, "renders")


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config["SECRET_KEY"] = settings.secret_key
    app.register_blueprint(api, url_prefix="/api")

    os.makedirs(POSTER_DIR, exist_ok=True)

    @app.get("/")
    def index():
        return render_template("index.html", status=settings.provider_status())

    @app.get("/renders/<path:filename>")
    def renders(filename):
        return send_from_directory(POSTER_DIR, filename)

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "providers": settings.provider_status()}

    return app


app = create_app()
