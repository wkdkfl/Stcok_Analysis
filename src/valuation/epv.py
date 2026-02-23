"""
Earnings Power Value (EPV) — Bruce Greenwald Framework.
Value of current normalized earnings in perpetuity, assuming ZERO growth.
EPV > Reproduction Value of Assets → competitive moat exists.
"""

import numpy as np
from typing import Dict, Any, Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import DCF_DEFAULTS
from src.fetcher.yahoo import get_stmt_series


def compute_epv(data: Dict[str, Any], overrides: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Compute Earnings Power Value.
    EPV = Normalized EBIT × (1 - tax) / WACC
    """
    cfg = {**DCF_DEFAULTS, **(overrides or {})}
    result = {
        "model": "Earnings Power Value (Greenwald)",
        "fair_value": None,
        "upside_pct": None,
        "confidence": "N/A",
        "moat_signal": None,
        "details": {},
    }

    current_price = data.get("current_price")
    shares = data.get("shares_outstanding")
    total_debt = data.get("total_debt") or 0
    cash = data.get("cash") or 0

    if not all([current_price, shares]) or shares <= 0:
        result["confidence"] = "Insufficient Data"
        return result

    # ── Normalize EBIT (average over available years) ────
    inc = data.get("income_stmt")
    ebit_series = get_stmt_series(inc, ["EBIT", "Operating Income"])

    if ebit_series is not None and len(ebit_series) > 0:
        # Use median to reduce impact of outliers
        normalized_ebit = float(ebit_series.median())
    elif data.get("ebit"):
        normalized_ebit = data["ebit"]
    else:
        result["confidence"] = "Insufficient Data"
        return result

    if normalized_ebit <= 0:
        result["confidence"] = "Low"
        result["details"]["error"] = "Negative normalized EBIT"
        return result

    # ── WACC ─────────────────────────────────────────────
    beta = data.get("beta") or 1.0
    risk_free = cfg.get("risk_free_rate", 0.043)
    erp = cfg.get("equity_risk_premium", 0.055)
    cost_of_equity = risk_free + beta * erp
    market_cap = data.get("market_cap") or (current_price * shares)

    if market_cap and total_debt:
        tc = market_cap + total_debt
        eq_w = market_cap / tc
        dt_w = total_debt / tc
        cost_of_debt = risk_free + 0.02
        wacc = eq_w * cost_of_equity + dt_w * cost_of_debt * (1 - cfg["tax_rate"])
    else:
        wacc = cfg["default_wacc"]
    wacc = max(wacc, 0.06)

    # ── EPV Calculation ──────────────────────────────────
    nopat = normalized_ebit * (1 - cfg["tax_rate"])
    enterprise_epv = nopat / wacc
    equity_epv = enterprise_epv - total_debt + cash
    epv_per_share = equity_epv / shares if equity_epv > 0 else None

    if epv_per_share and epv_per_share > 0:
        result["fair_value"] = round(epv_per_share, 2)
        result["upside_pct"] = round((epv_per_share / current_price - 1) * 100, 1)

    # ── Moat Assessment ──────────────────────────────────
    # Compare EPV to reproduction value (approximated by tangible book)
    tbv = data.get("tangible_book_value")
    if tbv and enterprise_epv > 0:
        reproduction_value = tbv + total_debt
        if enterprise_epv > reproduction_value * 1.5:
            result["moat_signal"] = "Strong Moat (EPV >> Asset Value)"
        elif enterprise_epv > reproduction_value:
            result["moat_signal"] = "Moderate Moat (EPV > Asset Value)"
        else:
            result["moat_signal"] = "No Clear Moat (EPV ≤ Asset Value)"
    else:
        result["moat_signal"] = "N/A"

    # ── Confidence ───────────────────────────────────────
    if ebit_series is not None and len(ebit_series) >= 3:
        cv = ebit_series.std() / ebit_series.mean() if ebit_series.mean() != 0 else 1
        if cv < 0.3:
            result["confidence"] = "High"
        elif cv < 0.6:
            result["confidence"] = "Medium"
        else:
            result["confidence"] = "Low"
    else:
        result["confidence"] = "Low"

    result["details"] = {
        "normalized_ebit": round(normalized_ebit),
        "nopat": round(nopat),
        "wacc": round(wacc * 100, 2),
        "enterprise_epv": round(enterprise_epv),
        "equity_epv": round(equity_epv) if equity_epv else None,
    }

    return result
