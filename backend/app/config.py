"""Settings read from environment / .env. Keys are never logged or printed."""
from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    gnani_api_key: SecretStr | None = None
    evon_base_url: str | None = None
    evon_api_key: SecretStr | None = None
    evon_model: str = "gnani/gnani-evon-v3.3-30B-A3B"
    frontend_origin: str = "http://localhost:5173"
    demo_only: bool = False
    admin_secret: SecretStr | None = None
    data_dir: Path = Path("./data")
    # Timbre v3.0 primary combination; on HTTP 400 gnani.py falls back to no speed at 48000 Hz.
    # Update after scripts/smoke_timbre.py shows which combination works (README "Measured API behaviour").
    tts_speed: float | None = 0.9
    tts_sample_rate: int = 24000
    # Hold GnaniGate for a whole streaming session (set false if concurrency_probe shows streams don't block).
    stream_holds_lock: bool = True

    def require(self, name: str):
        """Return a setting or fail clearly if it hasn't been configured yet."""
        value = getattr(self, name)
        if value is None or (isinstance(value, str) and ("<" in value or not value.strip())):
            raise RuntimeError(f"{name.upper()} is not set in .env (see .env.example)")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
