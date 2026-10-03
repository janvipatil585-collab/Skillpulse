from urllib.parse import urlsplit

LOCAL_CORS_ORIGINS = ("http://localhost:5173", "http://127.0.0.1:5173")
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "db"}


def is_production(environment: str) -> bool:
    return environment.strip().lower() in {"production", "prod"}


def resolve_database_url(value: str | None, environment: str) -> str:
    production = is_production(environment)
    database_url = (value or "").strip()
    if not database_url:
        if production:
            raise ValueError("DATABASE_URL must point to the managed PostgreSQL database in production")
        raise ValueError("DATABASE_URL is required; configure it in the ignored local .env file")

    if database_url.startswith("postgres://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgres://")
    elif database_url.startswith("postgresql://"):
        database_url = "postgresql+psycopg://" + database_url.removeprefix("postgresql://")

    parsed = urlsplit(database_url)
    if parsed.scheme != "postgresql+psycopg" or not parsed.hostname:
        raise ValueError("DATABASE_URL must be a valid PostgreSQL URL using psycopg")
    if production and parsed.hostname.lower() in LOCAL_HOSTS:
        raise ValueError("Production DATABASE_URL must not use a localhost or Docker-only database host")
    return database_url


def resolve_cors_origins(value: str | None, environment: str) -> tuple[str, ...]:
    production = is_production(environment)
    if value is None:
        if production:
            raise ValueError("CORS_ORIGINS must contain the deployed HTTPS frontend origin in production")
        value = ",".join(LOCAL_CORS_ORIGINS)

    origins = tuple(origin.strip().rstrip("/") for origin in value.split(",") if origin.strip())
    if production:
        if not origins:
            raise ValueError("CORS_ORIGINS must contain the deployed HTTPS frontend origin in production")
        for origin in origins:
            parsed = urlsplit(origin)
            if parsed.scheme != "https" or not parsed.hostname or parsed.hostname.lower() in LOCAL_HOSTS:
                raise ValueError("Production CORS_ORIGINS must contain exact public HTTPS origins only")
            if parsed.path or parsed.query or parsed.fragment:
                raise ValueError("CORS_ORIGINS values must be origins without paths or query strings")
    return origins