from collections import defaultdict

from sqlalchemy import func, select

from app.database import SessionLocal
from models import LabourDemand, TrainingSupply
from services.demo_data import HISTORICAL_MONTHS, build_demo_dataset, historical_periods
from services.seed_demo_data import seed_demo_data


def test_demo_dataset_is_deterministic_and_has_meaningful_patterns() -> None:
    first = build_demo_dataset()
    second = build_demo_dataset()

    assert first == second
    assert len(first["states"]) == 5
    assert len(first["districts"]) == 10
    assert len(first["sectors"]) == 5
    assert len(first["trades"]) == 15
    assert len(first["labour_demand"]) == len(first["training_supply"]) == 3600
    assert len(historical_periods()) == HISTORICAL_MONTHS
    assert historical_periods()[0].isoformat() == "2024-10-01"
    assert historical_periods()[-1].isoformat() == "2026-09-01"

    demand_by_trade = defaultdict(list)
    supply_by_trade = defaultdict(list)
    for row in first["labour_demand"]:
        demand_by_trade[row["trade_name"]].append(row["demand_count"])
    for row in first["training_supply"]:
        supply_by_trade[row["trade_name"]].append(row["trainees_count"])

    assert demand_by_trade["Solar PV Technician"][-1] > demand_by_trade["Solar PV Technician"][0]
    assert demand_by_trade["Data Entry Operator"][-1] < demand_by_trade["Data Entry Operator"][0]
    assert demand_by_trade["Energy Auditor"] == supply_by_trade["Energy Auditor"]
    assert demand_by_trade["Solar PV Technician"][0] > supply_by_trade["Solar PV Technician"][0]
    assert demand_by_trade["Data Entry Operator"][0] < supply_by_trade["Data Entry Operator"][0]


def test_seed_is_idempotent_against_postgresql() -> None:
    first_seed = seed_demo_data()
    second_seed = seed_demo_data()

    assert first_seed == second_seed
    assert first_seed["states"] == 5
    assert first_seed["districts"] == 10
    assert first_seed["sectors"] == 5
    assert first_seed["trades"] == 15
    assert first_seed["labour_demand_records"] == 3600
    assert first_seed["training_supply_records"] == 3600

    with SessionLocal() as session:
        demand_count = session.scalar(select(func.count()).select_from(LabourDemand))
        supply_count = session.scalar(select(func.count()).select_from(TrainingSupply))

    assert demand_count == 3600
    assert supply_count == 3600