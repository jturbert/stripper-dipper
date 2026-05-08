"""
Downloads product images, removes backgrounds, pads to square, saves as PNG.
"""

import gc
import io
import re
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image
from rembg import remove, new_session

# Downscale images to this max dimension before rembg processing.
# rembg quality is near-identical at 1200px vs 3000px, but memory use drops ~6x.
MAX_PROCESS_DIM = 1200

# Loaded lazily on first use so Playwright can scrape without memory contention
_session = None


def _get_session():
    global _session
    if _session is None:
        _session = new_session("birefnet-general")
    return _session


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def download_image(url: str) -> bytes | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": url,
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read()
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        print(f"  [warn] Could not download {url}: {e}")
        return None


def _downscale(img: Image.Image, max_dim: int) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_dim:
        return img
    scale = max_dim / max(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def process_image(raw_bytes: bytes) -> Image.Image:
    """Remove background, pad to square with transparent background."""
    # Downscale before rembg to keep memory usage low
    img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")
    img = _downscale(img, MAX_PROCESS_DIM)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    del img

    output_bytes = remove(buf.getvalue(), session=_get_session())
    del buf

    no_bg = Image.open(io.BytesIO(output_bytes)).convert("RGBA")
    del output_bytes

    w, h = no_bg.size
    size = max(w, h)
    padding = 20
    canvas_size = size + padding * 2

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (0, 0, 0, 0))
    paste_x = (canvas_size - w) // 2
    paste_y = (canvas_size - h) // 2
    canvas.paste(no_bg, (paste_x, paste_y), no_bg)
    del no_bg

    return canvas


def _process_one(args) -> tuple[int, Path | None]:
    url, slug, images_dir, idx, log = args
    log(f"Downloading image {idx + 1}: {url[:80]}...")
    raw = download_image(url)
    if raw is None:
        return idx, None

    try:
        Image.open(io.BytesIO(raw)).verify()
    except Exception:
        log(f"[warn] Image {idx + 1} is not valid, skipping.")
        return idx, None

    log(f"Removing background from image {idx + 1}...")
    try:
        processed = process_image(raw)
    except Exception as e:
        log(f"[warn] Background removal failed for image {idx + 1}: {e}. Saving original.")
        try:
            processed = Image.open(io.BytesIO(raw)).convert("RGBA")
        except Exception:
            return idx, None
    finally:
        del raw
        gc.collect()

    filename = f"{slug}-{idx + 1:02d}.png"
    out_path = images_dir / filename
    processed.save(out_path, "PNG", optimize=True)
    del processed
    gc.collect()

    log(f"Saved: {filename}")
    return idx, out_path


def process_images(
    image_urls: list[str],
    product_name: str,
    output_dir: Path,
    on_progress=None,
    *,
    max_images: int = 10,
) -> list[Path]:
    """Download, process, and save product images. Returns saved paths."""
    log = on_progress or print

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(product_name)
    urls = image_urls[:max_images]

    args = [(url, slug, images_dir, idx, log) for idx, url in enumerate(urls)]

    results: list[tuple[int, Path | None]] = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(_process_one, args))

    # Return paths in original order, excluding failures
    saved = [path for _, path in sorted(results) if path is not None]

    return saved
