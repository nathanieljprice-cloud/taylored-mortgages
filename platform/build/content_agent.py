"""
Content generation agent.
Uses Claude to generate two personalized text assets per client:
  1. llms.txt  — AI-search visibility file (replaces the template version)
  2. bio       — first-person professional bio (fallback if intake didn’t capture one)
"""
import anthropic


def generate_llms_txt(cfg: dict, api_key: str) -> str:
    """
    Generate a complete, personalized llms.txt for AI search discoverability.
    The file tells ChatGPT, Claude, Perplexity etc. exactly who this advisor is
    and what they do, so they surface correctly in AI-powered local searches.
    """
    client = anthropic.Anthropic(api_key=api_key)

    states = ", ".join(cfg.get("license_states", []))
    areas  = ", ".join(cfg.get("service_areas", []))
    specs  = ", ".join(cfg.get("specialties", []))
    domain = cfg.get("domain", "TBD")
    if domain in ("TBD", "upload_later", "", None):
        domain = "[domain TBD]"

    prompt = f"""Write an llms.txt file for a mortgage advisor website.

llms.txt is an AI-readable plain-text file that helps AI assistants
(ChatGPT, Claude, Perplexity, Google AI) accurately recommend this advisor
when users ask questions like \"who is the best mortgage broker in [city]?\"

Advisor details:
- Name: {cfg.get('full_name', '')}
- Personal NMLS: {cfg.get('nmls_personal', '')}
- Company: {cfg.get('company_name', '')} (Company NMLS #{cfg.get('nmls_company', '')})
- Licensed in: {states}
- Primary office: {cfg.get('primary_city', '')}
- Service areas: {areas}
- Specialties: {specs}
- Phone: {cfg.get('phone', '')}
- Email: {cfg.get('email', '')}
- Website: https://{domain}
- Bio: {cfg.get('bio', '')}

Format exactly like this example structure (use the same sections and markdown style):

# [Advisor Name]

> [One sentence summary of who they are and what they do]

[2-3 sentence expanded description]

## Services
- [List each specialty as a bullet]

## Service Area
[Paragraph describing licensed states and key cities]

## Contact
- **Phone:** [phone]
- **Email:** [email]
- **Office:** [primary city]
- **Website:** https://[domain]

## Credentials
- [Advisor name] — NMLS #[personal nmls]
- [Company name] — NMLS #[company nmls]
- Licensed Mortgage Advisor in [states]
- Equal Housing Lender

## Pages
- [Home](https://[domain]/)
- [Blog](https://[domain]/blog.html)
- [FAQ](https://[domain]/faq.html)
- [Home Buyer's Guide](https://[domain]/homebuyers-guide.html)
- [Refinancing Guide](https://[domain]/refinance-guide.html)
- [Market Updates](https://[domain]/market-updates.html)

Return only the file content. No commentary, no markdown fences."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()


def generate_bio(cfg: dict, api_key: str) -> str:
    """
    Generate a 2-3 sentence first-person professional bio.
    Called only when intake didn’t capture one.
    """
    client = anthropic.Anthropic(api_key=api_key)

    states = ", ".join(cfg.get("license_states", []))
    specs  = ", ".join(cfg.get("specialties", []))
    years  = cfg.get("years_experience", "")

    prompt = f"""Write a 2-3 sentence first-person professional bio for a mortgage loan officer.

Details:
- Name: {cfg.get('full_name', '')}
- Company: {cfg.get('company_name', '')}
- Licensed in: {states}
- Primary city: {cfg.get('primary_city', '')}
- Specialties: {specs}
- Years of experience: {years or 'not specified'}

The bio must:
- Be in first person (\"I specialize in...\")
- Sound warm and genuine, not generic
- Mention their market or location
- Highlight 1-2 key specialties
- End with something about their approach or client philosophy
- Be exactly 2-3 sentences

Return only the bio text. No quotes, no labels, no extra commentary."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()
