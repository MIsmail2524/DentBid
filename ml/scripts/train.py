"""Train the DentBid segmentation models.

Damage model (dent, scratch, crack, glass_shatter, lamp_broken, tire_flat):
  python scripts/train.py damage --data datasets/damage/data.yaml

Car parts model (Ultralytics carparts-seg dataset, downloaded automatically):
  python scripts/train.py parts

Best weights are copied to ml/weights/{damage,parts}.pt.
A GPU is strongly recommended (Colab / Kaggle: see notebooks/train_colab.ipynb).
"""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path

from ultralytics import YOLO

ROOT = Path(__file__).resolve().parents[1]

# Tuned for small, thin damage regions: high resolution, strong colour/lighting
# augmentation (reflections on paint), no vertical flip (cars are not upside down).
DAMAGE_HYP = dict(
    imgsz=1024,
    epochs=150,
    patience=30,
    batch=-1,             # auto batch size for available GPU memory
    optimizer="AdamW",
    lr0=0.001,
    cos_lr=True,
    hsv_h=0.015,
    hsv_s=0.6,
    hsv_v=0.5,
    degrees=5.0,
    translate=0.1,
    scale=0.5,
    shear=2.0,
    perspective=0.0005,
    flipud=0.0,
    fliplr=0.5,
    mosaic=1.0,
    mixup=0.1,
    copy_paste=0.3,       # pastes damage instances onto other cars
    close_mosaic=15,
    overlap_mask=False,   # dents and scratches overlap often
    mask_ratio=2,         # finer masks for thin scratches
)

PARTS_HYP = dict(imgsz=640, epochs=100, patience=25, batch=-1, cos_lr=True, flipud=0.0)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("task", choices=["damage", "parts"])
    ap.add_argument("--data", default=None, help="data.yaml (damage task)")
    ap.add_argument("--model", default="yolo11m-seg.pt", help="base checkpoint (n/s/m/l/x)")
    ap.add_argument("--epochs", type=int, default=None)
    ap.add_argument("--imgsz", type=int, default=None)
    ap.add_argument("--batch", type=int, default=None)
    ap.add_argument("--device", default=None)
    ap.add_argument("--resume", action="store_true")
    args = ap.parse_args()

    if args.task == "damage":
        if not args.data:
            ap.error("--data is required for the damage task")
        data, hyp = args.data, dict(DAMAGE_HYP)
    else:
        data, hyp = args.data or "carparts-seg.yaml", dict(PARTS_HYP)

    for k in ("epochs", "imgsz", "batch"):
        v = getattr(args, k)
        if v is not None:
            hyp[k] = v
    if args.device is not None:
        hyp["device"] = args.device

    model = YOLO(args.model)
    results = model.train(data=data, project=str(ROOT / "runs"), name=args.task,
                          exist_ok=True, resume=args.resume, **hyp)

    best = Path(results.save_dir) / "weights" / "best.pt"
    dst = ROOT / "weights" / f"{args.task}.pt"
    dst.parent.mkdir(exist_ok=True)
    shutil.copy2(best, dst)
    print(f"best weights -> {dst}")


if __name__ == "__main__":
    main()
