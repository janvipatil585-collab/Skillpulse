# SkillPulse - GitHub Copilot Instructions

## Project

SkillPulse is an AI-enabled Labour Market Intelligence and Skill Demand-Supply Forecasting platform for the Smart India Hackathon problem statement:

> AI-Enabled Labour Market Intelligence and Skill Demand-Supply Forecasting Engine

The system must identify labour demand, training supply, skill gaps, future demand and supply, and training capacity recommendations.

## Architecture

Use this architecture:

React frontend -> FastAPI backend -> PostgreSQL database -> Python ML pipeline -> XGBoost forecasting model. Store forecast results in PostgreSQL, serve real results through FastAPI, and display them in React.

## Fixed Technology Stack

- Frontend: React, Vite, JavaScript, Tailwind CSS, Recharts, Leaflet
- Backend: Python, FastAPI, Pydantic, SQLAlchemy
- Database: PostgreSQL
- Data and ML: Pandas, NumPy, scikit-learn, XGBoost
- Infrastructure: Docker, Docker Compose
- Testing: Pytest, Vitest

Do not introduce alternative frameworks unless explicitly requested.

## Critical Rules

1. Never hardcode dashboard KPIs or forecast results.
2. Never generate fake ML predictions or random predictions.
3. Never use static chart data in the production frontend or fake API responses.
4. PostgreSQL is the source of truth. React must consume the FastAPI API.
5. Forecasts must come from the real XGBoost pipeline and be stored in PostgreSQL.
6. All filters must affect real backend queries.
7. Every important feature must have tests. Run tests after each major feature.
8. Fix errors instead of hiding them.
9. Do not declare a feature complete without executing and verifying it.
10. Do not leave TODO placeholders for core functionality or replace broken functionality with mock data.
11. Keep the application runnable with Docker Compose.

## MVP Data

Create a deterministic synthetic demonstration dataset so the MVP runs without live government APIs. It must contain:

- 5 Indian states
- At least 10 districts
- At least 5 sectors
- At least 15 trades
- 24 months of historical data

Data must contain meaningful trends, including trades that develop future shortages, trades that remain balanced, and trades with oversupply. Do not use random values without a deterministic seed.

## Database Entities

Create appropriate PostgreSQL models for:

- states
- districts
- sectors
- trades
- labour_demand
- training_supply
- forecasts
- model_metrics
- recommendations
- data_imports

## Forecasting

The forecasting engine must use XGBoost. Create meaningful time-series features, including lag features, rolling statistics, trend features, historical demand and supply, training capacity, sector, district, trade, and time information.

Use chronological train/validation splitting and calculate MAE, RMSE, and MAPE. Generate 3-month, 6-month, and 12-month forecasts. Store forecasts and model metrics in PostgreSQL.

## Skill Gap

Use:

`Skill Gap = Forecasted Demand - Forecasted Supply`

Calculate a meaningful gap percentage and classify results as Shortage, Balanced, or Oversupply. Implement classification thresholds in backend business logic, never in the frontend.

## Recommendations

Create a transparent training recommendation engine that considers forecast demand, forecast supply, skill gap, and current training capacity. Explain why each recommendation was generated.

Example: "Increase training capacity for Solar PV Technician in District X because forecast demand exceeds forecast supply."

## Backend

FastAPI must expose real endpoints for:

- Health
- States, districts, sectors, and trades
- Dashboard KPIs
- Demand vs. supply
- Forecasts
- Skill gaps
- Recommendations
- Model metrics
- Data import

All endpoints must use PostgreSQL or actual ML/business logic.

## Frontend

Create these pages:

- Dashboard
- Forecast
- Skill Gaps
- Recommendations
- Data
- Model

The dashboard must show total labour demand, total labour supply, total skill gaps, shortage count, oversupply count, a demand-vs-supply chart, a skill-gap table, and a geographic map. Use real API data.

Provide State, District, Sector, Trade, and Time Period filters. Filters must trigger real API queries.

## Model Transparency

The Model page must show:

- Model name
- Training period
- Forecast horizon
- MAE, RMSE, and MAPE
- Feature information
- Last training time
- Model version

## Docker

The complete application must run using Docker Compose and provide, at minimum, PostgreSQL, the FastAPI backend, and the React frontend. The ML pipeline must run through the backend or an appropriate application workflow.

## Testing and Verification

Before declaring the MVP complete, execute and verify:

- Backend tests, frontend tests, and API tests
- Database connectivity and data loading
- Model training and forecast generation
- Forecast persistence
- Skill-gap calculation
- Recommendation generation
- Frontend receipt of real API data
- Successful Docker Compose startup

## Development Workflow

Work incrementally. Inspect the existing repository before implementing major features. Prefer small, testable changes. After each major phase:

1. Run tests.
2. Run the application.
3. Inspect and fix errors.
4. Manually verify the feature.
5. Continue only after verification.

Never claim a feature is implemented merely because files were created. A feature is complete only when it executes successfully.

