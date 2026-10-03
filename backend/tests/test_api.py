from fastapi.testclient import TestClient

import app.main as main
from services.forecasting import run_forecasting_pipeline
from services.seed_demo_data import seed_demo_data


def test_data_endpoints_return_database_results_and_apply_filters() -> None:
    seed_demo_data()
    run_forecasting_pipeline()

    with TestClient(main.app) as client:
        summary = client.get("/api/dashboard/summary", params={"horizon": 3}).json()
        filtered_summary = client.get(
            "/api/dashboard/summary",
            params={"state": "KA", "horizon": 3},
        ).json()
        forecast_response = client.get("/api/forecasts", params={"state": "KA", "horizon": 3}).json()
        longer_horizon = client.get("/api/forecasts", params={"horizon": 6}).json()
        filter_options = client.get("/api/filters", params={"state": "KA"}).json()
        gap_response = client.get("/api/skill-gaps", params={"horizon": 3}).json()
        recommendations = client.get("/api/recommendations", params={"horizon": 3}).json()
        metrics = client.get("/api/model/metrics").json()
        data = client.get("/api/data/summary").json()

    assert summary["forecast_record_count"] == 450
    assert filtered_summary["forecast_record_count"] == 90
    assert forecast_response["count"] == 90
    assert all(row["state_code"] == "KA" for row in forecast_response["items"])
    assert longer_horizon["count"] == 900
    assert {row["forecast_horizon"] for row in longer_horizon["items"]} == {6}
    assert {row["code"] for row in filter_options["states"]} == {"KA", "GJ", "MH", "TN", "TS"}
    assert {row["name"] for row in filter_options["districts"]} == {"Bengaluru Urban", "Mysuru"}
    assert gap_response["count"] == 450
    assert recommendations["count"] > 0
    assert all(item["reason"] and item["recommended_additional_capacity"] >= 0 for item in recommendations["items"])
    assert metrics["count"] == 6
    assert data["states"] == 5
    assert data["districts"] == 10
    assert data["sectors"] == 5
    assert data["trades"] == 15
    assert data["demand_records"] == 3600
    assert data["supply_records"] == 3600
    assert data["forecast_records"] == 3150