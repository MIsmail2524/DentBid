#!/usr/bin/env bash
# DentBid: one command to install, build and run the whole system.
#
#   ./dentbid.sh              install what is missing, build the web app, start on http://localhost:8000
#   ./dentbid.sh --rebuild    force a fresh web build
#   PORT=9000 ./dentbid.sh    use another port
#
# Needs: Python 3.10+, Node.js 18+. First run downloads dependencies (a few minutes).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8000}"
REBUILD=0
for arg in "$@"; do
  case "$arg" in
    --rebuild) REBUILD=1 ;;
    -h|--help) sed -n '2,9p' "$0"; exit 0 ;;
    *) echo "unknown option: $arg"; exit 1 ;;
  esac
done

say() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
die() { printf '\033[1;31mERROR:\033[0m %s\n' "$*" >&2; exit 1; }

# ---------- prerequisites ----------
PY="$(command -v python3 || true)"
[ -n "$PY" ] || die "python3 not found. Install Python 3.10 or newer."
"$PY" -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' || die "Python 3.10+ required."
command -v node >/dev/null || die "node not found. Install Node.js 18 or newer."
command -v npm >/dev/null || die "npm not found."

# ---------- backend ----------
cd "$ROOT/backend"
if [ ! -x .venv/bin/python ]; then
  say "Creating Python environment"
  "$PY" -m venv .venv
fi
STAMP=.venv/.dentbid-installed
NEED_YOLO=0
[ -f "$ROOT/ml/weights/damage.pt" ] && NEED_YOLO=1
if [ ! -f "$STAMP" ] || [ requirements.txt -nt "$STAMP" ] || [ "$ROOT/ml/pyproject.toml" -nt "$STAMP" ] \
   || { [ "$NEED_YOLO" = 1 ] && ! .venv/bin/python -c 'import ultralytics' 2>/dev/null; }; then
  say "Installing backend dependencies"
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  if [ "$NEED_YOLO" = 1 ]; then
    say "Model weights found: installing PyTorch (CPU) + Ultralytics for AI analysis"
    .venv/bin/pip install -q torch torchvision --index-url https://download.pytorch.org/whl/cpu
    .venv/bin/pip install -q -e "$ROOT/ml[yolo]"
  else
    .venv/bin/pip install -q -e "$ROOT/ml"
  fi
  touch "$STAMP"
fi

if [ ! -f .env ]; then
  say "Creating backend/.env with fresh secrets"
  JWT=$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(48))')
  ADMIN_PW=$(.venv/bin/python -c 'import secrets; print(secrets.token_urlsafe(12))')
  umask 077
  cat > .env <<EOF
ENVIRONMENT=development
DATABASE_URL=sqlite:///./dentbid.db
JWT_SECRET=$JWT
ADMIN_EMAIL=admin@dentbid.app
ADMIN_PASSWORD=$ADMIN_PW
WEB_DIST_DIR=../mobile/dist
MEDIA_DIR=media
PRIVATE_MEDIA_DIR=private_media
CORS_ORIGINS=*
DENTBID_DAMAGE_WEIGHTS=../ml/weights/damage.pt
DENTBID_PARTS_WEIGHTS=../ml/weights/parts.pt
DENTBID_CAR_WEIGHTS=yolo11n-seg.pt
DENTBID_DEVICE=cpu
EOF
  umask 022
fi

# ---------- web app ----------
cd "$ROOT/mobile"
if [ ! -d node_modules ] || [ package.json -nt node_modules ]; then
  say "Installing app dependencies"
  npm ci --no-audit --no-fund --loglevel=error
  touch node_modules
fi
if [ "$REBUILD" = 1 ] || [ ! -f dist/index.html ] \
   || [ -n "$(find src app.json package.json -newer dist/index.html -print -quit 2>/dev/null)" ]; then
  say "Building web app"
  rm -rf dist
  EXPO_OFFLINE=1 CI=1 npx expo export --platform web --output-dir dist >/dev/null
fi

# ---------- run ----------
cd "$ROOT/backend"
ADMIN_EMAIL=$(grep '^ADMIN_EMAIL=' .env | cut -d= -f2-)
ADMIN_PW=$(grep '^ADMIN_PASSWORD=' .env | cut -d= -f2-)
LAN=$(hostname -I 2>/dev/null | awk '{print $1}')
echo
say "DentBid is starting"
echo "    Web app:   http://localhost:$PORT${LAN:+   (phones on your Wi-Fi: http://$LAN:$PORT)}"
echo "    API docs:  http://localhost:$PORT/docs"
echo "    Admin:     $ADMIN_EMAIL / $ADMIN_PW   (stored in backend/.env)"
if [ "$NEED_YOLO" = 0 ]; then
  echo "    AI model:  not installed. Put damage.pt and parts.pt in ml/weights/ and rerun (see ml/README.md)."
fi
echo "    Stop with Ctrl+C"
echo
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --proxy-headers
