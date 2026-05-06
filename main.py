#!/usr/bin/env python3
"""
Product Listing Automation — CLI entry point.

Usage:
    python main.py <url>
    python main.py        # prompts for URL
"""

import asyncio
import os
import sys

from pipeline import run_pipeline


def main():
    if len(sys.argv) > 1:
        url = sys.argv[1].strip()
    elif os.environ.get("PRODUCT_URL"):
        url = os.environ["PRODUCT_URL"].strip()
    else:
        url = input("Product page URL: ").strip()

    if not url.startswith("http"):
        print("Error: Please provide a full URL starting with http:// or https://")
        sys.exit(1)

    print()
    try:
        results = asyncio.run(run_pipeline(url, print, max_images=50))
    except RuntimeError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Write slug to file so GitHub Actions can use it for the artifact name
    with open("product_slug.txt", "w") as f:
        f.write(results["slug"])

    print()
    print("=" * 50)
    print(f"Output saved to: {results['output_dir']}/")


if __name__ == "__main__":
    main()
