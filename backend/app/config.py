from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DentBid API"
    database_url: str = "sqlite:///./dentbid.db"
    jwt_secret: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60 * 24 * 30
    media_dir: Path = Path("media")
    public_base_url: str = "http://localhost:8000"
    cors_origins: str = "*"

    request_ttl_hours: int = 48
    default_search_radius_km: float = 25.0
    max_photos_per_request: int = 8
    max_upload_mb: int = 15
    max_image_side: int = 2560

    dentbid_damage_weights: str = ""
    dentbid_parts_weights: str = ""
    dentbid_car_weights: str = "yolo11n-seg.pt"
    dentbid_device: str = "cpu"
    analysis_enabled: bool = True

    expo_access_token: str = ""

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
