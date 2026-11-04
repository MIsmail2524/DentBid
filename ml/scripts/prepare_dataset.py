"""Convert a COCO-format car damage dataset (e.g. CarDD) to YOLO segmentation format.

Usage:
  python scripts/prepare_dataset.py --coco-root /data/CarDD_release/CarDD_COCO --out datasets/damage

Expected input layout (CarDD):
  <coco-root>/annotations/instances_{train,val,test}2017.json
  <coco-root>/{train,val,test}2017/*.jpg

Any other COCO export works too (Roboflow, CVAT ...). Category names are
normalised ("glass shatter" -> "glass_shatter") and mapped onto DentBid classes;
use --map to map extra names, e.g. --map "paint chip=scratch" --map "dent_major=dent".
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

import yaml
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dentbid_cv.taxonomy import DAMAGE_CLASSES  # noqa: E402

SPLITS = {"train": "train2017", "val": "val2017", "test": "test2017"}


def norm(name: str) -> str:
    return name.strip().lower().replace("-", "_").replace(" ", "_")


def convert_split(coco_json: Path, img_dir: Path, out_dir: Path, split: str, name_map: dict[str, str]) -> dict:
    data = json.loads(coco_json.read_text())
    cat_to_cls: dict[int, int] = {}
    skipped_cats = set()
    for c in data["categories"]:
        n = name_map.get(norm(c["name"]), norm(c["name"]))
        if n in DAMAGE_CLASSES:
            cat_to_cls[c["id"]] = DAMAGE_CLASSES.index(n)
        else:
            skipped_cats.add(c["name"])

    anns_by_img: dict[int, list] = {}
    for a in data["annotations"]:
        anns_by_img.setdefault(a["image_id"], []).append(a)

    (out_dir / "images" / split).mkdir(parents=True, exist_ok=True)
    (out_dir / "labels" / split).mkdir(parents=True, exist_ok=True)
    stats = {"images": 0, "instances": 0, "skipped_rle": 0, "per_class": [0] * len(DAMAGE_CLASSES)}

    for img in tqdm(data["images"], desc=split):
        src = img_dir / img["file_name"]
        if not src.exists():
            continue
        w, h = img["width"], img["height"]
        lines = []
        for a in anns_by_img.get(img["id"], []):
            cls = cat_to_cls.get(a["category_id"])
            if cls is None:
                continue
            seg = a.get("segmentation")
            if not isinstance(seg, list) or not seg:
                stats["skipped_rle"] += 1
                continue
            # Several polygons per instance: keep each as its own line.
            for poly in seg:
                if len(poly) < 6:
                    continue
                coords = []
                for i in range(0, len(poly), 2):
                    coords.append(f"{min(max(poly[i] / w, 0), 1):.6f}")
                    coords.append(f"{min(max(poly[i + 1] / h, 0), 1):.6f}")
                lines.append(f"{cls} " + " ".join(coords))
                stats["instances"] += 1
                stats["per_class"][cls] += 1
        dst = out_dir / "images" / split / Path(img["file_name"]).name
        if not dst.exists():
            shutil.copy2(src, dst)
        (out_dir / "labels" / split / (dst.stem + ".txt")).write_text("\n".join(lines))
        stats["images"] += 1

    if skipped_cats:
        print(f"[{split}] categories not mapped (ignored): {sorted(skipped_cats)}")
    return stats


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--coco-root", required=True, type=Path)
    ap.add_argument("--out", default=Path("datasets/damage"), type=Path)
    ap.add_argument("--map", action="append", default=[], help='extra name mapping "src=dst"')
    args = ap.parse_args()

    name_map = {}
    for m in args.map:
        src, dst = m.split("=", 1)
        name_map[norm(src)] = norm(dst)

    present = {}
    for split, folder in SPLITS.items():
        js = args.coco_root / "annotations" / f"instances_{folder}.json"
        if not js.exists():
            print(f"skip {split}: {js} missing")
            continue
        stats = convert_split(js, args.coco_root / folder, args.out, split, name_map)
        present[split] = f"images/{split}"
        print(split, json.dumps(stats))

    if "val" not in present and "test" in present:
        present["val"] = present["test"]
    cfg = {"path": str(args.out.resolve()), **present, "names": {i: n for i, n in enumerate(DAMAGE_CLASSES)}}
    (args.out / "data.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    print(f"wrote {args.out / 'data.yaml'}")


if __name__ == "__main__":
    main()
