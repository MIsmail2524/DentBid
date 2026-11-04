"""Admin verification flow and attack scenarios. Each attack must fail."""

import base64
import io
import json
import time

import jwt
import numpy as np
from PIL import Image

from app.services.ratelimit import limiter

from .conftest import admin_headers, jpeg_bytes, register
from .test_flow import KARACHI, create_request, make_workshop

SHOP = {"name": "Garage One", "lat": 24.87, "lng": 67.01, "city": "Karachi", "phone": "+9221000"}


def png_bytes(w=800, h=600) -> bytes:
    buf = io.BytesIO()
    Image.fromarray(np.full((h, w, 3), 120, np.uint8)).save(buf, "PNG")
    return buf.getvalue()


# ---------------- admin verification ----------------
def test_unverified_workshop_is_blocked_until_approved(client):
    cust, _ = register(client, "c@x.com")
    h, _ = register(client, "w@x.com", role="workshop")
    ws = client.put("/api/workshops/me", headers=h, json=SHOP).json()
    rid = create_request(client, cust)["id"]

    r = client.get("/api/requests/feed", headers=h)
    assert r.status_code == 403 and "workshop_not_verified:pending" in r.text
    assert client.post(f"/api/requests/{rid}/quotes", headers=h, json={"amount": 100}).status_code == 403
    assert client.get(f"/api/requests/{rid}", headers=h).status_code == 404
    assert client.get(f"/api/workshops/{ws['id']}").status_code == 404           # not public yet
    assert client.get("/api/auth/me", headers=h).json()["workshop_status"] == "pending"

    # documents: upload, owner can read, other users cannot, stored outside /media
    doc = client.post("/api/workshops/me/documents", headers=h, data={"kind": "trade_license"},
                      files={"file": ("lic.jpg", jpeg_bytes(), "image/jpeg")})
    assert doc.status_code == 201, doc.text
    url = doc.json()["url"]
    assert client.get(url, headers=h).status_code == 200
    assert client.get(url, headers=cust).status_code == 404
    assert client.get(url).status_code == 401
    assert client.post("/api/workshops/me/documents", headers=h, data={"kind": "../../etc"},
                       files={"file": ("x.jpg", jpeg_bytes(), "image/jpeg")}).status_code == 422

    adm = admin_headers(client)
    pending = client.get("/api/admin/workshops?status=pending", headers=adm).json()
    assert [w["id"] for w in pending] == [ws["id"]] and pending[0]["document_count"] == 1
    detail = client.get(f"/api/admin/workshops/{ws['id']}", headers=adm).json()
    assert client.get(detail["documents"][0]["url"], headers=adm).status_code == 200

    rej = client.post(f"/api/admin/workshops/{ws['id']}/reject", headers=adm, json={"reason": "Licence photo unreadable"})
    assert rej.json()["verification_status"] == "rejected"
    me = client.get("/api/workshops/me", headers=h).json()
    assert me["rejection_reason"] == "Licence photo unreadable"
    # editing after rejection resubmits for review
    assert client.put("/api/workshops/me", headers=h, json=SHOP).json()["verification_status"] == "pending"

    assert client.post(f"/api/admin/workshops/{ws['id']}/approve", headers=adm).json()["verified"] is True
    assert client.get("/api/requests/feed", headers=h).status_code == 200
    q = client.post(f"/api/requests/{rid}/quotes", headers=h, json={"amount": 5000})
    assert q.status_code == 201

    # moving the shop 50 km requires a new review
    moved = client.put("/api/workshops/me", headers=h, json={**SHOP, "lat": 25.3}).json()
    assert moved["verification_status"] == "pending"
    client.post(f"/api/admin/workshops/{ws['id']}/approve", headers=adm)

    # suspension withdraws open quotes, customer can no longer accept them
    client.post(f"/api/admin/workshops/{ws['id']}/suspend", headers=adm, json={"reason": "Fraud reports"})
    assert client.post(f"/api/quotes/{q.json()['id']}/accept", headers=cust).status_code == 409

    actions = [a["action"] for a in client.get("/api/admin/audit", headers=adm).json()]
    assert actions[:3] == ["workshop.suspended", "workshop.approved", "workshop.approved"]
    stats = client.get("/api/admin/stats", headers=adm).json()
    assert stats["workshops"]["suspended"] == 1 and "analyzer" in stats


def test_admin_endpoints_need_admin(client):
    cust, _ = register(client, "c@x.com")
    shop = make_workshop(client, "w@x.com", 24.87, 67.01)
    for h in (cust, shop, {}):
        assert client.get("/api/admin/workshops", headers=h).status_code in (401, 403)
        assert client.post("/api/admin/workshops/1/approve", headers=h).status_code in (401, 403)
        assert client.get("/api/admin/users", headers=h).status_code in (401, 403)


def test_deactivated_user_loses_access_immediately(client):
    cust, user = register(client, "c@x.com")
    adm = admin_headers(client)
    assert client.get("/api/auth/me", headers=cust).status_code == 200
    client.post(f"/api/admin/users/{user['id']}/deactivate", headers=adm, json={"reason": "spam"})
    assert client.get("/api/auth/me", headers=cust).status_code == 401
    r = client.post("/api/auth/login", json={"email": "c@x.com", "password": "secret123"})
    assert r.status_code == 403
    me = client.get("/api/auth/me", headers=adm).json()
    assert client.post(f"/api/admin/users/{me['id']}/deactivate", headers=adm, json={"reason": "oops"}).status_code == 409


def test_admin_search_escapes_wildcards(client):
    make_workshop(client, "w@x.com", 24.87, 67.01)
    adm = admin_headers(client)
    assert len(client.get("/api/admin/workshops?q=Shop", headers=adm).json()) == 1
    assert client.get("/api/admin/workshops?q=%25", headers=adm).json() == []
    assert client.get("/api/admin/users?q=' OR 1=1 --", headers=adm).json() == []


# ---------------- authentication attacks ----------------
def test_cannot_register_as_admin(client):
    r = client.post("/api/auth/register", json={"name": "Eve", "email": "e@x.com", "password": "secret123", "role": "admin"})
    assert r.status_code == 422


def test_forged_and_tampered_tokens_rejected(client):
    h, user = register(client, "c@x.com")
    token = h["Authorization"].split()[1]
    # alg=none
    header = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    body = base64.urlsafe_b64encode(json.dumps({"sub": "1", "tv": 0, "iat": int(time.time()), "exp": int(time.time()) + 999,
                                                "typ": "access"}).encode()).rstrip(b"=").decode()
    for bad in (f"{header}.{body}.", token[:-4] + "AAAA",
                jwt.encode({"sub": str(user["id"]), "exp": int(time.time()) + 99, "iat": int(time.time()), "typ": "access"},
                           "guessed-secret", algorithm="HS256"),
                jwt.encode({"sub": "1", "exp": int(time.time()) - 10, "iat": int(time.time()) - 99, "typ": "access"},
                           "test-secret-that-is-long-enough-for-hs256", algorithm="HS256")):
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
    # logout-all revokes old tokens
    assert client.post("/api/auth/logout-all", headers=h).status_code == 204
    assert client.get("/api/auth/me", headers=h).status_code == 401


def test_login_bruteforce_is_rate_limited(client):
    register(client, "c@x.com")
    codes = [client.post("/api/auth/login", json={"email": "c@x.com", "password": f"wrong{i}xxx"}).status_code
             for i in range(12)]
    assert codes[:10] == [401] * 10 and codes[-1] == 429
    limiter.reset()


def test_login_does_not_reveal_unknown_email(client):
    register(client, "c@x.com")
    a = client.post("/api/auth/login", json={"email": "nobody@x.com", "password": "whatever1"})
    b = client.post("/api/auth/login", json={"email": "c@x.com", "password": "whatever1"})
    assert a.status_code == b.status_code == 401 and a.json() == b.json()


# ---------------- authorisation (IDOR) ----------------
def test_customers_cannot_touch_other_customers_data(client):
    alice, _ = register(client, "alice@x.com")
    bob, _ = register(client, "bob@x.com")
    shop = make_workshop(client, "w@x.com", 24.87, 67.01)
    rid = create_request(client, alice)["id"]
    qid = client.post(f"/api/requests/{rid}/quotes", headers=shop, json={"amount": 900}).json()["id"]
    assert client.get(f"/api/requests/{rid}", headers=bob).status_code == 404
    assert client.get(f"/api/requests/{rid}/quotes", headers=bob).status_code == 404
    assert client.post(f"/api/quotes/{qid}/accept", headers=bob).status_code == 404
    assert client.post(f"/api/quotes/{qid}/counter", headers=bob, json={"amount": 1}).status_code == 404
    assert client.post(f"/api/requests/{rid}/cancel", headers=bob).status_code == 404
    assert client.patch(f"/api/requests/{rid}/offer", headers=bob, json={"amount": 1}).status_code == 404
    assert client.get(f"/api/quotes/{qid}/messages", headers=bob).status_code == 404
    assert client.post(f"/api/quotes/{qid}/messages", headers=bob, json={"body": "hi"}).status_code == 404
    other_shop = make_workshop(client, "w2@x.com", 24.87, 67.01)
    assert client.post(f"/api/quotes/{qid}/withdraw", headers=other_shop).status_code == 404
    assert client.post(f"/api/quotes/{qid}/accept-counter", headers=other_shop).status_code == 404


def test_workshop_cannot_act_as_customer(client):
    shop = make_workshop(client, "w@x.com", 24.87, 67.01)
    r = client.post("/api/requests", headers=shop, data={"lat": "1", "lng": "1"},
                    files=[("photos", ("a.jpg", jpeg_bytes(), "image/jpeg"))])
    assert r.status_code == 403


# ---------------- input / upload attacks ----------------
def test_malicious_uploads_rejected(client):
    cust, _ = register(client, "c@x.com")
    base = {"lat": "24.86", "lng": "67.0"}

    def up(name, data, ctype="image/jpeg"):
        return client.post("/api/requests", headers=cust, data=base, files=[("photos", (name, data, ctype))]).status_code

    svg = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"></svg>'
    assert up("x.svg", svg, "image/svg+xml") == 400
    assert up("x.html", b"<script>alert(1)</script>", "text/html") == 400
    assert up("x.jpg", b"") == 400
    # GIF is not an allowed format even though Pillow can read it
    gif = io.BytesIO()
    Image.new("RGB", (10, 10)).save(gif, "GIF")
    assert up("x.gif", gif.getvalue(), "image/gif") == 400
    # decompression bomb: tiny PNG declaring 20000x20000 pixels
    bomb = io.BytesIO()
    Image.new("1", (20000, 20000)).save(bomb, "PNG")
    assert len(bomb.getvalue()) < 200_000
    assert up("bomb.png", bomb.getvalue(), "image/png") == 400
    # JPEG with a script appended (polyglot) is accepted but re-encoded: payload gone
    poly = jpeg_bytes() + b"<script>alert(1)</script>"
    r = client.post("/api/requests", headers=cust, data=base, files=[("photos", ("p.jpg", poly, "image/jpeg"))])
    assert r.status_code == 201
    img = client.get(r.json()["photos"][0]["url"])
    assert img.status_code == 200 and b"<script>" not in img.content
    assert img.headers["x-content-type-options"] == "nosniff"
    # PNG accepted and stored as JPEG
    assert up("ok.png", png_bytes(), "image/png") == 201


def test_too_many_photos_and_oversized_fields(client):
    cust, _ = register(client, "c@x.com")
    files = [("photos", (f"{i}.jpg", jpeg_bytes(64, 64), "image/jpeg")) for i in range(9)]
    assert client.post("/api/requests", headers=cust, data={"lat": "1", "lng": "1"}, files=files).status_code == 422
    r = client.post("/api/requests", headers=cust, data={"lat": "1", "lng": "1", "car_make": "A" * 500},
                    files=[("photos", ("a.jpg", jpeg_bytes(), "image/jpeg"))])
    assert r.status_code == 422
    r = client.post("/api/requests", headers=cust, data={"lat": "999", "lng": "1"},
                    files=[("photos", ("a.jpg", jpeg_bytes(), "image/jpeg"))])
    assert r.status_code == 422
    shop = make_workshop(client, "w@x.com", 24.87, 67.01)
    rid = create_request(client, cust)["id"]
    for bad in ({"amount": -5}, {"amount": 0}, {"amount": "1e30"}, {"amount": 10, "eta_days": -1},
                {"amount": 10, "notes": "x" * 5000}):
        assert client.post(f"/api/requests/{rid}/quotes", headers=shop, json=bad).status_code == 422


def test_body_size_limit(client):
    cust, _ = register(client, "c@x.com")
    r = client.post("/api/requests", headers={**cust, "Content-Length": str(500 * 1024 * 1024)},
                    content=b"x")
    assert r.status_code == 413


# ---------------- media access ----------------
def test_media_requires_valid_signature(client):
    cust, _ = register(client, "c@x.com")
    url = create_request(client, cust)["photos"][0]["url"]
    path = url.split("?")[0]
    assert client.get(url).status_code == 200
    assert client.get(path).status_code == 422                      # unsigned
    assert client.get(path + "?exp=9999999999&sig=" + "0" * 32).status_code == 403
    exp = url.split("exp=")[1].split("&")[0]
    sig = url.split("sig=")[1]
    other = path.rsplit("/", 1)[0] + "/other.jpg"
    assert client.get(f"{other}?exp={exp}&sig={sig}").status_code == 403   # signature bound to path
    assert client.get(f"/media/../app/config.py?exp={exp}&sig={sig}").status_code in (403, 404)
    assert client.get(f"/media/requests/1/..%2F..%2F..%2Fapp%2Fconfig.py?exp={exp}&sig={sig}").status_code in (403, 404)


def test_health_does_not_leak_internals(client):
    r = client.get("/api/health").json()
    assert set(r["analyzer"]) == {"available", "model_version"}


def test_security_headers_and_cors(client):
    r = client.get("/api/health", headers={"Origin": "https://evil.example"})
    assert r.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in r.headers["content-security-policy"]
    assert r.headers.get("access-control-allow-credentials") is None


def test_websocket_requires_token_message(client):
    import pytest
    from starlette.websockets import WebSocketDisconnect

    h, _ = register(client, "c@x.com")
    token = h["Authorization"].split()[1]
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"token": "garbage"})
        with pytest.raises(WebSocketDisconnect):
            ws.receive_json()
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"token": token})
        assert ws.receive_json() == {"type": "ready"}
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


def test_cannot_quote_outside_service_area_or_view_far_requests(client):
    cust, _ = register(client, "c@x.com")
    rid = create_request(client, cust)["id"]
    far = make_workshop(client, "far@x.com", KARACHI[0] + 0.5, KARACHI[1])   # ~55 km away
    assert client.get(f"/api/requests/{rid}", headers=far).status_code == 404
    assert client.post(f"/api/requests/{rid}/quotes", headers=far, json={"amount": 10}).status_code == 403
