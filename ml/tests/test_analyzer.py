import cv2
import numpy as np
import pytest

from dentbid_cv.analyzer import Segment, analyze_predictions, annotate, summarize_report
from dentbid_cv.measure import paint_layer_from_contrast, skeleton_length_px
from dentbid_cv.quality import check_quality
from dentbid_cv.severity import grade

H, W = 720, 1280


def car_image(color=(40, 40, 160)):
    img = np.full((H, W, 3), 200, np.uint8)
    cv2.rectangle(img, (100, 200), (1180, 620), color, -1)
    # mild texture so sharpness is realistic
    noise = np.random.default_rng(0).integers(-12, 12, img.shape, dtype=np.int16)
    return np.clip(img.astype(np.int16) + noise, 0, 255).astype(np.uint8)


def rect_mask(x1, y1, x2, y2):
    m = np.zeros((H, W), bool)
    m[y1:y2, x1:x2] = True
    return m


def seg(name, mask, conf=0.9):
    ys, xs = np.nonzero(mask)
    return Segment(name, conf, mask, (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1))


def door():
    # front door: 110 cm reference over 550 px -> 0.2 cm/px
    return seg("front_door", rect_mask(300, 200, 850, 620))


def test_skeleton_length_horizontal_and_diagonal():
    m = np.zeros((200, 200), bool)
    m[100, 20:120] = True
    assert skeleton_length_px(m) == pytest.approx(99, abs=2)
    d = np.zeros((200, 200), bool)
    for i in range(100):
        d[50 + i, 50 + i] = True
    assert skeleton_length_px(d) == pytest.approx(99 * np.sqrt(2), rel=0.03)


def test_paint_layer_thresholds():
    assert paint_layer_from_contrast(2) == "clear_coat"
    assert paint_layer_from_contrast(10) == "base_coat"
    assert paint_layer_from_contrast(40) == "primer_or_metal"


def test_deep_scratch_measured_in_cm_and_graded():
    img = car_image()
    # bright line on dark red paint = primer exposed
    cv2.line(img, (400, 400), (700, 420), (230, 230, 230), 5)
    m = np.zeros((H, W), np.uint8)
    cv2.line(m, (400, 400), (700, 420), 1, 7)
    r = analyze_predictions(img, [seg("scratch", m.astype(bool))], [door()])
    d = r.damages[0]
    assert d.part == "front_door"
    assert d.measurements.scale_source == "part:front_door"
    # 300 px long at 0.2 cm/px ~ 60 cm
    assert d.measurements.length_cm == pytest.approx(60, rel=0.1)
    assert d.measurements.paint_layer == "primer_or_metal"
    assert d.repair_method == "panel_repaint"
    assert d.severity in ("moderate", "severe")


def test_light_scratch_is_minor_polish():
    img = car_image()
    m = np.zeros((H, W), np.uint8)
    cv2.line(m, (400, 300), (460, 300), 1, 3)
    r = analyze_predictions(img, [seg("scratch", m.astype(bool), conf=0.8)], [door()])
    d = r.damages[0]
    assert d.measurements.paint_layer == "clear_coat"
    assert d.repair_method == "polish"
    assert d.severity == "minor"


def test_dent_severity_grows_with_size_and_depth():
    flat = car_image()
    small = analyze_predictions(flat, [seg("dent", rect_mask(500, 350, 530, 380))], [door()]).damages[0]

    creased = car_image()
    # strong shading gradient inside the dent region simulates a deep crease
    for i in range(200):
        cv2.line(creased, (450 + i, 300), (450 + i, 500), (int(40 + 200 * (i % 40) / 40),) * 3, 1)
    big = analyze_predictions(creased, [seg("dent", rect_mask(450, 300, 650, 500))], [door()]).damages[0]

    assert big.measurements.area_cm2 > small.measurements.area_cm2
    assert big.measurements.depth_index > small.measurements.depth_index
    assert big.severity_score > small.severity_score
    assert small.repair_method == "pdr"
    assert big.severity != "minor"


def test_duplicate_masks_removed_and_report_merges_parts():
    img = car_image()
    m = rect_mask(500, 350, 600, 450)
    r1 = analyze_predictions(img, [seg("dent", m, 0.9), seg("scratch", m, 0.5)], [door()])
    assert len(r1.damages) == 1
    r2 = analyze_predictions(img, [seg("crack", rect_mask(520, 360, 540, 440))], [door()])
    rep = summarize_report([r1, r2])
    assert rep["photos_analyzed"] == 2
    assert len(rep["parts"]) == 1  # same door in both photos
    assert rep["overall_severity"] == grade(rep["overall_score"])


def test_no_damage_and_no_scale_warnings():
    r = analyze_predictions(car_image(), [], [])
    assert r.overall_severity == "none"
    assert "no_damage_detected" in r.warnings
    assert "scale_unavailable" in r.warnings


def test_quality_flags_blur_and_dark():
    dark = np.full((720, 1280, 3), 10, np.uint8)
    q = check_quality(dark)
    assert not q.ok and "too_dark" in q.issues and "blurry" in q.issues


def test_annotate_returns_same_shape():
    img = car_image()
    r = analyze_predictions(img, [seg("dent", rect_mask(500, 350, 600, 450))], [door()])
    out = annotate(img, r)
    assert out.shape == img.shape
    assert r.to_dict()["damages"][0]["type"] == "dent"
