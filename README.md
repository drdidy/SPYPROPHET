# SPY Prophet

SPY Prophet is an **analysis-only** Streamlit terminal for SPY 0DTE structure workflows.

## Quick Start
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m pytest -q
streamlit run app.py
```

## What it includes
- SPY hourly data ingest (`yfinance`) with US/Central normalization.
- Prior-day pivot and dynamic line projection engines.
- Bias, signal, decision quality, risk guardrails.
- Prophet Chart, Replay Lab, Options Cockpit, Journal Analytics.
- Mock options mode + optional Tastytrade quote mode.

## Tastytrade secrets (optional)
Create `.streamlit/secrets.toml` locally:

```toml
TASTYTRADE_CLIENT_ID = "your_client_id"
TASTYTRADE_CLIENT_SECRET = "your_client_secret"
TASTYTRADE_REFRESH_TOKEN = "your_refresh_token"
TASTYTRADE_ENVIRONMENT = "production"
```

- Missing secrets => safe fallback to MOCK provider.
- Never commit secrets.

## Modes
- **MOCK**: deterministic fake quote data for UI/testing.
- **TASTYTRADE**: live quote attempt; falls back to MOCK on failure.

## Replay bias safety
- **Step Replay** hides future candles/signals by default.
- **Full Day Review** enables hindsight/outcome review.

## Auto-Journal
- Sidebar toggle: **Auto-journal live signals** (default OFF).
- Journal path: `data/signal_journal.json`.
- Duplicate-safe upsert prevents rerun spam.
- Malformed JSON is backed up as `data/signal_journal.corrupt.YYYYMMDD_HHMMSS.json`.

## Troubleshooting
- `ModuleNotFoundError: pandas` (or others): reinstall requirements in active venv.
- Empty SPY data: retry and verify network/data availability.
- Missing secrets: app reports missing key names and uses MOCK fallback.
- Tastytrade failures: app reports provider error and uses MOCK fallback.

## Known limitations
- yfinance may have delays/gaps.
- Hourly candles cannot resolve intrabar target-vs-stop sequence.
- Option projection is delta-only (ignores gamma/IV/theta/liquidity/spread).
- 0DTE Greeks can change rapidly.
- Mock quotes are not live market data.

## Safety
**No order execution is implemented.**
No submit/cancel/replace/dry-run trading functions are provided.
