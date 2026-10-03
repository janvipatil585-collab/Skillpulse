from __future__ import annotations

from math import ceil
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from models import TrainingSupply


def build_recommendations(session: Session, forecasts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not forecasts:
        return []

    series_keys = {(int(row["district_id"]), int(row["trade_id"])) for row in forecasts}
    latest_supply_period = (
        select(
            TrainingSupply.district_id.label("district_id"),
            TrainingSupply.trade_id.label("trade_id"),
            func.max(TrainingSupply.period).label("period"),
        )
        .group_by(TrainingSupply.district_id, TrainingSupply.trade_id)
        .subquery()
    )
    supply_rows = session.execute(
        select(
            TrainingSupply.district_id,
            TrainingSupply.trade_id,
            TrainingSupply.trainees_count,
            TrainingSupply.training_capacity,
        ).join(
            latest_supply_period,
            (TrainingSupply.district_id == latest_supply_period.c.district_id)
            & (TrainingSupply.trade_id == latest_supply_period.c.trade_id)
            & (TrainingSupply.period == latest_supply_period.c.period),
        )
    ).all()
    current_supply = {
        (int(row.district_id), int(row.trade_id)): {
            "trainees_count": int(row.trainees_count),
            "training_capacity": int(row.training_capacity),
        }
        for row in supply_rows
        if (int(row.district_id), int(row.trade_id)) in series_keys
    }

    recommendations = []
    for forecast in forecasts:
        if forecast["classification"] != "shortage":
            continue
        series = (int(forecast["district_id"]), int(forecast["trade_id"]))
        current = current_supply.get(series)
        if current is None:
            continue
        headroom = max(current["training_capacity"] - current["trainees_count"], 0)
        shortage = max(float(forecast["skill_gap"]), 0.0)
        additional_capacity = max(ceil(shortage - headroom), 0)
        if float(forecast["gap_percentage"]) >= 25:
            priority = "high"
        elif float(forecast["gap_percentage"]) >= 10:
            priority = "medium"
        else:
            priority = "low"

        if additional_capacity:
            reason = (
                f"Forecast demand of {forecast['forecast_demand']:.1f} exceeds supply of "
                f"{forecast['forecast_supply']:.1f} by {shortage:.1f}. Current capacity has "
                f"{headroom} available places, leaving {additional_capacity} additional places to add."
            )
        else:
            reason = (
                f"Forecast demand of {forecast['forecast_demand']:.1f} exceeds supply of "
                f"{forecast['forecast_supply']:.1f} by {shortage:.1f}; current capacity has "
                f"{headroom} available places, enough to cover the projected gap."
            )
        recommendations.append(
            {
                **forecast,
                "current_training_capacity": current["training_capacity"],
                "current_trainees": current["trainees_count"],
                "available_capacity": headroom,
                "recommended_additional_capacity": additional_capacity,
                "priority": priority,
                "reason": reason,
            }
        )
    return recommendations