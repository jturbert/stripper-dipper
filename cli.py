"""
Shared CLI argument parsing, logging setup, and input resolution.
Used by main.py, text_only.py, and images_only.py.
"""

import argparse
import logging
import os
import sys
from pathlib import Path


def parse_args(description: str, *, include_max_images: bool = False) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument(
        "input",
        nargs="?",
        metavar="URL_OR_PDF",
        help="Product page URL (http/https) or path to a PDF file",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )
    if include_max_images:
        parser.add_argument(
            "--max-images",
            type=int,
            default=10,
            dest="max_images",
            metavar="N",
            help="Maximum number of images to process (default: 10)",
        )
    return parser.parse_args()


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


def resolve_input(args: argparse.Namespace) -> tuple[str | None, str | None]:
    """Return (url, pdf_path) from CLI args, env vars, or interactive prompt."""
    val: str = args.input or ""
    if not val:
        val = os.environ.get("PDF_PATH") or os.environ.get("PRODUCT_URL") or ""
    if not val:
        val = input("Product page URL or path to PDF: ").strip()
    if not val:
        logging.error("No input provided.")
        sys.exit(1)

    val = val.strip()
    if val.lower().endswith(".pdf"):
        if not Path(val).exists():
            logging.error("PDF not found: %s", val)
            sys.exit(1)
        return None, val

    if not val.startswith("http"):
        logging.error("URL must start with http:// or https://")
        sys.exit(1)

    return val, None
