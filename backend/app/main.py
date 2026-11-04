import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from . import models  # noqa: F401  (register tables)
from .config import get_settings
from .db import Base, engine
from .routers import auth, meta, quotes, requests, workshops, ws
from .services.storage import media_root

logging.basicConfig(level=logging.INFO)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.jwt_secret == "dev-secret-change-me":
        logging.getLogger("dentbid").warning("JWT_SECRET is the development default. Set a long random value in production.")
    Base.metadata.create_all(engine)
    yield


app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials="*" not in settings.cors_list,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (meta.router, auth.router, workshops.router, requests.router, quotes.router):
    app.include_router(r, prefix="/api")
app.include_router(ws.router)
app.mount("/media", StaticFiles(directory=media_root()), name="media")
