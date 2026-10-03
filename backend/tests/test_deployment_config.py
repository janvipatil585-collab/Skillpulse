import pytest

from app.deployment_config import resolve_cors_origins, resolve_database_url


def test_development_requires_database_url_but_keeps_local_cors_defaults() -> None:
    with pytest.raises(ValueError, match="DATABASE_URL is required"):
        resolve_database_url(None, "development")
    assert resolve_cors_origins(None, "development") == (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )


def test_render_postgres_url_is_normalized_for_psycopg() -> None:
    assert resolve_database_url("postgresql://user:pass@private-host:5432/app", "production") == (
        "postgresql+psycopg://user:pass@private-host:5432/app"
    )


@pytest.mark.parametrize("database_url", [None, "postgresql://user:pass@localhost:5432/app", "postgresql://user:pass@db:5432/app"])
def test_production_rejects_missing_or_local_database(database_url: str | None) -> None:
    with pytest.raises(ValueError):
        resolve_database_url(database_url, "production")


def test_production_requires_exact_https_frontend_origins() -> None:
    assert resolve_cors_origins("https://skillpulse.example,https://preview.example", "production") == (
        "https://skillpulse.example",
        "https://preview.example",
    )
    for invalid in (None, "", "http://skillpulse.example", "https://localhost:5173"):
        with pytest.raises(ValueError):
            resolve_cors_origins(invalid, "production")