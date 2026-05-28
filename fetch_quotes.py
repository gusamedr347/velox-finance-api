"""
Fetch stock/forex/crypto quotes from Yahoo Finance (and Binance P2P for USDT)
and push them to a Zoho Creator Custom API endpoint in a single batched call.

Special case: the 'USDT' ticker is sourced from Binance's public P2P API
(USD/VES rate), since Yahoo doesn't carry a meaningful USDT/VES quote.

Environment variables:
    ZOHO_BATCH_URL — Custom API endpoint for receiveQuotesBatch (with ?publickey=...)
    ZOHO_LIST_URL  — Custom API endpoint for listTickers        (with ?publickey=...) [optional]
    TICKERS        — comma-separated fallback list if ZOHO_LIST_URL is unset or fails
"""

import os
import json
import sys
import time
from datetime import datetime, timezone

import requests
import yfinance as yf

from usdt_scraper import scrape_binance_rate


ZOHO_BATCH_URL = os.environ["ZOHO_BATCH_URL"]
ZOHO_LIST_URL  = os.environ.get("ZOHO_LIST_URL")


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def safe(v, default=0):
    try:
        if v is None or v != v:
            return default
        return v
    except Exception:
        return default


def safe_str(v, default=""):
    if v is None:
        return default
    try:
        s = str(v).strip()
        return s if s else default
    except Exception:
        return default


def fattr(fast_info, name, default=None):
    try:
        v = getattr(fast_info, name, None)
        if v is None or v != v:
            return default
        return v
    except Exception:
        return default


def epoch_to_iso(epoch):
    if epoch is None or epoch == "" or epoch == 0:
        return ""
    try:
        ts = int(epoch)
        return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    except Exception:
        return ""


def empty_payload(symbol: str) -> dict:
    """Skeleton payload with all fields zeroed/blank — starting point for non-Yahoo sources."""
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    return {
        "symbol": symbol,
        "bid": 0, "ask": 0, "last": 0, "volume": 0,
        "bidSize": 0, "askSize": 0,
        "avgVol52": 0, "high52": 0, "low52": 0,
        "fechaUltimo": now_iso, "barTime": today,
        "open": 0, "high": 0, "low": 0, "close": 0, "barVolume": 0,
        "change52WPct": 0, "regularChange": 0, "regularChangePct": 0,
        "sharesOutstanding": 0,
        "longName": "", "currency": "", "country": "",
        "fullExchangeName": "", "typeDisp": "",
        "beta": 0,
        "dividendDate": "", "dividendRate": 0, "dividendYield": 0,
    }


# ----------------------------------------------------------------------
# Ticker list from Zoho
# ----------------------------------------------------------------------

def get_tickers() -> list[str]:
    if ZOHO_LIST_URL:
        try:
            r = requests.get(ZOHO_LIST_URL, timeout=15)
            r.raise_for_status()
            outer = r.json()
            inner_str = outer.get("result", "{}")
            inner = json.loads(inner_str) if isinstance(inner_str, str) else inner_str
            symbols = inner.get("symbols", [])
            if symbols:
                print(f"Fetched {len(symbols)} tickers from Zoho")
                return symbols
            print("Zoho returned empty ticker list; falling back to TICKERS env var.", file=sys.stderr)
        except Exception as e:
            print(f"Failed to fetch tickers from Zoho: {e} — falling back to TICKERS env var.", file=sys.stderr)

    fallback = os.environ.get("TICKERS", "").split(",")
    return [s.strip() for s in fallback if s.strip()]


# ----------------------------------------------------------------------
# Source: Binance P2P (USDT/VES)
# ----------------------------------------------------------------------

def fetch_usdt() -> dict | None:
    try:
        rate = scrape_binance_rate()
        bid  = rate["compra"]
        ask  = rate["venta"]
        last = (bid + ask) / 2.0

        payload = empty_payload("USDT")
        payload.update({
            "bid":              bid,
            "ask":              ask,
            "last":             last,
            "open":             last,
            "high":             last,
            "low":              last,
            "close":            last,
            "longName":         "Tether USD / Venezuelan Bolivar (Binance P2P)",
            "currency":         "VES",
            "country":          "Venezuela",
            "fullExchangeName": "Binance P2P",
            "typeDisp":         "CRYPTOCURRENCY",
        })
        return payload
    except Exception as e:
        print(f"[USDT] fetch failed: {e}", file=sys.stderr)
        return None


# ----------------------------------------------------------------------
# Source: Yahoo Finance
# ----------------------------------------------------------------------

def fetch_one(symbol: str) -> dict | None:
    try:
        t = yf.Ticker(symbol)
        fi = t.fast_info

        last       = fattr(fi, "last_price")
        volume     = fattr(fi, "last_volume", 0)
        day_high   = fattr(fi, "day_high")
        day_low    = fattr(fi, "day_low")
        day_open   = fattr(fi, "open")
        prev_close = fattr(fi, "previous_close")
        high52     = fattr(fi, "year_high")
        low52      = fattr(fi, "year_low")
        avg_vol_52 = fattr(fi, "three_month_average_volume", 0)

        try:
            full = t.info or {}
        except Exception:
            full = {}

        bid      = safe(full.get("bid"))
        ask      = safe(full.get("ask"))
        bid_size = safe(full.get("bidSize"))
        ask_size = safe(full.get("askSize"))

        last       = safe(last       or full.get("regularMarketPrice"))
        volume     = safe(volume     or full.get("regularMarketVolume"))
        day_high   = safe(day_high   or full.get("regularMarketDayHigh"), last)
        day_low    = safe(day_low    or full.get("regularMarketDayLow"),  last)
        day_open   = safe(day_open   or full.get("regularMarketOpen"),    last)
        prev_close = safe(prev_close or full.get("regularMarketPreviousClose"))
        high52     = safe(high52     or full.get("fiftyTwoWeekHigh"))
        low52      = safe(low52      or full.get("fiftyTwoWeekLow"))
        avg_vol_52 = safe(avg_vol_52 or full.get("averageVolume"), 0)

        change_52w_pct      = safe(full.get("fiftyTwoWeekChangePercent"))
        regular_change      = safe(full.get("regularMarketChange"))
        regular_change_pct  = safe(full.get("regularMarketChangePercent"))
        shares_outstanding  = safe(full.get("sharesOutstanding"), 0)
        long_name           = safe_str(full.get("longName"))
        currency            = safe_str(full.get("currency"))
        country             = safe_str(full.get("country"))
        full_exchange_name  = safe_str(full.get("fullExchangeName"))
        type_disp           = safe_str(full.get("typeDisp"))
        beta                = safe(full.get("beta"))
        dividend_date_iso   = epoch_to_iso(full.get("dividendDate"))
        dividend_rate       = safe(full.get("dividendRate"))
        dividend_yield      = safe(full.get("dividendYield"))

        if not last:
            return None

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        return {
            "symbol":              symbol,
            "bid":                 bid,
            "ask":                 ask,
            "last":                last,
            "volume":              volume,
            "bidSize":             bid_size,
            "askSize":             ask_size,
            "avgVol52":            avg_vol_52,
            "high52":              high52,
            "low52":               low52,
            "fechaUltimo":         now_iso,
            "barTime":             today,
            "open":                day_open,
            "high":                day_high,
            "low":                 day_low,
            "close":               last,
            "barVolume":           volume,
            "change52WPct":        change_52w_pct,
            "regularChange":       regular_change,
            "regularChangePct":    regular_change_pct,
            "sharesOutstanding":   shares_outstanding,
            "longName":            long_name,
            "currency":            currency,
            "country":             country,
            "fullExchangeName":    full_exchange_name,
            "typeDisp":            type_disp,
            "beta":                beta,
            "dividendDate":        dividend_date_iso,
            "dividendRate":        dividend_rate,
            "dividendYield":       dividend_yield,
        }
    except Exception:
        return None


# ----------------------------------------------------------------------
# Dispatcher
# ----------------------------------------------------------------------

def fetch_symbol(symbol: str) -> dict | None:
    if symbol.upper() == "USDT":
        return fetch_usdt()
    return fetch_one(symbol)


# ----------------------------------------------------------------------
# Push to Zoho (single batched call)
# ----------------------------------------------------------------------

def push_batch_to_zoho(payloads: list[dict]) -> bool:
    try:
        r = requests.post(
            ZOHO_BATCH_URL,
            files={"payload": (None, json.dumps(payloads))},
            timeout=60,
        )
        print(f"Zoho batch {r.status_code}: {r.text[:300]}")
        return r.ok
    except Exception as e:
        print(f"Batch push failed: {e}", file=sys.stderr)
        return False


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------

def main():
    start = time.monotonic()

    tickers = get_tickers()
    if not tickers:
        print("No tickers to fetch.", file=sys.stderr)
        sys.exit(1)

    print(f"Fetching {len(tickers)} tickers at {datetime.now(timezone.utc).isoformat()}")

    payloads = []
    skipped_symbols = []

    for sym in tickers:
        sym = sym.strip()
        if not sym:
            continue
        data = fetch_symbol(sym)
        if data is None:
            skipped_symbols.append(sym)
        else:
            payloads.append(data)

    pushed_ok = push_batch_to_zoho(payloads) if payloads else False

    elapsed = time.monotonic() - start
    print(f"\nDone. fetched={len(payloads)} skipped={len(skipped_symbols)} "
          f"pushed={'ok' if pushed_ok else 'FAIL'} — took {elapsed:.1f}s")
    if skipped_symbols:
        print(f"Skipped (no data): {', '.join(skipped_symbols)}")

    if not pushed_ok and payloads:
        sys.exit(1)


if __name__ == "__main__":
    main()