"""
Async pipeline orchestrator — shared by both the CLI (main.py) and web server (app.py).

log: callable(str) — receives progress messages.
     From async context: called directly.
     From threads (to_thread): called via loop.call_soon_threadsafe.
"""

import asyncio
from pathlib import Path

from generator import generate_description, generate_spec_tables
from image_processor import process_images, slugify
from scraper import scrape_product_page


def _wrap_html(table_html: str, title: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>{title}</title></head>
<body>
{table_html}
</body>
</html>
"""


async def run_pipeline(url: str, log) -> dict:
    loop = asyncio.get_running_loop()

    # thread_log: safe to call from worker threads spawned by to_thread
    def thread_log(msg: str) -> None:
        loop.call_soon_threadsafe(log, msg)

    # ---------------------------------------------------------------- scrape
    log(f"Scraping {url} ...")
    try:
        product = await scrape_product_page(url)
    except RuntimeError as e:
        raise RuntimeError(f"Scraping failed: {e}") from e

    log(f"Found: {product['name']}")
    log(f"Specs: {len(product['specs'])}   Images: {len(product['image_urls'])}")

    # ------------------------------------------------------ output directory
    slug = slugify(product["name"])
    output_dir = Path("output") / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    # --------------------------------------------------- generate via Claude
    def _generate() -> tuple[str, str, str]:
        thread_log("Generating description ...")
        desc = generate_description(product)
        thread_log("Description done.")
        thread_log("Generating spec tables ...")
        shopify, mailchimp = generate_spec_tables(product)
        thread_log("Spec tables done.")
        return desc, shopify, mailchimp

    description, shopify_html, mailchimp_html = await asyncio.to_thread(_generate)

    (output_dir / "description.md").write_text(
        f"# {product['name']}\n\n{description}\n", encoding="utf-8"
    )
    (output_dir / "specs-shopify.html").write_text(
        _wrap_html(shopify_html, "Shopify Specs"), encoding="utf-8"
    )
    (output_dir / "specs-mailchimp.html").write_text(
        _wrap_html(mailchimp_html, "Mailchimp Specs"), encoding="utf-8"
    )

    # -------------------------------------------------------- process images
    saved_paths: list[Path] = []
    if product["image_urls"]:
        n = min(len(product["image_urls"]), 10)
        log(f"Processing {n} image(s) ...")
        saved_paths = await asyncio.to_thread(
            process_images,
            product["image_urls"],
            product["name"],
            output_dir,
            on_progress=thread_log,
            max_images=10,
        )
        log(f"Images done. {len(saved_paths)} saved.")
    else:
        log("No images found on page.")

    log("All done.")
    return {
        "name": product["name"],
        "slug": slug,
        "description": description,
        "shopify_html": shopify_html,
        "mailchimp_html": mailchimp_html,
        "image_paths": [str(p).replace("\\", "/") for p in saved_paths],
        "output_dir": str(output_dir),
    }
