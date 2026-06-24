#!/usr/bin/env python3
"""Generate description and spec tables only — no image processing."""

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from cli import parse_args, resolve_input, setup_logging
from generator import generate_description, generate_spec_tables
from image_processor import slugify
from pdf_reader import read_pdf
from pipeline import wrap_html
from scraper import scrape_product_page


async def main() -> None:
    args = parse_args("Generate product description and spec tables from a URL or PDF.")
    setup_logging(args.verbose)
    url, pdf_path = resolve_input(args)

    if pdf_path:
        logging.info("Reading PDF: %s ...", pdf_path)
        product = await asyncio.to_thread(read_pdf, pdf_path)
    else:
        logging.info("Scraping %s ...", url)
        product = await scrape_product_page(url)

    logging.info("Found: %s", product["name"])

    slug = slugify(product["name"])
    output_dir = Path("output") / slug
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run both Claude calls in parallel — each takes ~5-10s, no shared state
    loop = asyncio.get_running_loop()

    def _gen_description():
        logging.info("Generating description ...")
        result = generate_description(product)
        logging.info("Description done.")
        return result

    def _gen_tables():
        logging.info("Generating spec tables ...")
        result = generate_spec_tables(product)
        logging.info("Spec tables done.")
        return result

    with ThreadPoolExecutor(max_workers=2) as pool:
        (description, meta_description), (shopify_html, mailchimp_html) = await asyncio.gather(
            loop.run_in_executor(pool, _gen_description),
            loop.run_in_executor(pool, _gen_tables),
        )

    (output_dir / "description.md").write_text(
        f"# {product['name']}\n\n{description}\n\n---\n\n**Meta description:**\n{meta_description}\n",
        encoding="utf-8",
    )
    (output_dir / "specs-shopify.html").write_text(
        wrap_html(shopify_html, "Shopify Specs"), encoding="utf-8"
    )
    (output_dir / "specs-mailchimp.html").write_text(
        wrap_html(mailchimp_html, "Mailchimp Specs"), encoding="utf-8"
    )

    Path("product_slug.txt").write_text(slug, encoding="utf-8")
    logging.info("\nOutput saved to: %s/", output_dir)


if __name__ == "__main__":
    asyncio.run(main())
