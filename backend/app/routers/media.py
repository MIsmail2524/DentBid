from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from ..security import check_media_sig
from ..services.storage import media_root, resolve_inside

router = APIRouter()


@router.get("/media/{path:path}", include_in_schema=False)
def media(path: str, exp: int = Query(...), sig: str = Query(..., max_length=64)):
    """Request photos, only through signed, expiring URLs handed out by the API."""
    if not check_media_sig(path, exp, sig):
        raise HTTPException(403, "Link expired or invalid")
    p = resolve_inside(media_root(), path)
    if p is None or not p.is_file():
        raise HTTPException(404, "Not found")
    return FileResponse(p, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})
