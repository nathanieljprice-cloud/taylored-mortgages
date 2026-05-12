"""
MortgageSite Builder — platform entry point.
Run: python app.py          (dev)
Prod: gunicorn app:app
"""
import json
import os
import re
import threading
from datetime import datetime
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

BASE_DIR    = Path(__file__).parent
CLIENTS_DIR = Path(os.environ.get("STORAGE_DIR", BASE_DIR)) / "clients"
BUILDS_DIR  = Path(os.environ.get("STORAGE_DIR", BASE_DIR)) / "builds"
CLIENTS_DIR.mkdir(parents=True, exist_ok=True)
BUILDS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory build status — keyed by slug
_status: dict[str, dict] = {}
_status_lock = threading.Lock()


def _api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return key


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _set_status(slug: str, status: str, message: str = "") -> None:
    with _status_lock:
        _status[slug] = {
            "status": status,
            "message": message,
            "updated_at": datetime.utcnow().isoformat(),
        }


# ── Intake routes ────────────────────────────────────────────────

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

    slug = None
    if complete and config:
        slug = _slug(config.get("full_name", "client"))
        path = CLIENTS_DIR / f"{slug}.json"
        path.write_text(json.dumps(config, indent=2))
        _set_status(slug, "queued", "Starting build…")
        threading.Thread(target=_run_build, args=(slug,), daemon=True).start()

    return jsonify({"message": display, "complete": complete, "config": config, "slug": slug})


@app.route("/api/reset", methods=["POST"])
def reset():
    session.pop("conversation", None)
    return jsonify({"ok": True})


# ── Build routes ───────────────────────────────────────────────────

@app.route("/api/build/<slug>", methods=["POST"])
def trigger_build(slug: str):
    """Manually re-trigger a build for an existing client config."""
    config_path = CLIENTS_DIR / f"{slug}.json"
    if not config_path.exists():
        return jsonify({"error": "client not found"}), 404
    _set_status(slug, "queued", "Starting build…")
    threading.Thread(target=_run_build, args=(slug,), daemon=True).start()
    return jsonify({"ok": True, "slug": slug})


@app.route("/api/build/<slug>/status")
def build_status(slug: str):
    with _status_lock:
        status = _status.get(slug, {"status": "not_started", "message": ""})
    return jsonify(status)


# ── Background build ──────────────────────────────────────────────

def _run_build(slug: str) -> None:
    """Full build sequence: content generation → template replacement → output."""
    from build.builder import build
    from build.content_agent import generate_bio, generate_llms_txt

    try:
        config_path = CLIENTS_DIR / f"{slug}.json"
        config = json.loads(config_path.read_text())
        api_key = _api_key()

        # 1. Bio (if intake didn’t collect one)
        if not config.get("bio"):
            _set_status(slug, "running", "Writing your bio…")
            config["bio"] = generate_bio(config, api_key)

        # 2. llms.txt — personalized AI visibility file
        _set_status(slug, "running", "Generating AI visibility file…")
        llms_content = generate_llms_txt(config, api_key)

        # 3. Apply template replacements across all site files
        _set_status(slug, "running", "Personalizing site content…")
        output_dir = BUILDS_DIR / slug
        build(config, output_dir)

        # 4. Write the Claude-generated llms.txt over the template-swapped version
        (output_dir / "llms.txt").write_text(llms_content, encoding="utf-8")

        # 5. Persist updated config (with generated bio)
        config_path.write_text(json.dumps(config, indent=2))

        _set_status(slug, "complete", f"Site ready at builds/{slug}/")

    except Exception as exc:
        _set_status(slug, "error", str(exc))


if __name__ == "__main__":
    app.run(debug=True, port=5001)
