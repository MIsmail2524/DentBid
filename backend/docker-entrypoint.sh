#!/bin/sh
# Generates JWT secret and admin password on first boot and keeps them in the /data volume.
set -e
SECRETS=/data/secrets.env
if [ ! -f "$SECRETS" ]; then
  umask 077
  python - > "$SECRETS" <<'PY'
import secrets
print(f"JWT_SECRET={secrets.token_urlsafe(48)}")
print(f"GENERATED_ADMIN_PASSWORD={secrets.token_urlsafe(12)}")
PY
fi
. "$SECRETS"
export JWT_SECRET="${JWT_SECRET_OVERRIDE:-$JWT_SECRET}"
export ADMIN_EMAIL="${ADMIN_EMAIL:-admin@dentbid.app}"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:-$GENERATED_ADMIN_PASSWORD}"
echo "DentBid admin: $ADMIN_EMAIL / $ADMIN_PASSWORD  (stored in the data volume, change it after first login)"
exec "$@"
