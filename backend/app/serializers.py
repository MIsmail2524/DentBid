"""Builds API responses from ORM objects, applying visibility rules."""

from __future__ import annotations

from datetime import datetime, timezone

from .models import DamageRequest, Quote, QuoteStatus, RequestStatus, User, Workshop
from .schemas import PhotoOut, QuoteOut, RequestCard, RequestOut, WorkshopPublic
from .services import geo
from .services.storage import media_url

ACTIVE_QUOTES = (QuoteStatus.pending, QuoteStatus.countered, QuoteStatus.accepted)


def aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def refresh_expiry(req: DamageRequest) -> bool:
    """Marks an open request as expired once its TTL passes. Returns True if changed."""
    if req.status in (RequestStatus.open, RequestStatus.analyzing) and aware(req.expires_at) < datetime.now(timezone.utc):
        req.status = RequestStatus.expired
        return True
    return False


def _active(req: DamageRequest) -> list[Quote]:
    return [q for q in req.quotes if q.status in ACTIVE_QUOTES]


def title_of(req: DamageRequest) -> str:
    car = " ".join(str(x) for x in (req.car_year, req.car_make, req.car_model) if x)
    return car or "Car repair request"


def workshop_public(w: Workshop, lat: float | None = None, lng: float | None = None,
                    reveal_contact: bool = False) -> WorkshopPublic:
    out = WorkshopPublic.model_validate(w)
    if lat is not None and lng is not None:
        out.distance_km = round(geo.haversine_km(lat, lng, w.lat, w.lng), 1)
    if reveal_contact:
        out.phone = w.phone or (w.owner.phone if w.owner else None)
    else:
        out.phone = out.address = out.lat = out.lng = None
    return out


def quote_out(q: Quote, req: DamageRequest) -> QuoteOut:
    out = QuoteOut.model_validate(q)
    booked = req.accepted_quote_id == q.id
    out.workshop = workshop_public(q.workshop, req.lat, req.lng, reveal_contact=booked)
    return out


def photos_out(req: DamageRequest) -> list[PhotoOut]:
    return [PhotoOut(id=p.id, url=media_url(p.path), annotated_url=media_url(p.annotated_path),
                     width=p.width, height=p.height, analysis=p.analysis) for p in req.photos]


def request_out(req: DamageRequest, viewer: User, workshop: Workshop | None = None) -> RequestOut:
    active = _active(req)
    lowest = min((q.amount for q in active), default=None)
    lat, lng = req.lat, req.lng
    my_quote = None
    customer_name = customer_phone = None
    distance = None

    if workshop is not None:
        mine = next((q for q in req.quotes if q.workshop_id == workshop.id), None)
        booked_with_me = mine is not None and req.accepted_quote_id == mine.id
        if mine is not None:
            my_quote = quote_out(mine, req)
        distance = round(geo.haversine_km(workshop.lat, workshop.lng, req.lat, req.lng), 1)
        if booked_with_me:
            customer_name, customer_phone = req.customer.name, req.customer.phone
        else:
            lat, lng = geo.fuzz(req.lat, req.lng)
            customer_name = req.customer.name.split(" ")[0]

    return RequestOut(
        id=req.id, status=req.status,
        car_make=req.car_make, car_model=req.car_model, car_year=req.car_year, car_color=req.car_color,
        description=req.description, city=req.city, country_code=req.country_code, currency=req.currency,
        customer_offer=req.customer_offer, search_radius_km=req.search_radius_km, lat=lat, lng=lng,
        analysis=req.analysis, overall_severity=req.overall_severity, overall_score=req.overall_score,
        photos=photos_out(req), quote_count=len(active), lowest_quote=lowest,
        accepted_quote_id=req.accepted_quote_id, created_at=aware(req.created_at),
        expires_at=aware(req.expires_at), distance_km=distance, my_quote=my_quote,
        customer_name=customer_name, customer_phone=customer_phone,
    )


def request_card(req: DamageRequest, workshop: Workshop | None = None) -> RequestCard:
    active = _active(req)
    first = req.photos[0] if req.photos else None
    thumb = media_url(first.annotated_path or first.path) if first else None
    mine = None
    distance = None
    if workshop is not None:
        q = next((q for q in req.quotes if q.workshop_id == workshop.id), None)
        mine = q.status if q else None
        distance = round(geo.haversine_km(workshop.lat, workshop.lng, req.lat, req.lng), 1)
    return RequestCard(
        id=req.id, status=req.status, title=title_of(req), thumbnail_url=thumb, city=req.city,
        currency=req.currency, customer_offer=req.customer_offer, overall_severity=req.overall_severity,
        overall_score=req.overall_score, damage_types=(req.analysis or {}).get("damage_types", []),
        quote_count=len(active), lowest_quote=min((q.amount for q in active), default=None),
        created_at=aware(req.created_at), expires_at=aware(req.expires_at),
        distance_km=distance, my_quote_status=mine,
    )
