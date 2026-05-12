"""
Build pipeline: client_config.json → customized site files.

Copies every template file from the repo root, applies an ordered set of
string replacements drawn from the client config, and writes output to
platform/builds/<slug>/. Claude-generated content (llms.txt, bio) is
injected by app.py before this is called.
"""
import shutil
from pathlib import Path

# Template root = repo root (three levels up from platform/build/builder.py)
TEMPLATE_ROOT = Path(__file__).resolve().parent.parent.parent

# Files to process (relative to repo root)
SITE_FILES = [
    "index.html",
    "blog.html",
    "faq.html",
    "homebuyers-guide.html",
    "refinance-guide.html",
    "market-updates.html",
    "reviews.html",
    "llms.txt",
    "sitemap.xml",
    "robots.txt",
    "blog-post-guide.html",
    "netlify.toml",
    "admin/config.yml",
    "_posts/.gitkeep",
]

COPY_DIRS = ["images"]


def build(config: dict, output_dir: Path) -> Path:
    """
    Generate a customized site for the given client config.
    Returns the output directory path.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs = _replacement_pairs(config)

    for rel in SITE_FILES:
        src = TEMPLATE_ROOT / rel
        if not src.exists():
            continue
        dst = output_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8", errors="replace")
        for old, new in pairs:
            text = text.replace(old, new)
        dst.write_text(text, encoding="utf-8")

    for d in COPY_DIRS:
        src_d = TEMPLATE_ROOT / d
        if src_d.exists():
            shutil.copytree(src_d, output_dir / d, dirs_exist_ok=True)

    for f in [".gitignore", "swap-domain.sh"]:
        src_f = TEMPLATE_ROOT / f
        if src_f.exists():
            shutil.copy2(src_f, output_dir / f)

    return output_dir


def _replacement_pairs(cfg: dict) -> list[tuple[str, str]]:
    """
    Ordered list of (old, new) pairs.
    Most specific / longest patterns come first to avoid partial-match clobbering.
    Pairs with an empty new value are dropped so we never blank out live content.
    """
    full_name  = cfg.get("full_name", "")
    first_name = full_name.split()[0] if full_name else ""
    last_name  = full_name.split()[-1] if len(full_name.split()) > 1 else ""

    nmls_p  = cfg.get("nmls_personal", "")
    nmls_c  = cfg.get("nmls_company", "")
    company = cfg.get("company_name", "")
    phone   = cfg.get("phone", "")
    email   = cfg.get("email", "")
    tagline = cfg.get("tagline", "")

    domain = cfg.get("domain", "")
    if domain in ("TBD", "upload_later", "", None):
        domain = ""
    else:
        domain = domain.replace("https://", "").replace("http://", "").rstrip("/")

    instagram   = cfg.get("instagram", "")
    linkedin    = cfg.get("linkedin", "")
    linkedin_id = ""
    if linkedin and "/in/" in linkedin:
        linkedin_id = linkedin.split("/in/")[-1].rstrip("/")

    states       = cfg.get("license_states", [])
    states_str   = _join(states)
    primary_city = cfg.get("primary_city", "")
    city_name    = primary_city.split(",")[0].strip() if "," in primary_city else primary_city

    raw: list[tuple[str, str]] = [
        # Brand name (before full name so "Taylored" isn’t left half-replaced)
        ("Taylored Mortgages", f"{first_name} Mortgages"),

        # Full name (before any single-token replacements)
        ("Taylor LaPierre",   full_name),

        # NMLS — with # prefix first, then bare number
        ("NMLS #2068598",     f"NMLS #{nmls_p}"),
        ("NMLS #370636",      f"NMLS #{nmls_c}"),
        ("2068598",           nmls_p),
        ("370636",            nmls_c),

        # Company — longest form first
        ("Acadia Lending Group, LLC", company),
        ("Acadia Lending Group",      company),

        # Contact
        ("tlapierre@acadialendinggroup.com", email),
        ("(207) 232-1918",                   phone),

        # Domain
        ("subtle-manatee-efc18b.netlify.app", domain or "subtle-manatee-efc18b.netlify.app"),

        # Social
        ("tayloredmortgages",              instagram),
        ("taylor-hogan-lapierre-8582618b", linkedin_id),

        # Location — specific phrases before shorter ones
        ("Maine and New Hampshire",   states_str),
        ("Maine or New Hampshire",    states_str),
        ("South Portland, Maine 04106", primary_city),
        ("South Portland, Maine",       primary_city),
        ("South Portland, ME",          primary_city),
        ("Portland, ME",                city_name),
    ]

    # Drop pairs where the replacement value is empty
    return [(o, n) for o, n in raw if o and n]


def _join(items: list[str]) -> str:
    if not items:      return ""
    if len(items) == 1: return items[0]
    if len(items) == 2: return f"{items[0]} and {items[1]}"
    return ", ".join(items[:-1]) + f", and {items[-1]}"
