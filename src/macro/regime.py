"""
Macro Regime Analysis — Yield curve, Credit spreads, VIX regime,
Sector rotation, Market cycle assessment.
"""

import yfinance as yf
import pandas as pd
import numpy as np
from typing import Dict, Any
import streamlit as st
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import SECTOR_ETFS, CACHE_TTL
from src.fetcher.ssl_session import get_session

_session = get_session()


def compute_macro_regime(macro_data: Dict[str, Any], stock_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze current macro environment and its implications for the stock.
    """
    result = {
        "yield_curve": _analyze_yield_curve(macro_data),
        "credit": _analyze_credit(macro_data),
        "vix": _analyze_vix(macro_data),
        "sector_rotation": _analyze_sector_rotation(stock_data.get("sector", "")),
        "erp": _analyze_erp(macro_data),
        "summary": "",
        "implication": "",
    }

    # Build summary
    summaries = []
    yc = result["yield_curve"]
    if yc.get("inverted"):
        summaries.append("수익률곡선 역전 (경기침체 경고)")
    else:
        spread = yc.get("spread")
        if spread is not None:
            summaries.append(f"수익률곡선 정상 (스프레드 {spread}%)")

    cr = result["credit"]
    summaries.append(f"신용 환경: {cr.get('regime', 'N/A')}")

    vx = result["vix"]
    summaries.append(f"변동성: {vx.get('regime', 'N/A')}")

    sr = result["sector_rotation"]
    if sr.get("cycle_phase"):
        summaries.append(f"경기 국면: {sr['cycle_phase']}")

    result["summary"] = " | ".join(summaries)

    # Implication for the stock
    sector = stock_data.get("sector", "")
    implications = _derive_implication(result, sector)
    result["implication"] = implications

    return result


def _analyze_yield_curve(macro: Dict) -> Dict:
    spread = macro.get("yield_spread")
    return {
        "treasury_10y": macro.get("treasury_10y"),
        "treasury_2y": macro.get("treasury_2y"),
        "spread": round(spread, 2) if spread is not None else None,
        "inverted": macro.get("yield_curve_inverted", False),
    }


def _analyze_credit(macro: Dict) -> Dict:
    return {
        "ig_spread": macro.get("ig_spread"),
        "hy_spread": macro.get("hy_spread"),
        "regime": macro.get("credit_regime", "N/A"),
    }


def _analyze_vix(macro: Dict) -> Dict:
    return {
        "level": macro.get("vix"),
        "regime": macro.get("vix_regime", "N/A"),
    }


def _analyze_erp(macro: Dict) -> Dict:
    erp = macro.get("equity_risk_premium")
    result = {"erp": round(erp * 100, 2) if erp else None, "assessment": "N/A"}
    if erp is not None:
        if erp > 0.06:
            result["assessment"] = "시장 저평가 (높은 ERP)"
        elif erp > 0.04:
            result["assessment"] = "정상 수준"
        elif erp > 0.02:
            result["assessment"] = "시장 고평가 (낮은 ERP)"
        else:
            result["assessment"] = "시장 매우 고평가 (극저 ERP)"
    return result


@st.cache_data(ttl=CACHE_TTL, show_spinner=False)
def _analyze_sector_rotation(stock_sector: str) -> Dict:
    """Analyze sector relative strength to determine business cycle phase."""
    result = {
        "cycle_phase": None,
        "sector_ranking": {},
        "stock_sector_rank": None,
        "favorable": None,
    }

    try:
        # Download 3-month returns for sector ETFs
        returns = {}
        for sector_name, etf in SECTOR_ETFS.items():
            try:
                t = yf.Ticker(etf, session=_session)
                h = t.history(period="3mo")
                if h is not None and len(h) > 10:
                    ret = (float(h["Close"].iloc[-1]) / float(h["Close"].iloc[0]) - 1) * 100
                    returns[sector_name] = round(ret, 1)
            except Exception:
                continue

        if not returns:
            return result

        # Sort by return
        sorted_sectors = sorted(returns.items(), key=lambda x: x[1], reverse=True)
        result["sector_ranking"] = dict(sorted_sectors)

        # Find stock's sector rank
        for i, (s, r) in enumerate(sorted_sectors):
            if s == stock_sector:
                result["stock_sector_rank"] = i + 1
                break

        # Determine cycle phase based on leading sectors
        top_3 = [s for s, _ in sorted_sectors[:3]]
        bottom_3 = [s for s, _ in sorted_sectors[-3:]]

        cyclicals = {"Technology", "Consumer Cyclical", "Financial Services", "Industrials"}
        defensives = {"Utilities", "Consumer Defensive", "Healthcare", "Real Estate"}

        top_cyclical = sum(1 for s in top_3 if s in cyclicals)
        top_defensive = sum(1 for s in top_3 if s in defensives)

        if top_cyclical >= 2:
            if "Technology" in top_3 or "Consumer Cyclical" in top_3:
                result["cycle_phase"] = "Early Expansion (초기 확장)"
            else:
                result["cycle_phase"] = "Mid Expansion (중기 확장)"
        elif top_defensive >= 2:
            if "Utilities" in top_3 or "Consumer Defensive" in top_3:
                result["cycle_phase"] = "Late Cycle / Slowdown (후기/둔화)"
            else:
                result["cycle_phase"] = "Recession Fear (침체 우려)"
        elif "Energy" in top_3:
            result["cycle_phase"] = "Late Expansion (후기 확장)"
        else:
            result["cycle_phase"] = "Transitional (전환기)"

        # Is the stock's sector favorable?
        if stock_sector in [s for s, _ in sorted_sectors[:4]]:
            result["favorable"] = True
        elif stock_sector in [s for s, _ in sorted_sectors[-3:]]:
            result["favorable"] = False
        else:
            result["favorable"] = None

    except Exception:
        pass

    return result


def _derive_implication(regime: Dict, sector: str) -> str:
    """Derive investment implication from macro regime."""
    parts = []

    yc = regime.get("yield_curve", {})
    if yc.get("inverted"):
        parts.append("수익률곡선 역전은 향후 6-18개월 경기 둔화 가능성을 시사합니다")

    cr = regime.get("credit", {})
    if cr.get("regime") in ["Stressed (Risk-Off)", "Widening (Caution)"]:
        parts.append("신용 스프레드 확대는 리스크 회피 환경을 나타냅니다")

    vx = regime.get("vix", {})
    if vx.get("regime") in ["High Volatility (Fear)", "Elevated (Cautious)"]:
        parts.append("높은 변동성 환경에서는 방어적 포지셔닝이 유리합니다")

    sr = regime.get("sector_rotation", {})
    if sr.get("favorable") is True:
        parts.append(f"{sector} 섹터는 현재 상대적으로 강세를 보이고 있습니다")
    elif sr.get("favorable") is False:
        parts.append(f"{sector} 섹터는 현재 상대적으로 약세를 보이고 있습니다")

    erp = regime.get("erp", {})
    if "저평가" in erp.get("assessment", ""):
        parts.append("높은 ERP는 시장 전반이 매력적임을 시사합니다")
    elif "고평가" in erp.get("assessment", ""):
        parts.append("낮은 ERP는 시장 전반이 비싸다는 것을 의미합니다")

    return ". ".join(parts) + "." if parts else "매크로 환경이 중립적입니다."
