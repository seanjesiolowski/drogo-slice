from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/drogo_slice"
    admin_username: str = "admin"
    admin_password: str = "changeme"

    brevo_api_key: str = ""
    digest_from_email: str = ""
    digest_from_name: str = "Drogo Slice"
    digest_to_emails: str = ""

    sentry_dsn: str = ""
    sentry_environment: str = "production"
    sentry_traces_sample_rate: float = 0.0

    model_config = {"env_file": ".env"}

    @field_validator("database_url", mode="before")
    @classmethod
    def fix_async_scheme(cls, v: str) -> str:
        # Railway injects postgresql:// but asyncpg requires postgresql+asyncpg://
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v


settings = Settings()
