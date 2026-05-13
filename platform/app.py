"""
SiteBuilder platform entry point.
Run: python app.py          (dev)
Prod: gunicorn app:app

Verticals:
  /              → mortgage intake (default)
  /v/mortgage    → mortgage intake
  /v/service     → service business intake
"""
import json
import os
import re
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, session

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

_status: dict[str, dict] = {}
_status_lock = threading.Lock()


def _api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return key


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _set_status(slug: str, status: str, message: str = "", **extra) -> None:
    with _status_lock:
        _status[slug] = {
            "status":     status,
            "message":    message,
            "updated_at": datetime.utcnow().isoformat(),
            **extra,
        }


# ── Intake routes ──────────────────────────────────

@app.route("/")
def index():
    return _render_vertical("mortgage")


@app.route("/v/mortgage")
def intake_mortgage():
    return _render_vertical("mortgage")


@app.route("/v/service")
def intake_service():
    return _render_vertical("service")


def _render_vertical(vertical: str):
    session.pop("conversation", None)
    session["vertical"] = vertical
    session.modified = True
    template = "intake_service.html" if vertical == "service" else "intake.html"
    return render_template(template)


# ── Conversation API ──────────────────────────────

@app.route("/api/start", methods=["POST"])
def start():
    session.pop("conversation", None)
    vertical = session.get("vertical", "mortgage")
    try:
        agent = _make_agent(vertical)
        text  = agent.start()
        session["conversation"] = agent.history
        session.modified = True
        return jsonify({"message": text})
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def chat():
    data         = request.get_json(silent=True) or {}
    user_message = data.get("message", "").strip()
    if not user_message:
        return jsonify({"error": "empty message"}), 400

    history  = session.get("conversation", [])
    vertical = session.get("vertical", "mortgage")
    try:
        agent = _make_agent(vertical)
        display, config, complete = agent.chat(history, user_message)
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 500

    session["conversation"] = agent.history
    session.modified = True

    slug = None
    if complete and config:
        name = config.get("business_name") or config.get("full_name", "client")
        slug = _slug(name)
        config["_vertical"] = vertical
        (CLIENTS_DIR / f"{slug}.json").write_text(json.dumps(config, indent=2))
        _set_status(slug, "queued", "Starting build…")
        threading.Thread(target=_run_build, args=(slug,), daemon=True).start()

    return jsonify({"message": display, "complete": complete, "config": config, "slug": slug})


@app.route("/api/reset", methods=["POST"])
def reset():
    session.pop("conversation", None)
    return jsonify({"ok": True})


# ── Build / deploy ────────────────────────────────

@app.route("/api/build/<slug>", methods=["POST"])
def trigger_build(slug: str):
    if not (CLIENTS_DIR / f"{slug}.json").exists():
        return jsonify({"error": "client not found"}), 404
    _set_status(slug, "queued", "Starting build…")
    threading.Thread(target=_run_build, args=(slug,), daemon=True).start()
    return jsonify({"ok": True, "slug": slug})


@app.route("/api/build/<slug>/status")
def build_status(slug: str):
    with _status_lock:
        status = _status.get(slug, {"status": "not_started", "message": ""})
    return jsonify(status)


# ── Helpers ─────────────────────────────────────────

def _make_agent(vertical: str):
    key = _api_key()
    if vertical == "service":
        from intake.service_agent import ServiceIntakeAgent
        return ServiceIntakeAgent(key)
    from intake.agent import IntakeAgent
    return IntakeAgent(key)


# ── Background pipeline ─────────────────────────────

def _run_build(slug: str) -> None:
    try:
        config_path = CLIENTS_DIR / f"{slug}.json"
        config      = json.loads(config_path.read_text())
        api_key     = _api_key()
        vertical    = config.get("_vertical", "mortgage")

        if vertical == "service":
            _run_service_build(slug, config, config_path, api_key)
        else:
            _run_mortgage_build(slug, config, config_path, api_key)

    except Exception as exc:
        _set_status(slug, "error", str(exc))


def _run_mortgage_build(slug, config, config_path, api_key):
    from build.builder       import build
    from build.content_agent import generate_bio, generate_llms_txt

    if not config.get("bio"):
        _set_status(slug, "running", "Writing your bio…")
        config["bio"] = generate_bio(config, api_key)

    _set_status(slug, "running", "Generating AI visibility file…")
    llms_content = generate_llms_txt(config, api_key)

    _set_status(slug, "running", "Personalizing site content…")
    output_dir = BUILDS_DIR / slug
    build(config, output_dir)
    (output_dir / "llms.txt").write_text(llms_content, encoding="utf-8")
    config_path.write_text(json.dumps(config, indent=2))

    _deploy(slug, output_dir)


def _run_service_build(slug, config, config_path, api_key):
    from build.service_builder       import build as svc_build
    from build.service_content_agent import generate_llms_txt

    _set_status(slug, "running", "Generating AI visibility file…")
    llms_content = generate_llms_txt(config, api_key)

    _set_status(slug, "running", "Personalizing site content…")
    output_dir = BUILDS_DIR / slug
    svc_build(config, output_dir)
    (output_dir / "llms.txt").write_text(llms_content, encoding="utf-8")
    config_path.write_text(json.dumps(config, indent=2))

    _deploy(slug, output_dir)


def _deploy(slug: str, output_dir: Path) -> None:
    repo_info = None
    gh_token  = os.environ.get("GITHUB_TOKEN")
    gh_org    = os.environ.get("GITHUB_ORG") or None
    if gh_token:
        from deploy.github_push import create_and_push
        _set_status(slug, "running", "Creating GitHub repository…")
        repo_info = create_and_push(slug, output_dir, gh_token, gh_org)

    deploy_info   = None
    netlify_token = os.environ.get("NETLIFY_TOKEN")
    if netlify_token:
        from deploy.netlify_deploy import create_and_deploy
        _set_status(slug, "running", "Deploying to Netlify…")
        deploy_info = create_and_deploy(slug, output_dir, netlify_token)

    final: dict = {"status": "complete", "updated_at": datetime.utcnow().isoformat()}
    if deploy_info:
        final["message"]   = "Your site is live!"
        final["url"]       = deploy_info["url"]
        final["admin_url"] = deploy_info["admin_url"]
    else:
        final["message"] = "Site files ready. Add NETLIFY_TOKEN to deploy."
    if repo_info:
        final["repo_url"] = repo_info["repo_url"]

    with _status_lock:
        _status[slug] = final


if __name__ == "__main__":
    app.run(debug=True, port=5001)
