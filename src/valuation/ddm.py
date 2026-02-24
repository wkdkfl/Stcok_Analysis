"""
Dividend Discount Model (DDM) — Gordon Growth & Multi-Stage.
Only active for dividend-paying stocks.
"""

import numpy as np
from typing import Dict, Any, Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import DCF_DEFAULTS
from src.market_context import get_dcf_overrides


def compute_ddm(data: Dict[str, Any], overrides: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Compute intrinsic value using DDM.
    Gordon: P = D1 / (r - g)
    Multi-stage: high growth → terminal growth
    """
    market = data.get("market", "US")
    cfg = {**DCF_DEFAULTS, **get_dcf_overrides(market), **(overrides or {})}
    result = {
        "model": "Dividend Discount Model",
        "fair_value": None,
        "upside_pct": None,
        "confidence": "N/A",
        "details": {},
    }

    current_price = data.get("current_price")
    dividend_rate = data.get("dividend_rate") or 0
    dividend_yield = data.get("dividend_yield") or 0
    payout_ratio = data.get("payout_ratio") or 0

    if not current_price or dividend_rate <= 0:
        result["confidence"] = "N/A (No Dividend)"
        result["details"]["note"] = "This stock does not pay dividends"
        return result

    beta = data.get("beta") or 1.0
    risk_free = cfg.get("risk_free_rate", 0.043)
    erp = cfg.get("equity_risk_premium", 0.055)
    cost_of_equity = risk_free + beta * erp

    # Dividend growth estimate
    eg = data.get("earnings_growth")
    roe = data.get("roe") or 0.10
    retention = 1 - min(payout_ratio, 0.95) if payout_ratio else 0.5
    sgr = roe * retention

    if eg and isinstance(eg, (int, float)):
        div_growth_high = min(eg, 0.20)  # cap high growth
    else:
        div_growth_high = min(sgr, 0.15)

    terminal_div_growth = min(cfg["terminal_growth_rate"], cost_of_equity - 0.01)

    # ── Multi-Stage DDM ──────────────────────────────────
    d0 = dividend_rate
    high_years = cfg["high_growth_years"]
    pv = 0.0
    current_div = d0

    for y in range(1, high_years + 1):
        current_div *= (1 + div_growth_high)
        pv += current_div / ((1 + cost_of_equity) ** y)

    # Terminal value
    terminal_div = current_div * (1 + terminal_div_growth)
    if cost_of_equity > terminal_div_growth:
        terminal_value = terminal_div / (cost_of_equity - terminal_div_growth)
        pv += terminal_value / ((1 + cost_of_equity) ** high_years)

    if pv > 0:
        result["fair_value"] = round(pv, 2)
        result["upside_pct"] = round((pv / current_price - 1) * 100, 1)

    # ── Simple Gordon Model (for comparison) ─────────────
    d1 = d0 * (1 + terminal_div_growth)
    if cost_of_equity > terminal_div_growth:
        gordon_value = d1 / (cost_of_equity - terminal_div_growth)
        result["details"]["gordon_value"] = round(gordon_value, 2)

    result["confidence"] = "High" if payout_ratio > 0.2 and payout_ratio < 0.8 else "Medium"

    result["details"].update({
        "current_dividend": d0,
        "dividend_yield": round(dividend_yield * 100, 2) if dividend_yield else None,
        "payout_ratio": round(payout_ratio * 100, 1) if payout_ratio else None,
        "div_growth_high": round(div_growth_high * 100, 2),
        "terminal_growth": round(terminal_div_growth * 100, 2),
        "cost_of_equity": round(cost_of_equity * 100, 2),
    })

    return result
