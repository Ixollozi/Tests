from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Medicalka"
    debug: bool = False
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60

    database_url: str = "postgresql+psycopg2://medicalka:medicalka@localhost:5432/medicalka"
    test_database_url: str = (
        "postgresql+psycopg2://medicalka:medicalka@localhost:5433/medicalka_test"
    )

    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/1"

    verification_token_ttl_hours: int = 24
    unverified_user_ttl_hours: int = 48


settings = Settings()
