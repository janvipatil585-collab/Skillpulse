from __future__ import annotations

import os
from datetime import date, datetime, timezone
from math import isfinite
from typing import Any

import numpy as np
import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder
from xgboost import XGBRegressor

from app.database import SessionLocal, init_db
from models import District, Forecast, LabourDemand, ModelMetric, Sector, State, Trade, TrainingSupply

MODEL_VERSION = os.getenv("MODEL_VERSION", "skillpulse-xgb-1.0.0").strip() or "skillpulse-xgb-1.0.0"
FORECAST_HORIZONS = (3, 6, 12)
BALANCED_GAP_TOLERANCE_PERCENT = 5.0
MINIMUM_HISTORY_MONTHS = 12
SERIES_KEYS = ("state_id", "district_id", "sector_id", "trade_id")
CATEGORICAL_FEATURES = ("state", "district", "sector", "trade", "month")
NUMERIC_FEATURES = (
    "year",
    "month_number",
    "trend_index",
    "historical_demand",
    "historical_supply",
    "demand_lag_1",
    "demand_lag_2",
    "demand_lag_3",
    "demand_lag_6",
    "supply_lag_1",
    "supply_lag_2",
    "supply_lag_3",
    "supply_lag_6",
    "demand_rolling_mean_3",
    "demand_rolling_std_3",
    "demand_rolling_mean_6",
    "demand_rolling_std_6",
    "supply_rolling_mean_3",
    "supply_rolling_std_3",
    "supply_rolling_mean_6",
    "supply_rolling_std_6",
    "training_capacity",
)
FEATURE_COLUMNS = (*CATEGORICAL_FEATURES, *NUMERIC_FEATURES)
MODEL_CONFIG: dict[str, object] = {
    "objective": "reg:squarederror",
    "n_estimators": 120,
    "max_depth": 3,
    "learning_rate": 0.05,
    "subsample": 1.0,
    "colsample_bytree": 1.0,
    "reg_lambda": 1.0,
    "random_state": 42,
    "n_jobs": 1,
    "tree_method": "hist",
    "verbosity": 0,
}


def add_months(period: date, month_count: int) -> date:
    month_index = period.year * 12 + period.month - 1 + month_count
    return date(month_index // 12, month_index % 12 + 1, 1)


def load_historical_panel(session: Session) -> pd.DataFrame:
    demand_statement = (
        select(
            State.id.label("state_id"),
            State.code.label("state_code"),
            State.name.label("state"),
            District.id.label("district_id"),
            District.name.label("district"),
            Sector.id.label("sector_id"),
            Sector.name.label("sector"),
            Trade.id.label("trade_id"),
            Trade.name.label("trade"),
            LabourDemand.period,
            LabourDemand.demand_count,
        )
        .join(District, District.state_id == State.id)
        .join(LabourDemand, LabourDemand.district_id == District.id)
        .join(Trade, Trade.id == LabourDemand.trade_id)
        .join(Sector, Sector.id == Trade.sector_id)
    )
    supply_statement = select(
        TrainingSupply.district_id,
        TrainingSupply.trade_id,
        TrainingSupply.period,
        TrainingSupply.trainees_count,
        TrainingSupply.training_capacity,
    )
    demand_rows = [dict(row) for row in session.execute(demand_statement).mappings()]
    supply_rows = [dict(row) for row in session.execute(supply_statement).mappings()]
    if not demand_rows or not supply_rows:
        raise ValueError("PostgreSQL must contain labour demand and training supply history before training")

    demand = pd.DataFrame(demand_rows)
    supply = pd.DataFrame(supply_rows)
    join_keys = ["district_id", "trade_id", "period"]
    try:
        panel = demand.merge(supply, on=join_keys, how="outer", validate="one_to_one", indicator=True)
    except pd.errors.MergeError as error:
        raise ValueError("Historical demand or supply contains duplicate district/trade/month records") from error
    if (panel["_merge"] != "both").any():
        raise ValueError("Every historical demand record must have a matching supply record, and vice versa")
    panel = panel.drop(columns="_merge")
    panel["period"] = pd.to_datetime(panel["period"])
    panel = panel.sort_values([*SERIES_KEYS, "period"]).reset_index(drop=True)

    numeric_columns = ("demand_count", "trainees_count", "training_capacity")
    if panel[list(numeric_columns)].isna().any().any():
        raise ValueError("Historical demand, supply, and capacity values cannot be null")
    if (panel[list(numeric_columns)] < 0).any().any():
        raise ValueError("Historical demand, supply, and capacity values must be non-negative")

    for key, group in panel.groupby(list(SERIES_KEYS), sort=False):
        periods = group["period"].tolist()
        if len(periods) < MINIMUM_HISTORY_MONTHS:
            raise ValueError(f"Series {key} has {len(periods)} months; at least {MINIMUM_HISTORY_MONTHS} are required")
        month_indexes = [period.year * 12 + period.month for period in periods]
        if any(period.day != 1 for period in periods) or any(
            current - previous != 1 for previous, current in zip(month_indexes, month_indexes[1:])
        ):
            raise ValueError(f"Series {key} must have valid, contiguous, month-start periods")
    return panel


def _feature_row(
    metadata: dict[str, Any],
    period: pd.Timestamp,
    trend_index: int,
    demand_history: list[float],
    supply_history: list[float],
    capacity_history: list[float],
) -> dict[str, Any]:
    if min(len(demand_history), len(supply_history), len(capacity_history)) < 6:
        raise ValueError("At least six complete historical months are required for lag features")

    features: dict[str, Any] = {
        "state": metadata["state"],
        "district": metadata["district"],
        "sector": metadata["sector"],
        "trade": metadata["trade"],
        "month": period.strftime("%B"),
        "year": period.year,
        "month_number": period.month,
        "trend_index": trend_index,
        "historical_demand": demand_history[-1],
        "historical_supply": supply_history[-1],
        "training_capacity": capacity_history[-1],
    }
    for target, history in (("demand", demand_history), ("supply", supply_history)):
        for lag in (1, 2, 3, 6):
            features[f"{target}_lag_{lag}"] = history[-lag]
        for window in (3, 6):
            recent_values = np.asarray(history[-window:], dtype=float)
            features[f"{target}_rolling_mean_{window}"] = float(recent_values.mean())
            features[f"{target}_rolling_std_{window}"] = float(recent_values.std(ddof=0))
    return features


def build_feature_frame(panel: pd.DataFrame) -> pd.DataFrame:
    feature_records = []
    for _, group in panel.groupby(list(SERIES_KEYS), sort=False):
        group = group.sort_values("period").reset_index(drop=True)
        metadata = group.iloc[0].to_dict()
        demand_history = group["demand_count"].astype(float).tolist()
        supply_history = group["trainees_count"].astype(float).tolist()
        capacity_history = group["training_capacity"].astype(float).tolist()
        for index in range(6, len(group)):
            current = group.iloc[index]
            previous_demand = demand_history[:index]
            previous_supply = supply_history[:index]
            previous_capacity = capacity_history[:index]
            record = _feature_row(
                metadata,
                pd.Timestamp(current["period"]),
                index,
                previous_demand,
                previous_supply,
                previous_capacity,
            )
            record.update(
                {
                    "state_id": int(current["state_id"]),
                    "district_id": int(current["district_id"]),
                    "sector_id": int(current["sector_id"]),
                    "trade_id": int(current["trade_id"]),
                    "period": current["period"],
                    "demand_target": float(current["demand_count"]),
                    "supply_target": float(current["trainees_count"]),
                }
            )
            feature_records.append(record)
    if not feature_records:
        raise ValueError("Historical panel did not produce any trainable feature rows")
    features = pd.DataFrame(feature_records)
    if features[list(FEATURE_COLUMNS)].isna().any().any():
        raise ValueError("Feature generation produced missing feature values")
    return features.sort_values([*SERIES_KEYS, "period"]).reset_index(drop=True)


def chronological_split(
    feature_frame: pd.DataFrame,
    validation_months: int = 3,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    periods = sorted(pd.Timestamp(period) for period in feature_frame["period"].unique())
    if validation_months < 1 or len(periods) <= validation_months:
        raise ValueError("Chronological split requires more periods than validation months")
    validation_start = periods[-validation_months]
    training = feature_frame[feature_frame["period"] < validation_start].copy()
    validation = feature_frame[feature_frame["period"] >= validation_start].copy()
    if training.empty or validation.empty:
        raise ValueError("Chronological split produced an empty training or validation dataset")
    return training, validation


def train_model(
    training_frame: pd.DataFrame,
    target_column: str,
    model_config: dict[str, object] | None = None,
) -> Pipeline:
    if target_column not in ("demand_target", "supply_target"):
        raise ValueError(f"Unsupported model target: {target_column}")
    if training_frame.empty:
        raise ValueError("Cannot train XGBoost with an empty dataset")

    preprocessor = ColumnTransformer(
        transformers=[
            ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), list(CATEGORICAL_FEATURES)),
            ("numeric", "passthrough", list(NUMERIC_FEATURES)),
        ],
        remainder="drop",
    )
    configuration = {**MODEL_CONFIG, **(model_config or {})}
    model = Pipeline(
        steps=[
            ("preprocessor", preprocessor),
            ("regressor", XGBRegressor(**configuration)),
        ]
    )
    model.fit(training_frame[list(FEATURE_COLUMNS)], training_frame[target_column].to_numpy(dtype=float))
    return model


def calculate_metrics(actual: list[float] | np.ndarray, predicted: list[float] | np.ndarray) -> dict[str, float]:
    actual_values = np.asarray(actual, dtype=float)
    predicted_values = np.asarray(predicted, dtype=float)
    if actual_values.size == 0 or actual_values.shape != predicted_values.shape:
        raise ValueError("Metric inputs must be non-empty arrays with matching shapes")
    if not np.isfinite(actual_values).all() or not np.isfinite(predicted_values).all():
        raise ValueError("Metric inputs must contain only finite values")
    errors = predicted_values - actual_values
    nonzero_actual = actual_values != 0
    if not nonzero_actual.any():
        raise ValueError("MAPE is undefined when every actual value is zero")
    return {
        "mae": float(np.mean(np.abs(errors))),
        "rmse": float(np.sqrt(np.mean(np.square(errors)))),
        "mape": float(np.mean(np.abs(errors[nonzero_actual] / actual_values[nonzero_actual])) * 100.0),
    }


def calculate_skill_gap(forecast_demand: float, forecast_supply: float) -> dict[str, float | str]:
    if not isfinite(forecast_demand) or not isfinite(forecast_supply):
        raise ValueError("Forecast demand and supply must be finite")
    if forecast_demand < 0 or forecast_supply < 0:
        raise ValueError("Forecast demand and supply must be non-negative")
    gap = forecast_demand - forecast_supply
    gap_percentage = gap / forecast_demand * 100 if forecast_demand else (0.0 if not forecast_supply else -100.0)
    if abs(gap_percentage) <= BALANCED_GAP_TOLERANCE_PERCENT:
        classification = "balanced"
    elif gap_percentage > 0:
        classification = "shortage"
    else:
        classification = "oversupply"
    return {"skill_gap": gap, "gap_percentage": gap_percentage, "classification": classification}


def _feature_count(model: Pipeline) -> int:
    preprocessor = model.named_steps["preprocessor"]
    return len(preprocessor.get_feature_names_out())


def _initial_series_states(panel: pd.DataFrame, before: pd.Timestamp | None = None) -> list[dict[str, Any]]:
    states = []
    for _, full_group in panel.groupby(list(SERIES_KEYS), sort=False):
        group = full_group if before is None else full_group[full_group["period"] < before]
        group = group.sort_values("period")
        if group.empty:
            raise ValueError("A forecast series has no history before the forecast origin")
        first = group.iloc[0]
        states.append(
            {
                "metadata": {column: first[column] for column in (
                    "state_id", "state_code", "state", "district_id", "district",
                    "sector_id", "sector", "trade_id", "trade",
                )},
                "periods": [period.date() for period in group["period"]],
                "demand": group["demand_count"].astype(float).tolist(),
                "supply": group["trainees_count"].astype(float).tolist(),
                "capacity": group["training_capacity"].astype(float).tolist(),
            }
        )
    return states


def _simulate_forecasts(
    panel: pd.DataFrame,
    demand_model: Pipeline,
    supply_model: Pipeline,
    steps: int,
    before: pd.Timestamp | None = None,
) -> list[dict[str, Any]]:
    series_states = _initial_series_states(panel, before)
    forecast_records = []
    for _ in range(steps):
        next_features = []
        next_periods = []
        for state in series_states:
            next_period = add_months(state["periods"][-1], 1)
            next_periods.append(next_period)
            next_features.append(
                _feature_row(
                    state["metadata"],
                    pd.Timestamp(next_period),
                    len(state["demand"]),
                    state["demand"],
                    state["supply"],
                    state["capacity"],
                )
            )
        feature_batch = pd.DataFrame(next_features, columns=FEATURE_COLUMNS)
        demand_predictions = np.maximum(0.0, demand_model.predict(feature_batch))
        supply_predictions = np.maximum(0.0, supply_model.predict(feature_batch))
        for index, state in enumerate(series_states):
            demand_value = float(demand_predictions[index])
            supply_value = float(supply_predictions[index])
            state["periods"].append(next_periods[index])
            state["demand"].append(demand_value)
            state["supply"].append(supply_value)
            state["capacity"].append(state["capacity"][-1])
            forecast_records.append(
                {
                    **state["metadata"],
                    "forecast_month": next_periods[index],
                    "forecast_demand": demand_value,
                    "forecast_supply": supply_value,
                }
            )
    return forecast_records


def _evaluate_horizon(
    panel: pd.DataFrame,
    feature_frame: pd.DataFrame,
    horizon: int,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    training, validation = chronological_split(feature_frame, validation_months=horizon)
    demand_model = train_model(training, "demand_target")
    supply_model = train_model(training, "supply_target")
    validation_start = pd.Timestamp(validation["period"].min())
    predictions = _simulate_forecasts(
        panel,
        demand_model,
        supply_model,
        steps=horizon,
        before=validation_start,
    )
    series_count = panel.groupby(list(SERIES_KEYS), sort=False).ngroups
    endpoint = predictions[-series_count:]
    actual_rows = panel[panel["period"] == pd.Timestamp(endpoint[0]["forecast_month"])]
    actual_by_key = {
        tuple(int(row[column]) for column in SERIES_KEYS): row
        for row in actual_rows.to_dict("records")
    }
    ordered_actuals = [
        actual_by_key[tuple(int(prediction[column]) for column in SERIES_KEYS)]
        for prediction in endpoint
    ]
    metric_records = []
    for target, target_column in (("demand", "demand_count"), ("supply", "trainees_count")):
        model = demand_model if target == "demand" else supply_model
        predicted = [prediction[f"forecast_{target}"] for prediction in endpoint]
        actual = [float(row[target_column]) for row in ordered_actuals]
        metric_records.append(
            {
                "model_version": MODEL_VERSION,
                "target": target,
                "training_start_date": pd.Timestamp(training["period"].min()).date(),
                "training_end_date": pd.Timestamp(training["period"].max()).date(),
                "forecast_horizon": horizon,
                **calculate_metrics(actual, predicted),
                "training_rows": len(training),
                "validation_rows": len(endpoint),
                "feature_count": _feature_count(model),
            }
        )
    return metric_records, {"training_rows": len(training), "validation_rows": len(validation)}


def _build_forecast_rows(panel: pd.DataFrame, models: dict[str, Pipeline]) -> list[dict[str, Any]]:
    recursive_predictions = _simulate_forecasts(
        panel,
        models["demand"],
        models["supply"],
        steps=max(FORECAST_HORIZONS),
    )
    forecast_rows = []
    for horizon in FORECAST_HORIZONS:
        for prediction in recursive_predictions:
            months_ahead = (prediction["forecast_month"].year - panel["period"].max().year) * 12
            months_ahead += prediction["forecast_month"].month - panel["period"].max().month
            if months_ahead > horizon:
                continue
            gap = calculate_skill_gap(prediction["forecast_demand"], prediction["forecast_supply"])
            forecast_rows.append(
                {
                    "state_id": int(prediction["state_id"]),
                    "district_id": int(prediction["district_id"]),
                    "sector_id": int(prediction["sector_id"]),
                    "trade_id": int(prediction["trade_id"]),
                    "forecast_month": prediction["forecast_month"],
                    "forecast_horizon": horizon,
                    "forecast_demand": prediction["forecast_demand"],
                    "forecast_supply": prediction["forecast_supply"],
                    "skill_gap": gap["skill_gap"],
                    "gap_percentage": gap["gap_percentage"],
                    "classification": gap["classification"],
                    "model_version": MODEL_VERSION,
                }
            )
    return forecast_rows


def _upsert_rows(
    session: Session,
    model: type,
    rows: list[dict[str, Any]],
    conflict_columns: list[str],
    update_columns: list[str],
) -> None:
    statement = insert(model).values(rows)
    updates = {column: getattr(statement.excluded, column) for column in update_columns}
    session.execute(statement.on_conflict_do_update(index_elements=conflict_columns, set_=updates))


def _store_results(forecast_rows: list[dict[str, Any]], metric_rows: list[dict[str, Any]], trained_at: datetime) -> None:
    for row in metric_rows:
        row["trained_at"] = trained_at
        row["model_config"] = dict(MODEL_CONFIG)
    for row in forecast_rows:
        row["generated_at"] = trained_at

    with SessionLocal() as session, session.begin():
        session.execute(delete(Forecast).where(Forecast.model_version == MODEL_VERSION))
        session.execute(delete(ModelMetric).where(ModelMetric.model_version == MODEL_VERSION))
        _upsert_rows(
            session,
            Forecast,
            forecast_rows,
            ["district_id", "trade_id", "forecast_month", "forecast_horizon"],
            [
                "state_id", "sector_id", "forecast_demand", "forecast_supply", "skill_gap",
                "gap_percentage", "classification", "model_version", "generated_at",
            ],
        )
        _upsert_rows(
            session,
            ModelMetric,
            metric_rows,
            ["model_version", "target", "forecast_horizon"],
            [
                "training_start_date", "training_end_date", "trained_at", "mae", "rmse", "mape",
                "training_rows", "validation_rows", "feature_count", "model_config",
            ],
        )


def run_forecasting_pipeline() -> dict[str, Any]:
    init_db()
    with SessionLocal() as session:
        panel = load_historical_panel(session)

    feature_frame = build_feature_frame(panel)
    standard_training, standard_validation = chronological_split(feature_frame, validation_months=3)
    metric_rows = []
    horizon_splits = {}
    for horizon in FORECAST_HORIZONS:
        horizon_metrics, sizes = _evaluate_horizon(panel, feature_frame, horizon)
        metric_rows.extend(horizon_metrics)
        horizon_splits[str(horizon)] = sizes

    final_models = {
        "demand": train_model(feature_frame, "demand_target"),
        "supply": train_model(feature_frame, "supply_target"),
    }
    forecast_rows = _build_forecast_rows(panel, final_models)
    trained_at = datetime.now(timezone.utc)
    _store_results(forecast_rows, metric_rows, trained_at)

    forecast_counts = {
        str(horizon): sum(row["forecast_horizon"] == horizon for row in forecast_rows)
        for horizon in FORECAST_HORIZONS
    }
    with SessionLocal() as session:
        stored_forecasts = session.scalar(
            select(func.count()).select_from(Forecast).where(Forecast.model_version == MODEL_VERSION)
        )
        stored_metrics = session.scalar(
            select(func.count()).select_from(ModelMetric).where(ModelMetric.model_version == MODEL_VERSION)
        )

    return {
        "model_version": MODEL_VERSION,
        "training_dataset_size": len(standard_training),
        "validation_dataset_size": len(standard_validation),
        "final_training_dataset_size": len(feature_frame),
        "raw_feature_count": len(FEATURE_COLUMNS),
        "feature_count": _feature_count(final_models["demand"]),
        "model_configuration": dict(MODEL_CONFIG),
        "horizon_split_sizes": horizon_splits,
        "metrics": metric_rows,
        "forecast_counts": forecast_counts,
        "forecast_rows_stored": int(stored_forecasts or 0),
        "model_metric_rows_stored": int(stored_metrics or 0),
    }


if __name__ == "__main__":
    import json

    print(json.dumps(run_forecasting_pipeline(), default=str, indent=2, sort_keys=True))