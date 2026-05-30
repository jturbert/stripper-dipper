#!/usr/bin/env python3
"""
Generate description and spec tables only — no image processing.

Usage:
    python text_only.py <url>
    python text_only.py <path/to/file.pdf>
    python text_only.py   # reads PRODUCT_URL or PDF_PATH env var, or prompts
"""

import asyncio
import os
import sys
from pathlib import Path

from generator import generate_description, generate_spec_tables
from image_processor import slugify
from pdf_reader import read_pdf
from pipeline import _wrap_html
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
    else:
        print(f"Scraping {url} ...")
        product = await scrape_product_page(url)

    print(f"Found: {product['name']}")

    slug = slugify(product["name"])
    output_dir = Path("output") / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    print("Generating description ...")
    description, meta_description = generate_description(product)
    print("Description done.")

    print("Generating spec tables ...")
    shopify_html, mailchimp_html = generate_spec_tables(product)
    print("Spec tables done.")

    (output_dir / "description.md").write_text(
        f"# {product['name']}\n\n{description}\n\n---\n\n**Meta description:**\n{meta_description}\n",
        encoding="utf-8",
    )
    (output_dir / "specs-shopify.html").write_text(
        _wrap_html(shopify_html, "Shopify Specs"), encoding="utf-8"
    )
    (output_dir / "specs-mailchimp.html").write_text(
        _wrap_html(mailchimp_html, "Mailchimp Specs"), encoding="utf-8"
    )

    with open("product_slug.txt", "w") as f:
        f.write(slug)

    print(f"\nOutput saved to: {output_dir}/")


if __name__ == "__main__":
    asyncio.run(main())
