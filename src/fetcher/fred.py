"""
FRED (Federal Reserve Economic Data) fetcher.
Provides macro-economic data: Treasury yields, credit spreads, VIX, PMI, etc.
Falls back to yfinance if FRED API key is not configured.
"""

import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
from typing import Dict, Any, Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import FRED_API_KEY, FRED_SERIES, CACHE_TTL
from src.fetcher.ssl_session import get_session

_session = get_session()


def _get_fred_client():
    """Try to create FRED client; returns None if key not set."""
    if not FRED_API_KEY:
        return None
    try:
        from fredapi import Fred
        return Fred(api_key=FRED_API_KEY)
    except Exception:
        return None


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def fetch_macro_data() -> Dict[str, Any]:
    """
    Fetch macro-economic data from FRED API (or fallback to yfinance).
    Returns dictionary of macro indicators.
    """
    data: Dict[str, Any] = {}
    fred = _get_fred_client()

    if fred:
        data = _fetch_from_fred(fred)
    else:
        data = _fetch_from_yfinance_fallback()

    # ── Derived ──────────────────────────────────────────
    t10 = data.get("treasury_10y")
    t2 = data.get("treasury_2y")
    if t10 is not None and t2 is not None:
        data["yield_spread"] = t10 - t2
        data["yield_curve_inverted"] = data["yield_spread"] < 0
    else:
        data["yield_spread"] = None
        data["yield_curve_inverted"] = None

    # ERP estimate: S&P earnings yield - 10Y Treasury
    try:
        sp = yf.Ticker("^GSPC", session=_session)
        sp_info = sp.info or {}
        sp_pe = sp_info.get("trailingPE", None)
        if sp_pe and t10 is not None:
            data["equity_risk_premium"] = (1 / sp_pe) - (t10 / 100)
        else:
            data["equity_risk_premium"] = 0.055  # fallback
    except Exception:
        data["equity_risk_premium"] = 0.055

    # VIX regime classification
    vix = data.get("vix")
    if vix is not None:
        if vix < 15:
            data["vix_regime"] = "Low Volatility (Complacent)"
        elif vix < 20:
            data["vix_regime"] = "Normal"
        elif vix < 30:
            data["vix_regime"] = "Elevated (Cautious)"
        else:
            data["vix_regime"] = "High Volatility (Fear)"
    else:
        data["vix_regime"] = "N/A"

    # Credit spread interpretation
    hy = data.get("hy_spread")
    if hy is not None:
        if hy < 3.5:
            data["credit_regime"] = "Tight (Risk-On)"
        elif hy < 5.0:
            data["credit_regime"] = "Normal"
        elif hy < 7.0:
            data["credit_regime"] = "Widening (Caution)"
        else:
            data["credit_regime"] = "Stressed (Risk-Off)"
    else:
        data["credit_regime"] = "N/A"

    return data


def _fetch_from_fred(fred) -> Dict[str, Any]:
    """Fetch data using FRED API."""
    data = {}
    for key, series_id in FRED_SERIES.items():
        try:
            s = fred.get_series(series_id)
            if s is not None and len(s) > 0:
                data[key] = float(s.dropna().iloc[-1])
            else:
                data[key] = None
        except Exception:
            data[key] = None
    return data


def _fetch_from_yfinance_fallback() -> Dict[str, Any]:
    """Fallback: use yfinance for key macro data."""
    data = {}

    # Treasury yields via ^TNX (10Y), ^IRX (13-week)
    try:
        tnx = yf.Ticker("^TNX", session=_session)
        h = tnx.history(period="5d")
        if h is not None and not h.empty:
            data["treasury_10y"] = float(h["Close"].iloc[-1])
        else:
            data["treasury_10y"] = None
    except Exception:
        data["treasury_10y"] = None

    # 2-Year Treasury - use ^TWO or estimate
    try:
        two = yf.Ticker("^TWO", session=_session)
        h = two.history(period="5d")
        if h is not None and not h.empty:
            data["treasury_2y"] = float(h["Close"].iloc[-1])
        else:
            data["treasury_2y"] = None
    except Exception:
        data["treasury_2y"] = None

    # VIX
    try:
        vix = yf.Ticker("^VIX", session=_session)
        h = vix.history(period="5d")
        if h is not None and not h.empty:
            data["vix"] = float(h["Close"].iloc[-1])
        else:
            data["vix"] = None
    except Exception:
        data["vix"] = None

    # Fed Funds, IG/HY spreads, consumer sentiment — not available via yfinance
    data["fed_funds"] = None
    data["ig_spread"] = None
    data["hy_spread"] = None
    data["consumer_sentiment"] = None

    return data


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def get_risk_free_rate() -> float:
    """Get current risk-free rate (10Y Treasury / 100)."""
    try:
        tnx = yf.Ticker("^TNX", session=_session)
        h = tnx.history(period="5d")
        if h is not None and not h.empty:
            return float(h["Close"].iloc[-1]) / 100.0
        return 0.043  # fallback
    except Exception:
        return 0.043
