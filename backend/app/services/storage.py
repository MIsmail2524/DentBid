"""Photo storage on local disk (swap for S3 in production).

Every upload is decoded and re-encoded as JPEG, which drops EXIF/GPS metadata
and any payload hidden in the original file (polyglots, scripts in SVG etc.).
"""

from __future__ import annotations

import io
import uuid
import warnings
from pathlib import Path

from fastapi import HTTPException, UploadFile
from PIL import Image, ImageOps

from ..config import get_settings
from ..security import sign_media

ALLOWED = {"JPEG", "PNG", "WEBP", "MPO"}


def media_root() -> Path:
    root = get_settings().media_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def private_root() -> Path:
    root = get_settings().private_media_dir
    root.mkdir(parents=True, exist_ok=True)
    return root


def _decode(data: bytes) -> Image.Image:
    s = get_settings()
    Image.MAX_IMAGE_PIXELS = s.max_image_pixels
    try:
        with warnings.catch_warnings():
            # Pillow only warns between 1x and 2x the limit; treat that as an error too
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(data))
            fmt = img.format
            if fmt not in ALLOWED:
                raise HTTPException(400, f"Unsupported image format {fmt}")
            if img.width * img.height > s.max_image_pixels:
                raise HTTPException(400, "Image dimensions too large")
            img.load()
            img = ImageOps.exif_transpose(img)
    except HTTPException:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise HTTPException(400, "Image dimensions too large")
    except Exception:
        raise HTTPException(400, "File is not a valid image")
    return img.convert("RGB")


def _read_limited(upload: UploadFile) -> bytes:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = upload.file.read(limit + 1)
    if len(data) > limit:
        raise HTTPException(413, f"Photo larger than {get_settings().max_upload_mb} MB")
    if not data:
        raise HTTPException(400, "Empty file")
    return data


def _save(upload: UploadFile, root: Path, folder: str) -> tuple[str, int, int]:
    img = _decode(_read_limited(upload))
    s = get_settings()
    img.thumbnail((s.max_image_side, s.max_image_side))
    rel = Path(folder) / f"{uuid.uuid4().hex}.jpg"
    dst = root / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    img.save(dst, "JPEG", quality=90)  # no exif= argument: metadata dropped
    return rel.as_posix(), img.width, img.height


def save_photo(upload: UploadFile, folder: str) -> tuple[str, int, int]:
    """Request photo. Returns (relative path, width, height)."""
    return _save(upload, media_root(), folder)


def save_private(upload: UploadFile, folder: str) -> str:
    """Verification document; only reachable through an authorised endpoint."""
    return _save(upload, private_root(), folder)[0]


def resolve_inside(root: Path, rel: str) -> Path | None:
    """Joins rel to root and refuses anything escaping root (path traversal)."""
    base = root.resolve()
    p = (base / rel).resolve()
    if base != p and base not in p.parents:
        return None
    return p


def media_url(rel: str | None) -> str | None:
    """Short-lived signed URL. Works in <img> tags, which cannot send auth headers."""
    if not rel:
        return None
    base = get_settings().public_base_url.rstrip("/")
    return f"{base}/media/{rel}?{sign_media(rel)}"
