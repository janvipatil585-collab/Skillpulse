from datetime import date

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from models.base import Base


class State(Base):
    __tablename__ = "states"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    code: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)


class District(Base):
    __tablename__ = "districts"
    __table_args__ = (UniqueConstraint("state_id", "name", name="uq_district_state_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    state_id: Mapped[int] = mapped_column(ForeignKey("states.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)


class Sector(Base):
    __tablename__ = "sectors"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)


class Trade(Base):
    __tablename__ = "trades"
    __table_args__ = (UniqueConstraint("sector_id", "name", name="uq_trade_sector_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    sector_id: Mapped[int] = mapped_column(ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)


class LabourDemand(Base):
    __tablename__ = "labour_demand"
    __table_args__ = (
        UniqueConstraint("district_id", "trade_id", "period", name="uq_labour_demand_period"),
        CheckConstraint("demand_count >= 0", name="ck_labour_demand_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id", ondelete="CASCADE"), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    demand_count: Mapped[int] = mapped_column(Integer, nullable=False)


class TrainingSupply(Base):
    __tablename__ = "training_supply"
    __table_args__ = (
        UniqueConstraint("district_id", "trade_id", "period", name="uq_training_supply_period"),
        CheckConstraint("trainees_count >= 0", name="ck_training_supply_nonnegative"),
        CheckConstraint("training_capacity >= 0", name="ck_training_capacity_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id", ondelete="CASCADE"), nullable=False)
    period: Mapped[date] = mapped_column(Date, nullable=False)
    trainees_count: Mapped[int] = mapped_column(Integer, nullable=False)
    training_capacity: Mapped[int] = mapped_column(Integer, nullable=False)


class Forecast(Base):
    __tablename__ = "forecasts"
    __table_args__ = (
        UniqueConstraint(
            "district_id", "trade_id", "forecast_month", "forecast_horizon",
            name="uq_forecast_series_month_horizon",
        ),
        CheckConstraint("forecast_horizon IN (3, 6, 12)", name="ck_forecast_supported_horizon"),
        CheckConstraint("forecast_demand >= 0", name="ck_forecast_demand_nonnegative"),
        CheckConstraint("forecast_supply >= 0", name="ck_forecast_supply_nonnegative"),
        CheckConstraint(
            "classification IN ('shortage', 'balanced', 'oversupply')",
            name="ck_forecast_classification",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    state_id: Mapped[int] = mapped_column(ForeignKey("states.id", ondelete="CASCADE"), nullable=False)
    district_id: Mapped[int] = mapped_column(ForeignKey("districts.id", ondelete="CASCADE"), nullable=False)
    sector_id: Mapped[int] = mapped_column(ForeignKey("sectors.id", ondelete="CASCADE"), nullable=False)
    trade_id: Mapped[int] = mapped_column(ForeignKey("trades.id", ondelete="CASCADE"), nullable=False)
    forecast_month: Mapped[date] = mapped_column(Date, nullable=False)
    forecast_horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    forecast_demand: Mapped[float] = mapped_column(Float, nullable=False)
    forecast_supply: Mapped[float] = mapped_column(Float, nullable=False)
    skill_gap: Mapped[float] = mapped_column(Float, nullable=False)
    gap_percentage: Mapped[float] = mapped_column(Float, nullable=False)
    classification: Mapped[str] = mapped_column(String(20), nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    generated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class ModelMetric(Base):
    __tablename__ = "model_metrics"
    __table_args__ = (
        UniqueConstraint("model_version", "target", "forecast_horizon", name="uq_model_metric_version_target_horizon"),
        CheckConstraint("target IN ('demand', 'supply')", name="ck_model_metric_target"),
        CheckConstraint("forecast_horizon IN (3, 6, 12)", name="ck_model_metric_supported_horizon"),
        CheckConstraint("mae >= 0 AND rmse >= 0 AND mape >= 0", name="ck_model_metric_nonnegative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)
    target: Mapped[str] = mapped_column(String(20), nullable=False)
    training_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    training_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    trained_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    forecast_horizon: Mapped[int] = mapped_column(Integer, nullable=False)
    mae: Mapped[float] = mapped_column(Float, nullable=False)
    rmse: Mapped[float] = mapped_column(Float, nullable=False)
    mape: Mapped[float] = mapped_column(Float, nullable=False)
    training_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    validation_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    feature_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_config: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)