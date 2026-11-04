"""Evaluate a trained damage model: per-class box/mask mAP plus a severity sanity report.

  python scripts/evaluate.py --weights weights/damage.pt --data datasets/damage/data.yaml --split test
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ultralytics import YOLO

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dentbid_cv.taxonomy import DAMAGE_CLASSES  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", required=True)
    ap.add_argument("--data", required=True)
    ap.add_argument("--split", default="val")
    ap.add_argument("--imgsz", type=int, default=1024)
    args = ap.parse_args()

    m = YOLO(args.weights).val(data=args.data, split=args.split, imgsz=args.imgsz, plots=True)
    report = {
        "box_map50": round(float(m.box.map50), 4),
        "box_map50_95": round(float(m.box.map), 4),
        "mask_map50": round(float(m.seg.map50), 4),
        "mask_map50_95": round(float(m.seg.map), 4),
        "per_class_mask_map50_95": {},
    }
    for i, idx in enumerate(m.seg.ap_class_index):
        report["per_class_mask_map50_95"][DAMAGE_CLASSES[int(idx)]] = round(float(m.seg.maps[int(idx)]), 4)
    print(json.dumps(report, indent=2))
    out = Path(args.weights).with_suffix(".eval.json")
    out.write_text(json.dumps(report, indent=2))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
