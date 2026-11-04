"""Photo quality checks so customers retake blurry or dark photos before analysis."""

from __future__ import annotations

import cv2
import numpy as np

from .types import ImageQuality

MIN_SIDE_PX = 480
MIN_SHARPNESS = 60.0
MIN_BRIGHTNESS = 45.0
MAX_BRIGHTNESS = 215.0
MAX_GLARE = 0.12


def check_quality(image_bgr: np.ndarray) -> ImageQuality:
    h, w = image_bgr.shape[:2]
    gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

    # Normalise size before measuring sharpness so the threshold does not
    # depend on camera resolution.
    scale = 1024.0 / max(h, w)
    small = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA) if scale < 1 else gray
    sharpness = float(cv2.Laplacian(small, cv2.CV_64F).var())
    brightness = float(gray.mean())
    glare_ratio = float((gray >= 250).mean())

    issues: list[str] = []
    if min(h, w) < MIN_SIDE_PX:
        issues.append("low_resolution")
    if sharpness < MIN_SHARPNESS:
        issues.append("blurry")
    if brightness < MIN_BRIGHTNESS:
        issues.append("too_dark")
    if brightness > MAX_BRIGHTNESS:
        issues.append("overexposed")
    if glare_ratio > MAX_GLARE:
        issues.append("strong_glare")

    return ImageQuality(
        width=w,
        height=h,
        sharpness=round(sharpness, 1),
        brightness=round(brightness, 1),
        glare_ratio=round(glare_ratio, 4),
        ok=not issues,
        issues=issues,
    )
