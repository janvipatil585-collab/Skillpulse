# SkillPulse Deployment

## Architecture

The production topology keeps the existing application architecture intact:

```text
Vercel React/Vite SPA
        | HTTPS JSON API (VITE_API_BASE_URL)
        v
Render FastAPI container (XGBoost pipeline + SQLAlchemy)
        | private PostgreSQL connection (DATABASE_URL)
        v
Render PostgreSQL
```

Forecasts and metrics are produced by the real deterministic XGBoost service and stored in PostgreSQL. FastAPI reads those persisted rows; it does not train or fabricate predictions inside request handlers. `render.yaml` describes the backend and private managed database. `frontend/vercel.json` provides client-side route fallback.

The local Docker database is not exposed as the production database. Production PostgreSQL is provisioned separately and its Render IP allow list is empty, allowing private-network access only. The local Docker volume remains unchanged.

## Accounts and Repository Prerequisites

- A Vercel account for the React frontend.
- A Render account for the FastAPI container and managed PostgreSQL.
- A GitHub repository containing this workspace. Render Blueprints sync from a connected Git repository. This workspace currently has no project-level Git remote, so publish it to a dedicated repository before creating the Blueprint. Do not stage `.env` files.
- A custom domain is optional; Vercel and Render provide HTTPS service domains.

The free Render web service may sleep when idle, and free Render PostgreSQL has platform limits/expiry. Use an appropriate paid database/service plan for a persistent public portal.

## Environment Variables

Set secrets only in the relevant hosting dashboard, never in Git or Vercel `VITE_` variables.

| Variable | Where | Required value |
| --- | --- | --- |
| `VITE_API_BASE_URL` | Vercel frontend | Public Render API origin, e.g. `https://skillpulse-api.onrender.com`; no trailing slash is needed. |
| `DATABASE_URL` | Render backend | Render PostgreSQL private `connectionString`. The app normalizes Render's `postgresql://` URL to the psycopg SQLAlchemy driver. |
| `CORS_ORIGINS` | Render backend | Comma-separated exact HTTPS Vercel origin(s), e.g. `https://skillpulse-portal.vercel.app`. Do not include paths or `*`. |
| `ENVIRONMENT` | Render backend | `production`; production startup rejects missing/local database and CORS settings. |
| `MODEL_VERSION` | Render backend | `skillpulse-xgb-1.0.0` (or the version being deployed). |

`POSTGRES_PASSWORD`, `DATABASE_URL`, and other database credentials are backend/database-only. Never create a `VITE_DATABASE_URL` or any other frontend database credential.

For local development, copy `.env.example` to `.env` and `frontend/.env.example` to `frontend/.env`. Those examples contain local-only defaults and are excluded from Git by the root `.gitignore`.

## Prepare the Repository

From the SkillPulse workspace, after creating an empty private or public GitHub repository:

```powershell
git init
git add .
git status --short
git commit -m "Prepare SkillPulse deployment"
git branch -M main
git remote add origin https://github.com/<account>/<repository>.git
git push -u origin main
```

Review `git status` before committing. `.env`, frontend `.env`, Python virtual environments, Node dependencies, build output, and `.vercel` are ignored. Keep `.env.example` files; they contain placeholders/local development values, not production credentials.

## Deploy FastAPI and PostgreSQL on Render

1. Sign in to [Render](https://render.com) and choose **New → Blueprint**.
2. Connect the GitHub repository and select its deployment branch. Render reads the root `render.yaml`.
3. Review the proposed resources: `skillpulse-api` (Docker web service) and `skillpulse-postgres` (managed PostgreSQL). Keep the database private; do not add public IP allow-list entries.
4. When prompted for `CORS_ORIGINS`, enter the planned exact Vercel production origin. If the Vercel domain is not known yet, deploy the backend first and set this variable in the Render service's Environment page after frontend creation.
5. Apply the Blueprint. The backend listens on Render's `PORT`, and `/health` is its health check.
6. `initialDeployHook` seeds the deterministic demo history and runs the real XGBoost pipeline after the first successful backend deploy. Confirm its logs show completion. If the hook was skipped or fails, open the Render service Shell and run:

```sh
python -m services.seed_demo_data
python -m services.forecasting
```

7. Copy the backend's public HTTPS `onrender.com` origin. Keep the database's private `DATABASE_URL` inside Render only.
8. Verify `https://<backend>.onrender.com/health` and `https://<backend>.onrender.com/docs`.

The idempotent seed command creates the same deterministic historical series. The forecasting command trains demand and supply XGBoost models, stores 3/6/12-month monthly forecast rows, and persists model metrics.

## Deploy the Frontend on Vercel

### CLI

After completing `vercel login` in a browser:

```powershell
cd frontend
vercel link
vercel env add VITE_API_BASE_URL production
```

When prompted for the value, enter the public Render API origin, for example `https://skillpulse-api.onrender.com`. Then deploy:

```powershell
vercel --prod
```

The CLI prints the production HTTPS URL. Save that exact origin and add it to Render's `CORS_ORIGINS` if it differs from the planned value, then redeploy the backend.

### Vercel Dashboard

1. Import the GitHub repository into Vercel.
2. Set **Root Directory** to `frontend` and select Vite.
3. Set build command to `npm run build` and output directory to `dist`.
4. Add `VITE_API_BASE_URL` for Production (and Preview if desired), using the Render API HTTPS origin.
5. Deploy. `frontend/vercel.json` rewrites client routes to `index.html`.
6. Copy the assigned production domain into Render's `CORS_ORIGINS` as an exact HTTPS origin and redeploy the API.

Changing a Vercel environment variable requires a new deployment. The frontend uses localhost only in Vite development; a production build without `VITE_API_BASE_URL` displays a configuration error instead of requesting localhost.

## Verify the Deployment

Use the actual deployed origins:

```sh
curl -fsS https://<backend>.onrender.com/health
curl -fsS 'https://<backend>.onrender.com/api/dashboard/summary?horizon=3'
curl -fsS 'https://<backend>.onrender.com/api/forecasts?horizon=3'
curl -fsS 'https://<backend>.onrender.com/api/skill-gaps?horizon=3'
curl -fsS 'https://<backend>.onrender.com/api/recommendations?horizon=3'
curl -fsS https://<backend>.onrender.com/api/model/metrics
curl -fsS https://<backend>.onrender.com/api/data/summary
```

Check the Render PostgreSQL console for stored data:

```sql
SELECT count(*) FROM labour_demand;
SELECT count(*) FROM training_supply;
SELECT forecast_horizon, count(*) FROM forecasts GROUP BY forecast_horizon ORDER BY forecast_horizon;
SELECT count(*) FROM model_metrics;
```

Open the Vercel URL and verify Dashboard, Forecast, Skill Gaps, Recommendations, Data, and Model. Change State, District, Sector, Trade, and horizon and confirm the API-backed results change. Check Render logs for CORS/database errors and Vercel deployment logs for build errors.

## Local Run After Deployment Configuration

Local development remains unchanged and uses local-only defaults:

```powershell
Copy-Item .env.example .env
Copy-Item frontend/.env.example frontend/.env
docker compose up --build -d
docker compose exec backend python -m services.seed_demo_data
docker compose exec backend python -m services.forecasting
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`; the local API is `http://localhost:8000` and the local PostgreSQL port is `5432`. Do not use the local `.env` values in a hosting dashboard.

## Troubleshooting

- **Production frontend requests localhost:** set `VITE_API_BASE_URL` in Vercel Production and redeploy.
- **CORS error:** set `CORS_ORIGINS` to the exact Vercel origin, with `https://`, no path/trailing slash, then redeploy FastAPI.
- **Backend fails during startup:** verify `ENVIRONMENT=production`, a reachable managed Postgres `DATABASE_URL`, and a valid HTTPS `CORS_ORIGINS` value. Never point production at `localhost`, `127.0.0.1`, or Docker's `db` hostname.
- **Empty forecast pages:** check the initial deployment hook logs; run both seed and forecasting commands from the Render Shell.
- **Render service is waking up:** free web services can sleep; wait for `/health` to return `{"status":"healthy"}` or select an always-on plan.
- **Vercel deep link returns 404:** confirm `frontend/vercel.json` is included and the Vercel project root is `frontend`.
- **Database exposed publicly:** remove external IP allow-list entries; the backend and database should communicate over Render's private network.

## Public URL Status

No hosted deployment is declared complete by this configuration alone. The final URL exists only after the Render Blueprint is applied, initial seeding/training is verified, Vercel is authenticated and deployed, and the production Vercel origin is allowed by backend CORS.