"""Bidding: workshops quote, customers counter / accept (inDrive style)."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_user, require_customer, require_workshop
from ..models import DamageRequest, Message, Quote, QuoteStatus, RequestStatus, Role, User, Workshop
from ..schemas import CounterIn, MessageIn, MessageOut, QuoteIn, QuoteOut, RequestCard
from ..serializers import quote_out, refresh_expiry, request_card
from ..services import geo
from ..services.realtime import notify_users

router = APIRouter(tags=["quotes"])


def _request(db: Session, request_id: int) -> DamageRequest:
    req = db.get(DamageRequest, request_id)
    if req is None:
        raise HTTPException(404, "Request not found")
    if refresh_expiry(req):
        db.commit()
    return req


def _quote(db: Session, quote_id: int) -> Quote:
    q = db.get(Quote, quote_id)
    if q is None:
        raise HTTPException(404, "Quote not found")
    if refresh_expiry(q.request):
        db.commit()
    return q


def _book(db: Session, req: DamageRequest, winner: Quote) -> list[User]:
    """Accepts one quote, rejects the rest. Returns workshop owners to notify of rejection."""
    # Lock the row so two workshops accepting counters at once cannot both win.
    db.refresh(req, with_for_update=True)
    if req.status != RequestStatus.open:
        raise HTTPException(409, "This request is no longer open")
    req.status = RequestStatus.booked
    req.accepted_quote_id = winner.id
    winner.status = QuoteStatus.accepted
    losers = []
    for q in req.quotes:
        if q.id != winner.id and q.status in (QuoteStatus.pending, QuoteStatus.countered):
            q.status = QuoteStatus.rejected
            losers.append(q.workshop.owner)
    return losers


@router.post("/requests/{request_id}/quotes", response_model=QuoteOut, status_code=201)
def submit_quote(request_id: int, data: QuoteIn, background: BackgroundTasks,
                 ws: Workshop = Depends(require_workshop), db: Session = Depends(get_db)):
    """Create or revise this workshop's quote for a request."""
    req = _request(db, request_id)
    if req.status != RequestStatus.open:
        raise HTTPException(409, "This request is not accepting quotes")
    d = geo.haversine_km(ws.lat, ws.lng, req.lat, req.lng)
    if d > max(req.search_radius_km, ws.service_radius_km):
        raise HTTPException(403, "Request is outside your service area")

    q = db.query(Quote).filter(Quote.request_id == req.id, Quote.workshop_id == ws.id).one_or_none()
    fields = data.model_dump()
    if fields.get("breakdown") is not None:
        fields["breakdown"] = [{"item": b["item"], "amount": float(b["amount"])} for b in fields["breakdown"]]
    revised = q is not None
    if q is None:
        q = Quote(request_id=req.id, workshop_id=ws.id, currency=req.currency, **fields)
        db.add(q)
    else:
        if q.status == QuoteStatus.accepted:
            raise HTTPException(409, "Quote already accepted")
        for k, v in fields.items():
            setattr(q, k, v)
        q.status = QuoteStatus.pending
        q.counter_amount = None
    db.commit()
    db.refresh(q)
    title = "Updated quote" if revised else "New quote"
    background.add_task(notify_users, [req.customer], {"type": "quote.new", "request_id": req.id, "quote_id": q.id},
                        f"{title} from {ws.name}", f"{q.amount} {q.currency}, ready in {q.eta_days} day(s)")
    return quote_out(q, req)


@router.get("/requests/{request_id}/quotes", response_model=list[QuoteOut])
def list_quotes(request_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    req = _request(db, request_id)
    if req.customer_id == user.id or user.role == Role.admin:
        qs = [q for q in req.quotes if q.status != QuoteStatus.withdrawn]
    elif user.role == Role.workshop and user.workshop is not None:
        qs = [q for q in req.quotes if q.workshop_id == user.workshop.id]
    else:
        raise HTTPException(404, "Request not found")
    return [quote_out(q, req) for q in qs]


@router.get("/quotes/mine", response_model=list[RequestCard])
def my_quoted_requests(ws: Workshop = Depends(require_workshop), db: Session = Depends(get_db)):
    """Requests this workshop has quoted on, newest first (jobs tab)."""
    reqs = (db.query(DamageRequest).join(Quote, Quote.request_id == DamageRequest.id)
            .filter(Quote.workshop_id == ws.id).order_by(Quote.updated_at.desc()).limit(200).all())
    changed = [refresh_expiry(r) for r in reqs]
    if any(changed):
        db.commit()
    return [request_card(r, ws) for r in reqs]


@router.post("/quotes/{quote_id}/accept", response_model=QuoteOut)
def accept_quote(quote_id: int, background: BackgroundTasks,
                 user: User = Depends(require_customer), db: Session = Depends(get_db)):
    q = _quote(db, quote_id)
    req = q.request
    if req.customer_id != user.id:
        raise HTTPException(404, "Quote not found")
    if q.status not in (QuoteStatus.pending, QuoteStatus.countered):
        raise HTTPException(409, f"Quote is {q.status.value}")
    if q.status == QuoteStatus.countered:
        # customer drops their counter and takes the workshop's price
        q.counter_amount = None
    losers = _book(db, req, q)
    db.commit()
    background.add_task(notify_users, [q.workshop.owner],
                        {"type": "quote.accepted", "request_id": req.id, "quote_id": q.id},
                        "Your quote was accepted!", f"{q.amount} {q.currency}. Contact the customer to schedule.")
    background.add_task(notify_users, losers, {"type": "quote.rejected", "request_id": req.id})
    return quote_out(q, req)


@router.post("/quotes/{quote_id}/counter", response_model=QuoteOut)
def counter_quote(quote_id: int, data: CounterIn, background: BackgroundTasks,
                  user: User = Depends(require_customer), db: Session = Depends(get_db)):
    q = _quote(db, quote_id)
    req = q.request
    if req.customer_id != user.id:
        raise HTTPException(404, "Quote not found")
    if req.status != RequestStatus.open or q.status not in (QuoteStatus.pending, QuoteStatus.countered):
        raise HTTPException(409, "Quote cannot be countered")
    if data.amount >= q.amount:
        raise HTTPException(422, "Counter offer must be lower than the quote")
    q.counter_amount = data.amount
    q.status = QuoteStatus.countered
    db.commit()
    background.add_task(notify_users, [q.workshop.owner],
                        {"type": "quote.countered", "request_id": req.id, "quote_id": q.id},
                        "Customer sent a counter offer", f"{data.amount} {q.currency} instead of {q.amount}")
    return quote_out(q, req)


@router.post("/quotes/{quote_id}/accept-counter", response_model=QuoteOut)
def accept_counter(quote_id: int, background: BackgroundTasks,
                   ws: Workshop = Depends(require_workshop), db: Session = Depends(get_db)):
    """Workshop agrees to the customer's price: the job is booked immediately."""
    q = _quote(db, quote_id)
    if q.workshop_id != ws.id:
        raise HTTPException(404, "Quote not found")
    if q.status != QuoteStatus.countered or q.counter_amount is None:
        raise HTTPException(409, "No counter offer to accept")
    req = q.request
    q.amount = q.counter_amount
    q.counter_amount = None
    losers = _book(db, req, q)
    db.commit()
    background.add_task(notify_users, [req.customer],
                        {"type": "quote.accepted", "request_id": req.id, "quote_id": q.id},
                        f"{ws.name} accepted your price", f"Booked for {q.amount} {q.currency}")
    background.add_task(notify_users, losers, {"type": "quote.rejected", "request_id": req.id})
    return quote_out(q, req)


@router.post("/quotes/{quote_id}/reject", response_model=QuoteOut)
def reject_quote(quote_id: int, background: BackgroundTasks,
                 user: User = Depends(require_customer), db: Session = Depends(get_db)):
    q = _quote(db, quote_id)
    if q.request.customer_id != user.id:
        raise HTTPException(404, "Quote not found")
    if q.status not in (QuoteStatus.pending, QuoteStatus.countered):
        raise HTTPException(409, f"Quote is {q.status.value}")
    q.status = QuoteStatus.rejected
    db.commit()
    background.add_task(notify_users, [q.workshop.owner],
                        {"type": "quote.rejected", "request_id": q.request_id, "quote_id": q.id})
    return quote_out(q, q.request)


@router.post("/quotes/{quote_id}/withdraw", response_model=QuoteOut)
def withdraw_quote(quote_id: int, ws: Workshop = Depends(require_workshop), db: Session = Depends(get_db)):
    q = _quote(db, quote_id)
    if q.workshop_id != ws.id:
        raise HTTPException(404, "Quote not found")
    if q.status not in (QuoteStatus.pending, QuoteStatus.countered):
        raise HTTPException(409, f"Quote is {q.status.value}")
    q.status = QuoteStatus.withdrawn
    db.commit()
    notify_users([q.request.customer], {"type": "quote.withdrawn", "request_id": q.request_id, "quote_id": q.id})
    return quote_out(q, q.request)


def _chat_party(q: Quote, user: User) -> User:
    """Returns the other participant, or raises if the user is not part of the chat."""
    if q.request.customer_id == user.id:
        return q.workshop.owner
    if q.workshop.owner_id == user.id:
        return q.request.customer
    raise HTTPException(404, "Quote not found")


@router.get("/quotes/{quote_id}/messages", response_model=list[MessageOut])
def list_messages(quote_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = _quote(db, quote_id)
    _chat_party(q, user)
    return db.query(Message).filter(Message.quote_id == q.id).order_by(Message.id).limit(500).all()


@router.post("/quotes/{quote_id}/messages", response_model=MessageOut, status_code=201)
def send_message(quote_id: int, data: MessageIn, background: BackgroundTasks,
                 user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    q = _quote(db, quote_id)
    other = _chat_party(q, user)
    if q.status in (QuoteStatus.withdrawn, QuoteStatus.rejected):
        raise HTTPException(409, "This conversation is closed")
    m = Message(quote_id=q.id, sender_id=user.id, body=data.body.strip())
    db.add(m)
    db.commit()
    event = {"type": "message.new", "quote_id": q.id, "request_id": q.request_id,
             "message": MessageOut.model_validate(m).model_dump(mode="json")}
    background.add_task(notify_users, [other, user], event)
    background.add_task(notify_users, [other], {"type": "message.push", "quote_id": q.id, "request_id": q.request_id},
                        f"Message from {user.name}", data.body[:120])
    return m
