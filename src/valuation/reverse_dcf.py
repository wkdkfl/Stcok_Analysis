"""
Reverse DCF — Implied Expectations Analysis.
Backs out the growth rate the market is currently pricing in,
so the user can compare it to their own assumptions.
"""

import numpy as np
from scipy.optimize import brentq
from typing import Dict, Any, Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import DCF_DEFAULTS


def compute_reverse_dcf(data: Dict[str, Any], overrides: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Solve for the implied growth rate that justifies the current market price.
    """
    cfg = {**DCF_DEFAULTS, **(overrides or {})}
    result = {
        "model": "Reverse DCF",
        "implied_growth_rate": None,
        "implied_revenue_growth": None,
        "assessment": None,
        "details": {},
    }

    fcf = data.get("fcf")
    current_price = data.get("current_price")
    shares = data.get("shares_outstanding")
    total_debt = data.get("total_debt") or 0
    cash = data.get("cash") or 0
    market_cap = data.get("market_cap")
    beta = data.get("beta") or 1.0

    if not all([fcf, current_price, shares, market_cap]) or fcf <= 0:
        result["assessment"] = "Insufficient Data (need positive FCF)"
        return result

    # Compute WACC
    risk_free = cfg.get("risk_free_rate", 0.043)
    erp = cfg.get("equity_risk_premium", 0.055)
    cost_of_equity = risk_free + beta * erp
    wacc = cost_of_equity  # simplified — use equity cost
    if total_debt and market_cap:
        total_capital = market_cap + total_debt
        eq_w = market_cap / total_capital
        dt_w = total_debt / total_capital
        cost_of_debt = risk_free + 0.02
        wacc = eq_w * cost_of_equity + dt_w * cost_of_debt * (1 - cfg["tax_rate"])
    wacc = max(wacc, 0.06)

    target_ev = market_cap + total_debt - cash
    terminal_growth = cfg["terminal_growth_rate"]
    high_years = cfg["high_growth_years"]
    fade_years = cfg["fade_years"]

    def ev_at_growth(g):
        """Compute Enterprise Value for a given growth rate."""
        pv = 0.0
        cf = fcf
        yr = 0
        for y in range(1, high_years + 1):
            cf *= (1 + g)
            pv += cf / ((1 + wacc) ** y)
            yr = y
        for y in range(1, fade_years + 1):
            fade_pct = y / fade_years
            fg = g * (1 - fade_pct) + terminal_growth * fade_pct
            cf *= (1 + fg)
            total_yr = high_years + y
            pv += cf / ((1 + wacc) ** total_yr)
            yr = total_yr
        tcf = cf * (1 + terminal_growth)
        if wacc <= terminal_growth:
            return float("inf")
        tv = tcf / (wacc - terminal_growth)
        pv += tv / ((1 + wacc) ** yr)
        return pv

    # Solve for implied growth: ev_at_growth(g) = target_ev
    try:
        implied_g = brentq(lambda g: ev_at_growth(g) - target_ev, -0.30, 0.80, xtol=1e-5)
        result["implied_growth_rate"] = round(implied_g * 100, 2)
    except Exception:
        result["assessment"] = "Could not solve (price outside model range)"
        return result

    # Compare to actual growth
    actual_growth = data.get("earnings_growth") or data.get("revenue_growth")
    hist_growth = None
    if data.get("revenue_growth_hist") is not None and len(data["revenue_growth_hist"]) > 0:
        hist_growth = data["revenue_growth_hist"].mean()

    result["details"] = {
        "wacc": round(wacc * 100, 2),
        "target_ev": target_ev,
        "actual_earnings_growth": round(actual_growth * 100, 2) if actual_growth else None,
        "hist_revenue_growth": round(hist_growth * 100, 2) if hist_growth else None,
    }

    # Assessment
    ig = implied_g
    if actual_growth is not None:
        diff = ig - actual_growth
        if diff > 0.10:
            result["assessment"] = f"시장은 {result['implied_growth_rate']}% 성장을 가정 — 과대평가 가능 (실제 추정: {round(actual_growth*100,1)}%)"
        elif diff < -0.10:
            result["assessment"] = f"시장은 {result['implied_growth_rate']}% 성장만 가정 — 과소평가 가능 (실제 추정: {round(actual_growth*100,1)}%)"
        else:
            result["assessment"] = f"시장 내재 성장률 ({result['implied_growth_rate']}%)이 실제 추정치와 유사 — 적정 가격대"
    else:
        if ig > 0.25:
            result["assessment"] = f"시장은 연 {result['implied_growth_rate']}% 고성장을 가정 — 높은 기대 반영"
        elif ig < 0.05:
            result["assessment"] = f"시장은 연 {result['implied_growth_rate']}% 저성장만 가정 — 보수적 가격"
        else:
            result["assessment"] = f"시장 내재 성장률: 연 {result['implied_growth_rate']}%"

    return result
