#!/usr/bin/env python3
"""Product Listing Generator — full pipeline (scrape + describe + images)."""

import asyncio
import logging
import sys
from pathlib import Path

from cli import parse_args, resolve_input, setup_logging
from pipeline import run_pipeline


def main() -> None:
    args = parse_args(
        "Generate a full product listing from a URL or PDF.",
        include_max_images=True,
    )
    setup_logging(args.verbose)
    url, pdf_path = resolve_input(args)

    try:
        results = asyncio.run(
            run_pipeline(
                url or "",
                logging.info,
                max_images=args.max_images,
                pdf_path=pdf_path,
            )
        )
    except RuntimeError as e:
        logging.error("Pipeline failed: %s", e)
        sys.exit(1)

    Path("product_slug.txt").write_text(results["slug"], encoding="utf-8")
    logging.info("\nOutput saved to: %s/", results["output_dir"])


if __name__ == "__main__":
    main()
