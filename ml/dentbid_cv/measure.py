"""Geometric and photometric measurements of a single damage mask."""

from __future__ import annotations

import cv2
import numpy as np
from skimage.morphology import skeletonize


def mask_polygon(mask: np.ndarray, epsilon_ratio: float = 0.004) -> list[list[float]]:
    """Largest outer contour of a binary mask, simplified."""
    contours, _ = cv2.findContours(mask.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return []
    c = max(contours, key=cv2.contourArea)
    eps = epsilon_ratio * cv2.arcLength(c, True)
    approx = cv2.approxPolyDP(c, eps, True)
    return [[float(x), float(y)] for x, y in approx.reshape(-1, 2)]


def skeleton_length_px(mask: np.ndarray) -> float:
    """Approximate centre-line length of an elongated mask (scratch, crack).

    Diagonal steps count as sqrt(2), straight steps as 1.
    """
    skel = skeletonize(mask.astype(bool))
    if not skel.any():
        return 0.0
    s = skel
    straight = (s[:, 1:] & s[:, :-1]).sum() + (s[1:, :] & s[:-1, :]).sum()
    # Count a diagonal link only when it is not already bridged by an
    # orthogonal corner, otherwise corners would be counted twice.
    d1 = s[1:, 1:] & s[:-1, :-1] & ~s[:-1, 1:] & ~s[1:, :-1]
    d2 = s[1:, :-1] & s[:-1, 1:] & ~s[:-1, :-1] & ~s[1:, 1:]
    return float(straight + (d1.sum() + d2.sum()) * np.sqrt(2))


def elongation(mask: np.ndarray) -> float:
    """Ratio of long to short side of the minimum-area rectangle (1 = round)."""
    pts = cv2.findNonZero(mask.astype(np.uint8))
    if pts is None or len(pts) < 5:
        return 1.0
    (_, _), (w, h), _ = cv2.minAreaRect(pts)
    short = max(min(w, h), 1.0)
    return float(max(w, h) / short)


def _ring(mask: np.ndarray, width: int) -> np.ndarray:
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * width + 1, 2 * width + 1))
    dil = cv2.dilate(mask.astype(np.uint8), k)
    return (dil > 0) & ~mask.astype(bool)


def paint_contrast(image_bgr: np.ndarray, mask: np.ndarray) -> float:
    """Colour distance (LAB, Euclidean ~ deltaE76) between damage and surrounding paint.

    Deep scratches expose primer (grey/white) or bare metal and give large
    values; clear-coat scratches barely change the colour.
    """
    m = mask.astype(bool)
    if m.sum() < 10:
        return 0.0
    ring = _ring(m, width=max(4, int(np.sqrt(m.sum()) * 0.15)))
    if ring.sum() < 10:
        return 0.0
    lab = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2LAB).astype(np.float32)
    # OpenCV 8-bit LAB scales L to 0-255; bring it back to 0-100.
    lab[..., 0] *= 100.0 / 255.0
    lab[..., 1:] -= 128.0
    inside = np.median(lab[m], axis=0)
    outside = np.median(lab[ring], axis=0)
    return float(np.linalg.norm(inside - outside))


def paint_layer_from_contrast(delta_e: float) -> str:
    if delta_e < 6.0:
        return "clear_coat"
    if delta_e < 18.0:
        return "base_coat"
    return "primer_or_metal"
