"""
Portfolio Fetcher — batch multi-ticker price download using yf.download().
In-memory cache with 4-hour TTL.
"""

import time
import numpy as np
import pandas as pd
import yfinance as yf
from typing import Dict, List, Optional

# ── In-memory cache ──────────────────────────────────────
_price_cache: Dict[str, dict] = {}
_CACHE_TTL = 14400  # 4 hours

BENCHMARKS = {
    "S&P 500 (SPY)": "SPY",
    "NASDAQ 100 (QQQ)": "QQQ",
    "Dow Jones (DIA)": "DIA",
    "Russell 2000 (IWM)": "IWM",
    "KOSPI (^KS11)": "^KS11",
    "KOSDAQ (^KQ11)": "^KQ11",
    "KODEX 200 (069500)": "069500.KS",
}


def _get_session():
    """Get SSL-safe session."""
    try:
        from src.fetcher.ssl_session import get_session
        return get_session()  # may be None on Cloud
    except Exception:
        return None


def fetch_multi_history(
    tickers: List[str],
    start: str,
    end: str,
) -> Optional[pd.DataFrame]:
    """
    Fetch daily Close prices for multiple tickers in one batch.

    Returns
    -------
    pd.DataFrame with DatetimeIndex, columns = ticker symbols, values = Close price.
    Missing dates are forward-filled.  Returns None on failure.
    """
    cache_key = f"{'_'.join(sorted(tickers))}_{start}_{end}"
    cached = _price_cache.get(cache_key)
    if cached and (time.time() - cached.get("_ts", 0)) < _CACHE_TTL:
        return cached["data"]

    try:
        session = _get_session()
        dl_kwargs = dict(
            tickers=tickers,
            start=start,
            end=end,
            interval="1d",
            auto_adjust=True,
            progress=False,
        )
        if session is not None:
            dl_kwargs["session"] = session
        raw = yf.download(**dl_kwargs)
        if raw is None or raw.empty:
            return None

        # yf.download returns MultiIndex columns (Price, Ticker) for multiple tickers
        if isinstance(raw.columns, pd.MultiIndex):
            prices = raw["Close"] if "Close" in raw.columns.get_level_values(0) else raw.xs("Close", axis=1, level=0)
        else:
            # Single ticker
            prices = raw[["Close"]].rename(columns={"Close": tickers[0]})

        # Forward-fill missing dates, drop any all-NaN rows
        prices = prices.ffill().dropna(how="all")

        # Ensure columns are strings
        prices.columns = [str(c) for c in prices.columns]

        _price_cache[cache_key] = {"data": prices, "_ts": time.time()}
        return prices

    except Exception:
        return None


def fetch_benchmark(name: str, start: str, end: str) -> Optional[pd.Series]:
    """Fetch a single benchmark price series."""
    ticker = BENCHMARKS.get(name, name)
    df = fetch_multi_history([ticker], start, end)
    if df is not None and ticker in df.columns:
        return df[ticker].dropna()
    return None


def fetch_benchmarks(names: List[str], start: str, end: str) -> pd.DataFrame:
    """Fetch multiple benchmarks at once."""
    tickers = [BENCHMARKS.get(n, n) for n in names]
    df = fetch_multi_history(tickers, start, end)
    if df is None:
        return pd.DataFrame()
    # Rename columns to friendly names
    rename_map = {v: k for k, v in BENCHMARKS.items() if v in df.columns}
    return df.rename(columns=rename_map)
