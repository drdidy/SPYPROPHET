# SPY Prophet

SPY Prophet is an **analysis-only** Streamlit terminal for same-day SPY structure workflows.

> **No order execution is implemented.** No submit / cancel / replace / dry-run trading functions are provided.

## Quick start

### Local (venv)
```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
python -m pytest -q
streamlit run app.py
```

### Docker
```bash
docker build -t spyprophet .
docker run --rm -p 8501:8501 \
  --env-file .env \
  -v "$(pwd)/data:/app/data" \
  spyprophet
# Open http://localhost:8501
```

The Docker image runs as a non-root user, exposes Streamlit's built-in
`/_stcore/health` for orchestrator health checks, and stores the journal under
`/app/data` (mount a volume to persist).

## Configuration

All configuration is read from environment variables first, then from
`.streamlit/secrets.toml` if present. Copy `.env.example` to `.env` and fill in.

### Required for live Tastytrade quotes
- `TASTYTRADE_CLIENT_ID`
- `TASTYTRADE_CLIENT_SECRET`
- `TASTYTRADE_REFRESH_TOKEN`
- `TASTYTRADE_ENVIRONMENT` (default `production`)

Without these, the Options Cockpit stays in "Tastytrade pending" state and
falls back to delayed yfinance marks for review only.

> **Note on refresh tokens:** the provider now captures rotated refresh tokens
> from Tastytrade's OAuth response and logs a warning when rotation occurs.
> When you see that warning, update your secret store with the new value.

### Optional
- `OPENAI_API_KEY` — enables AI morning briefing
- `UNUSUAL_WHALES_API_KEY` — flow data
- `ECONOMIC_CALENDAR_API_URL`, `GEX_API_URL`, `SOCIAL_SENTIMENT_API_URL` — must be `https://` to a public host (private/loopback addresses are rejected)
- `JOURNAL_PATH` — override journal storage path (default `data/signal_journal.json`)
- `SENTRY_DSN` — enable error reporting to Sentry

## What it includes

- SPY hourly candle ingest (`yfinance`) with US/Central display normalization.
- **Prior-day H/L anchors** and dynamic line projection engines. *(These are
  prior-session high/low anchors with sloped projection — not classical floor
  pivots `(H+L+C)/3`. Earlier docs called them "pivots"; the math is the same,
  the naming is now accurate.)*
- Bias, signal, decision quality, and risk guardrails.
- Prophet Chart, Replay Lab, Options Cockpit, Journal Analytics.
- Options Cockpit uses live Tastytrade quotes when credentials are configured.

## Data sources

- **SPY candles**: `yfinance` (ET-aware; converted to US/Central for display).
- **Options quotes**: live Tastytrade when configured, with delayed yfinance
  fallback for mark-only review.
- No mock quote mode is used in the product app.

## Replay bias safety

- **Step Replay** hides future candles and signals by default.
- **Full Day Review** enables hindsight/outcome review.
- The "Show future outcome overlays" toggle in Step Replay surfaces target/stop
  hits computed against the full day; off by default.

## Auto-Journal

- Sidebar toggle: **Auto-journal live signals** (default OFF).
- Journal path: `JOURNAL_PATH` env var or `data/signal_journal.json`.
- Atomic write (tmp + fsync + rename); duplicate-safe upsert prevents rerun spam.
- Malformed JSON is backed up as `data/signal_journal.corrupt.YYYYMMDD_HHMMSS.json`
  with `0600` permissions; backups older than 30 days are pruned automatically.
- Backups themselves are gitignored.

## Operations

### Logging
The app uses Python's `logging` module (`logger = logging.getLogger("spyprophet")`).
Set `SPYPROPHET_LOG_LEVEL` (`DEBUG`/`INFO`/`WARNING`/`ERROR`) to control
verbosity. Default is `INFO`.

### Sentry
Set `SENTRY_DSN` to send unhandled exceptions and `logger.error/warning` to
Sentry. Tune sampling with `SENTRY_TRACES_SAMPLE_RATE` (default `0.0`, off).

### Health check
Streamlit serves `/_stcore/health` natively; the Dockerfile wires this into a
container `HEALTHCHECK` directive.

## Deployment notes

This app does not implement authentication. **Do not expose it publicly without
fronting it with an auth layer** (oauth2-proxy, Cloudflare Access, Streamlit's
native auth, basic-auth at a reverse proxy, etc.) — exposing port 8501 would
mean exposing the Tastytrade-authenticated session to anyone on the network.

For shared/multi-user hosting, the journal is currently a single shared file at
`JOURNAL_PATH`. Single-tenant deployment is the supported configuration; for
multi-tenant, namespace `JOURNAL_PATH` per user or migrate to a database.

## CI

GitHub Actions runs pytest against Python 3.11 and 3.12 on every push and PR
(`.github/workflows/ci.yml`). The same workflow performs a smoke `docker build`.

## Troubleshooting

- `ModuleNotFoundError`: reinstall requirements in active venv.
- Empty SPY data: yfinance occasionally returns empty payloads — retry, and
  check the logs for `fetch_spy_hourly failed`.
- Missing Tastytrade secrets: app reports the missing key names and leaves
  the Options Cockpit unavailable.
- Tastytrade auth failure: check `last_error` field in the cockpit status; the
  provider logs a warning when the refresh token rotates.

## Known limitations

- yfinance may have delays/gaps; halt bars (where `O==H==L==C`) are not
  currently filtered.
- Hourly candles cannot resolve intrabar target-vs-stop sequence.
- Option projection is delta-only (ignores gamma / IV / theta / liquidity / spread).
- Same-day option Greeks can change rapidly.
- NYSE holidays and half-days (1pm ET close) are not yet special-cased; the
  app trusts whatever bars yfinance returns.
