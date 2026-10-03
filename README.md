# SkillPulse

See [DEPLOYMENT.md](DEPLOYMENT.md) for the Vercel + Render production deployment runbook.

SkillPulse is a labour-market intelligence demo: PostgreSQL stores historical demand and training supply, FastAPI serves database-backed results, and a deterministic XGBoost pipeline stores evaluation metrics and monthly forecasts for the React dashboard.

## Local Demo

1. Copy `.env.example` to `.env` and set a local database password.
2. Start the API and PostgreSQL with `docker compose up --build -d`.
3. Seed the development database with `docker compose exec backend python -m services.seed_demo_data`.
4. Train and persist forecasts with `docker compose exec backend python -m services.forecasting`.
5. Copy `frontend/.env.example` to `frontend/.env`, then run `npm install`, `npm run dev`, `npm test`, and `npm run build` from `frontend/`.
6. Open `http://localhost:5173`. FastAPI docs are at `http://localhost:8000/docs`.

The seed command is repeatable. The forecasting command trains XGBoost demand and supply models from PostgreSQL and replaces the stored result set for the active model version. The API never trains or generates predictions in request handlers.

## Backend Deployment

Deploy `backend/Dockerfile` as a separate container/service and attach a managed PostgreSQL instance. Configure:

- `DATABASE_URL`: SQLAlchemy PostgreSQL URL, for example `postgresql+psycopg://user:password@host:5432/database`.
- `CORS_ORIGINS`: comma-separated exact frontend origins, including the production Vercel domain and any preview domains that should be allowed.

Run database initialization through the application startup, then run `python -m services.seed_demo_data` and `python -m services.forecasting` as deployment/release jobs. Keep database credentials exclusively in the backend deployment environment.

## Vercel Frontend Deployment

Set the Vercel project root to `frontend/`, framework preset to Vite, build command to `npm run build`, and output directory to `dist`. Set `VITE_API_BASE_URL` to the public FastAPI base URL (for example `https://api.example.com`). `frontend/vercel.json` provides history fallback for the client-side routes.

Only the public API URL belongs in a `VITE_` variable. Never put database credentials or private backend secrets in frontend environment variables. The backend `CORS_ORIGINS` must include the deployed Vercel origin.