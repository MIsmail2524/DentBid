from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import get_db
from ..deps import get_current_user, require_customer, require_verified_workshop, require_workshop
from ..models import DamagePhoto, DamageRequest, QuoteStatus, RequestStatus, Review, Role, User, VerificationStatus, Workshop
from ..schemas import CounterIn, RequestCard, RequestOut, ReviewIn, ReviewOut, StatusIn
from ..serializers import refresh_expiry, request_card, request_out
from ..services import geo
from ..services.analysis import matching_workshops, run_analysis
from ..services.locale import locale_for
from ..services.realtime import notify_users
from ..services.storage import save_photo

router = APIRouter(prefix="/requests", tags=["requests"])

OPEN_FEED = (RequestStatus.open,)


def _get(db: Session, request_id: int) -> DamageRequest:
    req = db.get(DamageRequest, request_id)
    if req is None:
        raise HTTPException(404, "Request not found")
    if refresh_expiry(req):
        db.commit()
    return req


def _workshop_of(db: Session, user: User) -> Workshop | None:
    if user.role != Role.workshop:
        return None
    return db.query(Workshop).filter(Workshop.owner_id == user.id).one_or_none()


def _can_view(req: DamageRequest, user: User, ws: Workshop | None) -> bool:
    if user.role == Role.admin or req.customer_id == user.id:
        return True
    if ws is None:
        return False
    if any(q.workshop_id == ws.id for q in req.quotes):
        return True
    if ws.verification_status != VerificationStatus.approved:
        return False
    d = geo.haversine_km(ws.lat, ws.lng, req.lat, req.lng)
    return req.status == RequestStatus.open and d <= min(req.search_radius_km, ws.service_radius_km)


@router.post("", response_model=RequestOut, status_code=201)
def create_request(
    background: BackgroundTasks,
    photos: list[UploadFile] = File(...),
    lat: float = Form(..., ge=-90, le=90),
    lng: float = Form(..., ge=-180, le=180),
    city: str | None = Form(None, max_length=80),
    country_code: str | None = Form(None, pattern="^[A-Za-z]{2}$"),
    car_make: str | None = Form(None, max_length=60),
    car_model: str | None = Form(None, max_length=60),
    car_year: int | None = Form(None, ge=1950, le=2100),
    car_color: str | None = Form(None, max_length=40),
    description: str | None = Form(None, max_length=2000),
    customer_offer: Decimal | None = Form(None, gt=0, max_digits=12, decimal_places=2),
    search_radius_km: float | None = Form(None, gt=0, le=200),
    user: User = Depends(require_customer),
    db: Session = Depends(get_db),
):
    s = get_settings()
    if not photos:
        raise HTTPException(422, "Add at least one photo")
    if len(photos) > s.max_photos_per_request:
        raise HTTPException(422, f"At most {s.max_photos_per_request} photos")

    cc = (country_code or user.country_code or "").upper() or None
    currency = user.currency if user.country_code == cc and user.currency else locale_for(cc).currency
    now = datetime.now(timezone.utc)
    req = DamageRequest(
        customer_id=user.id, lat=lat, lng=lng, city=city, country_code=cc, currency=currency,
        car_make=car_make, car_model=car_model, car_year=car_year, car_color=car_color,
        description=description, customer_offer=customer_offer,
        search_radius_km=search_radius_km or s.default_search_radius_km,
        expires_at=now + timedelta(hours=s.request_ttl_hours),
    )
    db.add(req)
    db.flush()
    for up in photos:
        rel, w, h = save_photo(up, f"requests/{req.id}")
        req.photos.append(DamagePhoto(path=rel, width=w, height=h))
    db.commit()
    background.add_task(run_analysis, req.id)
    return request_out(req, user)


@router.get("/mine", response_model=list[RequestCard])
def my_requests(user: User = Depends(require_customer), db: Session = Depends(get_db)):
    reqs = (db.query(DamageRequest).filter(DamageRequest.customer_id == user.id)
            .order_by(DamageRequest.created_at.desc()).limit(100).all())
    if any([refresh_expiry(r) for r in reqs]):
        db.commit()
    return [request_card(r) for r in reqs]


@router.get("/feed", response_model=list[RequestCard])
def workshop_feed(
    ws: Workshop = Depends(require_verified_workshop),
    db: Session = Depends(get_db),
    severity: str | None = Query(None, pattern="^(minor|moderate|severe)$"),
    damage_type: str | None = None,
    sort: str = Query("distance", pattern="^(distance|newest|severity)$"),
):
    """Open requests in this workshop's service area."""
    now = datetime.now(timezone.utc)
    lat1, lat2, lng1, lng2 = geo.bounding_box(ws.lat, ws.lng, ws.service_radius_km)
    q = (db.query(DamageRequest)
         .filter(DamageRequest.status.in_(OPEN_FEED), DamageRequest.expires_at > now,
                 DamageRequest.lat.between(lat1, lat2), DamageRequest.lng.between(lng1, lng2)))
    if severity:
        q = q.filter(DamageRequest.overall_severity == severity)
    cards = []
    for r in q.limit(500):
        d = geo.haversine_km(ws.lat, ws.lng, r.lat, r.lng)
        if d > ws.service_radius_km or d > r.search_radius_km:
            continue
        types = (r.analysis or {}).get("damage_types") or []
        if damage_type and damage_type not in types:
            continue
        if ws.services and types and not set(types) & set(ws.services):
            continue
        cards.append(request_card(r, ws))
    key = {"distance": lambda c: c.distance_km or 0,
           "newest": lambda c: -c.created_at.timestamp(),
           "severity": lambda c: -(c.overall_score or 0)}[sort]
    return sorted(cards, key=key)[:100]


@router.get("/{request_id}", response_model=RequestOut)
def get_request(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = _get(db, request_id)
    ws = _workshop_of(db, user)
    if not _can_view(req, user, ws):
        raise HTTPException(404, "Request not found")
    return request_out(req, user, ws if req.customer_id != user.id else None)


@router.post("/{request_id}/cancel", response_model=RequestOut)
def cancel(request_id: int, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    req = _get(db, request_id)
    if req.customer_id != user.id:
        raise HTTPException(404, "Request not found")
    if req.status not in (RequestStatus.analyzing, RequestStatus.open, RequestStatus.booked):
        raise HTTPException(409, f"Cannot cancel a {req.status.value} request")
    req.status = RequestStatus.cancelled
    owners = []
    for q in req.quotes:
        if q.status in (QuoteStatus.pending, QuoteStatus.countered, QuoteStatus.accepted):
            q.status = QuoteStatus.rejected
            owners.append(q.workshop.owner)
    db.commit()
    notify_users(owners, {"type": "request.cancelled", "request_id": req.id})
    return request_out(req, user)


@router.patch("/{request_id}/offer", response_model=RequestOut)
def raise_offer(request_id: int, data: CounterIn, background: BackgroundTasks,
                user: User = Depends(require_customer), db: Session = Depends(get_db)):
    """inDrive-style: customer changes the price they are willing to pay."""
    req = _get(db, request_id)
    if req.customer_id != user.id:
        raise HTTPException(404, "Request not found")
    if req.status != RequestStatus.open:
        raise HTTPException(409, "Request is not open")
    req.customer_offer = data.amount
    db.commit()
    owners = [w.owner for w, _ in matching_workshops(db, req)]
    background.add_task(notify_users, owners, {"type": "request.offer", "request_id": req.id},
                        "Customer updated their offer", f"Now offering {data.amount} {req.currency}")
    return request_out(req, user)


@router.post("/{request_id}/reanalyze", response_model=RequestOut)
def reanalyze(request_id: int, background: BackgroundTasks,
              user: User = Depends(require_customer), db: Session = Depends(get_db)):
    req = _get(db, request_id)
    if req.customer_id != user.id:
        raise HTTPException(404, "Request not found")
    if req.status not in (RequestStatus.analyzing, RequestStatus.open):
        raise HTTPException(409, "Only open requests can be re-analysed")
    background.add_task(run_analysis, req.id)
    return request_out(req, user)


@router.post("/{request_id}/status", response_model=RequestOut)
def update_job_status(request_id: int, data: StatusIn, background: BackgroundTasks,
                      ws: Workshop = Depends(require_workshop), db: Session = Depends(get_db)):
    req = _get(db, request_id)
    accepted = next((q for q in req.quotes if q.id == req.accepted_quote_id), None)
    if accepted is None or accepted.workshop_id != ws.id:
        raise HTTPException(403, "Only the booked workshop can update this job")
    allowed = {"in_progress": (RequestStatus.booked,),
               "completed": (RequestStatus.booked, RequestStatus.in_progress)}[data.status]
    if req.status not in allowed:
        raise HTTPException(409, f"Cannot move from {req.status.value} to {data.status}")
    req.status = RequestStatus(data.status)
    if req.status == RequestStatus.completed:
        ws.jobs_completed += 1
    db.commit()
    msg = "Your car repair has started" if data.status == "in_progress" else "Your car is ready"
    background.add_task(notify_users, [req.customer], {"type": f"job.{data.status}", "request_id": req.id},
                        msg, ws.name)
    return request_out(req, ws.owner, ws)


@router.post("/{request_id}/review", response_model=ReviewOut, status_code=201)
def review(request_id: int, data: ReviewIn, user: User = Depends(require_customer), db: Session = Depends(get_db)):
    req = _get(db, request_id)
    if req.customer_id != user.id:
        raise HTTPException(404, "Request not found")
    if req.status != RequestStatus.completed:
        raise HTTPException(409, "You can review once the job is completed")
    if db.query(Review).filter(Review.request_id == req.id).first():
        raise HTTPException(409, "Already reviewed")
    accepted = next(q for q in req.quotes if q.id == req.accepted_quote_id)
    ws = accepted.workshop
    r = Review(request_id=req.id, workshop_id=ws.id, customer_id=user.id, rating=data.rating, comment=data.comment)
    db.add(r)
    ws.rating_avg = round((ws.rating_avg * ws.rating_count + data.rating) / (ws.rating_count + 1), 2)
    ws.rating_count += 1
    db.commit()
    return r
