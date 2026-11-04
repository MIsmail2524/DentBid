from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, require_workshop
from ..models import Review, Role, User, VerificationStatus, Workshop, WorkshopDocument
from ..schemas import DocumentOut, ReviewOut, WorkshopIn, WorkshopOut
from ..serializers import aware
from ..services import geo
from ..services.realtime import notify_users
from ..services.storage import private_root, resolve_inside, save_private

router = APIRouter(prefix="/workshops", tags=["workshops"])

DOC_KINDS = {"shop_front", "trade_license", "owner_id", "other"}
MAX_DOCS = 10
APPROVED = VerificationStatus.approved


def document_out(d: WorkshopDocument) -> DocumentOut:
    # served by an authorised endpoint; the app fetches it with the bearer token
    return DocumentOut(id=d.id, kind=d.kind, url=f"/api/workshops/documents/{d.id}/file",
                       created_at=aware(d.created_at))


def _admins(db: Session) -> list[User]:
    return db.query(User).filter(User.role == Role.admin, User.is_active.is_(True)).all()


@router.put("/me", response_model=WorkshopOut)
def upsert_my_workshop(data: WorkshopIn, background: BackgroundTasks,
                       user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != Role.workshop:
        raise HTTPException(403, "Only workshop accounts can have a workshop profile")
    w = db.query(Workshop).filter(Workshop.owner_id == user.id).one_or_none()
    fields = data.model_dump()
    fields["country_code"] = (fields.get("country_code") or user.country_code or "").upper() or None
    resubmitted = False
    if w is None:
        w = Workshop(owner_id=user.id, **fields)
        w.set_status(VerificationStatus.pending)
        db.add(w)
        resubmitted = True
    else:
        moved = geo.haversine_km(w.lat, w.lng, data.lat, data.lng) > 1.0
        renamed = w.name.strip().lower() != data.name.strip().lower()
        for k, v in fields.items():
            setattr(w, k, v)
        # Identity changes on an approved shop, or any edit after rejection, need a new review.
        if (w.verification_status == APPROVED and (moved or renamed)) or \
                w.verification_status == VerificationStatus.rejected:
            w.set_status(VerificationStatus.pending)
            w.rejection_reason = None
            resubmitted = True
    db.commit()
    if resubmitted:
        background.add_task(notify_users, _admins(db), {"type": "admin.workshop_pending", "workshop_id": w.id},
                            "Workshop waiting for verification", w.name)
    return w


@router.get("/me", response_model=WorkshopOut)
def get_my_workshop(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    w = db.query(Workshop).filter(Workshop.owner_id == user.id).one_or_none()
    if w is None:
        raise HTTPException(404, "No workshop profile yet")
    return w


@router.get("/me/documents", response_model=list[DocumentOut])
def my_documents(ws: Workshop = Depends(require_workshop)):
    return [document_out(d) for d in ws.documents]


@router.post("/me/documents", response_model=DocumentOut, status_code=201)
def upload_document(file: UploadFile = File(...), kind: str = Form("other"),
                    ws: Workshop = Depends(require_workshop), db: Session = Depends(get_db)):
    if kind not in DOC_KINDS:
        raise HTTPException(422, f"kind must be one of {sorted(DOC_KINDS)}")
    if len(ws.documents) >= MAX_DOCS:
        raise HTTPException(409, f"At most {MAX_DOCS} documents")
    rel = save_private(file, f"workshops/{ws.id}")
    d = WorkshopDocument(workshop_id=ws.id, kind=kind, path=rel)
    db.add(d)
    db.commit()
    return document_out(d)


@router.delete("/me/documents/{doc_id}", status_code=204)
def delete_document(doc_id: int, ws: Workshop = Depends(require_workshop), db: Session = Depends(get_db)):
    d = db.get(WorkshopDocument, doc_id)
    if d is None or d.workshop_id != ws.id:
        raise HTTPException(404, "Document not found")
    if ws.verification_status == APPROVED:
        raise HTTPException(409, "Documents of a verified workshop cannot be deleted")
    p = resolve_inside(private_root(), d.path)
    db.delete(d)
    db.commit()
    if p and p.exists():
        p.unlink()


@router.get("/documents/{doc_id}/file")
def document_file(doc_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Only the workshop owner and admins can open verification documents."""
    d = db.get(WorkshopDocument, doc_id)
    if d is None or (user.role != Role.admin and d.workshop.owner_id != user.id):
        raise HTTPException(404, "Document not found")
    p = resolve_inside(private_root(), d.path)
    if p is None or not p.is_file():
        raise HTTPException(404, "Document not found")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "private, no-store"})


@router.get("/nearby", response_model=list[WorkshopOut])
def nearby(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180),
           radius_km: float = Query(25, gt=0, le=200), db: Session = Depends(get_db)):
    lat1, lat2, lng1, lng2 = geo.bounding_box(lat, lng, radius_km)
    out = []
    q = db.query(Workshop).filter(Workshop.verification_status == APPROVED,
                                  Workshop.lat.between(lat1, lat2), Workshop.lng.between(lng1, lng2))
    for w in q.limit(1000):
        d = geo.haversine_km(lat, lng, w.lat, w.lng)
        if d <= radius_km:
            o = WorkshopOut.model_validate(w)
            o.distance_km = round(d, 1)
            # public listing: hide exact pin, phone and review notes
            o.lat, o.lng = geo.fuzz(w.lat, w.lng)
            o.phone = o.address = o.rejection_reason = None
            out.append(o)
    return sorted(out, key=lambda o: (-o.rating_avg, o.distance_km))[:50]


@router.get("/{workshop_id}", response_model=WorkshopOut)
def get_workshop(workshop_id: int, db: Session = Depends(get_db)):
    w = db.get(Workshop, workshop_id)
    if w is None or w.verification_status != APPROVED:
        raise HTTPException(404, "Workshop not found")
    o = WorkshopOut.model_validate(w)
    o.lat, o.lng = geo.fuzz(w.lat, w.lng)
    o.phone = o.address = o.rejection_reason = None
    return o


@router.get("/{workshop_id}/reviews", response_model=list[ReviewOut])
def reviews(workshop_id: int, db: Session = Depends(get_db)):
    return (db.query(Review).filter(Review.workshop_id == workshop_id)
            .order_by(Review.created_at.desc()).limit(50).all())
