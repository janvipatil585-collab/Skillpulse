from datetime import date

STATES = (
    {"code": "MH", "name": "Maharashtra"},
    {"code": "KA", "name": "Karnataka"},
    {"code": "TN", "name": "Tamil Nadu"},
    {"code": "TS", "name": "Telangana"},
    {"code": "GJ", "name": "Gujarat"},
)

DISTRICTS = (
    {"state_code": "MH", "name": "Pune", "factor": 100},
    {"state_code": "MH", "name": "Nagpur", "factor": 95},
    {"state_code": "KA", "name": "Bengaluru Urban", "factor": 115},
    {"state_code": "KA", "name": "Mysuru", "factor": 90},
    {"state_code": "TN", "name": "Chennai", "factor": 110},
    {"state_code": "TN", "name": "Coimbatore", "factor": 100},
    {"state_code": "TS", "name": "Hyderabad", "factor": 112},
    {"state_code": "TS", "name": "Warangal", "factor": 85},
    {"state_code": "GJ", "name": "Ahmedabad", "factor": 108},
    {"state_code": "GJ", "name": "Surat", "factor": 98},
)

TRADE_PROFILES = (
    {"sector": "Renewable Energy", "name": "Solar PV Technician", "demand": 100, "demand_step": 3, "supply": 55, "supply_step": 1},
    {"sector": "Renewable Energy", "name": "Wind Turbine Technician", "demand": 70, "demand_step": 2, "supply": 42, "supply_step": 1},
    {"sector": "Renewable Energy", "name": "Energy Auditor", "demand": 60, "demand_step": 1, "supply": 60, "supply_step": 1},
    {"sector": "Information Technology", "name": "Data Entry Operator", "demand": 120, "demand_step": -2, "supply": 150, "supply_step": -1},
    {"sector": "Information Technology", "name": "Cloud Support Associate", "demand": 65, "demand_step": 2, "supply": 45, "supply_step": 1},
    {"sector": "Information Technology", "name": "Cybersecurity Analyst", "demand": 40, "demand_step": 2, "supply": 25, "supply_step": 1},
    {"sector": "Healthcare", "name": "General Duty Assistant", "demand": 90, "demand_step": 1, "supply": 90, "supply_step": 1},
    {"sector": "Healthcare", "name": "Medical Lab Technician", "demand": 70, "demand_step": 1, "supply": 52, "supply_step": 1},
    {"sector": "Healthcare", "name": "Community Health Worker", "demand": 80, "demand_step": 1, "supply": 100, "supply_step": 1},
    {"sector": "Manufacturing", "name": "CNC Operator", "demand": 85, "demand_step": 1, "supply": 85, "supply_step": 1},
    {"sector": "Manufacturing", "name": "Welding Technician", "demand": 95, "demand_step": 1, "supply": 125, "supply_step": 1},
    {"sector": "Manufacturing", "name": "Industrial Electrician", "demand": 88, "demand_step": 1, "supply": 68, "supply_step": 1},
    {"sector": "Agriculture", "name": "Organic Farmer", "demand": 110, "demand_step": -1, "supply": 110, "supply_step": -1},
    {"sector": "Agriculture", "name": "Food Processing Technician", "demand": 65, "demand_step": 1, "supply": 48, "supply_step": 1},
    {"sector": "Agriculture", "name": "Irrigation Pump Technician", "demand": 75, "demand_step": -1, "supply": 105, "supply_step": -1},
)

START_YEAR = 2024
START_MONTH = 10
HISTORICAL_MONTHS = 24
MINIMUM_RECORDS_PER_SERIES = len(DISTRICTS) * len(TRADE_PROFILES) * HISTORICAL_MONTHS


def historical_periods() -> list[date]:
    periods = []
    start_index = START_YEAR * 12 + START_MONTH - 1
    for offset in range(HISTORICAL_MONTHS):
        month_index = start_index + offset
        periods.append(date(month_index // 12, month_index % 12 + 1, 1))
    return periods


def build_demo_dataset() -> dict[str, list[dict[str, object]]]:
    periods = historical_periods()
    demand_records = []
    supply_records = []

    for district in DISTRICTS:
        for trade in TRADE_PROFILES:
            for month_offset, period in enumerate(periods):
                factor = district["factor"]
                demand_count = (trade["demand"] * factor + 50) // 100 + trade["demand_step"] * month_offset
                trainees_count = (trade["supply"] * factor + 50) // 100 + trade["supply_step"] * month_offset
                training_capacity = trainees_count + (15 * factor + 50) // 100
                demand_records.append(
                    {
                        "state_code": district["state_code"],
                        "district_name": district["name"],
                        "trade_name": trade["name"],
                        "period": period,
                        "demand_count": demand_count,
                    }
                )
                supply_records.append(
                    {
                        "state_code": district["state_code"],
                        "district_name": district["name"],
                        "trade_name": trade["name"],
                        "period": period,
                        "trainees_count": trainees_count,
                        "training_capacity": training_capacity,
                    }
                )

    dataset = {
        "states": [dict(state) for state in STATES],
        "districts": [dict(district) for district in DISTRICTS],
        "sectors": [{"name": name} for name in dict.fromkeys(trade["sector"] for trade in TRADE_PROFILES)],
        "trades": [
            {"sector_name": trade["sector"], "name": trade["name"]}
            for trade in TRADE_PROFILES
        ],
        "labour_demand": demand_records,
        "training_supply": supply_records,
    }
    validate_demo_dataset(dataset)
    return dataset


def validate_demo_dataset(dataset: dict[str, list[dict[str, object]]]) -> None:
    states_by_code = {str(state["code"]) for state in dataset["states"]}
    sectors_by_name = {str(sector["name"]) for sector in dataset["sectors"]}
    trades_by_name = {str(trade["name"]) for trade in dataset["trades"]}
    district_keys = {
        (str(district["state_code"]), str(district["name"]))
        for district in dataset["districts"]
    }

    if len(states_by_code) < 5 or len(dataset["districts"]) < 10:
        raise ValueError("Demo dataset must contain at least 5 states and 10 districts")
    if len(sectors_by_name) < 5 or len(dataset["trades"]) < 15:
        raise ValueError("Demo dataset must contain at least 5 sectors and 15 trades")
    if any(str(district["state_code"]) not in states_by_code for district in dataset["districts"]):
        raise ValueError("Every district must reference a defined state")
    if any(str(trade["sector_name"]) not in sectors_by_name for trade in dataset["trades"]):
        raise ValueError("Every trade must reference a defined sector")
    if {str(trade["name"]) for trade in dataset["trades"]} != trades_by_name:
        raise ValueError("Trade names must be unique in the demo dataset")

    expected_records = len(dataset["districts"]) * len(dataset["trades"]) * HISTORICAL_MONTHS
    periods = set(historical_periods())
    for table_name in ("labour_demand", "training_supply"):
        records = dataset[table_name]
        if len(records) != expected_records:
            raise ValueError(f"{table_name} must contain {expected_records} historical records")
        for record in records:
            district_key = (str(record["state_code"]), str(record["district_name"]))
            if district_key not in district_keys:
                raise ValueError(f"{table_name} contains a missing district reference")
            if str(record["trade_name"]) not in trades_by_name:
                raise ValueError(f"{table_name} contains a missing trade reference")
            if record["period"] not in periods:
                raise ValueError(f"{table_name} contains a date outside the 24-month history")
            value_fields = ("demand_count",) if table_name == "labour_demand" else ("trainees_count", "training_capacity")
            if any(int(record[field]) < 0 for field in value_fields):
                raise ValueError(f"{table_name} values must be non-negative")