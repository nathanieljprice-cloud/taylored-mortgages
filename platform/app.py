"""
MortgageSite Builder — platform entry point.
Run: python app.py          (dev)
Prod: gunicorn app:app
"""
import json
import os
import re
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session
from intake.agent import IntakeAgent

app = Flask(__name__)

_key = os.environ.get("SECRET_KEY", os.urandom(32).hex())
app.secret_key = _key
app.config.update(
    SESSION_COOKIE_SAMESITE="Strict",
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=not os.environ.get("FLASK_DEBUG"),
)

CLIENTS_DIR = Path(os.environ.get("STORAGE_DIR", ".")) / "clients"
CLIENTS_DIR.mkdir(parents=True, exist_ok=True)


def _api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return key


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


@app.route("/")
def index():
    session.pop("conversation", None)
    return render_template("intake.html")


@app.route("/api/start", methods=["POST"])
def start():
    """Called once on page load to get the opening greeting."""
    session.pop("conversation", None)
    try:
        agent = IntakeAgent(_api_key())
        text = agent.start()
        session["conversation"] = agent.history
        session.modified = True
        return jsonify({"message": text})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "empty message"}), 400

    history = session.get("conversation", [])
    try:
        agent = IntakeAgent(_api_key())
        display, config, complete = agent.chat(history, user_message)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    session["conversation"] = agent.history
    session.modified = True

    if complete and config:
        slug = _slug(config.get("full_name", "client"))
        path = CLIENTS_DIR / f"{slug}.json"
        path.write_text(json.dumps(config, indent=2))

    return jsonify({"message": display, "complete": complete, "config": config})


@app.route("/api/reset", methods=["POST"])
def reset():
    session.pop("conversation", None)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5001)
