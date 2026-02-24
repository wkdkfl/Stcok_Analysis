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
def fetch_macro_data(market: str = "US") -> Dict[str, Any]:
    """
    Fetch macro-economic data from FRED API (or fallback to yfinance).
    For Korean market, fetches Korean macro indicators.
    Returns dictionary of macro indicators.
    """
    if market == "KR":
        return _fetch_korean_macro()

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
def get_risk_free_rate(market: str = "US") -> float:
    """Get current risk-free rate. US: 10Y Treasury / KR: ~3.5% fallback."""
    if market == "KR":
        return 0.035  # 한국 국고채 10년물 근사값
    try:
        tnx = yf.Ticker("^TNX", session=_session)
        h = tnx.history(period="5d")
        if h is not None and not h.empty:
            return float(h["Close"].iloc[-1]) / 100.0
        return 0.043  # fallback
    except Exception:
        return 0.043


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _fetch_korean_macro() -> Dict[str, Any]:
    """
    Fetch Korean macro indicators via yfinance (KOSPI index, etc.).
    BOK ECOS API 없이도 기본적인 한국 매크로 환경을 제공합니다.
    """
    data: Dict[str, Any] = {}

    # KOSPI 지수
    try:
        kospi = yf.Ticker("^KS11", session=_session)
        h = kospi.history(period="5d")
        if h is not None and not h.empty:
            data["kospi_level"] = float(h["Close"].iloc[-1])
    except Exception:
        data["kospi_level"] = None

    # KOSDAQ 지수
    try:
        kosdaq = yf.Ticker("^KQ11", session=_session)
        h = kosdaq.history(period="5d")
        if h is not None and not h.empty:
            data["kosdaq_level"] = float(h["Close"].iloc[-1])
    except Exception:
        data["kosdaq_level"] = None

    # 한국 관련 지표 (고정 근사값 — BOK ECOS API 연동 시 동적 업데이트 가능)
    data["treasury_10y"] = 3.5       # 국고채 10년물 (근사)
    data["treasury_2y"] = 3.2        # 국고채 2년물 (근사)
    data["yield_spread"] = 0.3
    data["yield_curve_inverted"] = False
    data["bok_base_rate"] = 3.0      # 한은 기준금리 (근사)
    data["fed_funds"] = data["bok_base_rate"]  # 매크로 레짐 호환용

    # VIX 대용 — CBOE VIX를 참고 지표로 폴백
    try:
        vix = yf.Ticker("^VIX", session=_session)
        h = vix.history(period="5d")
        if h is not None and not h.empty:
            data["vix"] = float(h["Close"].iloc[-1])
    except Exception:
        data["vix"] = None

    # VIX regime
    vix_val = data.get("vix")
    if vix_val is not None:
        if vix_val < 15:
            data["vix_regime"] = "Low Volatility (안정)"
        elif vix_val < 20:
            data["vix_regime"] = "Normal (보통)"
        elif vix_val < 30:
            data["vix_regime"] = "Elevated (경계)"
        else:
            data["vix_regime"] = "High Volatility (공포)"
    else:
        data["vix_regime"] = "N/A"

    # 신용 스프레드 — 한국 데이터 미지원, N/A 처리
    data["ig_spread"] = None
    data["hy_spread"] = None
    data["credit_regime"] = "N/A"
    data["consumer_sentiment"] = None

    # ERP — KOSPI P/E 기반 추정
    try:
        kospi_info = yf.Ticker("^KS11", session=_session).info or {}
        kospi_pe = kospi_info.get("trailingPE", None)
        if kospi_pe and data.get("treasury_10y") is not None:
            data["equity_risk_premium"] = (1 / kospi_pe) - (data["treasury_10y"] / 100)
        else:
            data["equity_risk_premium"] = 0.065
    except Exception:
        data["equity_risk_premium"] = 0.065

    return data
