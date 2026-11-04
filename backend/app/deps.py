from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import Role, User, VerificationStatus, Workshop
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def user_from_token(db: Session, token: str) -> User | None:
    decoded = decode_token(token)
    if decoded is None:
        return None
    uid, tv = decoded
    user = db.get(User, uid)
    if user is None or not user.is_active or user.token_version != tv:
        return None
    return user


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    user = user_from_token(db, creds.credentials)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


def require_customer(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.customer:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customers only")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != Role.admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admins only")
    return user


def require_workshop(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Workshop:
    """Any workshop profile, verified or not (profile and document management)."""
    if user.role != Role.workshop:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Workshops only")
    ws = db.query(Workshop).filter(Workshop.owner_id == user.id).one_or_none()
    if ws is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Create your workshop profile first")
    return ws


def require_verified_workshop(ws: Workshop = Depends(require_workshop)) -> Workshop:
    """Seeing jobs and quoting needs admin approval."""
    if ws.verification_status != VerificationStatus.approved:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"workshop_not_verified:{ws.verification_status.value}")
    return ws
