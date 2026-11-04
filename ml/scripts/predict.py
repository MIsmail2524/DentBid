"""Analyse photos from the command line and save an annotated image + JSON report.

  python scripts/predict.py photo1.jpg photo2.jpg --damage weights/damage.pt --parts weights/parts.pt
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dentbid_cv import DamageAnalyzer  # noqa: E402
from dentbid_cv.analyzer import annotate, summarize_report  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("images", nargs="+", type=Path)
    ap.add_argument("--damage", default="weights/damage.pt")
    ap.add_argument("--parts", default="weights/parts.pt")
    ap.add_argument("--out", default=Path("runs/predict"), type=Path)
    args = ap.parse_args()

    analyzer = DamageAnalyzer(damage_weights=args.damage, parts_weights=args.parts)
    args.out.mkdir(parents=True, exist_ok=True)
    results = []
    for p in args.images:
        img = cv2.imread(str(p))
        if img is None:
            print(f"cannot read {p}")
            continue
        r = analyzer.analyze(img)
        results.append(r)
        cv2.imwrite(str(args.out / f"{p.stem}_annotated.jpg"), annotate(img, r))
        (args.out / f"{p.stem}.json").write_text(json.dumps(r.to_dict(), indent=2))
        print(f"{p.name}: {r.overall_severity} ({r.overall_score}) - {r.summary}")
    print(json.dumps(summarize_report(results), indent=2))


if __name__ == "__main__":
    main()
