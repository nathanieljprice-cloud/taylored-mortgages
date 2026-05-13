"""
Build pipeline for the service business vertical.

Copies files from the service site template repository, applies client-specific
string replacements, and writes output to builds/<slug>/.

SERVICE_TEMPLATE_ROOT: path to the service-template repository.
Defaults to a sibling "service-template" directory from the taylored-mortgages root.
Override via SERVICE_TEMPLATE_ROOT env var for standalone deployments.

Town lists (area-town divs / area-chip spans) are replaced using block markers:
  <!-- AREA_TOWNS_START --> ... <!-- AREA_TOWNS_END -->
  <!-- AREA_CHIPS_START --> ... <!-- AREA_CHIPS_END -->
If markers are absent the town lists remain as-is (Integrity's defaults).
"""
import os
import re
import shutil
from pathlib import Path

SERVICE_TEMPLATE_ROOT = Path(os.environ.get(
    "SERVICE_TEMPLATE_ROOT",
    str(Path(__file__).resolve().parent.parent.parent / "service-template"),
))

SUPPORT_EMAIL = os.environ.get("SUPPORT_EMAIL", "support@mortgagesite.io")

SITE_FILES = [
    "index.html",
    "services.html",
    "faq.html",
    "contact.html",
    "llms.txt",
    "sitemap.xml",
    "robots.txt",
    "netlify.toml",
]


def build(config: dict, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    pairs  = _replacement_pairs(config)
    towns  = config.get("service_towns", [])

    for rel in SITE_FILES:
        src = SERVICE_TEMPLATE_ROOT / rel
        if not src.exists():
            continue
        dst = output_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        text = src.read_text(encoding="utf-8", errors="replace")
        for old, new in pairs:
            text = text.replace(old, new)
        if towns:
            text = _replace_town_blocks(text, towns)
        dst.write_text(text, encoding="utf-8")

    for f in [".gitignore"]:
        src_f = SERVICE_TEMPLATE_ROOT / f
        if src_f.exists():
            shutil.copy2(src_f, output_dir / f)

    return output_dir


def _replacement_pairs(cfg: dict) -> list[tuple[str, str]]:
    biz_name = cfg.get("business_name", "")
    services = cfg.get("services", [])
    subtitle = cfg.get("services_subtitle") or (
        " & ".join(services[:2]) if len(services) >= 2 else (services[0] if services else "")
    )
    subtitle_html = subtitle.replace("&", "&amp;")

    primary_city = cfg.get("primary_city", "")
    city_name    = primary_city.split(",")[0].strip() if "," in primary_city else primary_city
    state_abbr   = primary_city.split(",")[-1].strip() if "," in primary_city else ""
    service_area = f"{city_name} area" if city_name else ""

    phone        = cfg.get("phone", "")
    phone_digits = "".join(c for c in phone if c.isdigit())
    email        = cfg.get("email", "")

    domain = cfg.get("domain", "")
    if domain in ("TBD", "", None):
        domain = ""
    else:
        domain = domain.replace("https://", "").replace("http://", "").rstrip("/")

    years     = str(cfg.get("years_experience", ""))
    years_str = f"{years}+" if years and years.isdigit() else (years or "10+")

    num_proj  = str(cfg.get("num_projects", ""))
    proj_str  = f"{num_proj}+" if num_proj and num_proj.isdigit() else (num_proj or "100+")

    words    = biz_name.split()
    initials = "".join(w[0] for w in words if w)[:3].upper() or "SB"

    raw: list[tuple[str, str]] = [
        ("Integrity Site Services",           biz_name),
        ("Hydroseeding &amp; Light Excavation", subtitle_html),
        ("Hydroseeding & Light Excavation",    subtitle),
        ("Southern New Hampshire",             service_area or state_abbr or "Southern NH"),
        ("Bedford, NH",                        primary_city),
        ("Bedford",                            city_name),
        ("(603) 555-0100",                    phone),
        ("6035550100",                         phone_digits),
        ("info@integritysite.com",             email),
        ("integrity-site.netlify.app",         domain or "integrity-site.netlify.app"),
        ("500+",                               proj_str),
        ("15+",                                years_str),
        (">IS<",                               f">{initials}<"),
        ("pricenj01@me.com",                  SUPPORT_EMAIL),
    ]
    return [(o, n) for o, n in raw if o and n]


def _replace_town_blocks(text: str, towns: list[str]) -> str:
    """Replace <!-- AREA_TOWNS_START/END --> and <!-- AREA_CHIPS_START/END --> blocks."""
    towns_html = "\n".join(f'<div class="area-town">{t}</div>' for t in towns)
    chips_html = "".join(f'<span class="area-chip">{t}</span>' for t in towns)

    text = _replace_block(text, "AREA_TOWNS", towns_html)
    text = _replace_block(text, "AREA_CHIPS", chips_html)
    return text


def _replace_block(text: str, name: str, new_html: str) -> str:
    start = f"<!-- {name}_START -->"
    end   = f"<!-- {name}_END -->"
    pattern = re.escape(start) + r".*?" + re.escape(end)
    replacement = f"{start}\n{new_html}\n{end}"
    return re.sub(pattern, replacement, text, flags=re.DOTALL)
