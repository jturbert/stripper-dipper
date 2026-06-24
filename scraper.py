"""
Playwright-based scraper for manufacturer product pages.
Returns structured product data: name, description, specs, image URLs.
"""

import re
import asyncio
from urllib.parse import urljoin, urlparse, urlunparse
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

    def _collect(img_list: list[dict]) -> list[str]:
        results = []
        for img in img_list:
            src = img.get("dataSrc") or img.get("src") or ""
            if not src or src.startswith("data:"):
                continue
            abs_url = urljoin(base_url, src)
            w, h = img.get("width", 0), img.get("height", 0)
            if w and h and (w < 150 or h < 150):
                continue
            if abs_url not in seen:
                seen.add(abs_url)
                results.append(abs_url)
        return results

    js = """(sel) => [...document.querySelectorAll(sel)].map(el => ({
        src: el.src || el.getAttribute('data-src') || '',
        dataSrc: el.dataset.src || el.dataset.lazySrc || '',
        width: el.naturalWidth || el.width || 0,
        height: el.naturalHeight || el.height || 0,
    }))"""

    # Strategy 1: images inside recognised product gallery containers
    gallery_selectors = [
        "[class*='product-gallery'] img",
        "[class*='product-image'] img",
        "[class*='product-media'] img",
        "[class*='product-photo'] img",
        "[class*='media-gallery'] img",
        "[class*='image-gallery'] img",
        "[class*='product-images'] img",
        "[class*='gallery-viewer'] img",
        "[id*='product-gallery'] img",
        "[id*='product-images'] img",
        "[class*='swiper-slide'] img",
        "[class*='slick-slide'] img",
        "[class*='carousel-item'] img",
        "figure.product img",
        ".product__media img",
    ]
    gallery_images: list[str] = []
    for sel in gallery_selectors:
        try:
            imgs = await page.evaluate(f"() => ({js})('{sel}')")
            gallery_images.extend(_collect(imgs))
        except Exception:
            continue
        if len(gallery_images) >= 2:
            break

    if len(gallery_images) >= 2:
        return gallery_images

    # Strategy 2: all page images, filtered by size and domain
    try:
        all_imgs = await page.evaluate(f"() => ({js})('img')")
        all_images = _collect(all_imgs)
    except Exception:
        all_images = []

    # Also pick largest srcset variant for each img
    try:
        srcsets = await page.eval_on_selector_all(
            "img[srcset], source[srcset]",
            "els => els.map(el => el.srcset)",
        )
        for srcset in srcsets:
            parts = [p.strip().split() for p in srcset.split(",") if p.strip()]
            # pick the widest declared size
            best = max(parts, key=lambda p: int(p[1].rstrip("w")) if len(p) > 1 and p[1].endswith("w") else 0, default=None)
            if best:
                abs_url = urljoin(base_url, best[0])
                if abs_url not in seen:
                    seen.add(abs_url)
                    all_images.append(abs_url)
    except Exception:
        pass

    # Resolve WordPress thumbnails to originals (strip -WxH size suffix)
    all_images = [_resolve_wp_thumbnail(u) for u in all_images]
    # Re-deduplicate after resolution
    seen_resolved: set[str] = set()
    deduped: list[str] = []
    for u in all_images:
        if u not in seen_resolved:
            seen_resolved.add(u)
            deduped.append(u)
    all_images = deduped

    # Prefer same-domain images with product-related path segments
    product_images = [
        u for u in all_images
        if domain in u and any(k in u.lower() for k in (
            "product", "shop", "item", "catalog", "cdn", "uploads"
        ))
    ]
    return product_images if len(product_images) >= 2 else all_images


def _resolve_wp_thumbnail(url: str) -> str:
    """Convert a WordPress thumbnail URL to its original by stripping the -WxH suffix."""
    # Matches e.g. image-300x200.jpg -> image.jpg
    return re.sub(r"-\d+x\d+(\.[a-zA-Z]+)$", r"\1", url)
