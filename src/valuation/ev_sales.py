"""
EV/Sales (Revenue Multiple) Valuation.
Fair Value = (Revenue × Sector P/S - Debt + Cash) / Shares

Critical for high-growth, pre-profit companies (e.g., early-stage SaaS, biotech).
Also useful as a cross-check for profitable companies.
"""

import json
import os
from typing import Dict, Any

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import SECTOR_MULTIPLES_FALLBACK, KR_SECTOR_MULTIPLES_FALLBACK

# Growth-adjusted P/S premium table
# Companies growing faster than sector avg get a P/S premium
GROWTH_PS_MULTIPLIER = {
    # revenue_growth vs sector_avg ratio → P/S multiplier
    # e.g., 2x sector growth → 1.5x P/S
    "very_high": 1.8,   # > 3× sector avg
    "high": 1.4,         # 2-3× sector avg
    "above_avg": 1.15,   # 1.3-2× sector avg
    "average": 1.0,      # 0.7-1.3× sector avg
    "below_avg": 0.8,    # 0.3-0.7× sector avg
    "low": 0.6,          # < 0.3× sector avg
}


def compute_ev_sales(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute fair value using EV/Sales (Revenue Multiple) methodology.
    Adjusts P/S multiple based on company growth vs sector average.
    """
    result = {
        "model": "EV/Sales",
        "fair_value": None,
        "upside_pct": None,
        "confidence": "N/A",
        "details": {},
    }

    current_price = data.get("current_price")
    shares = data.get("shares_outstanding")
    revenue = data.get("revenue")
    sector = data.get("sector", "")
    market = data.get("market", "US")

    if not current_price or not shares or not revenue or revenue <= 0:
        result["confidence"] = "Insufficient Data"
        return result

    total_debt = data.get("total_debt") or 0
    cash = data.get("cash") or 0

    # Load sector benchmarks
    benchmarks = _load_sector_benchmarks(sector, market)
    base_ps = benchmarks.get("ps")
    if not base_ps:
        base_ps = benchmarks.get("ev_ebitda", 15) * 0.3  # Rough P/S estimate

    # Adjust P/S for company growth vs sector average
    company_rev_growth = data.get("revenue_growth")
    sector_rev_growth = benchmarks.get("revenue_growth")

    growth_mult = 1.0
    if company_rev_growth is not None and sector_rev_growth and sector_rev_growth > 0:
        ratio = company_rev_growth / (sector_rev_growth / 100.0)  # sector is in %
        if ratio > 3.0:
            growth_mult = GROWTH_PS_MULTIPLIER["very_high"]
        elif ratio > 2.0:
            growth_mult = GROWTH_PS_MULTIPLIER["high"]
        elif ratio > 1.3:
            growth_mult = GROWTH_PS_MULTIPLIER["above_avg"]
        elif ratio > 0.7:
            growth_mult = GROWTH_PS_MULTIPLIER["average"]
        elif ratio > 0.3:
            growth_mult = GROWTH_PS_MULTIPLIER["below_avg"]
        else:
            growth_mult = GROWTH_PS_MULTIPLIER["low"]

    adjusted_ps = base_ps * growth_mult

    # Also consider gross margin quality (higher margin → higher deserved P/S)
    gross_margin = data.get("gross_margin")
    sector_gm = benchmarks.get("gross_margin")
    margin_adj = 1.0
    if gross_margin is not None and sector_gm and sector_gm > 0:
        gm_ratio = (gross_margin * 100) / sector_gm  # gross_margin is decimal
        margin_adj = max(0.8, min(1.2, 0.6 + gm_ratio * 0.4))

    final_ps = adjusted_ps * margin_adj

    # Calculate fair value
    implied_ev = revenue * final_ps
    implied_equity = implied_ev - total_debt + cash
    fair_value = implied_equity / shares if implied_equity > 0 else None

    if fair_value and fair_value > 0:
        result["fair_value"] = round(fair_value, 2)
        result["upside_pct"] = round((fair_value / current_price - 1) * 100, 1)

    # Confidence
    has_growth = company_rev_growth is not None
    has_margin = gross_margin is not None
    if has_growth and has_margin and revenue > 0:
        result["confidence"] = "High"
    elif revenue > 0:
        result["confidence"] = "Medium"
    else:
        result["confidence"] = "Low"

    result["details"] = {
        "revenue": revenue,
        "base_ps": round(base_ps, 2),
        "growth_multiplier": round(growth_mult, 2),
        "margin_adjustment": round(margin_adj, 2),
        "final_ps": round(final_ps, 2),
        "company_rev_growth": round(company_rev_growth * 100, 1) if company_rev_growth else None,
        "sector": sector,
    }

    return result


def _load_sector_benchmarks(sector: str, market: str = "US") -> dict:
    """Load sector benchmarks from JSON file or fallback config."""
    json_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sector_benchmarks.json")
    try:
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                benchmarks = json.load(f)
                if market == "KR" and "KR" in benchmarks and sector in benchmarks["KR"]:
                    return benchmarks["KR"][sector]
                if sector in benchmarks:
                    return benchmarks[sector]
    except Exception:
        pass

    if market == "KR":
        fb = KR_SECTOR_MULTIPLES_FALLBACK.get(sector, {"ev_ebitda": 10.0, "pe": 12.0, "ps": 1.5})
    else:
        fb = SECTOR_MULTIPLES_FALLBACK.get(sector, {"ev_ebitda": 15.0, "pe": 18.0, "ps": 3.0})

    return fb
