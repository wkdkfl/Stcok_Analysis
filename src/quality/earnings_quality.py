"""
Earnings Quality: Accrual Ratio, Cash Conversion, ROIC vs WACC Spread, EVA.
"""

import numpy as np
from typing import Dict, Any
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import DCF_DEFAULTS


def compute_earnings_quality(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute earnings quality metrics."""
    result = {
        "accrual_ratio": data.get("accrual_ratio"),
        "cash_conversion": data.get("cash_conversion"),
        "earnings_quality": "N/A",
    }

    ar = result["accrual_ratio"]
    ccr = result["cash_conversion"]

    if ar is not None and ccr is not None:
        if ar < -0.05 and ccr > 1.0:
            result["earnings_quality"] = "Excellent"
        elif ar < 0 and ccr > 0.8:
            result["earnings_quality"] = "Good"
        elif ar < 0.05 and ccr > 0.5:
            result["earnings_quality"] = "Fair"
        else:
            result["earnings_quality"] = "Poor"
    elif ccr is not None:
        if ccr > 1.0:
            result["earnings_quality"] = "Good"
        elif ccr > 0.5:
            result["earnings_quality"] = "Fair"
        else:
            result["earnings_quality"] = "Poor"

    return result


def compute_eva(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute Economic Value Added and ROIC vs WACC spread.
    EVA = NOPAT - (WACC × Invested Capital)
    """
    result = {
        "eva": None,
        "roic": None,
        "wacc": None,
        "spread": None,
        "verdict": "N/A",
    }

    nopat = data.get("nopat")
    ic = data.get("invested_capital")
    roic = data.get("roic")
    beta = data.get("beta") or 1.0

    if not nopat or not ic or ic <= 0:
        return result

    # Compute WACC
    cfg = DCF_DEFAULTS
    risk_free = cfg["risk_free_rate"]
    erp = cfg["equity_risk_premium"]
    cost_of_equity = risk_free + beta * erp

    mc = data.get("market_cap") or 0
    td = data.get("total_debt") or 0
    if mc and td:
        tc = mc + td
        eq_w = mc / tc
        dt_w = td / tc
        cod = risk_free + 0.02
        wacc = eq_w * cost_of_equity + dt_w * cod * (1 - cfg["tax_rate"])
    else:
        wacc = cfg["default_wacc"]

    wacc = max(wacc, 0.04)
    eva = nopat - (wacc * ic)

    result["eva"] = round(eva / 1e6, 1)  # in millions
    result["roic"] = round(roic * 100, 2) if roic else None
    result["wacc"] = round(wacc * 100, 2)
    result["spread"] = round((roic - wacc) * 100, 2) if roic else None

    if result["spread"] is not None:
        s = result["spread"]
        if s > 10:
            result["verdict"] = "Strong Value Creator (Wide Moat)"
        elif s > 3:
            result["verdict"] = "Value Creator (Moat)"
        elif s > 0:
            result["verdict"] = "Slight Value Creator"
        elif s > -3:
            result["verdict"] = "Value Neutral"
        else:
            result["verdict"] = "Value Destroyer"

    return result


def compute_quality_grade(piotroski: Dict, altman: Dict, beneish: Dict,
                          eq: Dict, eva_data: Dict) -> Dict[str, Any]:
    """
    Compute overall Quality Grade from A+ to F.
    """
    score = 0
    max_score = 0

    # Piotroski (weight: 25)
    f_score = piotroski.get("score", 0)
    score += (f_score / 9) * 25
    max_score += 25

    # Altman Z (weight: 20)
    z = altman.get("z_score")
    if z is not None:
        if z > 3.0:
            score += 20
        elif z > 2.0:
            score += 12
        elif z > 1.81:
            score += 6
        max_score += 20

    # Beneish M (weight: 15)
    m = beneish.get("m_score")
    if m is not None:
        if m < -2.22:
            score += 15
        elif m < -1.78:
            score += 8
        max_score += 15

    # Earnings Quality (weight: 20)
    eq_grade = eq.get("earnings_quality", "N/A")
    eq_map = {"Excellent": 20, "Good": 14, "Fair": 8, "Poor": 2}
    score += eq_map.get(eq_grade, 0)
    max_score += 20

    # EVA/ROIC Spread (weight: 20)
    spread = eva_data.get("spread")
    if spread is not None:
        if spread > 10:
            score += 20
        elif spread > 5:
            score += 15
        elif spread > 0:
            score += 10
        elif spread > -5:
            score += 4
        max_score += 20

    if max_score == 0:
        return {"grade": "N/A", "score": 0, "max_score": 0}

    pct = score / max_score * 100

    if pct >= 90:
        grade = "A+"
    elif pct >= 80:
        grade = "A"
    elif pct >= 70:
        grade = "B+"
    elif pct >= 60:
        grade = "B"
    elif pct >= 50:
        grade = "C+"
    elif pct >= 40:
        grade = "C"
    elif pct >= 30:
        grade = "D"
    else:
        grade = "F"

    return {"grade": grade, "score": round(score, 1), "max_score": max_score}
