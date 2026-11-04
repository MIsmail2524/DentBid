from __future__ import annotations

import enum
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Role(str, enum.Enum):
    customer = "customer"
    workshop = "workshop"
    admin = "admin"


class RequestStatus(str, enum.Enum):
    analyzing = "analyzing"     # photos uploaded, AI running
    open = "open"               # visible to workshops, collecting quotes
    booked = "booked"           # customer accepted a quote
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    expired = "expired"


class QuoteStatus(str, enum.Enum):
    pending = "pending"         # waiting for customer
    countered = "countered"     # customer proposed another price, waiting for workshop
    accepted = "accepted"
    rejected = "rejected"
    withdrawn = "withdrawn"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[Role] = mapped_column(Enum(Role, native_enum=False), default=Role.customer)
    name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(32))
    password_hash: Mapped[str] = mapped_column(String(255))
    country_code: Mapped[str | None] = mapped_column(String(2))
    currency: Mapped[str | None] = mapped_column(String(3))
    language: Mapped[str | None] = mapped_column(String(8))
    push_token: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    workshop: Mapped[Workshop | None] = relationship(back_populates="owner", uselist=False)


class Workshop(Base):
    __tablename__ = "workshops"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(32))
    address: Mapped[str | None] = mapped_column(String(255))
    city: Mapped[str | None] = mapped_column(String(80))
    country_code: Mapped[str | None] = mapped_column(String(2))
    lat: Mapped[float] = mapped_column(Float, index=True)
    lng: Mapped[float] = mapped_column(Float, index=True)
    service_radius_km: Mapped[float] = mapped_column(Float, default=25.0)
    # damage types the workshop repairs, e.g. ["dent", "scratch", "glass_shatter"]
    services: Mapped[list] = mapped_column(JSON, default=list)
    about: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    rating_avg: Mapped[float] = mapped_column(Float, default=0.0)
    rating_count: Mapped[int] = mapped_column(Integer, default=0)
    jobs_completed: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User] = relationship(back_populates="workshop")


class DamageRequest(Base):
    __tablename__ = "damage_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus, native_enum=False), default=RequestStatus.analyzing, index=True)

    car_make: Mapped[str | None] = mapped_column(String(60))
    car_model: Mapped[str | None] = mapped_column(String(60))
    car_year: Mapped[int | None] = mapped_column(Integer)
    car_color: Mapped[str | None] = mapped_column(String(40))
    description: Mapped[str | None] = mapped_column(Text)

    lat: Mapped[float] = mapped_column(Float, index=True)
    lng: Mapped[float] = mapped_column(Float, index=True)
    city: Mapped[str | None] = mapped_column(String(80))
    country_code: Mapped[str | None] = mapped_column(String(2))
    currency: Mapped[str] = mapped_column(String(3), default="USD")
    # inDrive-style: customer can suggest the price they want to pay
    customer_offer: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    search_radius_km: Mapped[float] = mapped_column(Float, default=25.0)

    analysis: Mapped[dict | None] = mapped_column(JSON)
    overall_severity: Mapped[str | None] = mapped_column(String(16))
    overall_score: Mapped[float | None] = mapped_column(Float)

    accepted_quote_id: Mapped[int | None] = mapped_column(ForeignKey("quotes.id", use_alter=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    customer: Mapped[User] = relationship(foreign_keys=[customer_id])
    photos: Mapped[list[DamagePhoto]] = relationship(back_populates="request", cascade="all, delete-orphan",
                                                     order_by="DamagePhoto.id")
    quotes: Mapped[list[Quote]] = relationship(back_populates="request", foreign_keys="Quote.request_id",
                                               order_by="Quote.amount")


class DamagePhoto(Base):
    __tablename__ = "damage_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("damage_requests.id"), index=True)
    path: Mapped[str] = mapped_column(String(255))
    annotated_path: Mapped[str | None] = mapped_column(String(255))
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    analysis: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    request: Mapped[DamageRequest] = relationship(back_populates="photos")


class Quote(Base):
    __tablename__ = "quotes"
    __table_args__ = (UniqueConstraint("request_id", "workshop_id", name="uq_quote_request_workshop"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("damage_requests.id"), index=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), index=True)
    status: Mapped[QuoteStatus] = mapped_column(Enum(QuoteStatus, native_enum=False), default=QuoteStatus.pending)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    counter_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    eta_days: Mapped[int] = mapped_column(Integer, default=1)
    warranty_months: Mapped[int] = mapped_column(Integer, default=0)
    includes_parts: Mapped[bool] = mapped_column(Boolean, default=True)
    pickup_available: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text)
    # per-damage price breakdown: [{"damage": "Dent on hood", "amount": 4000}]
    breakdown: Mapped[list | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    request: Mapped[DamageRequest] = relationship(back_populates="quotes", foreign_keys=[request_id])
    workshop: Mapped[Workshop] = relationship()


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(primary_key=True)
    quote_id: Mapped[int] = mapped_column(ForeignKey("quotes.id"), index=True)
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Review(Base):
    __tablename__ = "reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[int] = mapped_column(ForeignKey("damage_requests.id"), unique=True)
    workshop_id: Mapped[int] = mapped_column(ForeignKey("workshops.id"), index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
