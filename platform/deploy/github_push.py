"""
GitHub deploy: create a private repo and push all built site files
using the Git Data API (blobs → tree → commit → ref).
"""
import base64
import time
from pathlib import Path

import requests

_API = "https://api.github.com"
_ACCEPT = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


def create_and_push(
    slug: str,
    build_dir: Path,
    token: str,
    org: str | None = None,
) -> dict:
    """
    Create a new private repo and push build_dir as the initial commit.
    Returns {"repo_url": str, "owner": str, "repo_name": str}.
    """
    h = {**_ACCEPT, "Authorization": f"Bearer {token}"}
    repo_name = f"{slug}-mortgage-site"

    endpoint = f"{_API}/orgs/{org}/repos" if org else f"{_API}/user/repos"
    payload = {
        "name": repo_name,
        "private": True,
        "description": "Mortgage advisor site — built by MortgageSite Builder",
        "auto_init": False,
        "has_wiki": False,
        "has_projects": False,
    }
    r = requests.post(endpoint, headers=h, json=payload, timeout=30)
    if r.status_code == 422:
        repo_name = f"{slug}-{int(time.time()) % 10000}"
        payload["name"] = repo_name
        r = requests.post(endpoint, headers=h, json=payload, timeout=30)
    r.raise_for_status()

    data  = r.json()
    owner = data["owner"]["login"]
    base  = f"{_API}/repos/{owner}/{repo_name}"

    _push_initial_commit(base, build_dir, h)

    return {"repo_url": data["html_url"], "owner": owner, "repo_name": repo_name}


def _push_initial_commit(base: str, build_dir: Path, headers: dict) -> None:
    """Push all files as a single initial commit."""
    entries = []
    for p in sorted(build_dir.rglob("*")):
        if p.is_dir():
            continue
        rel = str(p.relative_to(build_dir)).replace("\\", "/")
        if any(part.startswith(".git") for part in p.parts):
            continue
        entries.append((p, rel))

    tree = []
    for fpath, rel in entries:
        raw = fpath.read_bytes()
        try:
            blob_body = {"content": raw.decode("utf-8"), "encoding": "utf-8"}
        except UnicodeDecodeError:
            blob_body = {"content": base64.b64encode(raw).decode(), "encoding": "base64"}

        br = requests.post(f"{base}/git/blobs", headers=headers, json=blob_body, timeout=60)
        br.raise_for_status()
        tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": br.json()["sha"]})

    tr = requests.post(f"{base}/git/trees", headers=headers, json={"tree": tree}, timeout=30)
    tr.raise_for_status()

    cr = requests.post(f"{base}/git/commits", headers=headers, json={
        "message": "Initial site — MortgageSite Builder",
        "tree": tr.json()["sha"],
    }, timeout=30)
    cr.raise_for_status()

    rr = requests.post(f"{base}/git/refs", headers=headers, json={
        "ref": "refs/heads/main",
        "sha": cr.json()["sha"],
    }, timeout=30)
    rr.raise_for_status()
