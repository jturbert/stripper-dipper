#!/usr/bin/env python3
"""
Scrape and process images only — no text generation.

Usage:
    python images_only.py <url>
    python images_only.py        # reads PRODUCT_URL env var or prompts
"""

import asyncio
import os
import sys
from pathlib import Path

from image_processor import process_images, slugify
from scraper import scrape_product_page


async def main():
    if len(sys.argv) > 1:
        url = sys.argv[1].strip()
    elif os.environ.get("PRODUCT_URL"):
        url = os.environ["PRODUCT_URL"].strip()
    else:
        url = input("Product page URL: ").strip()

    if not url.startswith("http"):
        print("Error: Please provide a full URL starting with http:// or https://")
        sys.exit(1)

    print(f"Scraping {url} ...")
    product = await scrape_product_page(url)
    print(f"Found: {product['name']}")
    print(f"Images found: {len(product['image_urls'])}")

    slug = slugify(product["name"])
    output_dir = Path("output") / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    if not product["image_urls"]:
        print("No images found on page.")
        sys.exit(0)

    print(f"Processing {len(product['image_urls'])} image(s) ...")
    saved = await asyncio.to_thread(
        process_images,
        product["image_urls"],
        product["name"],
        output_dir,
        print,
        max_images=50,
    )

    with open("product_slug.txt", "w") as f:
        f.write(slug)

    print(f"\n{len(saved)} image(s) saved to: {output_dir}/images/")


if __name__ == "__main__":
    asyncio.run(main())
