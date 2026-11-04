#!/usr/bin/env bash
# Train both DentBid models on a GPU server (run inside a tmux/screen session over SSH):
#
#   git clone https://github.com/MIsmail2524/DentBid.git && cd DentBid/ml
#   bash scripts/gpu_train.sh            # full run (yolo11m damage, yolo11s parts)
#   MODEL=yolo11l-seg.pt bash scripts/gpu_train.sh   # bigger damage model
#
# Then copy the weights back to the app machine:
#   scp user@gpu:DentBid/ml/weights/{damage,parts}.pt ml/weights/
set -euo pipefail
cd "$(dirname "$0")/.."

MODEL="${MODEL:-yolo11m-seg.pt}"
PARTS_MODEL="${PARTS_MODEL:-yolo11s-seg.pt}"
EPOCHS="${EPOCHS:-150}"
IMGSZ="${IMGSZ:-1024}"
DEVICE="${DEVICE:-0}"

command -v nvidia-smi >/dev/null && nvidia-smi --query-gpu=name,memory.total --format=csv || echo "WARNING: no nvidia-smi found"

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
. .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r requirements.txt huggingface_hub

python - <<'PY'
import torch
print("torch", torch.__version__, "cuda:", torch.cuda.is_available())
assert torch.cuda.is_available(), "CUDA not available: install the CUDA build of torch for this server"
PY

[ -f datasets/damage/data.yaml ] || python scripts/fetch_cardd_hf.py --out datasets/damage

python scripts/train.py damage --data datasets/damage/data.yaml --model "$MODEL" \
  --epochs "$EPOCHS" --imgsz "$IMGSZ" --device "$DEVICE"
python scripts/evaluate.py --weights weights/damage.pt --data datasets/damage/data.yaml --split test --imgsz "$IMGSZ"

python scripts/train.py parts --model "$PARTS_MODEL" --device "$DEVICE"

ls -la weights/
echo "Done. Copy ml/weights/damage.pt and ml/weights/parts.pt to the app server."
