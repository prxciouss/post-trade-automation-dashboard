#Generate Trades ############################################################################################################################################################

# ABOUT: This script builds the simulated trade blotter the rest of the project runs on.
# It creates 150+ trades spread across 4 asset classes (Equity, Fixed Income, FX,
# Commodity), each with the operational fields the original v1 project had (trade_id,
# client_name, status, settlement_date, issue_type, owner, priority) PLUS 7 new fields
# (asset_class, product, side, quantity, price, notional, trade_date).
#
# WHAT'S NEW IN THIS VERSION vs v1:
# 1. price is no longer a random number - it comes from REAL historical market data
#    (see fetch_market_data.py), with a small random jitter to represent the difference
#    between the day's closing print and the actual execution price.
# 2. status is now a 5-STAGE LIFECYCLE (Executed -> Validated -> Pending Settlement ->
#    Settled / Failed) instead of a flat 3-value status. Each trade also gets a set of
#    REAL TIMESTAMPS recording when it moved through each stage it reached - these are
#    saved separately in Data/lifecycle_events.csv and used to calculate average
#    time-to-settlement in post_trade_automation.py.
#
# Two output files:
#   Data/trades.csv           -> one row per trade (14 columns total)
#   Data/lifecycle_events.csv -> one row per (trade, stage) the trade actually reached

#Libraries ############################################################################################################################################################
import os
import pandas as pd
import random
from datetime import timedelta, datetime, time

from fetch_market_data import (
    MARKET_UNIVERSE,
    PRODUCT_DISPLAY_NAMES,
    load_cached_market_prices,
    fetch_and_cache_market_prices,
)

#Reproducibility ############################################################################################################################################################
# Fixing the random seed means re-running this script produces the SAME simulated
# blotter every time, which makes the numbers on my CV stable rather than shifting
# every time I regenerate the data for a demo.
random.seed(42)

#Configuration ############################################################################################################################################################
NUMBER_OF_TRADES = 160
    # comfortably over the "150+" figure quoted on my CV

CLIENTS = [
    "Barclays", "HSBC", "Citi", "JPMorgan", "Goldman Sachs",
    "Deutsche Bank", "UBS", "Morgan Stanley",
]

OWNERS = ["Aisha", "James", "Sarah", "Michael", "Olusegun", "Priya"]

PRIORITIES = ["Low", "Medium", "High"]
PRIORITY_WEIGHTS = [0.45, 0.35, 0.20]
    # skewed so most trades are Low/Medium priority, like a real desk

SIDES = ["Buy", "Sell"]

# 5-stage lifecycle. A trade either makes it all the way to Settled, or it
# diverts to Failed at some point along the way.
LIFECYCLE_STAGES = ["Executed", "Validated", "Pending Settlement", "Settled"]
STATUS_OPTIONS = ["Executed", "Validated", "Pending Settlement", "Settled", "Failed"]
    # the actual weights used to pick a status are chosen further down, conditional
    # on whether each trade's settlement date has arrived yet - see generate_trades()

ISSUE_TYPES_FOR_FAILED_TRADES = [
    "Missing confirmation",
    "Price mismatch",
    "Duplicate trade",
    "Settlement instruction error",
    "Counterparty rejection",
    "Insufficient collateral",
]

# Rough quantity ranges per asset class, chosen so the resulting notionals
# (quantity * price) look like plausible trade sizes for that asset class.
QUANTITY_RANGES = {
    "Equity": (50, 5000),               # shares
    "Fixed Income": (100, 20000),       # ETF units, standing in for bond nominal
    "FX": (100000, 5000000),            # currency units - FX trades in large notionals
    "Commodity": (1, 500),              # contracts/lots
}

# Approximate fallback price anchors, ONLY used if neither a cached nor a fresh
# real-data fetch is available (e.g. running fully offline with no prior cache).
# These are not live prices - they exist purely so the project still runs end to
# end for a demo with no internet connection, with a small random walk applied.
FALLBACK_PRICE_ANCHORS = {
    "AAPL": 200, "MSFT": 420, "GOOGL": 175, "AMZN": 185, "JPM": 210, "GS": 480,
    "BARC.L": 2.85, "HSBA.L": 6.80,
    "TLT": 90, "IEF": 95, "LQD": 108, "HYG": 78, "AGG": 98,
    "EURUSD=X": 1.08, "GBPUSD=X": 1.27, "USDJPY=X": 155, "GBPEUR=X": 1.17,
    "AUDUSD=X": 0.65, "USDCHF=X": 0.88,
    "GC=F": 2400, "CL=F": 78, "SI=F": 29, "NG=F": 2.5, "HG=F": 4.3,
}

TRADE_ID_PREFIX = "T"

#Market data loading ############################################################################################################################################################

def get_market_prices():
    """
    Tries the cached CSV first (fast, offline-friendly). If it doesn't exist,
    tries a fresh live fetch. If BOTH fail (e.g. no internet and no cache yet),
    returns None and generate_trades.py falls back to simulated prices, printing
    a clear warning so it's obvious in the console output which mode was used.
    """
    market_prices_df = load_cached_market_prices()

    if market_prices_df is not None:
        print(f"Loaded {len(market_prices_df)} cached real market price rows from Data/market_prices.csv")
        return market_prices_df

    print("No cached market prices found - attempting a live fetch from Yahoo Finance...")
    try:
        return fetch_and_cache_market_prices()
    except Exception as fetch_error:
        print(f"Live fetch failed ({fetch_error}).")
        print("Falling back to SIMULATED prices for this run - see FALLBACK_PRICE_ANCHORS.")
        print("Run 'python fetch_market_data.py' when you have internet access to use real data.")
        return None


def pick_product(asset_class):
    return random.choice(MARKET_UNIVERSE[asset_class])


TODAY = pd.Timestamp.today().normalize()
RECENCY_HALF_LIFE_DAYS = 10
    # controls how strongly trade_date sampling favours recent days - see
    # pick_price_and_date(). A ~10 day half-life means most trades are booked in
    # roughly the last couple of weeks (like a live trading book), with a longer
    # tail reaching back across the full price history for variety.


def pick_price_and_date(product, asset_class, market_prices_df):
    """
    Returns (trade_date, price) for a given product.

    If real market data is available, picks a REAL trading day for that product
    and uses that day's real close price, with a small execution jitter. Trading
    days are sampled with a RECENCY BIAS (most likely to be recent) rather than
    uniformly across the whole 6 months - this matters later on, because it means
    most trades are recent enough that whether they've reached their settlement
    date yet is a genuine toss-up, rather than every trade being from months ago
    and therefore automatically overdue if it hasn't settled.

    Falls back to a simulated price anchor with a random walk if no real data
    is available at all.
    """
    if market_prices_df is not None:
        product_prices = market_prices_df[market_prices_df["product"] == product]

        if not product_prices.empty:
            days_ago = (TODAY - product_prices["trade_date"]).dt.days.clip(lower=0)
            recency_weights = (0.5 ** (days_ago / RECENCY_HALF_LIFE_DAYS)).to_numpy()
                # exponential decay -> a day twice the half-life away is 1/4 as likely to be picked

            row = product_prices.sample(1, weights=recency_weights).iloc[0]
            trade_date = row["trade_date"]
            real_close_price = row["close_price"]

            # Simulate the trade executing slightly off the day's closing print
            # (real trades don't all happen exactly at the market close)
            execution_jitter = random.uniform(-0.002, 0.002)
                # +/- 0.2%
            price = round(real_close_price * (1 + execution_jitter), 4)

            return trade_date, price

    # --- Fallback path: no real data available at all ---
    days_ago = min(random.expovariate(1 / RECENCY_HALF_LIFE_DAYS), 90)
        # exponential distribution -> same recency bias as the real-data path above
    trade_date = TODAY - timedelta(days=int(days_ago))
    anchor_price = FALLBACK_PRICE_ANCHORS.get(product, 100)
    simulated_jitter = random.uniform(-0.05, 0.05)
        # +/- 5% random walk around the anchor, since there's no real reference price
    price = round(anchor_price * (1 + simulated_jitter), 4)

    return trade_date, price


#Lifecycle timestamp generation ############################################################################################################################################################

def build_lifecycle_timestamps(trade_date, final_status):
    """
    Builds a dict of {stage: timestamp} for every stage the trade actually reached,
    based on its final status. Returns (timestamps_dict, settlement_completed_timestamp)
    where settlement_completed_timestamp is only set for Settled trades (used later
    for the average time-to-settlement KPI).
    """
    # Trade "happens" at some point during the business day it was booked
    executed_time = datetime.combine(
        trade_date.date() if hasattr(trade_date, "date") else trade_date,
        time(hour=random.randint(8, 16), minute=random.randint(0, 59)),
    )

    timestamps = {"Executed": executed_time}
    current_time = executed_time

    if final_status == "Failed":
        # A failed trade can fail right after Executed, or later in the pipeline
        # (e.g. it passed validation but then failed at settlement)
        failure_point = random.choices(
            ["Executed", "Validated", "Pending Settlement"],
            weights=[0.3, 0.4, 0.3],
        )[0]

        if failure_point in ["Validated", "Pending Settlement"]:
            current_time += timedelta(minutes=random.randint(30, 240))
            timestamps["Validated"] = current_time

        if failure_point == "Pending Settlement":
            current_time += timedelta(hours=random.randint(2, 20))
            timestamps["Pending Settlement"] = current_time

        current_time += timedelta(hours=random.randint(1, 24))
        timestamps["Failed"] = current_time

        return timestamps, None

    # Otherwise, walk forward through however much of the happy path was reached
    stage_index = LIFECYCLE_STAGES.index(final_status)

    if stage_index >= 1:
        current_time += timedelta(minutes=random.randint(30, 240))
        timestamps["Validated"] = current_time

    if stage_index >= 2:
        current_time += timedelta(hours=random.randint(2, 20))
        timestamps["Pending Settlement"] = current_time

    if stage_index >= 3:
        current_time += timedelta(hours=random.randint(12, 48))
        timestamps["Settled"] = current_time

    settled_timestamp = timestamps.get("Settled")

    return timestamps, settled_timestamp


#Main generation loop ############################################################################################################################################################

def generate_trades():
    market_prices_df = get_market_prices()

    trades = []
    lifecycle_events = []

    for i in range(1, NUMBER_OF_TRADES + 1):
        trade_id = f"{TRADE_ID_PREFIX}{i:04d}"

        asset_class = random.choice(list(MARKET_UNIVERSE.keys()))
        product = pick_product(asset_class)
        product_name = PRODUCT_DISPLAY_NAMES.get(product, product)

        trade_date, price = pick_price_and_date(product, asset_class, market_prices_df)

        side = random.choice(SIDES)

        min_qty, max_qty = QUANTITY_RANGES[asset_class]
        quantity = random.randint(min_qty, max_qty)

        # NOTE on FX notional: real FX trades are sized by the DEALT currency amount
        # itself (e.g. "buy GBP 2,000,000 vs USD"), not by amount * rate - the rate
        # just tells you the other currency leg. quantity for FX already represents
        # that dealt amount, so notional = quantity directly. For every other asset
        # class, notional = quantity * price (shares * share price, contracts *
        # contract price, etc), which is the standard convention there.
        # Flagged in the README's Limitations & Simplifications section.
        if asset_class == "FX":
            notional = round(float(quantity), 2)
        else:
            notional = round(quantity * price, 2)

        client_name = random.choice(CLIENTS)

        # ~8% chance of a missing owner, to exercise the "Missing Owners" validation check
        owner = random.choice(OWNERS) if random.random() > 0.08 else None

        priority = random.choices(PRIORITIES, weights=PRIORITY_WEIGHTS)[0]

        # Standard T+2 settlement convention (a simplification - real settlement
        # cycles vary by asset class and market, e.g. FX spot is typically T+2 but
        # some markets have moved to T+1)
        trade_date_ts = pd.Timestamp(trade_date)
        settlement_date = trade_date_ts + pd.tseries.offsets.BusinessDay(2)

        # Status depends on whether the trade's settlement date has arrived yet -
        # a trade can't realistically be "Settled" before its settlement date is
        # even due. This is what makes "Overdue" a meaningful subset of
        # "Outstanding" later on, rather than the two measures being identical:
        #   - settlement not yet due  -> still working through the pipeline
        #     (Executed/Validated/Pending Settlement), NOT overdue
        #   - settlement date has passed -> mostly Settled or Failed by now, but
        #     a small share are still stuck in the pipeline -> genuinely OVERDUE
        settlement_is_due = settlement_date <= TODAY

        if settlement_is_due:
            status = random.choices(
                STATUS_OPTIONS,
                weights=[0.03, 0.035, 0.035, 0.72, 0.18],
                    # [Executed, Validated, Pending Settlement, Settled, Failed]
            )[0]
        else:
            status = random.choices(
                ["Executed", "Validated", "Pending Settlement"],
                weights=[0.35, 0.35, 0.30],
            )[0]

        issue_type = (
            random.choice(ISSUE_TYPES_FOR_FAILED_TRADES) if status == "Failed" else None
        )

        # ~4% chance of a missing settlement date, to exercise that validation check
        if random.random() < 0.04:
            settlement_date = pd.NaT

        lifecycle_timestamps, _ = build_lifecycle_timestamps(trade_date_ts, status)
        for stage, stage_timestamp in lifecycle_timestamps.items():
            lifecycle_events.append({
                "trade_id": trade_id,
                "stage": stage,
                "timestamp": stage_timestamp,
            })

        trades.append({
            "trade_id": trade_id,
            "client_name": client_name,
            "status": status,
            "settlement_date": settlement_date,
            "issue_type": issue_type,
            "owner": owner,
            "priority": priority,
            "asset_class": asset_class,
            "product": product_name,
            "side": side,
            "quantity": quantity,
            "price": price,
            "notional": notional,
            "trade_date": trade_date_ts.date(),
        })

    trades_df = pd.DataFrame(trades)
    lifecycle_df = pd.DataFrame(lifecycle_events)

    # Deliberately inject a handful of duplicate trade_ids so the "Duplicate Trade
    # IDs" validation check has something to actually catch (mirrors v1's sample data,
    # which had one duplicate row on purpose)
    duplicate_rows = trades_df.sample(n=4, random_state=1)
    trades_df = pd.concat([trades_df, duplicate_rows], ignore_index=True)

    # Make sure the Data/ folder exists before writing into it - a fresh clone of
    # the repo won't have it, since git doesn't track empty directories
    os.makedirs("Data", exist_ok=True)
    trades_df.to_csv("Data/trades.csv", index=False)
    lifecycle_df.to_csv("Data/lifecycle_events.csv", index=False)

    print(f"\nGenerated {len(trades_df)} trade rows (including {len(duplicate_rows)} intentional duplicates)")
    print(f"Saved to Data/trades.csv and Data/lifecycle_events.csv")
    print("\nBreakdown by asset class:")
    print(trades_df["asset_class"].value_counts())
    print("\nBreakdown by status:")
    print(trades_df["status"].value_counts())

    return trades_df, lifecycle_df


if __name__ == "__main__":
    generate_trades()
