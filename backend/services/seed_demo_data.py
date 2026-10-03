import json

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.database import SessionLocal, init_db
from models import District, LabourDemand, Sector, State, Trade, TrainingSupply
from services.demo_data import (
    HISTORICAL_MONTHS,
    MINIMUM_RECORDS_PER_SERIES,
    build_demo_dataset,
    historical_periods,
)


def _upsert(
    session: Session,
    model: type,
    records: list[dict[str, object]],
    conflict_columns: list[str],
    update_columns: list[str],
) -> None:
    if not records:
        return
    statement = insert(model).values(records)
    updates = {column: getattr(statement.excluded, column) for column in update_columns}
    session.execute(statement.on_conflict_do_update(index_elements=conflict_columns, set_=updates))


def _table_count(session: Session, model: type) -> int:
    return int(session.scalar(select(func.count()).select_from(model)) or 0)


def _validate_database(session: Session) -> dict[str, object]:
    counts = {
        "states": _table_count(session, State),
        "districts": _table_count(session, District),
        "sectors": _table_count(session, Sector),
        "trades": _table_count(session, Trade),
        "labour_demand_records": _table_count(session, LabourDemand),
        "training_supply_records": _table_count(session, TrainingSupply),
    }
    minimums = {
        "states": 5,
        "districts": 10,
        "sectors": 5,
        "trades": 15,
        "labour_demand_records": MINIMUM_RECORDS_PER_SERIES,
        "training_supply_records": MINIMUM_RECORDS_PER_SERIES,
    }
    for key, minimum in minimums.items():
        if counts[key] < minimum:
            raise RuntimeError(f"Database validation failed: {key} has {counts[key]}, expected at least {minimum}")

    orphan_checks = (
        select(func.count()).select_from(District).outerjoin(State, District.state_id == State.id).where(State.id.is_(None)),
        select(func.count()).select_from(Trade).outerjoin(Sector, Trade.sector_id == Sector.id).where(Sector.id.is_(None)),
        select(func.count()).select_from(LabourDemand).outerjoin(District, LabourDemand.district_id == District.id).where(District.id.is_(None)),
        select(func.count()).select_from(LabourDemand).outerjoin(Trade, LabourDemand.trade_id == Trade.id).where(Trade.id.is_(None)),
        select(func.count()).select_from(TrainingSupply).outerjoin(District, TrainingSupply.district_id == District.id).where(District.id.is_(None)),
        select(func.count()).select_from(TrainingSupply).outerjoin(Trade, TrainingSupply.trade_id == Trade.id).where(Trade.id.is_(None)),
    )
    if any(session.scalar(check) for check in orphan_checks):
        raise RuntimeError("Database validation failed: one or more required foreign keys are missing")

    invalid_demand = session.scalar(select(func.count()).select_from(LabourDemand).where(LabourDemand.demand_count < 0))
    invalid_supply = session.scalar(
        select(func.count())
        .select_from(TrainingSupply)
        .where((TrainingSupply.trainees_count < 0) | (TrainingSupply.training_capacity < 0))
    )
    if invalid_demand or invalid_supply:
        raise RuntimeError("Database validation failed: demand and supply values must be non-negative")

    first_period, last_period = historical_periods()[0], historical_periods()[-1]
    for model in (LabourDemand, TrainingSupply):
        actual_range = session.execute(select(func.min(model.period), func.max(model.period))).one()
        if actual_range != (first_period, last_period):
            raise RuntimeError(f"Database validation failed: unexpected date range for {model.__tablename__}")

    counts["date_range"] = {"start": first_period.isoformat(), "end": last_period.isoformat()}
    counts["historical_months"] = HISTORICAL_MONTHS
    return counts


def seed_demo_data() -> dict[str, object]:
    dataset = build_demo_dataset()
    init_db()

    with SessionLocal() as session, session.begin():
        _upsert(session, State, dataset["states"], ["code"], ["name"])
        state_ids = dict(session.execute(select(State.code, State.id)).all())

        district_rows = [
            {"state_id": state_ids[str(row["state_code"])], "name": row["name"]}
            for row in dataset["districts"]
        ]
        _upsert(session, District, district_rows, ["state_id", "name"], ["name"])

        _upsert(session, Sector, dataset["sectors"], ["name"], ["name"])
        sector_ids = dict(session.execute(select(Sector.name, Sector.id)).all())

        trade_rows = [
            {"sector_id": sector_ids[str(row["sector_name"])], "name": row["name"]}
            for row in dataset["trades"]
        ]
        _upsert(session, Trade, trade_rows, ["sector_id", "name"], ["name"])

        district_ids = {
            (state_code, district_name): district_id
            for state_code, district_name, district_id in session.execute(
                select(State.code, District.name, District.id).join(District, District.state_id == State.id)
            )
        }
        trade_ids = {
            (sector_name, trade_name): trade_id
            for sector_name, trade_name, trade_id in session.execute(
                select(Sector.name, Trade.name, Trade.id).join(Trade, Trade.sector_id == Sector.id)
            )
        }

        sector_by_trade = {str(row["name"]): str(row["sector_name"]) for row in dataset["trades"]}
        demand_rows = [
            {
                "district_id": district_ids[(str(row["state_code"]), str(row["district_name"]))],
                "trade_id": trade_ids[(sector_by_trade[str(row["trade_name"])], str(row["trade_name"]))],
                "period": row["period"],
                "demand_count": row["demand_count"],
            }
            for row in dataset["labour_demand"]
        ]
        supply_rows = [
            {
                "district_id": district_ids[(str(row["state_code"]), str(row["district_name"]))],
                "trade_id": trade_ids[(sector_by_trade[str(row["trade_name"])], str(row["trade_name"]))],
                "period": row["period"],
                "trainees_count": row["trainees_count"],
                "training_capacity": row["training_capacity"],
            }
            for row in dataset["training_supply"]
        ]
        _upsert(
            session,
            LabourDemand,
            demand_rows,
            ["district_id", "trade_id", "period"],
            ["demand_count"],
        )
        _upsert(
            session,
            TrainingSupply,
            supply_rows,
            ["district_id", "trade_id", "period"],
            ["trainees_count", "training_capacity"],
        )

    with SessionLocal() as session:
        return _validate_database(session)


def main() -> None:
    print(json.dumps(seed_demo_data(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()