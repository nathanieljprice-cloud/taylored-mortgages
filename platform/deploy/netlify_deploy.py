"""
Netlify deploy: create a site and upload a ZIP of the built files.
nnetlify.toml in the build is processed automatically, so security
headers and redirect rules apply without any extra configuration.
"""
import io
import time
import zipfile
from pathlib import Path

import requests

_API = "https://api.netlify.com/api/v1"


def create_and_deploy(slug: str, build_dir: Path, token: str) -> dict:
    """
    Create a Netlify site and deploy build_dir via ZIP upload.
    Returns {"url": str, "site_id": str, "deploy_id": str, "admin_url": str}.
    """
    auth = {"Authorization": f"Bearer {token}"}
    json_h = {**auth, "Content-Type": "application/json"}

    # Create site
    site_name = f"{slug}-mortgage"
    r = requests.post(f"{_API}/sites", headers=json_h, json={"name": site_name}, timeout=30)
    if r.status_code == 422:
        site_name = f"{slug}-{int(time.time()) % 100000}"
        r = requests.post(f"{_API}/sites", headers=json_h, json={"name": site_name}, timeout=30)
    r.raise_for_status()
    site    = r.json()
    site_id = site["id"]

    # Build ZIP — skip .gitkeep and .git internals
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(build_dir.rglob("*")):
            if p.is_dir() or p.name == ".gitkeep":
                continue
            if any(part.startswith(".git") for part in p.parts):
                continue
            zf.write(p, p.relative_to(build_dir))
    buf.seek(0)

    # Deploy
    dr = requests.post(
        f"{_API}/sites/{site_id}/deploys",
        headers={**auth, "Content-Type": "application/zip"},
        data=buf.read(),
        timeout=120,
    )
    dr.raise_for_status()
    deploy = dr.json()

    return {
        "url":       f"https://{site_name}.netlify.app",
        "site_id":   site_id,
        "deploy_id": deploy.get("id", ""),
        "admin_url": site.get("admin_url", f"https://app.netlify.com/sites/{site_name}"),
    }
