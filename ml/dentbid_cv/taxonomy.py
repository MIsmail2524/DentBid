"""Damage classes, car parts and reference data used for measurement and grading."""

from __future__ import annotations

# Damage classes, in the order the damage model is trained on (CarDD order).
DAMAGE_CLASSES: list[str] = [
    "dent",
    "scratch",
    "crack",
    "glass_shatter",
    "lamp_broken",
    "tire_flat",
]

# Human readable labels.
DAMAGE_LABELS: dict[str, str] = {
    "dent": "Dent",
    "scratch": "Scratch",
    "crack": "Crack",
    "glass_shatter": "Shattered glass",
    "lamp_broken": "Broken lamp",
    "tire_flat": "Flat tire",
}

# Base weight of each class in the severity score (0-1). Higher means the class
# is inherently more serious regardless of size.
CLASS_BASE_SEVERITY: dict[str, float] = {
    "scratch": 0.15,
    "dent": 0.10,
    "crack": 0.55,
    "lamp_broken": 0.60,
    "glass_shatter": 0.75,
    "tire_flat": 0.50,
}

# Car parts, in the order of the Ultralytics carparts-seg dataset.
PART_CLASSES: list[str] = [
    "back_bumper",
    "back_door",
    "back_glass",
    "back_left_door",
    "back_left_light",
    "back_light",
    "back_right_door",
    "back_right_light",
    "front_bumper",
    "front_door",
    "front_glass",
    "front_left_door",
    "front_left_light",
    "front_light",
    "front_right_door",
    "front_right_light",
    "hood",
    "left_mirror",
    "object",
    "right_mirror",
    "tailgate",
    "trunk",
    "wheel",
]

# Typical real-world width (longest visible side) of each part in centimetres.
# Used to turn pixels into an approximate physical size. Values are averages
# for a compact/mid-size sedan and are only an estimate.
PART_REFERENCE_CM: dict[str, float] = {
    "back_bumper": 170.0,
    "back_door": 105.0,
    "back_glass": 120.0,
    "back_left_door": 100.0,
    "back_left_light": 40.0,
    "back_light": 40.0,
    "back_right_door": 100.0,
    "back_right_light": 40.0,
    "front_bumper": 175.0,
    "front_door": 110.0,
    "front_glass": 140.0,
    "front_left_door": 110.0,
    "front_left_light": 55.0,
    "front_light": 55.0,
    "front_right_door": 110.0,
    "front_right_light": 55.0,
    "hood": 150.0,
    "left_mirror": 25.0,
    "right_mirror": 25.0,
    "tailgate": 130.0,
    "trunk": 130.0,
    "wheel": 65.0,
}

# Whole-car fallback when no part is found: typical visible length in a side view.
CAR_REFERENCE_CM = 450.0

PART_LABELS: dict[str, str] = {p: p.replace("_", " ").title() for p in PART_CLASSES}
PART_LABELS["object"] = "Other"

# Parts that are plastic (bumpers, mirrors). Plastic dents usually need heat
# reshaping or replacement rather than paintless dent repair.
PLASTIC_PARTS = {"back_bumper", "front_bumper", "left_mirror", "right_mirror"}
GLASS_PARTS = {"back_glass", "front_glass"}
LIGHT_PARTS = {
    "back_left_light", "back_light", "back_right_light",
    "front_left_light", "front_light", "front_right_light",
}

SEVERITY_LEVELS = ("minor", "moderate", "severe")
