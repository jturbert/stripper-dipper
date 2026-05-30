#!/usr/bin/env python3
"""
Scrape and process images only — no text generation.

Usage:
    python images_only.py <url>
    python images_only.py <path/to/file.pdf>
    python images_only.py   # reads PRODUCT_URL or PDF_PATH env var, or prompts
"""

import asyncio
import os
import sys
from pathlib import Path

from image_processor import process_images, process_images_from_bytes, slugify
from pdf_reader import read_pdf
from scraper import scrape_product_page


async def main():
    url = None
    pdf_path = None

    if len(sys.argv) > 1:
        arg = sys.argv[1].strip()
        if arg.lower().endswith(".pdf"):
            pdf_path = arg
        else:
            url = arg
    elif os.environ.get("PDF_PATH"):
        pdf_path = os.environ["PDF_PATH"].strip()
    elif os.environ.get("PRODUCT_URL"):
        url = os.environ["PRODUCT_URL"].strip()
    else:
        val = input("Product page URL or path to PDF: ").strip()
        if val.lower().endswith(".pdf"):
            pdf_path = val
        else:
            url = val

    if not pdf_path and (not url or not url.startswith("http")):
        print("Error: Please provide a full URL (http://...) or a path to a PDF file.")
        sys.exit(1)

    if pdf_path:
        print(f"Reading PDF: {pdf_path} ...")
        product = read_pdf(pdf_path)
        print(f"Found: {product['name']}")
        print(f"Embedded images: {len(product['raw_image_bytes'])}")
    else:
        print(f"Scraping {url} ...")
        product = await scrape_product_page(url)
        print(f"Found: {product['name']}")
        print(f"Images found: {len(product['image_urls'])}")

    slug = slugify(product["name"])
    output_dir = Path("output") / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    if product.get("raw_image_bytes"):
        n = len(product["raw_image_bytes"])
        print(f"Processing {n} embedded image(s) ...")
        saved = await asyncio.to_thread(
            process_images_from_bytes,
            product["raw_image_bytes"],
            product["name"],
            output_dir,
            print,
            max_images=50,
        )
    elif product.get("image_urls"):
        n = len(product["image_urls"])
        print(f"Processing {n} image(s) ...")
        saved = await asyncio.to_thread(
            process_images,
            product["image_urls"],
            product["name"],
            output_dir,
            print,
            max_images=50,
        )
    else:
        print("No images found.")
        saved = []

    with open("product_slug.txt", "w") as f:
        f.write(slug)

    print(f"\n{len(saved)} image(s) saved to: {output_dir}/images/")


if __name__ == "__main__":
    asyncio.run(main())
