"""Ham tasarım görselinden Pinterest'e uygun dikey pin görseli üretir.

Pinterest'in önerdiği 2:3 dikey oran kullanılır (varsayılan 1000x1500 px).
Şablon: üstte tasarım (contain ile ortalanır), altta sabit bir bant içinde
ürün adı ve marka adı metin overlay'i.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger("pinterest_pod")

CANVAS_SIZE = (1000, 1500)  # Pinterest önerilen 2:3 dikey oran
BOTTOM_BAND_HEIGHT = 260
BACKGROUND_COLOR = (255, 255, 255)
BAND_COLOR = (24, 24, 24)
TITLE_COLOR = (255, 255, 255)
BRAND_COLOR = (200, 200, 200)
PADDING = 40

_FALLBACK_FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/Library/Fonts/Arial Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
]


class ImageGenerationError(Exception):
    pass


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "urun"


def _load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    candidates = [font_path] if font_path else []
    candidates += _FALLBACK_FONT_PATHS
    for path in candidates:
        if not path:
            continue
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    logger.warning(
        "Hiçbir TrueType font bulunamadı (FONT_PATH boş/geçersiz), "
        "PIL varsayılan bitmap fontu kullanılacak (düşük kalite)."
    )
    return ImageFont.load_default()


def _open_design_image(source: str) -> Image.Image:
    parsed = urlparse(source)
    if parsed.scheme in ("http", "https"):
        resp = requests.get(source, timeout=30)
        resp.raise_for_status()
        from io import BytesIO

        return Image.open(BytesIO(resp.content)).convert("RGBA")

    path = Path(source)
    if not path.is_absolute():
        path = Path.cwd() / path
    if not path.exists():
        raise ImageGenerationError(f"Tasarım görseli bulunamadı: {source}")
    return Image.open(path).convert("RGBA")


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont, max_width: int) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        bbox = draw.textbbox((0, 0), candidate, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def generate_pin_image(
    design_source: str,
    urun_adi: str,
    brand_name: str,
    output_dir: Path,
    font_path: str = "",
    logo_path: str = "",
    filename_hint: str = "",
    force: bool = False,
) -> Path:
    """Verilen tasarımdan pin görselini üretir ve output_dir içine kaydeder.

    Aynı ürün için görsel zaten üretilmişse (force=False) yeniden üretmez,
    var olan dosyanın yolunu döner (idempotent).
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    slug = slugify(filename_hint or urun_adi)
    out_path = output_dir / f"{slug}.png"

    if out_path.exists() and not force:
        return out_path

    design = _open_design_image(design_source)

    canvas = Image.new("RGB", CANVAS_SIZE, BACKGROUND_COLOR)
    content_height = CANVAS_SIZE[1] - BOTTOM_BAND_HEIGHT
    content_box = (CANVAS_SIZE[0], content_height)

    design_ratio = design.width / design.height
    box_ratio = content_box[0] / content_box[1]
    if design_ratio > box_ratio:
        new_width = content_box[0]
        new_height = round(new_width / design_ratio)
    else:
        new_height = content_box[1]
        new_width = round(new_height * design_ratio)
    resized = design.resize((new_width, new_height), Image.LANCZOS)

    offset_x = (CANVAS_SIZE[0] - new_width) // 2
    offset_y = (content_height - new_height) // 2
    canvas.paste(resized, (offset_x, offset_y), resized)

    draw = ImageDraw.Draw(canvas)
    band_top = CANVAS_SIZE[1] - BOTTOM_BAND_HEIGHT
    draw.rectangle([(0, band_top), (CANVAS_SIZE[0], CANVAS_SIZE[1])], fill=BAND_COLOR)

    max_text_width = CANVAS_SIZE[0] - 2 * PADDING
    title_font = _load_font(font_path, 54)
    brand_font = _load_font(font_path, 32)

    title_lines = _wrap_text(draw, urun_adi, title_font, max_text_width)[:3]
    line_height = title_font.size + 10
    title_block_height = len(title_lines) * line_height
    text_y = band_top + PADDING

    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        line_width = bbox[2] - bbox[0]
        x = (CANVAS_SIZE[0] - line_width) // 2
        draw.text((x, text_y), line, font=title_font, fill=TITLE_COLOR)
        text_y += line_height

    if logo_path:
        try:
            logo = Image.open(logo_path).convert("RGBA")
            logo.thumbnail((160, 80))
            logo_x = (CANVAS_SIZE[0] - logo.width) // 2
            logo_y = CANVAS_SIZE[1] - PADDING - logo.height
            canvas.paste(logo, (logo_x, logo_y), logo)
        except OSError as exc:
            logger.warning("Logo yüklenemedi (%s), sadece marka adı yazılacak: %s", logo_path, exc)
            logo_path = ""

    if brand_name and not logo_path:
        bbox = draw.textbbox((0, 0), brand_name, font=brand_font)
        brand_width = bbox[2] - bbox[0]
        x = (CANVAS_SIZE[0] - brand_width) // 2
        y = CANVAS_SIZE[1] - PADDING - brand_font.size
        draw.text((x, y), brand_name, font=brand_font, fill=BRAND_COLOR)

    canvas.save(out_path, "PNG")
    return out_path
