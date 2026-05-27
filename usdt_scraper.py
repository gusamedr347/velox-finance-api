"""
Fetch Binance P2P USDT/VES exchange rates directly from Binance's public API.
This is the same endpoint Binance's own P2P page uses — no scraping, no CAPTCHA.
"""

import requests

API_URL = "https://p2p.binance.com/bapi/c2c/v2/friendly/c2c/adv/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/json",
    "Accept": "application/json",
}


def _query(trade_type: str, rows: int = 5) -> list[float]:
    """Query Binance P2P search. trade_type='BUY' or 'SELL'. Returns ad prices."""
    payload = {
        "asset":      "USDT",
        "fiat":       "VES",
        "tradeType":  trade_type,   # BUY = ads selling USDT (you buy)
        "page":       1,
        "rows":       rows,
        "payTypes":   [],
        "publisherType": None,
    }
    r = requests.post(API_URL, json=payload, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json()
    ads = data.get("data", []) or []
    return [float(ad["adv"]["price"]) for ad in ads if "adv" in ad and "price" in ad["adv"]]


def scrape_binance_rate() -> dict:
    """
    Returns the best Binance P2P USDT/VES rates:
      compra = best price for USER to BUY USDT (lowest 'SELL' ad on Binance)
      venta  = best price for USER to SELL USDT (highest 'BUY' ad on Binance)
    The function name is kept for compatibility with fetch_quotes.py.
    """
    # When user buys USDT, they look at SELL ads (people selling USDT) — pick the lowest price
    sell_prices = _query("SELL")
    # When user sells USDT, they look at BUY ads (people buying USDT) — pick the highest price
    buy_prices  = _query("BUY")

    if not sell_prices or not buy_prices:
        raise RuntimeError("Binance P2P returned no ads for USDT/VES")

    compra = min(sell_prices)   # cheapest seller
    venta  = max(buy_prices)    # highest bidder

    return {
        "compra": compra,
        "venta":  venta,
    }


if __name__ == "__main__":
    data = scrape_binance_rate()
    print(f"Compra: Bs. {data['compra']:.2f}")
    print(f"Venta:  Bs. {data['venta']:.2f}")
    print(f"Spread: Bs. {data['venta'] - data['compra']:.2f}")