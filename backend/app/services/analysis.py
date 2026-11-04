"""Runs the DentBid CV engine on a request's photos in a background worker."""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

import cv2

from ..config import get_settings
from ..db import SessionLocal
from ..models import DamageRequest, RequestStatus, Workshop
from . import geo
from .realtime import notify_users
from .storage import media_root

log = logging.getLogger("dentbid.analysis")

_lock = threading.Lock()
_analyzer = None
_analyzer_error: str | None = None


def get_analyzer():
    """Loads the models once. Returns None (and remembers why) when unavailable."""
    global _analyzer, _analyzer_error
    if _analyzer is not None or _analyzer_error is not None:
        return _analyzer
    with _lock:
        if _analyzer is not None or _analyzer_error is not None:
            return _analyzer
        s = get_settings()
        if not s.analysis_enabled:
            _analyzer_error = "analysis_disabled"
            return None
        try:
            from dentbid_cv import DamageAnalyzer
            _analyzer = DamageAnalyzer(
                damage_weights=s.dentbid_damage_weights or None,
                parts_weights=s.dentbid_parts_weights,
                car_weights=s.dentbid_car_weights,
                device=s.dentbid_device or None,
            )
            log.info("damage analyzer loaded: %s", _analyzer.version)
        except Exception as e:  # missing weights, missing ultralytics ...
            _analyzer_error = f"{type(e).__name__}: {e}"
            log.warning("damage analyzer unavailable: %s", _analyzer_error)
    return _analyzer


def analyzer_status() -> dict:
    a = get_analyzer()
    return {"available": a is not None, "model_version": getattr(a, "version", None), "error": _analyzer_error}


def matching_workshops(db, req: DamageRequest) -> list[tuple[Workshop, float]]:
    lat1, lat2, lng1, lng2 = geo.bounding_box(req.lat, req.lng, req.search_radius_km)
    cands = db.query(Workshop).filter(Workshop.lat.between(lat1, lat2), Workshop.lng.between(lng1, lng2)).all()
    types = set((req.analysis or {}).get("damage_types") or [])
    out = []
    for w in cands:
        d = geo.haversine_km(req.lat, req.lng, w.lat, w.lng)
        if d > req.search_radius_km or d > w.service_radius_km:
            continue
        if types and w.services and not types & set(w.services):
            continue
        out.append((w, d))
    return sorted(out, key=lambda x: x[1])


def run_analysis(request_id: int) -> None:
    from dentbid_cv.analyzer import annotate, summarize_report
    from dentbid_cv.quality import check_quality

    db = SessionLocal()
    try:
        req = db.get(DamageRequest, request_id)
        if req is None:
            return
        analyzer = get_analyzer()
        root = media_root()
        results = []
        for photo in req.photos:
            img = cv2.imread(str(root / photo.path))
            if img is None:
                photo.analysis = {"error": "unreadable"}
                continue
            if analyzer is None:
                photo.analysis = {"quality": check_quality(img).__dict__}
                continue
            try:
                r = analyzer.analyze(img)
            except Exception as e:
                log.exception("analysis failed for photo %s", photo.id)
                photo.analysis = {"error": str(e), "quality": check_quality(img).__dict__}
                continue
            results.append(r)
            ann_rel = photo.path.rsplit(".", 1)[0] + "_annotated.jpg"
            cv2.imwrite(str(root / ann_rel), annotate(img, r), [cv2.IMWRITE_JPEG_QUALITY, 88])
            photo.annotated_path = ann_rel
            photo.analysis = r.to_dict()

        if analyzer is None:
            req.analysis = {"status": "unavailable", "reason": _analyzer_error,
                            "photos_analyzed": 0, "damage_types": []}
        else:
            report = summarize_report(results)
            report["status"] = "done" if results else "failed"
            report["model_version"] = analyzer.version
            report["analyzed_at"] = datetime.now(timezone.utc).isoformat()
            report["summary"] = " ".join(r.summary for r in results if r.damages) or (
                results[0].summary if results else "Analysis failed for all photos.")
            req.analysis = report
            req.overall_severity = report["overall_severity"]
            req.overall_score = report["overall_score"]

        if req.status == RequestStatus.analyzing:
            req.status = RequestStatus.open
        db.commit()

        notify_users([req.customer], {"type": "request.analyzed", "request_id": req.id},
                     "Damage report ready", "Nearby workshops can now send you quotes.")
        owners = [w.owner for w, _ in matching_workshops(db, req)]
        sev = req.overall_severity or "new"
        notify_users(owners, {"type": "request.new", "request_id": req.id},
                     "New repair request nearby", f"{sev.title()} damage on a {req.car_make or 'car'}. Send your quote.")
    finally:
        db.close()
