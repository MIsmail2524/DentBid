import numpy as np
import pytest

from app.services import analysis
from dentbid_cv.analyzer import Segment, analyze_predictions

from .conftest import jpeg_bytes, register

KARACHI = (24.8607, 67.0011)


class FakeAnalyzer:
    """Stands in for the YOLO models: one dent on the front door."""
    version = "fake-1"

    def analyze(self, img):
        h, w = img.shape[:2]
        dent = np.zeros((h, w), bool)
        dent[300:400, 500:620] = True
        door = np.zeros((h, w), bool)
        door[200:600, 300:850] = True
        return analyze_predictions(
            img,
            [Segment("dent", 0.9, dent, (500, 300, 620, 400))],
            [Segment("front_door", 0.9, door, (300, 200, 850, 600))],
            model_version=self.version,
        )


@pytest.fixture()
def fake_model(monkeypatch):
    monkeypatch.setattr(analysis, "get_analyzer", lambda: FakeAnalyzer())


def make_workshop(client, email, lat, lng, services=None):
    h, _ = register(client, email, role="workshop")
    r = client.put("/api/workshops/me", headers=h, json={
        "name": f"Shop {email[:4]}", "lat": lat, "lng": lng, "city": "Karachi",
        "service_radius_km": 20, "services": services or [], "phone": "+92211111111"})
    assert r.status_code == 200, r.text
    return h


def create_request(client, h, offer=None):
    data = {"lat": str(KARACHI[0]), "lng": str(KARACHI[1]), "city": "Karachi", "country_code": "PK",
            "car_make": "Toyota", "car_model": "Corolla", "car_year": "2019"}
    if offer:
        data["customer_offer"] = str(offer)
    r = client.post("/api/requests", headers=h, data=data,
                    files=[("photos", ("a.jpg", jpeg_bytes(), "image/jpeg")),
                           ("photos", ("b.jpg", jpeg_bytes(), "image/jpeg"))])
    assert r.status_code == 201, r.text
    return r.json()


def test_locale_detection(client):
    assert client.get("/api/locale?country=PK").json()["currency"] == "PKR"
    ae = client.get("/api/locale?country=AE").json()
    assert ae["currency"] == "AED" and ae["language"] == "ar" and ae["rtl"]
    via_header = client.get("/api/locale", headers={"CF-IPCountry": "IN"}).json()
    assert via_header["currency"] == "INR" and via_header["detected_from"] == "ip"
    assert client.get("/api/locale?country=ZZ").json()["detected_from"] == "default"


def test_register_sets_locale_and_login(client):
    h, user = register(client, "a@x.com", country="SA")
    assert user["currency"] == "SAR" and user["language"] == "ar"
    assert client.post("/api/auth/login", json={"email": "a@x.com", "password": "wrong-pass"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "A@x.com", "password": "secret123"}).status_code == 200
    assert client.get("/api/auth/me", headers=h).json()["email"] == "a@x.com"


def test_full_bidding_flow(client, fake_model):
    cust, _ = register(client, "cust@x.com")
    near = make_workshop(client, "near@x.com", 24.87, 67.01, services=["dent", "scratch"])
    near2 = make_workshop(client, "near2@x.com", 24.85, 67.02)
    far = make_workshop(client, "far@x.com", 31.52, 74.35)   # Lahore
    glass_only = make_workshop(client, "glass@x.com", 24.86, 67.00, services=["glass_shatter"])

    req = create_request(client, cust, offer=8000)
    rid = req["id"]
    assert req["currency"] == "PKR"

    # analysis ran in the background
    detail = client.get(f"/api/requests/{rid}", headers=cust).json()
    assert detail["status"] == "open"
    assert detail["analysis"]["status"] == "done"
    assert detail["analysis"]["damage_types"] == ["dent"]
    assert detail["overall_severity"] in ("minor", "moderate", "severe")
    assert detail["photos"][0]["annotated_url"].endswith("_annotated.jpg")
    dmg = detail["photos"][0]["analysis"]["damages"][0]
    assert dmg["part"] == "front_door" and dmg["measurements"]["width_cm"] > 0

    # feed: near shops see it, far + glass-only shops do not
    assert [c["id"] for c in client.get("/api/requests/feed", headers=near).json()] == [rid]
    assert client.get("/api/requests/feed", headers=far).json() == []
    assert client.get("/api/requests/feed", headers=glass_only).json() == []
    assert client.get(f"/api/requests/{rid}", headers=far).status_code == 404

    # workshop sees fuzzed location and no phone before booking
    wview = client.get(f"/api/requests/{rid}", headers=near).json()
    assert wview["lat"] == round(KARACHI[0], 2) and wview["customer_phone"] is None

    q1 = client.post(f"/api/requests/{rid}/quotes", headers=near, json={
        "amount": 12000, "eta_days": 2, "warranty_months": 6,
        "breakdown": [{"item": "PDR front door", "amount": 12000}]}).json()
    q2 = client.post(f"/api/requests/{rid}/quotes", headers=near2, json={"amount": 9500}).json()
    assert client.post(f"/api/requests/{rid}/quotes", headers=far, json={"amount": 1}).status_code == 403

    quotes = client.get(f"/api/requests/{rid}/quotes", headers=cust).json()
    assert {q["amount"] for q in quotes} == {"12000.00", "9500.00"}
    assert all(q["workshop"]["phone"] is None for q in quotes)
    assert client.get(f"/api/requests/{rid}", headers=cust).json()["lowest_quote"] == "9500.00"

    # chat
    assert client.post(f"/api/quotes/{q1['id']}/messages", headers=cust, json={"body": "Can you do 10k?"}).status_code == 201
    assert client.post(f"/api/quotes/{q1['id']}/messages", headers=near2, json={"body": "hi"}).status_code == 404
    assert len(client.get(f"/api/quotes/{q1['id']}/messages", headers=near).json()) == 1

    # counter must be lower; workshop accepts counter -> booked
    assert client.post(f"/api/quotes/{q1['id']}/counter", headers=cust, json={"amount": 13000}).status_code == 422
    c = client.post(f"/api/quotes/{q1['id']}/counter", headers=cust, json={"amount": 10000}).json()
    assert c["status"] == "countered"
    booked = client.post(f"/api/quotes/{q1['id']}/accept-counter", headers=near).json()
    assert booked["status"] == "accepted" and booked["amount"] == "10000.00"

    detail = client.get(f"/api/requests/{rid}", headers=cust).json()
    assert detail["status"] == "booked" and detail["accepted_quote_id"] == q1["id"]
    after = {q["id"]: q for q in client.get(f"/api/requests/{rid}/quotes", headers=cust).json()}
    assert after[q2["id"]]["status"] == "rejected"
    assert after[q1["id"]]["workshop"]["phone"] == "+92211111111"  # contact revealed after booking
    assert client.post(f"/api/quotes/{q2['id']}/accept", headers=cust).status_code == 409

    # booked workshop now sees exact location + phone
    wview = client.get(f"/api/requests/{rid}", headers=near).json()
    assert wview["lat"] == KARACHI[0] and wview["customer_phone"] == "+923001234567"

    # job lifecycle + review
    assert client.post(f"/api/requests/{rid}/status", headers=near2, json={"status": "completed"}).status_code == 403
    assert client.post(f"/api/requests/{rid}/review", headers=cust, json={"rating": 5}).status_code == 409
    assert client.post(f"/api/requests/{rid}/status", headers=near, json={"status": "in_progress"}).json()["status"] == "in_progress"
    assert client.post(f"/api/requests/{rid}/status", headers=near, json={"status": "completed"}).json()["status"] == "completed"
    assert client.post(f"/api/requests/{rid}/review", headers=cust, json={"rating": 4, "comment": "Good"}).status_code == 201
    shop = client.get("/api/workshops/me", headers=near).json()
    assert shop["rating_avg"] == 4 and shop["jobs_completed"] == 1

    assert [c["id"] for c in client.get("/api/quotes/mine", headers=near).json()] == [rid]
    assert client.get("/api/requests/mine", headers=cust).json()[0]["status"] == "completed"


def test_accept_quote_directly_and_cancel(client, fake_model):
    cust, _ = register(client, "c2@x.com")
    shop = make_workshop(client, "s2@x.com", 24.87, 67.01)
    rid = create_request(client, cust)["id"]
    q = client.post(f"/api/requests/{rid}/quotes", headers=shop, json={"amount": 5000}).json()
    # revise quote
    q = client.post(f"/api/requests/{rid}/quotes", headers=shop, json={"amount": 4500}).json()
    assert q["amount"] == "4500.00"
    assert client.post(f"/api/quotes/{q['id']}/accept", headers=cust).json()["status"] == "accepted"
    assert client.post(f"/api/requests/{rid}/quotes", headers=shop, json={"amount": 1}).status_code == 409
    assert client.post(f"/api/requests/{rid}/cancel", headers=cust).json()["status"] == "cancelled"


def test_without_model_request_still_opens(client):
    cust, _ = register(client, "c3@x.com")
    rid = create_request(client, cust)["id"]
    d = client.get(f"/api/requests/{rid}", headers=cust).json()
    assert d["status"] == "open"
    assert d["analysis"]["status"] == "unavailable"
    assert "quality" in d["photos"][0]["analysis"]


def test_permissions(client):
    cust, _ = register(client, "c4@x.com")
    shop_user, _ = register(client, "s4@x.com", role="workshop")
    assert client.get("/api/requests/feed", headers=shop_user).status_code == 409  # no profile yet
    assert client.get("/api/requests/feed", headers=cust).status_code == 403
    assert client.put("/api/workshops/me", headers=cust, json={"name": "XY", "lat": 1, "lng": 1}).status_code == 403
    r = client.post("/api/requests", headers=cust, data={"lat": "1", "lng": "1"},
                    files=[("photos", ("x.jpg", b"not an image", "image/jpeg"))])
    assert r.status_code == 400
