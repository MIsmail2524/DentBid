# Build from the repository root: docker build -f backend/Dockerfile .
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /srv
# CPU-only PyTorch keeps the image ~2 GB smaller; use the CUDA index on GPU hosts.
RUN pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
COPY ml /srv/ml
RUN pip install "/srv/ml[yolo]"
COPY backend/requirements.txt /srv/backend/requirements.txt
RUN pip install -r /srv/backend/requirements.txt
COPY backend /srv/backend

WORKDIR /srv/backend
ENV DENTBID_DAMAGE_WEIGHTS=/srv/ml/weights/damage.pt \
    DENTBID_PARTS_WEIGHTS=/srv/ml/weights/parts.pt \
    MEDIA_DIR=/data/media
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
