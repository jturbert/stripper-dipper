"""
Calls the Anthropic API to generate product description, meta description, and spec tables.
"""

import os
import anthropic

SYSTEM_PROMPT = """
Write copy for a specialist hi-fi webshop. Use the tone and rules below exactly.

TONE
- Conversational and direct. Write like a knowledgeable friend who works at a great hi-fi shop, not a marketing department.
- Be specific about what is actually good. "The bass is fast and controlled" is better than "delivers an immersive soundscape."
- Mention technical highlights and marquee features (drivers, technology, materials, key specs) and explain why they matter.
- Practical details are welcome: weight, comfort, battery life, what it pairs well with, who it is for.
- Short sentences are fine. So is a touch of personality.

RULES
- Use American English spelling throughout (color not colour, favor not favour, etc.).
- Start the first sentence with the full product name.
- Description length: 1 to 3 paragraphs. Do not pad to fill space.
- No em dashes. Use commas or a new sentence instead.
- Do not use the word "experience" as a verb ("experience the clarity" is banned).
- No hollow hi-fi cliches: "takes your listening to the next level", "sonic journey", "audiophile-grade", "immersive soundscape", "sound perfection", "captivating experience".
- No hard sell. Do not tell the customer to buy it.
- Include SEO keywords naturally and specifically (actual driver type, technology name, product category).
- No links. No markdown. Plain text only.

EXAMPLES OF THE RIGHT TONE
"The HiFiMAN HE1000 Unveiled is aptly named. Compared to the rest of the HE1000 line it sounds clearer, cleaner, and more effortless. Vocals are a touch forward, and trying different amplifiers and tracks with this headphone is a true joy. It has detail and a touch of warmth, and the open planar magnetic drivers reward a good source and amp."

"The HiFiMAN Mini Shangri-La is an electrostatic headphone at a price that actually makes sense. Linear, dynamic, musical, fast, light, and comfortable, it is simply the best value in an over-ear electrostatic headphone."

"If you are shopping for the best-sounding wireless Bluetooth headphone, the Focal Bathys MG should be at the top of your list. Magnesium drivers with M-shaped domes, over 30 hours of battery, genuine leather and aluminum construction, and active noise cancellation that does not compromise the sound."

OUTPUT FORMAT
Return your response in exactly this format (include the markers):

===DESCRIPTION===
[1-3 paragraphs of product description]
===META===
[One sentence, maximum 150 characters, SEO-optimized Google meta description. Include the product name and the single most important feature or value proposition. American English.]
"""

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
- Background colors for header row and alternating rows

Specifications:
{specs}
"""


def generate_description(product_data: dict) -> tuple[str, str]:
    """Returns (description, meta_description)."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=4)

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
    raw = message.content[0].text.strip()
    description = _extract_section(raw, "DESCRIPTION", "META")
    meta = _extract_section(raw, "META", None)[:150]
    return description, meta


def generate_spec_tables(product_data: dict) -> tuple[str, str]:
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"], max_retries=4)

    if product_data["specs"]:
        specs_text = "\n".join(
            f"- {s['name']}: {s['value']}" for s in product_data["specs"]
        )
    else:
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
