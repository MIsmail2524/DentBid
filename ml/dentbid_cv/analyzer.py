"""DamageAnalyzer: runs the segmentation models and produces a graded damage report.

Three YOLO segmentation models are used:
  * damage model (required): dent, scratch, crack, glass_shatter, lamp_broken, tire_flat
  * parts model (optional):  23 car parts, used to locate damage and estimate scale
  * car model (optional):    COCO model, used to find the car outline when no part is found

The core logic (`analyze_predictions`) works on plain masks so it can be tested
without loading any model.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Protocol

import cv2
import numpy as np

from . import measure, severity
from .quality import check_quality
from .taxonomy import (
    CAR_REFERENCE_CM,
    DAMAGE_CLASSES,
    DAMAGE_LABELS,
    PART_LABELS,
    PART_REFERENCE_CM,
)
from .types import AnalysisResult, Damage, ImageQuality, Measurements, PartSummary

COCO_VEHICLE_IDS = {2: "car", 5: "bus", 7: "truck"}
SEVERITY_COLORS_BGR = {"minor": (80, 200, 80), "moderate": (0, 190, 255), "severe": (40, 40, 230)}


@dataclass
class Segment:
    name: str
    confidence: float
    mask: np.ndarray            # HxW bool, same size as the image
    bbox: tuple[float, float, float, float]


class Segmenter(Protocol):
    def __call__(self, image_bgr: np.ndarray) -> list[Segment]: ...


class YoloSegmenter:
    """Wraps an Ultralytics segmentation model."""

    def __init__(self, weights: str, conf: float = 0.25, imgsz: int = 1024,
                 names: list[str] | None = None, keep_ids: dict[int, str] | None = None,
                 device: str | None = None):
        from ultralytics import YOLO  # imported lazily: heavy dependency

        self.model = YOLO(weights)
        self.conf = conf
        self.imgsz = imgsz
        self.names = names
        self.keep_ids = keep_ids
        self.device = device

    def __call__(self, image_bgr: np.ndarray) -> list[Segment]:
        h, w = image_bgr.shape[:2]
        res = self.model.predict(image_bgr, conf=self.conf, imgsz=self.imgsz,
                                 retina_masks=True, verbose=False, device=self.device)[0]
        if res.masks is None:
            return []
        out: list[Segment] = []
        masks = res.masks.data.cpu().numpy()
        for i, box in enumerate(res.boxes):
            cls = int(box.cls.item())
            if self.keep_ids is not None:
                if cls not in self.keep_ids:
                    continue
                name = self.keep_ids[cls]
            elif self.names is not None and cls < len(self.names):
                name = self.names[cls]
            else:
                name = str(res.names.get(cls, cls))
            m = masks[i]
            if m.shape != (h, w):
                m = cv2.resize(m, (w, h), interpolation=cv2.INTER_NEAREST)
            out.append(Segment(name=name, confidence=float(box.conf.item()), mask=m > 0.5,
                               bbox=tuple(float(v) for v in box.xyxy[0].tolist())))
        return out


def _bbox_of(mask: np.ndarray) -> tuple[float, float, float, float]:
    ys, xs = np.nonzero(mask)
    if len(xs) == 0:
        return (0.0, 0.0, 0.0, 0.0)
    return (float(xs.min()), float(ys.min()), float(xs.max() + 1), float(ys.max() + 1))


def _assign_part(dmask: np.ndarray, parts: list[Segment]) -> Segment | None:
    area = dmask.sum()
    if area == 0 or not parts:
        return None
    best, best_ov = None, 0.0
    for p in parts:
        ov = float((dmask & p.mask).sum()) / area
        if ov > best_ov:
            best, best_ov = p, ov
    return best if best_ov >= 0.2 else None


def _scale_cm_per_px(part: Segment | None, cars: list[Segment]) -> tuple[float | None, str | None]:
    if part is not None and part.name in PART_REFERENCE_CM:
        x1, y1, x2, y2 = part.bbox
        side = max(x2 - x1, y2 - y1)
        if side > 20:
            return PART_REFERENCE_CM[part.name] / side, f"part:{part.name}"
    if cars:
        car = max(cars, key=lambda c: c.mask.sum())
        x1, y1, x2, y2 = car.bbox
        side = max(x2 - x1, y2 - y1)
        if side > 50:
            return CAR_REFERENCE_CM / side, "car"
    return None, None


def _remove_duplicates(segs: list[Segment], iou_thr: float = 0.6) -> list[Segment]:
    """Class-agnostic mask NMS: the model sometimes labels one region twice."""
    segs = sorted(segs, key=lambda s: s.confidence, reverse=True)
    kept: list[Segment] = []
    for s in segs:
        dup = False
        for k in kept:
            inter = (s.mask & k.mask).sum()
            union = (s.mask | k.mask).sum()
            if union and inter / union > iou_thr:
                dup = True
                break
        if not dup:
            kept.append(s)
    return kept


def analyze_predictions(image_bgr: np.ndarray, damage_segs: list[Segment],
                        part_segs: list[Segment] | None = None,
                        car_segs: list[Segment] | None = None,
                        quality: ImageQuality | None = None,
                        model_version: str = "unknown") -> AnalysisResult:
    h, w = image_bgr.shape[:2]
    part_segs = [p for p in (part_segs or []) if p.name != "object"]
    car_segs = car_segs or []
    quality = quality or check_quality(image_bgr)

    car_mask = np.zeros((h, w), bool)
    for c in car_segs:
        car_mask |= c.mask
    if not car_mask.any():
        for p in part_segs:
            car_mask |= p.mask
    car_area = int(car_mask.sum())

    warnings: list[str] = []
    if not quality.ok:
        warnings.append("photo_quality:" + ",".join(quality.issues))

    damages: list[Damage] = []
    for idx, seg in enumerate(_remove_duplicates([s for s in damage_segs if s.mask.any()]), start=1):
        dmask = seg.mask
        area_px = int(dmask.sum())
        part = _assign_part(dmask, part_segs)
        cm_px, scale_src = _scale_cm_per_px(part, car_segs)
        x1, y1, x2, y2 = _bbox_of(dmask)

        width_cm = height_cm = area_cm2 = length_cm = mean_width_cm = None
        if cm_px is not None:
            width_cm = round((x2 - x1) * cm_px, 1)
            height_cm = round((y2 - y1) * cm_px, 1)
            area_cm2 = round(area_px * cm_px * cm_px, 1)

        contrast = None
        layer = None
        if seg.name in ("scratch", "crack"):
            length_px = measure.skeleton_length_px(dmask)
            # A blob-like "scratch" has a short skeleton; use the long side instead.
            if measure.elongation(dmask) < 2.0:
                length_px = max(length_px, max(x2 - x1, y2 - y1))
            if cm_px is not None:
                length_cm = round(length_px * cm_px, 1)
                mean_width_cm = round(area_px / max(length_px, 1.0) * cm_px, 2)
        if seg.name == "scratch":
            contrast = round(measure.paint_contrast(image_bgr, dmask), 2)
            layer = measure.paint_layer_from_contrast(contrast)

        m = Measurements(
            area_px=area_px,
            area_ratio_part=round(area_px / max(int(part.mask.sum()), 1), 4) if part is not None else None,
            area_ratio_car=round(area_px / car_area, 4) if car_area else None,
            area_ratio_image=round(area_px / float(h * w), 4),
            width_cm=width_cm, height_cm=height_cm, area_cm2=area_cm2,
            length_cm=length_cm, mean_width_cm=mean_width_cm,
            paint_contrast=contrast, paint_layer=layer,
            scale_source=scale_src,
        )
        score = severity.score_damage(seg.name, m, seg.confidence)
        grade = severity.grade(score)
        method, notes, hours = severity.recommend(seg.name, part.name if part else None, m, grade)

        damages.append(Damage(
            id=idx,
            type=seg.name,
            label=DAMAGE_LABELS.get(seg.name, seg.name),
            confidence=round(seg.confidence, 3),
            bbox=[round(v, 1) for v in (x1, y1, x2, y2)],
            polygon=measure.mask_polygon(dmask),
            part=part.name if part else None,
            part_label=PART_LABELS.get(part.name) if part else None,
            measurements=m,
            severity_score=score,
            severity=grade,
            repair_method=method,
            repair_notes=notes,
            labor_hours=hours,
        ))

    parts = summarize_parts(damages)
    overall = severity.combine_scores([d.severity_score for d in damages])
    hours = [round(sum(d.labor_hours[0] for d in damages), 1), round(sum(d.labor_hours[1] for d in damages), 1)]

    if not damages:
        warnings.append("no_damage_detected")
    if not car_segs and not part_segs:
        warnings.append("scale_unavailable")

    return AnalysisResult(
        model_version=model_version,
        image_width=w,
        image_height=h,
        quality=quality,
        car_detected=bool(car_segs or part_segs),
        damages=damages,
        parts=parts,
        overall_score=overall,
        overall_severity=severity.grade(overall) if damages else "none",
        summary=build_summary(damages),
        labor_hours=hours,
        warnings=warnings,
    )


def summarize_parts(damages: list[Damage]) -> list[PartSummary]:
    groups: dict[str, list[Damage]] = {}
    for d in damages:
        groups.setdefault(d.part or "unknown", []).append(d)
    out = []
    for part, ds in groups.items():
        score = severity.combine_scores([d.severity_score for d in ds])
        out.append(PartSummary(
            part=part,
            part_label=PART_LABELS.get(part, "Unlocated"),
            damage_count=len(ds),
            damage_types=sorted({d.type for d in ds}),
            severity_score=score,
            severity=severity.grade(score),
            recommendation=severity.part_recommendation([d.repair_method for d in ds]),
        ))
    return sorted(out, key=lambda p: p.severity_score, reverse=True)


def build_summary(damages: list[Damage]) -> str:
    if not damages:
        return "No visible damage detected. Try a closer, well-lit photo of the damaged area."
    parts = []
    for d in sorted(damages, key=lambda x: x.severity_score, reverse=True):
        where = f" on {d.part_label.lower()}" if d.part_label else ""
        size = ""
        mm = d.measurements
        if d.type in ("scratch", "crack") and mm.length_cm:
            size = f" (~{mm.length_cm:.0f} cm long)"
        elif mm.width_cm and mm.height_cm:
            size = f" (~{mm.width_cm:.0f}x{mm.height_cm:.0f} cm)"
        parts.append(f"{d.severity} {d.label.lower()}{where}{size}")
    return "Detected: " + "; ".join(parts) + "."


def annotate(image_bgr: np.ndarray, result: AnalysisResult) -> np.ndarray:
    """Draws masks and labels on a copy of the image for workshops to review."""
    out = image_bgr.copy()
    overlay = out.copy()
    thick = max(2, int(max(out.shape[:2]) / 500))
    for d in result.damages:
        color = SEVERITY_COLORS_BGR.get(d.severity, (255, 255, 255))
        if d.polygon:
            pts = np.array(d.polygon, np.int32).reshape(-1, 1, 2)
            cv2.fillPoly(overlay, [pts], color)
            cv2.polylines(out, [pts], True, color, thick)
    out = cv2.addWeighted(overlay, 0.35, out, 0.65, 0)
    font_scale = max(0.5, max(out.shape[:2]) / 1600)
    for d in result.damages:
        color = SEVERITY_COLORS_BGR.get(d.severity, (255, 255, 255))
        x1, y1 = int(d.bbox[0]), int(d.bbox[1])
        text = f"#{d.id} {d.label} | {d.severity} {d.severity_score:.0f}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thick)
        y = max(th + 6, y1 - 4)
        cv2.rectangle(out, (x1, y - th - 6), (x1 + tw + 6, y + 2), color, -1)
        cv2.putText(out, text, (x1 + 3, y - 2), cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 0, 0), thick, cv2.LINE_AA)
    return out


def summarize_report(results: Iterable[AnalysisResult]) -> dict:
    """Merges per-photo results into one report for a damage request.

    The same part photographed twice is counted once, using its worst grade.
    """
    results = list(results)
    by_part: dict[str, PartSummary] = {}
    all_scores: list[float] = []
    lo = hi = 0.0
    for r in results:
        for p in r.parts:
            prev = by_part.get(p.part)
            if prev is None or p.severity_score > prev.severity_score:
                by_part[p.part] = p
        lo += r.labor_hours[0] if r.labor_hours else 0
        hi += r.labor_hours[1] if r.labor_hours else 0
    all_scores = [p.severity_score for p in by_part.values()]
    overall = severity.combine_scores(all_scores)
    damage_types = sorted({t for p in by_part.values() for t in p.damage_types})
    return {
        "overall_score": overall,
        "overall_severity": severity.grade(overall) if all_scores else "none",
        "damage_types": damage_types,
        "damage_count": sum(len(r.damages) for r in results),
        "parts": [p.__dict__ for p in sorted(by_part.values(), key=lambda p: p.severity_score, reverse=True)],
        "labor_hours": [round(lo, 1), round(hi, 1)],
        "photos_analyzed": len(results),
        "photos_with_quality_issues": sum(1 for r in results if not r.quality.ok),
    }


def _file_version(path: str) -> str:
    p = Path(path)
    if not p.exists():
        return p.stem
    h = hashlib.sha1()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return f"{p.stem}-{h.hexdigest()[:8]}"


class DamageAnalyzer:
    """Loads the models once and analyses images.

    Configure with arguments or environment variables:
      DENTBID_DAMAGE_WEIGHTS  path to trained damage model (required)
      DENTBID_PARTS_WEIGHTS   path to trained car-parts model (optional)
      DENTBID_CAR_WEIGHTS     COCO segmentation model, default yolo11n-seg.pt (optional, "" disables)
      DENTBID_DEVICE          cpu, 0, mps ... (optional)
    """

    def __init__(self, damage_weights: str | None = None, parts_weights: str | None = None,
                 car_weights: str | None = None, device: str | None = None,
                 damage_conf: float = 0.25):
        damage_weights = damage_weights or os.getenv("DENTBID_DAMAGE_WEIGHTS")
        parts_weights = parts_weights if parts_weights is not None else os.getenv("DENTBID_PARTS_WEIGHTS", "")
        car_weights = car_weights if car_weights is not None else os.getenv("DENTBID_CAR_WEIGHTS", "yolo11n-seg.pt")
        device = device or os.getenv("DENTBID_DEVICE") or None
        if not damage_weights or not Path(damage_weights).exists():
            raise FileNotFoundError(
                f"Damage model weights not found: {damage_weights!r}. Train one with ml/scripts/train.py "
                "and set DENTBID_DAMAGE_WEIGHTS."
            )
        self.damage = YoloSegmenter(damage_weights, conf=damage_conf, names=DAMAGE_CLASSES, device=device)
        self.parts = YoloSegmenter(parts_weights, conf=0.35, device=device) if parts_weights and Path(parts_weights).exists() else None
        self.cars = YoloSegmenter(car_weights, conf=0.4, imgsz=640, keep_ids=COCO_VEHICLE_IDS, device=device) if car_weights else None
        self.version = _file_version(damage_weights) + (f"+{_file_version(parts_weights)}" if self.parts else "")

    def analyze(self, image_bgr: np.ndarray) -> AnalysisResult:
        quality = check_quality(image_bgr)
        dmg = self.damage(image_bgr)
        parts = self.parts(image_bgr) if self.parts else []
        cars = self.cars(image_bgr) if self.cars else []
        return analyze_predictions(image_bgr, dmg, parts, cars, quality=quality, model_version=self.version)

    def analyze_file(self, path: str | Path) -> AnalysisResult:
        img = cv2.imread(str(path))
        if img is None:
            raise ValueError(f"Cannot read image: {path}")
        return self.analyze(img)
