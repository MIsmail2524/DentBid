"""Stores uploaded photos on local disk under MEDIA_DIR (swap for S3 in production)."""

from __future__ import annotations

import io
import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

from ..config import get_settings

ALLOWED = {"JPEG", "PNG", "WEBP", "HEIF", "MPO"}


def media_root() -> Path:
    root = get_settings().media_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def save_photo(upload: UploadFile, folder: str) -> tuple[str, int, int]:
    """Validates, fixes EXIF rotation, strips metadata (GPS!), downsizes, saves as JPEG.

    Returns (relative path, width, height).
    """
    s = get_settings()
    data = upload.file.read(s.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > s.max_upload_mb * 1024 * 1024:
        raise HTTPException(413, f"Photo larger than {s.max_upload_mb} MB")
    try:
        img = Image.open(io.BytesIO(data))
        fmt = img.format
        img = ImageOps.exif_transpose(img)
    except Exception:
        raise HTTPException(400, "File is not a valid image")
    if fmt not in ALLOWED:
        raise HTTPException(400, f"Unsupported image format {fmt}")
    img = img.convert("RGB")
    img.thumbnail((s.max_image_side, s.max_image_side))

    rel = Path(folder) / f"{uuid.uuid4().hex}.jpg"
    dst = media_root() / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, "JPEG", quality=90)  # no exif= argument: metadata dropped
    return rel.as_posix(), img.width, img.height


def media_url(rel: str | None) -> str | None:
    if not rel:
        return None
    return f"{get_settings().public_base_url.rstrip('/')}/media/{rel}"
