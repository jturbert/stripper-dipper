"""
Calls the Anthropic API to generate product description and spec tables.
"""

import os
import anthropic

SYSTEM_PROMPT = (
    "Take the product information provided and write a brief, keyword-rich description "
    "for a webshop. Length: 1–2 paragraphs. Focus on key features and value "
    "propositions. Tone: casual, no hard sell — enthusiasm about a standout feature "
    "is fine. Include SEO keywords naturally. No links. No em dashes."
)

SPEC_TABLE_PROMPT = """
Using the product specifications below, generate TWO HTML spec tables.

Return ONLY valid HTML — no markdown, no explanation, no code fences.

Format your response exactly like this:
===SHOPIFY===
<table>...</table>
===MAILCHIMP===
<table>...</table>

Shopify table requirements:
- Standard <table> with minimal inline styling
- Two columns: Spec Name | Value
- <th> headers: "Specification" and "Value"
- Simple border styling only

Mailchimp table requirements:
- Same content and structure
- All CSS must be fully inline (no <style> blocks) for email client compatibility
- Safe email fonts: Arial, Helvetica, sans-serif
- Background colours for header row and alternating rows

Specifications:
{specs}
"""


def generate_description(product_data: dict) -> str:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    user_content = f"""Product Name: {product_data['name']}

Source URL: {product_data['source_url']}

Description from page:
{product_data['description']}

Additional page content:
{product_data['raw_text']}
"""

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
    )
    return message.content[0].text.strip()


def generate_spec_tables(product_data: dict) -> tuple[str, str]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    if product_data["specs"]:
        specs_text = "\n".join(
            f"- {s['name']}: {s['value']}" for s in product_data["specs"]
        )
    else:
        # Fall back to asking Claude to extract specs from raw text
        specs_text = (
            "No structured specs found. Extract from this page content:\n\n"
            + product_data["raw_text"]
        )

    message = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": SPEC_TABLE_PROMPT.format(specs=specs_text),
            }
        ],
    )

    raw = message.content[0].text.strip()
    shopify_html = _extract_section(raw, "SHOPIFY", "MAILCHIMP")
    mailchimp_html = _extract_section(raw, "MAILCHIMP", None)

    return shopify_html, mailchimp_html


def _extract_section(text: str, start_marker: str, end_marker: str | None) -> str:
    start_tag = f"==={start_marker}==="
    start_idx = text.find(start_tag)
    if start_idx == -1:
        return ""
    content_start = start_idx + len(start_tag)
    if end_marker:
        end_tag = f"==={end_marker}==="
        end_idx = text.find(end_tag, content_start)
        return text[content_start:end_idx].strip() if end_idx != -1 else text[content_start:].strip()
    return text[content_start:].strip()
