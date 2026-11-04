"""Download the CarDD mirror from Hugging Face (FiftyOne format) and convert it to YOLO segmentation.

  python scripts/fetch_cardd_hf.py --out datasets/damage

CarDD license: research / non-commercial use, images under Flickr and Shutterstock
terms. Read CarDD_license.pdf (downloaded with the data) before using the model commercially.

The mirror stores each instance mask as base64(zlib(.npy)) cropped to its bounding
box. Masks are decoded with allow_pickle=False, so the JSON cannot run code.
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import random
import shutil
import sys
import zlib
from pathlib import Path

import cv2
import numpy as np
import yaml
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dentbid_cv.taxonomy import DAMAGE_CLASSES  # noqa: E402

REPO = "harpreetsahota/CarDD"


def norm(name: str) -> str:
    return name.strip().lower().replace(" ", "_")


def decode_mask(det: dict) -> np.ndarray | None:
    m = det.get("mask")
    if not m:
        return None
    raw = m["$binary"]["base64"] if isinstance(m, dict) and "$binary" in m else m
    return np.load(io.BytesIO(zlib.decompress(base64.b64decode(raw))), allow_pickle=False).astype(np.uint8)


def to_polygons(det: dict, w: int, h: int) -> list[list[float]]:
    x, y, bw, bh = det["bounding_box"]  # relative [x, y, w, h]
    x0, y0 = int(round(x * w)), int(round(y * h))
    pw, ph = max(1, int(round(bw * w))), max(1, int(round(bh * h)))
    mask = decode_mask(det)
    full = np.zeros((h, w), np.uint8)
    if mask is None:
        full[y0:y0 + ph, x0:x0 + pw] = 1
    else:
        mask = cv2.resize(mask, (pw, ph), interpolation=cv2.INTER_NEAREST)
        x1, y1 = min(w, x0 + pw), min(h, y0 + ph)
        full[y0:y1, x0:x1] = mask[: y1 - y0, : x1 - x0]
    contours, _ = cv2.findContours(full, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    polys = []
    for c in contours:
        if cv2.contourArea(c) < 9:
            continue
        c = cv2.approxPolyDP(c, 0.002 * cv2.arcLength(c, True), True).reshape(-1, 2)
        if len(c) >= 3:
            polys.append([v for px, py in c for v in (px / w, py / h)])
    return polys


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("datasets/damage"))
    ap.add_argument("--cache", type=Path, default=Path("datasets/_cardd_hf"))
    ap.add_argument("--val", type=float, default=0.12)
    ap.add_argument("--test", type=float, default=0.08)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    from huggingface_hub import snapshot_download

    src = Path(snapshot_download(REPO, repo_type="dataset", local_dir=args.cache,
                                 allow_patterns=["samples.json", "metadata.json", "CarDD_license.pdf", "data/*"]))
    samples = json.loads((src / "samples.json").read_text())["samples"]
    random.Random(args.seed).shuffle(samples)
    n = len(samples)
    n_test, n_val = int(n * args.test), int(n * args.val)
    splits = {"test": samples[:n_test], "val": samples[n_test:n_test + n_val], "train": samples[n_test + n_val:]}

    stats = {}
    for split, items in splits.items():
        (args.out / "images" / split).mkdir(parents=True, exist_ok=True)
        (args.out / "labels" / split).mkdir(parents=True, exist_ok=True)
        per_class = [0] * len(DAMAGE_CLASSES)
        for s in tqdm(items, desc=split):
            img_path = src / s["filepath"]
            if not img_path.exists():
                continue
            w, h = s["metadata"]["width"], s["metadata"]["height"]
            seg = (s.get("segmentations") or {}).get("detections") or (s.get("detections") or {}).get("detections") or []
            lines = []
            for det in seg:
                name = norm(det["label"])
                if name not in DAMAGE_CLASSES:
                    continue
                cls = DAMAGE_CLASSES.index(name)
                for poly in to_polygons(det, w, h):
                    lines.append(f"{cls} " + " ".join(f"{min(max(v, 0), 1):.6f}" for v in poly))
                    per_class[cls] += 1
            dst = args.out / "images" / split / img_path.name
            if not dst.exists():
                shutil.copy2(img_path, dst)
            (args.out / "labels" / split / (img_path.stem + ".txt")).write_text("\n".join(lines))
        stats[split] = {"images": len(items), **dict(zip(DAMAGE_CLASSES, per_class))}

    cfg = {"path": str(args.out.resolve()), "train": "images/train", "val": "images/val", "test": "images/test",
           "names": dict(enumerate(DAMAGE_CLASSES))}
    (args.out / "data.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    shutil.copy2(src / "CarDD_license.pdf", args.out / "CarDD_license.pdf")
    print(json.dumps(stats, indent=2))
    print(f"wrote {args.out / 'data.yaml'}")


if __name__ == "__main__":
    main()
