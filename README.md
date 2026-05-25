# velox-trading-fetcher

Fetches stock, forex, and crypto quotes from Yahoo Finance and pushes them to a Zoho Creator app for storage and charting. Runs every 15 minutes via GitHub Actions.

## How it works

```
GitHub Actions (cron */15 * * * *)
        ↓
fetch_quotes.py
   ├─ GET  Zoho listTickers API   → list of symbols to fetch
   ├─ yfinance                    → bid, ask, last, volume, 52W range
   └─ POST Zoho receiveQuote API  → upserts into Yahoo_Finance + Price_History
```

The ticker list is managed in Zoho (form: `Productos Add`, field: `Codigo_Producto`). Add or remove rows there to control what gets fetched — no code changes needed.

## Files

- `fetch_quotes.py` — main script
- `test_fetch.py` — local-only diagnostic, prints payloads without touching Zoho
- `requirements.txt` — Python dependencies (`yfinance`, `requests`)
- `.github/workflows/fetch.yml` — GitHub Actions schedule + runner config

## Required secrets

Set under repo **Settings → Secrets and variables → Actions**:

| Name | Purpose |
|---|---|
| `ZOHO_URL` | `receiveQuote` Custom API endpoint (incl. `?publickey=...`) |
| `ZOHO_LIST_URL` | `listTickers` Custom API endpoint (incl. `?publickey=...`) |
| `TICKERS` | Fallback comma-separated ticker list if Zoho is unreachable |

## Local development

```bash
python -m venv .venv
source .venv/bin/activate          # or .venv\Scripts\Activate.ps1 on Windows
pip install -r requirements.txt

# Dry-run (no Zoho calls)
python test_fetch.py AAPL MSFT BVCC.CR

# Full run (writes to Zoho)
export ZOHO_URL="https://www.zohoapis.com/creator/custom/.../receiveQuote?publickey=..."
export ZOHO_LIST_URL="https://www.zohoapis.com/creator/custom/.../listTickers?publickey=..."
python fetch_quotes.py
```

## Notes

- Symbols not found on Yahoo (internal codes, dead tickers) are skipped silently.
- Bid/ask are populated only during the respective market's open hours.
- `Price_History` accumulates one row per ticker per trading day; a Zoho-side daily workflow prunes rows older than 2 years.
- GitHub Actions cron is best-effort — actual run intervals can drift 5-30 min during high load.
- A `.heartbeat` file is committed on each run to prevent GitHub auto-disabling the schedule after 60 days of inactivity.
