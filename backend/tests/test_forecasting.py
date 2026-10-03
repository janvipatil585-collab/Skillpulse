import numpy as np
import pandas as pd
import pytest
from sqlalchemy import func, select

from app.database import SessionLocal
from models import Forecast, ModelMetric
from services.forecasting import (
    FEATURE_COLUMNS,
    MODEL_CONFIG,
    build_feature_frame,
    calculate_metrics,
    calculate_skill_gap,
    chronological_split,
    load_historical_panel,
    run_forecasting_pipeline,
    train_model,
)
from services.seed_demo_data import seed_demo_data


def test_feature_generation_and_chronological_split() -> None:
    seed_demo_data()
    with SessionLocal() as session:
        panel = load_historical_panel(session)

    features = build_feature_frame(panel)
    training, validation = chronological_split(features, validation_months=3)

    assert len(FEATURE_COLUMNS) == 27
    assert len(features) == 2700
    assert len(training) == 2250
    assert len(validation) == 450
    assert training["period"].max() < validation["period"].min()
    assert {"demand_lag_1", "demand_lag_6", "supply_lag_3", "demand_rolling_std_6", "training_capacity"}.issubset(features.columns)


def test_xgboost_training_is_deterministic() -> None:
    seed_demo_data()
    with SessionLocal() as session:
        features = build_feature_frame(load_historical_panel(session))
    training, validation = chronological_split(features, validation_months=3)
    small_config = {**MODEL_CONFIG, "n_estimators": 12}

    first_model = train_model(training.head(180), "demand_target", small_config)
    second_model = train_model(training.head(180), "demand_target", small_config)
    first_predictions = first_model.predict(validation.head(20)[list(FEATURE_COLUMNS)])
    second_predictions = second_model.predict(validation.head(20)[list(FEATURE_COLUMNS)])

    np.testing.assert_array_equal(first_predictions, second_predictions)


def test_metric_and_skill_gap_calculation() -> None:
    metrics = calculate_metrics([10.0, 20.0], [12.0, 18.0])

    assert metrics["mae"] == 2.0
    assert metrics["rmse"] == 2.0
    assert metrics["mape"] == pytest.approx(15.0)
    assert calculate_skill_gap(100.0, 100.0) == {
        "skill_gap": 0.0,
        "gap_percentage": 0.0,
        "classification": "balanced",
    }
    assert calculate_skill_gap(100.0, 90.0)["classification"] == "shortage"
    assert calculate_skill_gap(100.0, 110.0)["classification"] == "oversupply"
    assert calculate_skill_gap(100.0, 96.0)["classification"] == "balanced"
    with pytest.raises(ValueError):
        calculate_skill_gap(-1.0, 0.0)


def test_pipeline_generates_and_persists_forecasts_and_metrics() -> None:
    seed_demo_data()
    result = run_forecasting_pipeline()

    assert result["training_dataset_size"] == 2250
    assert result["validation_dataset_size"] == 450
    assert result["final_training_dataset_size"] == 2700
    assert result["forecast_counts"] == {"3": 450, "6": 900, "12": 1800}
    assert result["forecast_rows_stored"] == 3150
    assert result["model_metric_rows_stored"] == 6
    assert result["feature_count"] > result["raw_feature_count"]
    assert len(result["metrics"]) == 6
    assert all(np.isfinite(metric[key]) for metric in result["metrics"] for key in ("mae", "rmse", "mape"))

    with SessionLocal() as session:
        forecast_count = session.scalar(
            select(func.count()).select_from(Forecast).where(Forecast.model_version == result["model_version"])
        )
        metric_count = session.scalar(
            select(func.count()).select_from(ModelMetric).where(ModelMetric.model_version == result["model_version"])
        )
        horizons = dict(
            session.execute(
                select(Forecast.forecast_horizon, func.count())
                .where(Forecast.model_version == result["model_version"])
                .group_by(Forecast.forecast_horizon)
            ).all()
        )
        sample = session.scalar(
            select(Forecast).where(Forecast.model_version == result["model_version"])
        )

    assert forecast_count == 3150
    assert metric_count == 6
    assert horizons == {3: 450, 6: 900, 12: 1800}
    assert sample is not None
    assert sample.skill_gap == pytest.approx(sample.forecast_demand - sample.forecast_supply)