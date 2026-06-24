"""
PDF reader — extracts product info from a manufacturer spec sheet or brochure.
Returns the same dict structure as scraper.py so the rest of the pipeline works unchanged.

Embedded images are returned as raw bytes in the 'raw_image_bytes' key.
"""

import logging
import re
from pathlib import Path

import pdfplumber
from pypdf import PdfReader


def read_pdf(pdf_path: str) -> dict:
    path = Path(pdf_path)
    if not path.exists():
        raise RuntimeError(f"PDF not found: {pdf_path}")

    all_text_parts = []
    specs = []
    image_bytes_list = []

    # ------------------------------------------------ text and tables
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_text_parts.append(text.strip())

            tables = page.extract_tables()
            for table in tables:
                for row in table:
                    if not row or len(row) < 2:
                        continue
                    k = str(row[0] or "").strip()
                    v = str(row[1] or "").strip()
                    # Skip header rows and empty cells
                    if k and v and k.lower() not in ("specification", "spec", "parameter", ""):
                        specs.append({"name": k, "value": v})

    raw_text = "\n\n".join(all_text_parts)

    # ------------------------------------------------ embedded images
    reader = PdfReader(pdf_path)
    for page in reader.pages:
        for img in page.images:
            try:
                data = img.data
                if data and len(data) > 1024:  # skip tiny icons
                    image_bytes_list.append(data)
            except Exception as e:
                logging.debug("Skipping PDF image: %s", e)
                continue

    # ------------------------------------------------ product name
    lines = [l.strip() for l in raw_text.split("\n") if l.strip()]
    if lines:
        # First line is usually the product name; if it's too long it's likely
        # a paragraph, so fall back to the filename
        name = lines[0] if len(lines[0]) <= 120 else path.stem.replace("-", " ").replace("_", " ").title()
    else:
        name = path.stem.replace("-", " ").replace("_", " ").title()

    # ------------------------------------------------ description
    # First few substantial lines after the name
    desc_lines = [l for l in lines[1:] if len(l) > 50][:5]
    description = "\n\n".join(desc_lines)

    # ------------------------------------------------ raw text (capped for API)
    raw_text_capped = re.sub(r"\n{3,}", "\n\n", raw_text).strip()[:8000]

    logging.info("PDF: %d text lines, %d spec rows, %d images", len(lines), len(specs), len(image_bytes_list))

    return {
        "name": name,
        "description": description,
        "specs": specs,
        "image_urls": [],           # no URLs for a PDF source
        "raw_image_bytes": image_bytes_list,
        "raw_text": raw_text_capped,
        "source_url": f"file://{path.absolute()}",
    }
