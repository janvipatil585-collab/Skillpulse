from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.database import get_db
from models import District, Forecast, LabourDemand, ModelMetric, Sector, State, Trade, TrainingSupply
from services.recommendations import build_recommendations

router = APIRouter(prefix="/api")
HORIZONS = {3, 6, 12}


def _forecast_statement(
    state: str | None,
    district: str | None,
    sector: str | None,
    trade: str | None,
    horizon: int | None,
):
    statement = (
        select(
            Forecast.id,
            Forecast.state_id,
            State.code.label("state_code"),
            State.name.label("state"),
            Forecast.district_id,
            District.name.label("district"),
            Forecast.sector_id,
            Sector.name.label("sector"),
            Forecast.trade_id,
            Trade.name.label("trade"),
            Forecast.forecast_month,
            Forecast.forecast_horizon,
            Forecast.forecast_demand,
            Forecast.forecast_supply,
            Forecast.skill_gap,
            Forecast.gap_percentage,
            Forecast.classification,
            Forecast.model_version,
            Forecast.generated_at,
        )
        .join(State, State.id == Forecast.state_id)
        .join(District, District.id == Forecast.district_id)
        .join(Sector, Sector.id == Forecast.sector_id)
        .join(Trade, Trade.id == Forecast.trade_id)
    )
    if state:
        statement = statement.where(or_(State.code.ilike(state), State.name.ilike(state)))
    if district:
        statement = statement.where(District.name.ilike(district))
    if sector:
        statement = statement.where(Sector.name.ilike(sector))
    if trade:
        statement = statement.where(Trade.name.ilike(trade))
    if horizon is not None:
        if horizon not in HORIZONS:
            raise HTTPException(status_code=422, detail="horizon must be 3, 6, or 12")
        statement = statement.where(Forecast.forecast_horizon == horizon)
    return statement


def _forecast_dict(row: Any) -> dict[str, Any]:
    result = dict(row._mapping)
    for key in ("forecast_demand", "forecast_supply", "skill_gap", "gap_percentage"):
        result[key] = float(result[key])
    if isinstance(result["generated_at"], datetime):
        result["generated_at"] = result["generated_at"].isoformat()
    return result


def _filtered_forecasts(
    session: Session,
    state: str | None,
    district: str | None,
    sector: str | None,
    trade: str | None,
    horizon: int | None,
) -> list[dict[str, Any]]:
    statement = _forecast_statement(state, district, sector, trade, horizon)
    statement = statement.order_by(Forecast.forecast_month, State.name, District.name, Trade.name)
    return [_forecast_dict(row) for row in session.execute(statement)]


def _historical_statement(state: str | None, district: str | None, sector: str | None, trade: str | None):
    statement = (
        select(LabourDemand)
        .join(District, District.id == LabourDemand.district_id)
        .join(State, State.id == District.state_id)
        .join(Trade, Trade.id == LabourDemand.trade_id)
        .join(Sector, Sector.id == Trade.sector_id)
    )
    if state:
        statement = statement.where(or_(State.code.ilike(state), State.name.ilike(state)))
    if district:
        statement = statement.where(District.name.ilike(district))
    if sector:
        statement = statement.where(Sector.name.ilike(sector))
    if trade:
        statement = statement.where(Trade.name.ilike(trade))
    return statement


@router.get("/dashboard/summary")
def dashboard_summary(
    state: str | None = None,
    district: str | None = None,
    sector: str | None = None,
    trade: str | None = None,
    horizon: int = Query(3),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = _forecast_statement(state, district, sector, trade, horizon).subquery()
    summary = session.execute(
        select(
            func.coalesce(func.sum(statement.c.forecast_demand), 0).label("total_labour_demand"),
            func.coalesce(func.sum(statement.c.forecast_supply), 0).label("total_labour_supply"),
            func.coalesce(
                func.sum(func.greatest(statement.c.skill_gap, 0)), 0
            ).label("total_skill_gap"),
            func.count().filter(statement.c.classification == "shortage").label("shortage_count"),
            func.count().filter(statement.c.classification == "oversupply").label("oversupply_count"),
            func.count().filter(statement.c.classification == "balanced").label("balanced_count"),
            func.count().label("forecast_record_count"),
        )
    ).one()
    return {
        "total_labour_demand": float(summary.total_labour_demand),
        "total_labour_supply": float(summary.total_labour_supply),
        "total_skill_gap": float(summary.total_skill_gap),
        "shortage_count": int(summary.shortage_count),
        "oversupply_count": int(summary.oversupply_count),
        "balanced_count": int(summary.balanced_count),
        "forecast_record_count": int(summary.forecast_record_count),
        "horizon": horizon,
    }


@router.get("/filters")
def filters(
    state: str | None = None,
    district: str | None = None,
    sector: str | None = None,
    trade: str | None = None,
    horizon: int | None = None,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    if horizon is not None and horizon not in HORIZONS:
        raise HTTPException(status_code=422, detail="horizon must be 3, 6, or 12")
    states = [dict(row._mapping) for row in session.execute(select(State.code, State.name).order_by(State.name))]
    district_statement = select(District.name, State.code, State.name.label("state")).join(State)
    if state:
        district_statement = district_statement.where(or_(State.code.ilike(state), State.name.ilike(state)))
    if district:
        district_statement = district_statement.where(District.name.ilike(district))
    districts = [dict(row._mapping) for row in session.execute(district_statement.order_by(State.name, District.name))]
    sector_statement = select(Sector.name).order_by(Sector.name)
    if sector:
        sector_statement = sector_statement.where(Sector.name.ilike(sector))
    sectors = [row.name for row in session.execute(sector_statement)]
    trade_statement = select(Trade.name, Sector.name.label("sector")).join(Sector)
    if sector:
        trade_statement = trade_statement.where(Sector.name.ilike(sector))
    if trade:
        trade_statement = trade_statement.where(Trade.name.ilike(trade))
    trades = [dict(row._mapping) for row in session.execute(trade_statement.order_by(Sector.name, Trade.name))]
    return {"states": states, "districts": districts, "sectors": sectors, "trades": trades, "horizons": [3, 6, 12]}


@router.get("/forecasts")
def forecasts(
    state: str | None = None,
    district: str | None = None,
    sector: str | None = None,
    trade: str | None = None,
    horizon: int = Query(3),
    limit: int = Query(5000, ge=1, le=10000),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = _filtered_forecasts(session, state, district, sector, trade, horizon)
    return {"count": len(rows[:limit]), "total": len(rows), "items": rows[:limit]}


@router.get("/skill-gaps")
def skill_gaps(
    state: str | None = None,
    district: str | None = None,
    sector: str | None = None,
    trade: str | None = None,
    horizon: int = Query(3),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = _filtered_forecasts(session, state, district, sector, trade, horizon)
    return {"count": len(rows), "items": rows}


@router.get("/recommendations")
def recommendations(
    state: str | None = None,
    district: str | None = None,
    sector: str | None = None,
    trade: str | None = None,
    horizon: int = Query(3),
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    rows = _filtered_forecasts(session, state, district, sector, trade, horizon)
    items = build_recommendations(session, rows)
    return {"count": len(items), "items": items}


@router.get("/model/metrics")
def model_metrics(
    horizon: int | None = None,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    statement = select(ModelMetric).order_by(ModelMetric.trained_at.desc(), ModelMetric.forecast_horizon, ModelMetric.target)
    if horizon is not None:
        if horizon not in HORIZONS:
            raise HTTPException(status_code=422, detail="horizon must be 3, 6, or 12")
        statement = statement.where(ModelMetric.forecast_horizon == horizon)
    items = [
        {
            "id": row.id,
            "model_version": row.model_version,
            "model_name": "XGBoost Regressor",
            "target": row.target,
            "training_start_date": row.training_start_date,
            "training_end_date": row.training_end_date,
            "trained_at": row.trained_at,
            "forecast_horizon": row.forecast_horizon,
            "mae": row.mae,
            "rmse": row.rmse,
            "mape": row.mape,
            "training_rows": row.training_rows,
            "validation_rows": row.validation_rows,
            "feature_count": row.feature_count,
            "model_config": row.model_config,
        }
        for row in session.scalars(statement)
    ]
    return {"count": len(items), "items": items}


@router.get("/data/summary")
def data_summary(
    state: str | None = None,
    district: str | None = None,
    sector: str | None = None,
    trade: str | None = None,
    horizon: int | None = None,
    session: Session = Depends(get_db),
) -> dict[str, Any]:
    if horizon is not None and horizon not in HORIZONS:
        raise HTTPException(status_code=422, detail="horizon must be 3, 6, or 12")
    demand_statement = _historical_statement(state, district, sector, trade).subquery()
    supply_statement = (
        select(TrainingSupply)
        .join(District, District.id == TrainingSupply.district_id)
        .join(State, State.id == District.state_id)
        .join(Trade, Trade.id == TrainingSupply.trade_id)
        .join(Sector, Sector.id == Trade.sector_id)
    )
    if state:
        supply_statement = supply_statement.where(or_(State.code.ilike(state), State.name.ilike(state)))
    if district:
        supply_statement = supply_statement.where(District.name.ilike(district))
    if sector:
        supply_statement = supply_statement.where(Sector.name.ilike(sector))
    if trade:
        supply_statement = supply_statement.where(Trade.name.ilike(trade))
    supply_statement = supply_statement.subquery()

    def count(statement) -> int:
        return int(session.scalar(select(func.count()).select_from(statement)) or 0)

    states_query = select(State.id)
    if state:
        states_query = states_query.where(or_(State.code.ilike(state), State.name.ilike(state)))
    districts_query = select(District.id).join(State)
    if state:
        districts_query = districts_query.where(or_(State.code.ilike(state), State.name.ilike(state)))
    if district:
        districts_query = districts_query.where(District.name.ilike(district))
    sectors_query = select(Sector.id)
    if sector:
        sectors_query = sectors_query.where(Sector.name.ilike(sector))
    trades_query = select(Trade.id).join(Sector)
    if sector:
        trades_query = trades_query.where(Sector.name.ilike(sector))
    if trade:
        trades_query = trades_query.where(Trade.name.ilike(trade))

    forecast_statement = _forecast_statement(state, district, sector, trade, horizon).subquery()
    return {
        "states": count(states_query.subquery()),
        "districts": count(districts_query.subquery()),
        "sectors": count(sectors_query.subquery()),
        "trades": count(trades_query.subquery()),
        "historical_months": int(session.scalar(select(func.count(func.distinct(demand_statement.c.period)))) or 0),
        "demand_records": count(demand_statement),
        "supply_records": count(supply_statement),
        "forecast_records": count(forecast_statement),
        "date_range": {
            "start": session.scalar(select(func.min(demand_statement.c.period))),
            "end": session.scalar(select(func.max(demand_statement.c.period))),
        },
    }