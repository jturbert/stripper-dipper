"""
Playwright-based scraper for manufacturer product pages.
Returns structured product data: name, description, specs, image URLs.
"""

import re
import asyncio
from urllib.parse import urljoin, urlparse
from playwright.async_api import async_playwright


async def scrape_product_page(url: str) -> dict:
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            )
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="load", timeout=60_000)
        except Exception:
            # Some pages never fire 'load' cleanly — try just waiting for the DOM
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=30_000)
            except Exception as e:
                await browser.close()
                raise RuntimeError(f"Failed to load page: {e}")

        # Let JS render after the initial load
        await page.wait_for_timeout(3_000)

        # --- product name ---
        name = await _extract_name(page)

        # --- description text ---
        description = await _extract_description(page)

        # --- specifications ---
        specs = await _extract_specs(page)

        # --- image URLs ---
        image_urls = await _extract_images(page, url)

        # --- raw page text (sent to Claude for context) ---
        raw_text = await page.inner_text("body")
        raw_text = re.sub(r"\n{3,}", "\n\n", raw_text).strip()

        await browser.close()

    return {
        "name": name,
        "description": description,
        "specs": specs,
        "image_urls": image_urls,
        "raw_text": raw_text[:8000],  # cap for API context
        "source_url": url,
    }


async def _extract_name(page) -> str:
    selectors = [
        "h1",
        "[class*='product-title']",
        "[class*='product-name']",
        "[class*='product_title']",
        "[itemprop='name']",
        "title",
    ]
    for sel in selectors:
        try:
            el = page.locator(sel).first
            text = (await el.inner_text(timeout=2_000)).strip()
            if text and len(text) < 200:
                return text
        except Exception:
            continue
    return "Unknown Product"


async def _extract_description(page) -> str:
    selectors = [
        "[class*='product-description']",
        "[class*='product_description']",
        "[itemprop='description']",
        "[class*='description']",
        "[class*='overview']",
        "[class*='about']",
        "article",
        "main p",
    ]
    chunks = []
    for sel in selectors:
        try:
            els = page.locator(sel)
            count = await els.count()
            for i in range(min(count, 5)):
                text = (await els.nth(i).inner_text(timeout=2_000)).strip()
                if len(text) > 80:
                    chunks.append(text)
            if chunks:
                break
        except Exception:
            continue
    return "\n\n".join(chunks[:3]) if chunks else ""


async def _extract_specs(page) -> list[dict]:
    """Returns list of {name, value} dicts."""
    specs = []

    # Strategy 1: definition lists
    try:
        dts = page.locator("dt")
        dds = page.locator("dd")
        dt_count = await dts.count()
        dd_count = await dds.count()
        if dt_count and dt_count == dd_count:
            for i in range(dt_count):
                k = (await dts.nth(i).inner_text()).strip()
                v = (await dds.nth(i).inner_text()).strip()
                if k and v:
                    specs.append({"name": k, "value": v})
            if specs:
                return specs
    except Exception:
        pass

    # Strategy 2: two-column tables
    try:
        tables = page.locator("table")
        count = await tables.count()
        for i in range(count):
            table = tables.nth(i)
            rows = table.locator("tr")
            row_count = await rows.count()
            for j in range(row_count):
                cells = rows.nth(j).locator("td, th")
                cell_count = await cells.count()
                if cell_count == 2:
                    k = (await cells.nth(0).inner_text()).strip()
                    v = (await cells.nth(1).inner_text()).strip()
                    if k and v:
                        specs.append({"name": k, "value": v})
            if specs:
                return specs
    except Exception:
        pass

    # Strategy 3: labelled list items / divs with colon or class hints
    try:
        selectors = [
            "[class*='spec'] li",
            "[class*='spec-row']",
            "[class*='spec_row']",
            "[class*='specification'] li",
            "[class*='features'] li",
        ]
        for sel in selectors:
            els = page.locator(sel)
            count = await els.count()
            for i in range(count):
                text = (await els.nth(i).inner_text()).strip()
                if ":" in text:
                    parts = text.split(":", 1)
                    specs.append({"name": parts[0].strip(), "value": parts[1].strip()})
            if specs:
                return specs
    except Exception:
        pass

    return specs


async def _extract_images(page, base_url: str) -> list[str]:
    domain = urlparse(base_url).netloc
    seen: set[str] = set()
    images: list[str] = []

    img_srcs = await page.eval_on_selector_all(
        "img",
        """els => els.map(el => ({
            src: el.src || '',
            dataSrc: el.dataset.src || '',
            width: el.naturalWidth || el.width || 0,
            height: el.naturalHeight || el.height || 0,
        }))""",
    )

    for img in img_srcs:
        src = img.get("dataSrc") or img.get("src") or ""
        if not src or src.startswith("data:"):
            continue
        abs_url = urljoin(base_url, src)
        # filter tiny icons / tracking pixels
        w, h = img.get("width", 0), img.get("height", 0)
        if w and h and (w < 100 or h < 100):
            continue
        if abs_url not in seen:
            seen.add(abs_url)
            images.append(abs_url)

    # Also grab srcset sources
    srcsets = await page.eval_on_selector_all(
        "img[srcset], source[srcset]",
        "els => els.map(el => el.srcset)",
    )
    for srcset in srcsets:
        for part in srcset.split(","):
            src = part.strip().split()[0]
            if src:
                abs_url = urljoin(base_url, src)
                if abs_url not in seen:
                    seen.add(abs_url)
                    images.append(abs_url)

    # Prefer product-domain images, deprioritise CDN-only if there are enough
    product_images = [u for u in images if domain in u or "product" in u.lower()]
    return product_images if product_images else images
