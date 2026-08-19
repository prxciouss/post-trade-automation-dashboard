#Fetch Market Data ############################################################################################################################################################

# ABOUT: This script pulls REAL historical daily closing prices from Yahoo Finance
# (via the yfinance library) for a fixed universe of instruments - one small basket
# per asset class - and saves them to Data/market_prices.csv.
#
# WHY THIS EXISTS: generate_trades.py needs a source of realistic prices. Rather than
# making every price up with random.uniform(), this script gives us real market prices
# that actually happened, so trade notionals in the simulation look like something a
# real desk would see, not just noise.
#
# WHY IT'S A SEPARATE SCRIPT (not just called inline from generate_trades.py every run):
# 1. Network calls are slow and can fail (no wifi, firewalled network, Yahoo rate-limits
#    you, etc). Fetching once and caching to CSV means generate_trades.py always works,
#    even offline - which matters if I'm demoing this project somewhere without wifi.
# 2. It keeps the trade generation reproducible - re-running generate_trades.py multiple
#    times uses the SAME price history, not a fresh (possibly different) download.
#
# HOW TO USE:
#   python fetch_market_data.py
# This creates/refreshes Data/market_prices.csv. You only need to re-run it occasionally
# (e.g. if the cached prices get too old) - generate_trades.py will tell you if the
# cache is missing.

#Libraries ############################################################################################################################################################
import os
import pandas as pd
import yfinance as yf
    # yfinance -> free wrapper around Yahoo Finance's public data, used here purely
    # for historical price *lookups*, not live trading

#Universe of instruments ############################################################################################################################################################
# One small, realistic basket per asset class. Tickers are real, tradable instruments.
#
# NOTE on Fixed Income: Yahoo Finance doesn't provide free per-bond OTC prices (real
# bond desks trade over the phone/via dealers, not on a public exchange feed), so as a
# simplification I'm using well-known bond ETFs as a PRICE PROXY for this asset class.
# This is flagged in the README's "Limitations & Simplifications" section - it's a
# deliberate simplification, not an oversight.
MARKET_UNIVERSE = {
    "Equity": ["AAPL", "MSFT", "GOOGL", "AMZN", "JPM", "GS", "BARC.L", "HSBA.L"],
    "Fixed Income": ["TLT", "IEF", "LQD", "HYG", "AGG"],
        # TLT/IEF = US Treasury ETFs, LQD/HYG = corporate bond ETFs, AGG = broad bond market
    "FX": ["EURUSD=X", "GBPUSD=X", "USDJPY=X", "GBPEUR=X", "AUDUSD=X", "USDCHF=X"],
    "Commodity": ["GC=F", "CL=F", "SI=F", "NG=F", "HG=F"],
        # GC=Gold, CL=Crude Oil (WTI), SI=Silver, NG=Natural Gas, HG=Copper - all futures
}

# Friendly display names, because "BARC.L" means nothing to a reader of the dashboard
PRODUCT_DISPLAY_NAMES = {
    "AAPL": "Apple Inc.", "MSFT": "Microsoft Corp.", "GOOGL": "Alphabet Inc.",
    "AMZN": "Amazon.com Inc.", "JPM": "JPMorgan Chase & Co.", "GS": "Goldman Sachs Group",
    "BARC.L": "Barclays PLC", "HSBA.L": "HSBC Holdings PLC",
    "TLT": "iShares 20+yr Treasury Bond ETF", "IEF": "iShares 7-10yr Treasury Bond ETF",
    "LQD": "iShares Investment Grade Corp Bond ETF", "HYG": "iShares High Yield Corp Bond ETF",
    "AGG": "iShares Core US Aggregate Bond ETF",
    "EURUSD=X": "EUR/USD", "GBPUSD=X": "GBP/USD", "USDJPY=X": "USD/JPY",
    "GBPEUR=X": "GBP/EUR", "AUDUSD=X": "AUD/USD", "USDCHF=X": "USD/CHF",
    "GC=F": "Gold Futures", "CL=F": "WTI Crude Oil Futures", "SI=F": "Silver Futures",
    "NG=F": "Natural Gas Futures", "HG=F": "Copper Futures",
}

CACHE_PATH = "Data/market_prices.csv"
LOOKBACK_PERIOD = "6mo"
    # 6 months gives plenty of trading days to sample trade_dates from, with buffer


def fetch_and_cache_market_prices(cache_path=CACHE_PATH, period=LOOKBACK_PERIOD):
    """
    Downloads real historical daily closing prices for every ticker in
    MARKET_UNIVERSE and writes them to a single long-format CSV:
        trade_date, asset_class, product, product_name, close_price

    Returns the resulting DataFrame. Raises if the download fails (caller decides
    what to do - see generate_trades.py, which falls back to simulated prices).
    """
    all_rows = []
    MAX_ATTEMPTS_PER_ASSET_CLASS = 3
        # Yahoo Finance occasionally times out on a single ticker (slow wifi, rate
        # limiting, etc) - retrying a couple of times clears most of these up
        # without needing any manual intervention

    for asset_class, tickers in MARKET_UNIVERSE.items():
        print(f"Fetching {asset_class} prices for: {tickers}")

        history = None
        for attempt in range(1, MAX_ATTEMPTS_PER_ASSET_CLASS + 1):
            try:
                # yf.download can take a list of tickers at once - much faster
                # than one-by-one
                attempt_history = yf.download(
                    tickers,
                    period=period,
                    interval="1d",
                    progress=False,
                    auto_adjust=True,
                        #auto_adjust=True -> adjusts Close for splits/dividends, gives one clean "Close" column
                    timeout=30,
                )
                if not attempt_history.empty:
                    history = attempt_history
                    break
                print(f"  Attempt {attempt}/{MAX_ATTEMPTS_PER_ASSET_CLASS}: no data came back, retrying...")
            except Exception as download_error:
                print(f"  Attempt {attempt}/{MAX_ATTEMPTS_PER_ASSET_CLASS} failed ({download_error}), retrying...")

        if history is None:
            # This asset class didn't come back after retrying - rather than
            # abandoning the WHOLE fetch (and losing the asset classes that DID
            # work), skip it and carry on. generate_trades.py falls back to
            # simulated prices only for the specific products missing from the cache.
            print(f"  Giving up on {asset_class} for this run - will use simulated fallback prices for it instead.")
            continue

        # When you pass a LIST of tickers, yfinance returns MultiIndex columns
        # e.g. history["Close"]["AAPL"]. When only one ticker resolves, this
        # still works because yfinance keeps the MultiIndex for consistency
        # as long as we always pass a list (even a list of 1).
        close_prices = history["Close"]

        for ticker in tickers:
            if ticker not in close_prices.columns:
                print(f"  WARNING: no data came back for {ticker}, skipping it")
                continue

            ticker_series = close_prices[ticker].dropna()

            for trade_date, price in ticker_series.items():
                all_rows.append({
                    "trade_date": trade_date.date(),
                    "asset_class": asset_class,
                    "product": ticker,
                    "product_name": PRODUCT_DISPLAY_NAMES.get(ticker, ticker),
                    "close_price": round(float(price), 4),
                })

    if not all_rows:
        raise ValueError("No market data could be fetched for ANY asset class - check your internet connection.")

    market_prices_df = pd.DataFrame(all_rows)

    # Make sure the Data/ folder actually exists before writing into it - a fresh
    # clone of the repo won't have it, since git doesn't track empty directories
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    market_prices_df.to_csv(cache_path, index=False)
    print(f"\nSaved {len(market_prices_df)} price rows to {cache_path}")

    return market_prices_df


def load_cached_market_prices(cache_path=CACHE_PATH):
    """
    Loads the cached CSV if it exists. Returns None (not an error) if it doesn't -
    the caller decides whether to fetch fresh data or fall back to simulated prices.
    """
    try:
        market_prices_df = pd.read_csv(cache_path, parse_dates=["trade_date"])
        return market_prices_df
    except FileNotFoundError:
        return None


if __name__ == "__main__":
    # Running this file directly refreshes the cache.
    fetch_and_cache_market_prices()