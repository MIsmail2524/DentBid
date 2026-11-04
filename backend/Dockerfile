# Build from the repository root:  docker compose up --build
# ---------- 1. web app ----------
FROM node:22-slim AS web
WORKDIR /web
COPY mobile/package.json mobile/package-lock.json ./
RUN npm ci --no-audit --no-fund --loglevel=error
COPY mobile/ ./
RUN EXPO_OFFLINE=1 CI=1 npx expo export --platform web --output-dir dist

# ---------- 2. API ----------
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 dentbid

WORKDIR /srv
# CPU-only PyTorch keeps the image ~2 GB smaller; use the CUDA index on GPU hosts.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY ml /srv/ml
RUN pip install "/srv/ml[yolo]"
COPY backend/requirements.txt /srv/backend/requirements.txt
RUN pip install -r /srv/backend/requirements.txt
COPY backend /srv/backend
COPY --from=web /web/dist /srv/web

WORKDIR /srv/backend
ENV DENTBID_DAMAGE_WEIGHTS=/srv/ml/weights/damage.pt \
    DENTBID_PARTS_WEIGHTS=/srv/ml/weights/parts.pt \
    MEDIA_DIR=/data/media \
    PRIVATE_MEDIA_DIR=/data/private_media \
    WEB_DIST_DIR=/srv/web \
    YOLO_CONFIG_DIR=/data/ultralytics
RUN mkdir -p /data && chown dentbid /data && chmod +x /srv/backend/docker-entrypoint.sh
USER dentbid
EXPOSE 8000
ENTRYPOINT ["/srv/backend/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
