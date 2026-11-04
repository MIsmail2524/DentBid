from fastapi import APIRouter, Request

from ..services.analysis import analyzer_status
from ..services.locale import country_from_headers, locale_for

router = APIRouter(tags=["meta"])


@router.get("/health")
def health():
    # public: no error strings or file paths (admins see details at /api/admin/stats)
    st = analyzer_status()
    return {"status": "ok", "analyzer": {"available": st["available"], "model_version": st["model_version"]}}


@router.get("/locale")
def detect_locale(request: Request, country: str | None = None, lang: str | None = None):
    """Currency and language for a country.

    The app passes `country` from GPS reverse geocoding; without it we use
    CDN/IP headers and then Accept-Language.
    """
    source = "gps"
    if not country:
        country, source = country_from_headers(request.headers)
    return locale_for(country, lang, source).to_dict()
