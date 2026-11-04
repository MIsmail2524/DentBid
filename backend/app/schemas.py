from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from .models import QuoteStatus, RequestStatus, Role

DamageType = Literal["dent", "scratch", "crack", "glass_shatter", "lamp_broken", "tire_flat"]


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------- auth / users ----------
class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    phone: str | None = Field(default=None, max_length=32)
    role: Literal["customer", "workshop"] = "customer"
    country_code: str | None = Field(default=None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$")
    language: str | None = Field(default=None, max_length=8)


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)


class UserOut(ORM):
    id: int
    role: Role
    name: str
    email: str
    phone: str | None
    country_code: str | None
    currency: str | None
    language: str | None
    has_workshop: bool = False
    workshop_status: str | None = None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=32)
    country_code: str | None = Field(default=None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$")
    currency: str | None = Field(default=None, min_length=3, max_length=3, pattern="^[A-Za-z]{3}$")
    language: str | None = Field(default=None, max_length=8)
    push_token: str | None = Field(default=None, max_length=255)


# ---------- workshops ----------
class WorkshopIn(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=32)
    address: str | None = Field(default=None, max_length=255)
    city: str | None = Field(default=None, max_length=80)
    country_code: str | None = Field(default=None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$")
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    service_radius_km: float = Field(default=25, gt=0, le=200)
    services: list[DamageType] = Field(default_factory=list)
    about: str | None = Field(default=None, max_length=2000)


class WorkshopOut(ORM):
    id: int
    name: str
    phone: str | None
    address: str | None
    city: str | None
    country_code: str | None
    lat: float
    lng: float
    service_radius_km: float
    services: list[str]
    about: str | None
    verified: bool
    verification_status: str
    rejection_reason: str | None
    rating_avg: float
    rating_count: int
    jobs_completed: int
    distance_km: float | None = None


class DocumentOut(BaseModel):
    id: int
    kind: str
    url: str
    created_at: datetime


class WorkshopPublic(ORM):
    """Shown to customers next to a quote (no exact location until booked)."""
    id: int
    name: str
    city: str | None
    verified: bool
    rating_avg: float
    rating_count: int
    jobs_completed: int
    distance_km: float | None = None
    phone: str | None = None
    address: str | None = None
    lat: float | None = None
    lng: float | None = None


# ---------- requests ----------
class PhotoOut(BaseModel):
    id: int
    url: str
    annotated_url: str | None
    width: int | None
    height: int | None
    analysis: dict | None


class RequestOut(BaseModel):
    id: int
    status: RequestStatus
    car_make: str | None
    car_model: str | None
    car_year: int | None
    car_color: str | None
    description: str | None
    city: str | None
    country_code: str | None
    currency: str
    customer_offer: Decimal | None
    search_radius_km: float
    lat: float
    lng: float
    analysis: dict | None
    overall_severity: str | None
    overall_score: float | None
    photos: list[PhotoOut]
    quote_count: int
    lowest_quote: Decimal | None
    accepted_quote_id: int | None
    created_at: datetime
    expires_at: datetime
    distance_km: float | None = None
    my_quote: QuoteOut | None = None
    customer_name: str | None = None
    customer_phone: str | None = None


class RequestCard(BaseModel):
    """Compact row for lists and the workshop feed."""
    id: int
    status: RequestStatus
    title: str
    thumbnail_url: str | None
    city: str | None
    currency: str
    customer_offer: Decimal | None
    overall_severity: str | None
    overall_score: float | None
    damage_types: list[str]
    quote_count: int
    lowest_quote: Decimal | None
    created_at: datetime
    expires_at: datetime
    distance_km: float | None = None
    my_quote_status: QuoteStatus | None = None


# ---------- quotes ----------
class BreakdownItem(BaseModel):
    item: str = Field(max_length=120)
    amount: Decimal = Field(ge=0)


class QuoteIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    eta_days: int = Field(default=1, ge=0, le=90)
    warranty_months: int = Field(default=0, ge=0, le=60)
    includes_parts: bool = True
    pickup_available: bool = False
    notes: str | None = Field(default=None, max_length=1000)
    breakdown: list[BreakdownItem] | None = None


class CounterIn(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)


class QuoteOut(ORM):
    id: int
    request_id: int
    status: QuoteStatus
    amount: Decimal
    currency: str
    counter_amount: Decimal | None
    eta_days: int
    warranty_months: int
    includes_parts: bool
    pickup_available: bool
    notes: str | None
    breakdown: list | None
    created_at: datetime
    updated_at: datetime
    workshop: WorkshopPublic | None = None


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class MessageOut(ORM):
    id: int
    quote_id: int
    sender_id: int
    body: str
    created_at: datetime


class ReviewIn(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ReviewOut(ORM):
    id: int
    workshop_id: int
    rating: int
    comment: str | None
    created_at: datetime


class ReasonIn(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AdminWorkshopOut(WorkshopOut):
    owner_id: int
    owner_name: str
    owner_email: str
    owner_phone: str | None
    owner_active: bool
    document_count: int
    created_at: datetime
    verified_at: datetime | None
    documents: list[DocumentOut] = []


class AdminUserOut(ORM):
    id: int
    role: Role
    name: str
    email: str
    phone: str | None
    country_code: str | None
    is_active: bool
    created_at: datetime


class AuditOut(ORM):
    id: int
    actor_id: int
    action: str
    target_type: str
    target_id: int
    details: dict | None
    created_at: datetime


class StatusIn(BaseModel):
    status: Literal["in_progress", "completed"]


RequestOut.model_rebuild()
