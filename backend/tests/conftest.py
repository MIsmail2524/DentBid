import io
import os
import tempfile

import numpy as np
import pytest
from PIL import Image

_tmp = tempfile.mkdtemp(prefix="dentbid-test-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["MEDIA_DIR"] = f"{_tmp}/media"
os.environ["DENTBID_DAMAGE_WEIGHTS"] = ""
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256"

from fastapi.testclient import TestClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestClient(app) as c:
        yield c


def jpeg_bytes(w=1280, h=720) -> bytes:
    arr = np.full((h, w, 3), 180, np.uint8)
    arr[200:600, 100:1180] = (160, 40, 40)
    arr += np.random.default_rng(1).integers(0, 20, arr.shape, dtype=np.uint8)
    buf = io.BytesIO()
    Image.fromarray(arr).save(buf, "JPEG")
    return buf.getvalue()


def register(client, email, role="customer", country="PK"):
    r = client.post("/api/auth/register", json={
        "name": f"{role.title()} User", "email": email, "password": "secret123",
        "role": role, "country_code": country, "phone": "+923001234567"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]
