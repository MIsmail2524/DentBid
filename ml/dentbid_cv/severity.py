"""Turns measurements into a 0-100 severity score, a grade and a repair suggestion.

The rules mirror how body shops assess damage:
  * scratches: depth (which paint layer is exposed) matters more than length
  * dents: size and sharpness/depth decide paintless repair vs. filler + paint
  * cracks, broken glass and lamps: almost always replacement
"""

from __future__ import annotations

import math

from .taxonomy import CLASS_BASE_SEVERITY, GLASS_PARTS, LIGHT_PARTS, PLASTIC_PARTS
from .types import Measurements

MINOR_MAX = 35.0
MODERATE_MAX = 65.0


def grade(score: float) -> str:
    if score < MINOR_MAX:
        return "minor"
    if score < MODERATE_MAX:
        return "moderate"
    return "severe"


def _size_factor(m: Measurements) -> float:
    """0-1 factor from physical area, falling back to share of the part/car."""
    if m.area_cm2 is not None:
        # <=5 cm2 ~ 0, 36 cm2 (6x6) ~ 0.38, 400 cm2 (20x20) ~ 0.84, >=900 cm2 (30x30) ~ 1.0
        return float(min(1.0, max(0.0, math.log10(max(m.area_cm2, 1.0) / 5.0) / math.log10(180.0))))
    ratio = m.area_ratio_part if m.area_ratio_part is not None else (m.area_ratio_car or 0.0)
    return float(min(1.0, math.sqrt(ratio / 0.35)))


def score_damage(damage_type: str, m: Measurements, confidence: float) -> float:
    base = CLASS_BASE_SEVERITY.get(damage_type, 0.3)
    size = _size_factor(m)

    if damage_type == "scratch":
        layer_w = {"clear_coat": 0.0, "base_coat": 0.45, "primer_or_metal": 1.0}.get(m.paint_layer or "", 0.3)
        length = min(1.0, (m.length_cm or 0.0) / 60.0) if m.length_cm is not None else size
        raw = base + 0.40 * layer_w + 0.30 * length + 0.15 * size
    elif damage_type == "dent":
        depth = m.depth_index or 0.0
        raw = base + 0.40 * size + 0.35 * depth
    elif damage_type == "crack":
        length = min(1.0, (m.length_cm or 0.0) / 40.0) if m.length_cm is not None else size
        raw = base + 0.30 * length + 0.15 * size
    else:  # glass_shatter, lamp_broken, tire_flat
        raw = base + 0.35 * size

    # Low-confidence detections are pulled toward the middle rather than
    # dropped, so workshops still see them but they do not dominate.
    conf_w = 0.6 + 0.4 * min(1.0, max(0.0, confidence))
    return round(float(min(1.0, raw) * 100.0 * conf_w + (1 - conf_w) * 40.0), 1)


def recommend(damage_type: str, part: str | None, m: Measurements, severity: str) -> tuple[str, str, list[float]]:
    """Returns (repair_method, notes, [labor_hours_low, labor_hours_high])."""
    plastic = part in PLASTIC_PARTS

    if damage_type == "scratch":
        layer = m.paint_layer or "base_coat"
        if layer == "clear_coat":
            return ("polish", "Surface scratch in clear coat; machine polish and compound.", [0.5, 1.5])
        if layer == "base_coat" and severity != "severe":
            return ("touch_up", "Colour coat scratched; touch-up paint, wet sand and polish.", [1.0, 3.0])
        return ("panel_repaint", "Scratch reaches primer/metal; sand, prime and repaint the panel.", [3.0, 8.0])

    if damage_type == "dent":
        if plastic:
            if severity == "severe":
                return ("replace_part", "Deformed plastic part; replacement usually cheaper than repair.", [1.5, 4.0])
            return ("plastic_reshape", "Plastic dent; heat reshape, then refinish if paint cracked.", [1.5, 4.0])
        if severity == "minor" and (m.depth_index or 0) < 0.45:
            return ("pdr", "Shallow dent with intact paint; paintless dent repair (PDR).", [0.5, 2.0])
        if severity == "moderate":
            return ("dent_repair_repaint", "Pull dent, apply filler, prime and repaint.", [3.0, 7.0])
        return ("panel_replace_or_major", "Large/deep dent or creased panel; major repair or panel replacement.", [6.0, 14.0])

    if damage_type == "crack":
        if plastic and severity == "minor":
            return ("plastic_weld", "Small crack in plastic; plastic welding and refinish.", [1.5, 3.5])
        return ("replace_part", "Cracked part; replacement recommended for safety and finish.", [1.5, 5.0])

    if damage_type == "glass_shatter" or part in GLASS_PARTS:
        return ("replace_glass", "Shattered glass must be replaced.", [1.5, 3.0])

    if damage_type == "lamp_broken" or part in LIGHT_PARTS:
        return ("replace_lamp", "Broken lamp housing/lens; replace lamp unit.", [0.5, 2.0])

    if damage_type == "tire_flat":
        return ("tire_service", "Flat tire; puncture repair or tire replacement.", [0.3, 1.0])

    return ("inspect", "Workshop inspection needed.", [1.0, 3.0])


def part_recommendation(methods: list[str]) -> str:
    if any(x.startswith("replace") or x == "panel_replace_or_major" for x in methods):
        return "replace"
    if any(x in ("panel_repaint", "dent_repair_repaint", "touch_up") for x in methods):
        return "repaint"
    return "repair"


def combine_scores(scores: list[float]) -> float:
    """Combine several damage scores: the worst dominates, extra damage adds a bit."""
    if not scores:
        return 0.0
    s = sorted(scores, reverse=True)
    extra = sum(x * 0.15 for x in s[1:])
    return round(min(100.0, s[0] + extra), 1)
