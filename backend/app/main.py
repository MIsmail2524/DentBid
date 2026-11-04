import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import models  # noqa: F401  (register tables)
from .config import DEV_SECRET, get_settings
from .db import Base, SessionLocal, engine
from .models import Role, User
from .routers import admin, auth, media, meta, quotes, requests, workshops, ws
from .security import hash_password
from .services.ratelimit import client_ip, limiter
from .services.storage import resolve_inside

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("dentbid")
settings = get_settings()


def bootstrap_admin() -> None:
    """Creates the first admin from ADMIN_EMAIL / ADMIN_PASSWORD if it does not exist yet."""
    email = settings.admin_email.strip().lower()
    if not email:
        return
    db = SessionLocal()
    try:
        u = db.query(User).filter(User.email == email).one_or_none()
        if u is not None:
            if u.role != Role.admin:
                log.warning("ADMIN_EMAIL %s belongs to a non-admin account; not promoting it", email)
            return
        password = settings.admin_password or secrets.token_urlsafe(16)
        db.add(User(name="Administrator", email=email, role=Role.admin, password_hash=hash_password(password)))
        db.commit()
        if settings.admin_password:
            log.info("admin account created: %s", email)
        else:
            log.warning("admin account created: %s / generated password: %s (change it after first login)",
                        email, password)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate_for_production()
    if settings.jwt_secret == DEV_SECRET:
        log.warning("JWT_SECRET is the development default. Set a long random value in production.")
    Base.metadata.create_all(engine)
    bootstrap_admin()
    yield


docs = settings.enable_docs and not settings.is_production
app = FastAPI(title=settings.app_name, version="0.2.0", lifespan=lifespan,
              docs_url="/docs" if docs else None, redoc_url=None, openapi_url="/openapi.json" if docs else None)


class BodyLimit:
    """Rejects request bodies above MAX_BODY_MB, including chunked uploads without Content-Length."""

    def __init__(self, app, max_bytes: int):
        self.app, self.max = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        for k, v in scope.get("headers", []):
            if k == b"content-length" and v.isdigit() and int(v) > self.max:
                return await JSONResponse({"detail": "Request too large"}, 413)(scope, receive, send)
        seen = 0

        async def limited():
            nonlocal seen
            msg = await receive()
            if msg["type"] == "http.request":
                seen += len(msg.get("body", b""))
                if seen > self.max:
                    raise HTTPException(413, "Request too large")
            return msg

        await self.app(scope, limited, send)


@app.middleware("http")
async def security_and_rate_limit(request, call_next):
    path = request.url.path
    if path.startswith("/api/"):
        ok, retry = limiter.hit(f"api:{client_ip(request)}", settings.rate_limit_per_minute, 60)
        if not ok:
            return JSONResponse({"detail": "Too many requests"}, 429, headers={"Retry-After": str(int(retry) + 1)})
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "DENY")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Permissions-Policy", "camera=(self), geolocation=(self), microphone=()")
    h.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    if path.startswith(("/api/", "/media/")):
        h.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    if settings.is_production:
        h.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=False,  # bearer tokens, no cookies: nothing for CSRF to ride on
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)
app.add_middleware(BodyLimit, max_bytes=settings.max_body_mb * 1024 * 1024)

for r in (meta.router, auth.router, workshops.router, requests.router, quotes.router, admin.router):
    app.include_router(r, prefix="/api")
app.include_router(ws.router)
app.include_router(media.router)


# ---------- web app (Expo web export) served from the same origin ----------
dist = settings.web_dist_dir


@app.get("/{full_path:path}", include_in_schema=False)
def web_app(full_path: str):
    if full_path.startswith(("api/", "media/", "ws")) or not (dist / "index.html").is_file():
        raise HTTPException(404, "Not found")
    f = resolve_inside(dist, full_path) if full_path else None
    if f is not None and f.is_file():
        cache = "public, max-age=31536000, immutable" if full_path.startswith("_expo/") else "no-cache"
        return FileResponse(f, headers={"Cache-Control": cache})
    # client-side routes (/request/12, /admin ...) all load the single-page app
    return FileResponse(dist / "index.html", headers={"Cache-Control": "no-cache"})
