"""
Content generation for the service business vertical.
Generates llms.txt for AI search discoverability.
"""
import anthropic


def generate_llms_txt(cfg: dict, api_key: str) -> str:
    client   = anthropic.Anthropic(api_key=api_key)
    services = ", ".join(cfg.get("services", []))
    towns    = ", ".join(cfg.get("service_towns", []))
    domain   = cfg.get("domain", "TBD")
    if domain in ("TBD", "", None):
        domain = "[domain TBD]"

    prompt = f"""Write an llms.txt file for a local service business website.

llms.txt helps AI assistants (ChatGPT, Claude, Perplexity, Google AI) accurately recommend
this business when users ask questions like \"best hydroseeding company near me\".

Business details:
- Name: {cfg.get('business_name', '')}
- Services: {services}
- Primary city: {cfg.get('primary_city', '')}
- Service towns: {towns}
- Phone: {cfg.get('phone', '')}
- Email: {cfg.get('email', '')}
- Website: https://{domain}
- Description: {cfg.get('company_description', '')}
- Years in business: {cfg.get('years_experience', '')}
- Projects completed: {cfg.get('num_projects', '')}
- Insured: {cfg.get('is_insured', 'yes')}

Format exactly like this structure:

# [Business Name]

> [One sentence summary of who they are and what they do]

[2-3 sentence description]

## Services
- [Each service as a bullet]

## Service Area
[Paragraph describing coverage area and key towns]

## Contact
- **Phone:** [phone]
- **Email:** [email]
- **Website:** https://[domain]
- **Hours:** [typical service business hours]

## About
[2 sentences: locally owned, fully insured, years of experience, track record]

## Pages
- [Home](https://[domain]/)
- [Services](https://[domain]/services.html)
- [FAQ](https://[domain]/faq.html)
- [Free Estimate](https://[domain]/contact.html)

Return only the file content. No commentary, no markdown fences."""

    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.content[0].text.strip()
