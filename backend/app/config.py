from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_SECRET = "dev-secret-change-me"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DentBid API"
    environment: str = "development"        # "production" enforces secure settings
    database_url: str = "sqlite:///./dentbid.db"
    jwt_secret: str = DEV_SECRET
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 30
    media_dir: Path = Path("media")
    private_media_dir: Path = Path("private_media")   # verification documents, never served statically
    media_url_ttl_seconds: int = 60 * 60 * 24
    public_base_url: str = ""                         # empty = relative URLs (same origin as the API)
    cors_origins: str = "*"
    web_dist_dir: Path = Path("../mobile/dist")       # built web app, served at / when present
    enable_docs: bool = True

    request_ttl_hours: int = 48
    default_search_radius_km: float = 25.0
    max_photos_per_request: int = 8
    max_upload_mb: int = 15
    max_image_side: int = 2560
    max_image_pixels: int = 50_000_000                # decompression-bomb guard (~7000x7000)
    max_body_mb: int = 130

    rate_limit_per_minute: int = 1200                 # per client IP, whole API (mobile carriers share IPs)
    login_attempts_per_15min: int = 10                # per IP + email

    admin_email: str = ""
    admin_password: str = ""

    dentbid_damage_weights: str = ""
    dentbid_parts_weights: str = ""
    dentbid_car_weights: str = "yolo11n-seg.pt"
    dentbid_device: str = "cpu"
    analysis_enabled: bool = True

    expo_access_token: str = ""

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    def validate_for_production(self) -> None:
        if not self.is_production:
            return
        problems = []
        if self.jwt_secret == DEV_SECRET or len(self.jwt_secret) < 32:
            problems.append("JWT_SECRET must be a random string of at least 32 characters")
        if self.admin_password and len(self.admin_password) < 12:
            problems.append("ADMIN_PASSWORD must be at least 12 characters")
        if problems:
            raise RuntimeError("Insecure production configuration: " + "; ".join(problems))


@lru_cache
def get_settings() -> Settings:
    return Settings()
