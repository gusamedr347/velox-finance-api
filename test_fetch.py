"""
Standalone fetcher — pulls quote data from Yahoo via yfinance and prints it.
No Zoho calls. Useful for verifying tickers and seeing what data is available
before wiring up the full pipeline.

Usage:
    python test_fetch.py                    # uses default tickers below
    python test_fetch.py AAPL MSFT BVCC.CR  # uses CLI args instead
"""

import json
import sys
from datetime import datetime, timezone

import yfinance as yf

# Default tickers if no CLI args given
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA", "BVCC.CR"]


def safe(v, default=0):
    """Coerce None/NaN to default; otherwise return as-is."""
    try:
        if v is None or v != v:  # None or NaN
            return default
        return v
    except Exception:
        return default


def fattr(fast_info, name, default=None):
    """Safe attribute access on yfinance's FastInfo object."""
    try:
        v = getattr(fast_info, name, None)
        if v is None or v != v:
            return default
        return v
    except Exception:
        return default


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

        # Always fetch .info — fast_info doesn't include bid/ask/bidSize/askSize
        try:
            full = t.info or {}
        except Exception as e:
            print(f"[{symbol}] .info fetch failed: {e}", file=sys.stderr)
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

        if not last:
            print(f"[{symbol}] no price data returned — skipping", file=sys.stderr)
            return None

        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
        today   = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        return {
            "symbol":       symbol,
            "bid":          bid,
            "ask":          ask,
            "last":         last,
            "volume":       volume,
            "bidSize":      bid_size,
            "askSize":      ask_size,
            "previousClose": prev_close,
            "avgVol52":     avg_vol_52,
            "high52":       high52,
            "low52":        low52,
            "fechaUltimo":  now_iso,
            "barTime":      today,
            "open":         day_open,
            "high":         day_high,
            "low":          day_low,
            "close":        last,
            "barVolume":    volume,
        }
    except Exception as e:
        print(f"[{symbol}] fetch failed: {e}", file=sys.stderr)
        return None


def format_row(data: dict) -> str:
    """Pretty one-liner for terminal-friendly summary."""
    s = data["symbol"]
    return (
        f"  {s:<12} "
        f"last={data['last']:>10.2f}  "
        f"bid={data['bid']:>10.2f}  "
        f"ask={data['ask']:>10.2f}  "
        f"vol={data['volume']:>12,}  "
        f"52W=[{data['low52']:.2f}, {data['high52']:.2f}]"
    )


def main():
    tickers = sys.argv[1:] if len(sys.argv) > 1 else DEFAULT_TICKERS
    print(f"Fetching {len(tickers)} tickers at {datetime.now(timezone.utc).isoformat()}\n")

    results = []
    for sym in tickers:
        sym = sym.strip()
        if not sym:
            continue
        print(f"→ {sym} ...", end=" ", flush=True)
        data = fetch_one(sym)
        if data:
            print("ok")
            results.append(data)
        else:
            print("FAILED")

    print("\n=== Summary ===")
    for r in results:
        print(format_row(r))

    print("\n=== Full payloads (what would be sent to Zoho) ===")
    print(json.dumps(results, indent=2, default=str))

    print(f"\nDone. Fetched {len(results)} of {len(tickers)}.")


if __name__ == "__main__":
    main()