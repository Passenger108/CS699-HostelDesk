import os
import uuid
from io import BytesIO

from flask import current_app
from PIL import Image, ImageDraw, ImageFont, ImageOps, UnidentifiedImageError

from app.common.errors import fail

MAX_BYTES = 10 * 1024 * 1024
FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
LONG_SIDE = 1600
BROKEN = (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError)


def folder() -> str:
    path = current_app.config.get("UPLOAD_FOLDER") or os.path.join(
        current_app.instance_path, "uploads"
    )
    os.makedirs(path, exist_ok=True)
    return path


def read_image(upload) -> Image.Image:
    if upload is None or not upload.filename:
        raise fail("PHOTO_REQUIRED", "photo")
    data = upload.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise fail("PHOTO_TOO_BIG", "photo")
    try:
        Image.open(BytesIO(data)).verify()
        image = Image.open(BytesIO(data))
        image.load()
    except BROKEN:
        raise fail("BAD_PHOTO", "photo") from None
    if image.format not in FORMATS or getattr(image, "is_animated", False):
        raise fail("BAD_PHOTO", "photo")
    if upload.mimetype != FORMATS[image.format]:
        raise fail("BAD_PHOTO", "photo")
    return image


def stamp(image: Image.Image, lines: list[str]) -> bytes:
    image = ImageOps.exif_transpose(image).convert("RGB")
    image.thumbnail((LONG_SIDE, LONG_SIDE))
    size = max(14, image.width // 40)
    font = ImageFont.load_default(size=size)
    draw = ImageDraw.Draw(image)
    text = "\n".join(lines)
    box = draw.multiline_textbbox((0, 0), text, font=font)
    top = image.height - (box[3] - box[1]) - size
    draw.rectangle((0, top, image.width, image.height), fill=(0, 0, 0))
    draw.multiline_text((size // 2, top + size // 2), text, fill=(255, 255, 255), font=font)
    out = BytesIO()
    image.save(out, "JPEG", quality=85)
    return out.getvalue()


def save(data: bytes) -> str:
    key = f"{uuid.uuid4().hex}.jpg"
    with open(os.path.join(folder(), key), "wb") as handle:
        handle.write(data)
    return key


def path_for(key: str) -> str:
    return os.path.join(folder(), os.path.basename(key))
