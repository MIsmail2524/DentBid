# DentBid CV engine

Detects car body damage in photos, measures it and grades severity so workshops can quote accurately without seeing the car first.

## What it reports per damage

| Field | Meaning |
|---|---|
| `type` | dent, scratch, crack, glass_shatter, lamp_broken, tire_flat |
| `part` | which panel: front_door, hood, front_bumper ... (23 parts) |
| `width_cm`, `height_cm`, `area_cm2` | size estimate, scaled from the known size of the detected part |
| `length_cm`, `mean_width_cm` | scratches/cracks: centre-line length and average width |
| `paint_layer` | scratches: `clear_coat` / `base_coat` / `primer_or_metal` (from LAB colour contrast with surrounding paint) |
| `depth_index` | dents: 0-1 depth cue from reflection/shading distortion |
| `severity_score`, `severity` | 0-100 score; minor < 35 <= moderate < 65 <= severe |
| `repair_method` | polish, touch_up, panel_repaint, pdr, dent_repair_repaint, plastic_reshape, replace_part ... |
| `labor_hours` | rough labour range for workshop reference |

Each photo also gets a quality check (blur, darkness, glare, resolution), so customers retake bad photos before workshops see them. Results from several photos merge into one report per request; a part photographed twice counts once.

## Pipeline

```
photo ─┬─ quality check
       ├─ damage model (YOLO11-seg) ── masks per damage
       ├─ parts model  (YOLO11-seg) ── which panel + cm/px scale
       └─ COCO model   (optional)   ── car outline fallback for scale
            └─ measure (skeleton length, LAB contrast, gradient depth) → grade → repair rule
```

## Train (GPU: Colab or Kaggle)

Open [notebooks/train_colab.ipynb](notebooks/train_colab.ipynb) in Colab, or run these steps:

```bash
pip install -r requirements.txt
python scripts/prepare_dataset.py --coco-root /data/CarDD_release/CarDD_COCO --out datasets/damage
python scripts/train.py damage --data datasets/damage/data.yaml --model yolo11m-seg.pt
python scripts/train.py parts --model yolo11s-seg.pt
python scripts/evaluate.py --weights weights/damage.pt --data datasets/damage/data.yaml --split test
```

Dataset: [CarDD](https://cardd-ustc.github.io) (request access). You can merge extra COCO datasets with `--map "paint_chip=scratch"`.

## Use

```bash
python scripts/predict.py car.jpg --damage weights/damage.pt --parts weights/parts.pt
```

```python
from dentbid_cv import DamageAnalyzer
result = DamageAnalyzer("weights/damage.pt", "weights/parts.pt").analyze_file("car.jpg")
print(result.overall_severity, result.summary)
```

## Accuracy notes

- Size in cm is an estimate based on average part sizes. Close-ups without a recognisable part fall back to the whole car, or report no cm value (`scale_unavailable`).
- `depth_index` and `paint_layer` are visual cues. Workshops should confirm them during inspection.
- Low-confidence detections stay in the report with a reduced score instead of being dropped.

## Tests

```bash
pip install -e '.[dev]' && pytest -q
```
