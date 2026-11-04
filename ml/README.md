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
            └─ measure (size, skeleton length, LAB paint contrast) → grade → repair rule
```

## Train on a GPU server (SSH)

```bash
git clone https://github.com/MIsmail2524/DentBid.git && cd DentBid/ml
tmux new -s train
bash scripts/gpu_train.sh          # MODEL=yolo11l-seg.pt for a bigger damage model
scp user@gpu:DentBid/ml/weights/{damage,parts}.pt ml/weights/    # run this on the app machine
```

The script:
1. downloads the CarDD mirror from Hugging Face (`harpreetsahota/CarDD`, 2.2 GB);
2. converts the masks to YOLO polygons and splits the data 80/12/8;
3. trains and evaluates the damage model, then trains the car-parts model.

CarDD is licensed for research and non-commercial use. Check `datasets/damage/CarDD_license.pdf` before any commercial use.

## Train on Colab or Kaggle

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

These were checked on real CarDD photos, using the dataset's true damage outlines in place of the model's:

- **Dent depth is not estimated.** Two shading-based depth cues scored no better than chance on 71 real dents (AUC 0.41 and 0.48), so dents are graded by size and the workshop judges depth from the photos.
- **Without a cm scale, size comes from the share of the photo** the damage covers (damage photos are usually close-ups of one panel).
- **A flat tyre's grade does not depend on how big the tyre looks** in the photo.
- Size in cm is an estimate based on average part sizes. Close-ups without a recognisable part fall back to the whole car, or report no cm value (`scale_unavailable`).
- `paint_layer` is a visual cue, and dark marks such as tyre rubber can look like exposed primer. Workshops should confirm it during inspection.
- Low-confidence detections stay in the report with a reduced score instead of being dropped.

## Tests

```bash
pip install -e '.[dev]' && pytest -q
```
