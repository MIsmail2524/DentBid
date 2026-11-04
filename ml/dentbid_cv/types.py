"""Result types returned by the analyzer. All are JSON serialisable via to_dict()."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ImageQuality:
    width: int
    height: int
    sharpness: float          # variance of Laplacian, higher is sharper
    brightness: float         # mean luminance 0-255
    glare_ratio: float        # share of blown-out pixels
    ok: bool
    issues: list[str] = field(default_factory=list)


@dataclass
class Measurements:
    area_px: int
    area_ratio_part: float | None     # share of the damaged part covered
    area_ratio_car: float | None      # share of the visible car covered
    area_ratio_image: float           # share of the photo covered (fallback when no car/part found)
    width_cm: float | None            # bounding box size, estimated
    height_cm: float | None
    area_cm2: float | None
    length_cm: float | None           # scratches/cracks: skeleton length
    mean_width_cm: float | None       # scratches/cracks: area / length
    paint_contrast: float | None      # scratches: CIEDE2000-like LAB distance to surroundings
    paint_layer: str | None           # scratches: clear_coat | base_coat | primer_or_metal
    scale_source: str | None          # which reference gave the cm/px scale


@dataclass
class Damage:
    id: int
    type: str
    label: str
    confidence: float
    bbox: list[float]                 # x1, y1, x2, y2 in pixels
    polygon: list[list[float]]        # simplified mask outline
    part: str | None
    part_label: str | None
    measurements: Measurements
    severity_score: float             # 0-100
    severity: str                     # minor | moderate | severe
    repair_method: str
    repair_notes: str
    labor_hours: list[float]          # [low, high] estimate


@dataclass
class PartSummary:
    part: str
    part_label: str
    damage_count: int
    damage_types: list[str]
    severity_score: float
    severity: str
    recommendation: str               # repair | repaint | replace


@dataclass
class AnalysisResult:
    model_version: str
    image_width: int
    image_height: int
    quality: ImageQuality
    car_detected: bool
    damages: list[Damage]
    parts: list[PartSummary]
    overall_score: float
    overall_severity: str
    summary: str
    labor_hours: list[float]
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
