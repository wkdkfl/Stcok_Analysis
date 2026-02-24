"""
Residual Income Model (Edwards-Bell-Ohlson).
Value = Book Value + PV of future excess earnings.
Works well for companies with reliable book values (esp. financials).
"""

import numpy as np
from typing import Dict, Any, Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import DCF_DEFAULTS
from src.market_context import get_dcf_overrides


def compute_residual_income(data: Dict[str, Any], overrides: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Compute intrinsic value using Residual Income Model.
    V = BPS + Σ[(ROE_t - r_e) × BPS_{t-1}] / (1+r_e)^t
    """
    market = data.get("market", "US")
    cfg = {**DCF_DEFAULTS, **get_dcf_overrides(market), **(overrides or {})}
    result = {
        "model": "Residual Income (EBO)",
        "fair_value": None,
        "upside_pct": None,
        "confidence": "N/A",
        "details": {},
    }

    bps = data.get("bps")
    roe = data.get("roe")
    current_price = data.get("current_price")
    beta = data.get("beta") or 1.0

    if not all([bps, roe, current_price]) or bps <= 0:
        result["confidence"] = "Insufficient Data"
        return result

    risk_free = cfg.get("risk_free_rate", 0.043)
    erp = cfg.get("equity_risk_premium", 0.055)
    cost_of_equity = risk_free + beta * erp

    # Project ROE fade towards cost of equity over projection period
    projection_years = cfg["high_growth_years"] + cfg["fade_years"]
    terminal_roe = cost_of_equity + 0.02  # assume slight moat remains

    pv_residual = 0.0
    current_bps = bps

    for y in range(1, projection_years + 1):
        # ROE fades linearly from current to terminal
        fade = y / projection_years
        projected_roe = roe * (1 - fade) + terminal_roe * fade

        # Excess return
        excess = projected_roe - cost_of_equity
        residual_income_per_share = excess * current_bps
        pv_residual += residual_income_per_share / ((1 + cost_of_equity) ** y)

        # BPS grows by retained earnings
        payout = data.get("payout_ratio") or 0.3
        retention = 1 - min(payout, 1.0)
        current_bps *= (1 + projected_roe * retention)

    # Terminal residual income (perpetuity with terminal ROE)
    terminal_excess = terminal_roe - cost_of_equity
    if terminal_excess > 0 and cost_of_equity > 0.01:
        terminal_ri = terminal_excess * current_bps
        # Apply a fade factor for conservatism
        pv_terminal = (terminal_ri / cost_of_equity) / ((1 + cost_of_equity) ** projection_years) * 0.5
        pv_residual += pv_terminal

    fair_value = bps + pv_residual

    if fair_value > 0:
        result["fair_value"] = round(fair_value, 2)
        result["upside_pct"] = round((fair_value / current_price - 1) * 100, 1)

    # Confidence based on ROE stability
    if roe > cost_of_equity and bps > 0:
        result["confidence"] = "High" if roe < 0.40 else "Medium"
    else:
        result["confidence"] = "Low"

    result["details"] = {
        "bps": round(bps, 2),
        "roe": round(roe * 100, 2),
        "cost_of_equity": round(cost_of_equity * 100, 2),
        "excess_return_spread": round((roe - cost_of_equity) * 100, 2),
        "projection_years": projection_years,
    }

    return result
