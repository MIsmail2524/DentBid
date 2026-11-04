from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from .db import get_db
from .models import Role, User, Workshop
from .security import decode_token

bearer = HTTPBearer(auto_error=False)


def get_current_user(creds: HTTPAuthorizationCredentials | None = Depends(bearer),
                     db: Session = Depends(get_db)) -> User:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    uid = decode_token(creds.credentials)
    user = db.get(User, uid) if uid else None
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return user


def require_customer(user: User = Depends(get_current_user)) -> User:
    if user.role not in (Role.customer, Role.admin):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Customers only")
    return user


def require_workshop(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Workshop:
    if user.role != Role.workshop:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Workshops only")
    ws = db.query(Workshop).filter(Workshop.owner_id == user.id).one_or_none()
    if ws is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Create your workshop profile first")
    return ws
