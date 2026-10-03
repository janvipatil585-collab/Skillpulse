from fastapi.testclient import TestClient

import app.main as main
from models import Base


def test_health_checks_database_and_returns_healthy() -> None:
    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_sqlalchemy_models_define_phase_one_tables() -> None:
    table_names = set(Base.metadata.tables)

    assert table_names == {
        "states",
        "districts",
        "sectors",
        "trades",
        "labour_demand",
        "training_supply",
        "forecasts",
        "model_metrics",
    }