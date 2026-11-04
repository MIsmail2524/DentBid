import math

EARTH_KM = 6371.0088


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lng2 - lng1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(math.sqrt(a))


def bounding_box(lat: float, lng: float, radius_km: float) -> tuple[float, float, float, float]:
    """Cheap SQL pre-filter before the exact haversine check."""
    dlat = radius_km / 111.32
    dlng = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def fuzz(lat: float, lng: float) -> tuple[float, float]:
    """Rounds to ~1 km so workshops do not see the exact address before booking."""
    return round(lat, 2), round(lng, 2)
