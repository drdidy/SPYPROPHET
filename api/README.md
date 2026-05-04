# SPY Prophet API

FastAPI service that exposes JSON endpoints over the existing trading
helpers in `app.py` and `tastytrade_provider.py`. Designed to run as a
**second** Render service alongside the Streamlit app, never replacing it.

## Endpoints

- `GET /api/health` — liveness + reports whether Tastytrade secrets are wired.
- `GET /api/quotes/spy?expiration=YYYY-MM-DD&call_strike=&put_strike=` —
  same-day call/put quote pair via Tastytrade. `call_strike` and
  `put_strike` default to spot ± 2.
- `GET /api/live` — composite snapshot for the `/live` page (spot, change,
  VIX regime, watch strikes, decision label, last-update timestamp).
- `GET /api/docs` — Swagger UI.

Phase-2 fields (`bias`, `signal`, `trigger`, `target`, `stop`, `guardrails`,
`intel`) are reserved on `/api/live` and return `null` until the briefing
composer is wired through. The Next.js page falls back gracefully.

## Local dev

```bash
pip install -r requirements-api.txt
uvicorn api.main:app --reload --port 8000
```

Visit <http://localhost:8000/api/docs>.

## Required env vars (Render dashboard → Environment)

| Key                            | Purpose                                   |
| ------------------------------ | ----------------------------------------- |
| `TASTYTRADE_CLIENT_ID`         | OAuth client id (already set)             |
| `TASTYTRADE_CLIENT_SECRET`     | OAuth client secret (already set)         |
| `TASTYTRADE_REFRESH_TOKEN`     | OAuth refresh token (already set)         |
| `TASTYTRADE_ENVIRONMENT`       | `production` (default) or `cert`          |
| `SPYPROPHET_API_ALLOWED_ORIGINS` | Optional comma-list to override CORS    |
| `SPYPROPHET_LOG_LEVEL`         | `INFO` (default), `DEBUG`, …              |
| `SENTRY_DSN`                   | Optional — same Sentry project as Streamlit |

## Deploying to Render

Create a **new Web Service** in the same Render account (`drdidy@gmail.com`):

1. Connect the same `drdidy/SPYPROPHET` repo.
2. Branch: `main`.
3. Runtime: **Docker**.
4. Dockerfile path: `Dockerfile.api`.
5. Plan: Free.
6. Region: same as the Streamlit service.
7. Health-check path: `/api/health`.
8. Add the env vars above (re-use the values already set on the Streamlit
   service — Render does not share env vars across services).
9. Auto-deploy on push to `main`: enabled.

Once live, point a Cloudflare CNAME `api.spyprophet.app → <new>.onrender.com`
and set `NEXT_PUBLIC_API_URL=https://api.spyprophet.app` on the Vercel
project. The Next.js `/live` page reads that env var.
