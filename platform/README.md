# MortgageSite Builder

An AI-powered platform that builds personalized mortgage advisor websites through a conversational intake experience.

## How It Works

1. **Intake** — An AI agent (Alex) collects the advisor's details through chat (~5 minutes)
2. **Content** — Claude generates a personalized bio and `llms.txt` AI visibility file
3. **Build** — String replacement personalizes the `taylored-mortgages` template site
4. **Deploy** — Site is pushed to a private GitHub repo and deployed live on Netlify

## Stack

- **Backend**: Flask + Python, `anthropic` SDK
- **AI**: Claude claude-sonnet-4-6 (intake agent + content generation)
- **Template**: `taylored-mortgages` — the base mortgage advisor site
- **Hosting**: Netlify (ZIP deploy API) + GitHub (Git Data API)

## Setup

### Prerequisites

1. Clone this repo (`mortgagesite-builder`)
2. Clone the template site as a sibling directory:
   ```bash
   git clone https://github.com/nathanieljprice-cloud/taylored-mortgages ../taylored-mortgages
   ```

### Install

```bash
cd platform
pip install -r requirements.txt
```

### Configure

```bash
cp .env.example .env
# Edit .env — at minimum set ANTHROPIC_API_KEY, SECRET_KEY, and TEMPLATE_ROOT
```

Key env vars:

| Variable | Required | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Powers the intake agent and content generation |
| `SECRET_KEY` | Yes | Flask session signing key (any long random string) |
| `TEMPLATE_ROOT` | Yes* | Absolute path to the `taylored-mortgages` clone |
| `SUPPORT_EMAIL` | No | Shown in the client handoff doc (default: `support@mortgagesite.io`) |
| `GITHUB_TOKEN` | No | PAT with `repo` scope — creates private client repos |
| `GITHUB_ORG` | No | GitHub org for client repos (blank = personal account) |
| `NETLIFY_TOKEN` | No | Personal access token — deploys live Netlify sites |

*`TEMPLATE_ROOT` defaults to three levels up from `builder.py`, which is correct only when running from within `taylored-mortgages/platform/`. For standalone deployments, always set it explicitly.

### Run

```bash
# Development
cd platform
python app.py
# → http://localhost:5001

# Production
gunicorn app:app --bind 0.0.0.0:8000
```

## Project Structure

```
platform/
├── app.py                   Flask entry point, session management, build pipeline
├── intake/
│   └── agent.py             Conversational intake agent (Alex)
├── build/
│   ├── builder.py           Template → personalized site (string replacement)
│   └── content_agent.py     Claude bio + llms.txt generation
├── deploy/
│   ├── github_push.py       Create GitHub repo + push files via Git Data API
│   └── netlify_deploy.py    Create Netlify site + deploy ZIP
├── templates/
│   └── intake.html          Chat UI + build progress screen
├── clients/                 Saved client configs (JSON, gitignored)
├── builds/                  Generated site output (gitignored)
├── .env.example
└── requirements.txt
```

## Template Replacement System

The builder replaces Taylor LaPierre's specific values with each client's values using ordered string substitution (longest/most-specific patterns first to prevent partial matches):

| Template value | Replaced with |
|---|---|
| `Taylored Mortgages` | `{first_name} Mortgages` |
| `Taylor LaPierre` | `full_name` |
| `NMLS #2068598` | `NMLS #{nmls_personal}` |
| `NMLS #370636` | `NMLS #{nmls_company}` |
| `Acadia Lending Group, LLC` | `company_name` |
| `tlapierre@acadialendinggroup.com` | `email` |
| `(207) 232-1918` | `phone` |
| `subtle-manatee-efc18b.netlify.app` | `domain` |
| `Maine and New Hampshire` | `license_states` (joined) |
| `South Portland, Maine 04106` | `primary_city` |
| `tayloredmortgages` | `instagram` handle |
| `pricenj01@me.com` | `SUPPORT_EMAIL` env var |

## Client Handoff

After a successful build + deploy, each client receives:

- **Live site URL** on Netlify
- **Private GitHub repo** with their full site source
- **`blog-post-guide.html`** — step-by-step instructions for publishing blog posts via GitHub or Netlify CMS (`/admin`)

Clients can publish posts without touching code by creating markdown files in `_posts/` through the GitHub web UI.

## Adding a New Template Site

The builder is template-agnostic. To support a second vertical (e.g., real estate agents):

1. Create a new template repo
2. Add a corresponding `builder_realty.py` with the new replacement pairs
3. Add a new intake question set in `intake/agent.py`
4. Point `TEMPLATE_ROOT` to the new template in your deployment
