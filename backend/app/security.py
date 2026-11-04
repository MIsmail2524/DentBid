import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import get_settings

# Verified against when the email does not exist, so login takes the same time
# whether or not an account exists (prevents user enumeration by timing).
_DUMMY_HASH = bcrypt.hashpw(b"dentbid-timing-equaliser", bcrypt.gensalt()).decode()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str | None) -> bool:
    try:
        ok = bcrypt.checkpw(password.encode()[:72], (hashed or _DUMMY_HASH).encode())
    except ValueError:
        return False
    return ok and hashed is not None


def create_token(user_id: int, token_version: int = 0) -> str:
    s = get_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "tv": token_version, "iat": now,
               "exp": now + timedelta(minutes=s.jwt_expire_minutes), "typ": "access"}
    return jwt.encode(payload, s.jwt_secret, algorithm=s.jwt_algorithm)


def decode_token(token: str) -> tuple[int, int] | None:
    """Returns (user_id, token_version) or None. Only the configured algorithm is accepted."""
    s = get_settings()
    try:
        payload = jwt.decode(token, s.jwt_secret, algorithms=[s.jwt_algorithm],
                             options={"require": ["sub", "exp", "iat"]})
        if payload.get("typ") != "access":
            return None
        return int(payload["sub"]), int(payload.get("tv", 0))
    except (jwt.PyJWTError, KeyError, ValueError, TypeError):
        return None


# ---------- signed media URLs ----------
def _media_sig(path: str, exp: int) -> str:
    key = hashlib.sha256(("media:" + get_settings().jwt_secret).encode()).digest()
    return hmac.new(key, f"{path}:{exp}".encode(), hashlib.sha256).hexdigest()[:32]


def sign_media(path: str) -> str:
    ttl = get_settings().media_url_ttl_seconds
    # round the expiry so URLs stay stable for a while and images can be cached
    exp = (int(time.time()) // 3600 + 1) * 3600 + ttl
    return f"exp={exp}&sig={_media_sig(path, exp)}"


def check_media_sig(path: str, exp: int, sig: str) -> bool:
    return exp >= time.time() and hmac.compare_digest(_media_sig(path, exp), sig)
