import base64
import importlib.util
import io
import zlib
from pathlib import Path

import numpy as np

spec = importlib.util.spec_from_file_location("fetch", Path(__file__).parents[1] / "scripts" / "fetch_cardd_hf.py")
fetch = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fetch)


def encode(mask: np.ndarray) -> dict:
    buf = io.BytesIO()
    np.save(buf, mask)
    return {"$binary": {"base64": base64.b64encode(zlib.compress(buf.getvalue())).decode(), "subType": "00"}}


def test_mask_in_bbox_frame_becomes_polygon_in_image_frame():
    w, h = 1000, 750
    m = np.zeros((100, 200), bool)
    m[20:80, 50:150] = True          # 100x60 px rectangle inside a 200x100 bbox
    det = {"bounding_box": [0.3, 0.4, 0.2, 100 / 750], "mask": encode(m)}
    polys = fetch.to_polygons(det, w, h)
    assert len(polys) == 1
    xs, ys = np.array(polys[0][0::2]) * w, np.array(polys[0][1::2]) * h
    assert abs(xs.min() - 350) <= 2 and abs(xs.max() - 449) <= 2
    assert abs(ys.min() - 320) <= 2 and abs(ys.max() - 379) <= 2


def test_pickle_payload_rejected():
    import pickle
    import pytest
    evil = base64.b64encode(zlib.compress(pickle.dumps(object()))).decode()
    with pytest.raises(Exception):
        fetch.decode_mask({"mask": {"$binary": {"base64": evil}}})
