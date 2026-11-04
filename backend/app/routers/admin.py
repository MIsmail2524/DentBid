"""Admin panel API: workshop verification, user management, audit log."""

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_admin
from ..models import (
    AuditLog, DamageRequest, Quote, QuoteStatus, RequestStatus, Role, User, VerificationStatus, Workshop,
)
from ..schemas import AdminUserOut, AdminWorkshopOut, AuditOut, ReasonIn
from ..serializers import aware
from ..services.analysis import analyzer_status
from ..services.realtime import notify_users
from .workshops import document_out

router = APIRouter(prefix="/admin", tags=["admin"])


def _audit(db: Session, admin: User, action: str, target_type: str, target_id: int, **details) -> None:
    db.add(AuditLog(actor_id=admin.id, action=action, target_type=target_type, target_id=target_id,
                    details=details or None))


def _like(q: str) -> str:
    # escape LIKE wildcards so a search for "%" does not match everything
    return "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def admin_workshop_out(w: Workshop, with_docs: bool = False) -> AdminWorkshopOut:
    base = AdminWorkshopOut.model_validate({
        **{c: getattr(w, c) for c in (
            "id", "name", "phone", "address", "city", "country_code", "lat", "lng", "service_radius_km",
            "services", "about", "verified", "rating_avg", "rating_count", "jobs_completed",
            "rejection_reason", "owner_id")},
        "verification_status": w.verification_status.value,
        "owner_name": w.owner.name, "owner_email": w.owner.email, "owner_phone": w.owner.phone,
        "owner_active": w.owner.is_active, "document_count": len(w.documents),
        "created_at": aware(w.created_at), "verified_at": aware(w.verified_at) if w.verified_at else None,
    })
    if with_docs:
        base.documents = [document_out(d) for d in w.documents]
    return base


def _get_workshop(db: Session, workshop_id: int) -> Workshop:
    w = db.get(Workshop, workshop_id)
    if w is None:
        raise HTTPException(404, "Workshop not found")
    return w


@router.get("/stats")
def stats(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    def count_by(col):
        return {(k.value if hasattr(k, "value") else k): v for k, v in db.query(col, func.count()).group_by(col).all()}
    accepted = db.query(func.count(Quote.id), func.coalesce(func.sum(Quote.amount), 0)).filter(
        Quote.status == QuoteStatus.accepted).one()
    return {
        "users": count_by(User.role),
        "workshops": count_by(Workshop.verification_status),
        "requests": count_by(DamageRequest.status),
        "quotes_total": db.query(func.count(Quote.id)).scalar(),
        "jobs_booked": accepted[0],
        "open_requests": db.query(func.count(DamageRequest.id)).filter(
            DamageRequest.status == RequestStatus.open).scalar(),
        "analyzer": analyzer_status(),
    }


@router.get("/workshops", response_model=list[AdminWorkshopOut])
def list_workshops(status: VerificationStatus | None = None, q: str | None = Query(None, max_length=100),
                   _: User = Depends(require_admin), db: Session = Depends(get_db)):
    query = db.query(Workshop).join(User, User.id == Workshop.owner_id)
    if status:
        query = query.filter(Workshop.verification_status == status)
    if q:
        like = _like(q)
        query = query.filter(or_(Workshop.name.ilike(like, escape="\\"), Workshop.city.ilike(like, escape="\\"),
                                 User.email.ilike(like, escape="\\"), Workshop.phone.ilike(like, escape="\\")))
    # oldest pending first so nobody waits forever
    rows = query.order_by(Workshop.created_at.asc() if status == VerificationStatus.pending
                          else Workshop.created_at.desc()).limit(200).all()
    return [admin_workshop_out(w) for w in rows]


@router.get("/workshops/{workshop_id}", response_model=AdminWorkshopOut)
def get_workshop(workshop_id: int, _: User = Depends(require_admin), db: Session = Depends(get_db)):
    return admin_workshop_out(_get_workshop(db, workshop_id), with_docs=True)


def _set_status(db: Session, admin: User, w: Workshop, status: VerificationStatus, reason: str | None,
                background: BackgroundTasks, title: str, body: str) -> AdminWorkshopOut:
    old = w.verification_status.value
    w.set_status(status)
    w.rejection_reason = reason
    if status == VerificationStatus.approved:
        w.verified_at, w.verified_by = datetime.now(timezone.utc), admin.id
    _audit(db, admin, f"workshop.{status.value}", "workshop", w.id, previous=old, reason=reason)
    db.commit()
    background.add_task(notify_users, [w.owner], {"type": "workshop.verification", "status": status.value}, title, body)
    return admin_workshop_out(w, with_docs=True)


@router.post("/workshops/{workshop_id}/approve", response_model=AdminWorkshopOut)
def approve(workshop_id: int, background: BackgroundTasks, admin: User = Depends(require_admin),
            db: Session = Depends(get_db)):
    w = _get_workshop(db, workshop_id)
    if not w.owner.is_active:
        raise HTTPException(409, "Owner account is disabled")
    return _set_status(db, admin, w, VerificationStatus.approved, None, background,
                       "Your workshop is verified", "You can now see nearby jobs and send quotes.")


@router.post("/workshops/{workshop_id}/reject", response_model=AdminWorkshopOut)
def reject(workshop_id: int, data: ReasonIn, background: BackgroundTasks, admin: User = Depends(require_admin),
           db: Session = Depends(get_db)):
    w = _get_workshop(db, workshop_id)
    return _set_status(db, admin, w, VerificationStatus.rejected, data.reason, background,
                       "Workshop verification needs changes", data.reason)


@router.post("/workshops/{workshop_id}/suspend", response_model=AdminWorkshopOut)
def suspend(workshop_id: int, data: ReasonIn, background: BackgroundTasks, admin: User = Depends(require_admin),
            db: Session = Depends(get_db)):
    w = _get_workshop(db, workshop_id)
    # open quotes from a suspended shop are withdrawn so customers cannot book it
    for q in db.query(Quote).filter(Quote.workshop_id == w.id,
                                    Quote.status.in_([QuoteStatus.pending, QuoteStatus.countered])):
        q.status = QuoteStatus.withdrawn
    return _set_status(db, admin, w, VerificationStatus.suspended, data.reason, background,
                       "Workshop suspended", data.reason)


@router.get("/users", response_model=list[AdminUserOut])
def list_users(role: Role | None = None, q: str | None = Query(None, max_length=100),
               _: User = Depends(require_admin), db: Session = Depends(get_db)):
    query = db.query(User)
    if role:
        query = query.filter(User.role == role)
    if q:
        like = _like(q)
        query = query.filter(or_(User.name.ilike(like, escape="\\"), User.email.ilike(like, escape="\\"),
                                 User.phone.ilike(like, escape="\\")))
    return query.order_by(User.created_at.desc()).limit(200).all()


@router.post("/users/{user_id}/deactivate", response_model=AdminUserOut)
def deactivate(user_id: int, data: ReasonIn, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found")
    if u.id == admin.id:
        raise HTTPException(409, "You cannot deactivate yourself")
    u.is_active = False
    u.token_version += 1  # revoke all sessions immediately
    _audit(db, admin, "user.deactivate", "user", u.id, reason=data.reason)
    db.commit()
    return u


@router.post("/users/{user_id}/activate", response_model=AdminUserOut)
def activate(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if u is None:
        raise HTTPException(404, "User not found")
    u.is_active = True
    _audit(db, admin, "user.activate", "user", u.id)
    db.commit()
    return u


@router.get("/audit", response_model=list[AuditOut])
def audit(_: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(AuditLog).order_by(AuditLog.id.desc()).limit(200).all()
