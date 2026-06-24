#!/usr/bin/env python3
"""Scrape and process images only — no text generation."""

import asyncio
import logging
from pathlib import Path

from cli import parse_args, resolve_input, setup_logging
from image_processor import process_images, process_images_from_bytes, slugify
from pdf_reader import read_pdf
from scraper import scrape_product_page


async def main() -> None:
    args = parse_args(
        "Download and process product images from a URL or PDF.",
        include_max_images=True,
    )
    setup_logging(args.verbose)
    url, pdf_path = resolve_input(args)

    if pdf_path:
        logging.info("Reading PDF: %s ...", pdf_path)
        product = await asyncio.to_thread(read_pdf, pdf_path)
        logging.info("Found: %s", product["name"])
        logging.info("Embedded images: %d", len(product["raw_image_bytes"]))
    else:
        logging.info("Scraping %s ...", url)
        product = await scrape_product_page(url)
        logging.info("Found: %s", product["name"])
        logging.info("Images found: %d", len(product["image_urls"]))

    slug = slugify(product["name"])
    output_dir = Path("output") / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    if product.get("raw_image_bytes"):
        n = min(len(product["raw_image_bytes"]), args.max_images)
        logging.info("Processing %d embedded image(s) ...", n)
        saved = await asyncio.to_thread(
            process_images_from_bytes,
            product["raw_image_bytes"],
            product["name"],
            output_dir,
            logging.info,
            max_images=args.max_images,
        )
    elif product.get("image_urls"):
        n = min(len(product["image_urls"]), args.max_images)
        logging.info("Processing %d image(s) ...", n)
        saved = await asyncio.to_thread(
            process_images,
            product["image_urls"],
            product["name"],
            output_dir,
            logging.info,
            max_images=args.max_images,
        )
    else:
        logging.info("No images found.")
        saved = []

    Path("product_slug.txt").write_text(slug, encoding="utf-8")
    logging.info("\n%d image(s) saved to: %s/images/", len(saved), output_dir)


if __name__ == "__main__":
    asyncio.run(main())
