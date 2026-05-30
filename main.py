#!/usr/bin/env python3
"""
Product Listing Automation — CLI entry point.

Usage:
    python main.py <url>
    python main.py        # reads PRODUCT_URL or PDF_PATH env var, or prompts
"""

import asyncio
import os
import sys

from pipeline import run_pipeline


def main():
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

    print()
    try:
        results = asyncio.run(run_pipeline(url or "", print, max_images=50, pdf_path=pdf_path))
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    with open("product_slug.txt", "w") as f:
        f.write(results["slug"])

    print()
    print("=" * 50)
    print(f"Output saved to: {results['output_dir']}/")


if __name__ == "__main__":
    main()
