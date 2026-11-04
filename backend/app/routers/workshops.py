from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user
from ..models import Review, Role, User, Workshop
from ..schemas import ReviewOut, WorkshopIn, WorkshopOut
from ..services import geo

router = APIRouter(prefix="/workshops", tags=["workshops"])


@router.put("/me", response_model=WorkshopOut)
def upsert_my_workshop(data: WorkshopIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if user.role != Role.workshop:
        raise HTTPException(403, "Only workshop accounts can have a workshop profile")
    w = db.query(Workshop).filter(Workshop.owner_id == user.id).one_or_none()
    fields = data.model_dump()
    fields["country_code"] = (fields.get("country_code") or user.country_code or "").upper() or None
    if w is None:
        w = Workshop(owner_id=user.id, **fields)
        db.add(w)
    else:
        for k, v in fields.items():
            setattr(w, k, v)
    db.commit()
    return w


@router.get("/me", response_model=WorkshopOut)
def get_my_workshop(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    w = db.query(Workshop).filter(Workshop.owner_id == user.id).one_or_none()
    if w is None:
        raise HTTPException(404, "No workshop profile yet")
    return w


@router.get("/nearby", response_model=list[WorkshopOut])
def nearby(lat: float = Query(ge=-90, le=90), lng: float = Query(ge=-180, le=180),
           radius_km: float = Query(25, gt=0, le=200), db: Session = Depends(get_db)):
    lat1, lat2, lng1, lng2 = geo.bounding_box(lat, lng, radius_km)
    out = []
    for w in db.query(Workshop).filter(Workshop.lat.between(lat1, lat2), Workshop.lng.between(lng1, lng2)):
        d = geo.haversine_km(lat, lng, w.lat, w.lng)
        if d <= radius_km:
            o = WorkshopOut.model_validate(w)
            o.distance_km = round(d, 1)
            # Public listing: hide exact pin, keep the city-level area.
            o.lat, o.lng = geo.fuzz(w.lat, w.lng)
            out.append(o)
    return sorted(out, key=lambda o: (-o.rating_avg, o.distance_km))[:50]


@router.get("/{workshop_id}", response_model=WorkshopOut)
def get_workshop(workshop_id: int, db: Session = Depends(get_db)):
    w = db.get(Workshop, workshop_id)
    if w is None:
        raise HTTPException(404, "Workshop not found")
    o = WorkshopOut.model_validate(w)
    o.lat, o.lng = geo.fuzz(w.lat, w.lng)
    return o


@router.get("/{workshop_id}/reviews", response_model=list[ReviewOut])
def reviews(workshop_id: int, db: Session = Depends(get_db)):
    return (db.query(Review).filter(Review.workshop_id == workshop_id)
            .order_by(Review.created_at.desc()).limit(50).all())
