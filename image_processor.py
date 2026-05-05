"""
Downloads product images, removes backgrounds, pads to square, saves as PNG.
"""

import io
import re
import urllib.request
import urllib.error
from pathlib import Path

from PIL import Image
from rembg import remove


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


def process_image(raw_bytes: bytes) -> Image.Image:
    """Remove background and pad to square with white background."""
    input_img = Image.open(io.BytesIO(raw_bytes)).convert("RGBA")

    # Remove background
    output_bytes = remove(raw_bytes)
    no_bg = Image.open(io.BytesIO(output_bytes)).convert("RGBA")

    # Pad to square
    w, h = no_bg.size
    size = max(w, h)
    padding = 20  # small border
    canvas_size = size + padding * 2

    canvas = Image.new("RGBA", (canvas_size, canvas_size), (255, 255, 255, 255))
    paste_x = (canvas_size - w) // 2
    paste_y = (canvas_size - h) // 2
    canvas.paste(no_bg, (paste_x, paste_y), no_bg)

    return canvas.convert("RGB")


def process_images(
    image_urls: list[str],
    product_name: str,
    output_dir: Path,
    on_progress=None,
    *,
    max_images: int = 10,
) -> list[Path]:
    """Download, process, and save product images. Returns saved paths.

    on_progress: optional callable(str) for progress messages — used by the
    web pipeline to stream updates; falls back to print when None.
    """
    log = on_progress or print

    images_dir = output_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(product_name)
    saved: list[Path] = []
    count = 0

    for url in image_urls:
        if count >= max_images:
            break

        log(f"Downloading image {count + 1}: {url[:80]}...")
        raw = download_image(url)
        if raw is None:
            continue

        try:
            Image.open(io.BytesIO(raw)).verify()
        except Exception:
            log("[warn] Not a valid image, skipping.")
            continue

        log("Removing background...")
        try:
            processed = process_image(raw)
        except Exception as e:
            log(f"[warn] Background removal failed: {e}. Saving original.")
            try:
                processed = Image.open(io.BytesIO(raw)).convert("RGB")
            except Exception:
                continue

        filename = f"{slug}-{count + 1:02d}.png"
        out_path = images_dir / filename
        processed.save(out_path, "PNG", optimize=True)
        saved.append(out_path)
        count += 1
        log(f"Saved: {filename}")

    return saved
