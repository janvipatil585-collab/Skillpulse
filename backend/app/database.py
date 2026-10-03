import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.deployment_config import resolve_database_url

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
DATABASE_URL = resolve_database_url(os.getenv("DATABASE_URL"), ENVIRONMENT)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    from models import District, Forecast, LabourDemand, ModelMetric, Sector, State, Trade, TrainingSupply  # noqa: F401
    from models.base import Base

    Base.metadata.create_all(bind=engine)