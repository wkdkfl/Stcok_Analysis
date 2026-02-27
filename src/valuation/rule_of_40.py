"""
Rule of 40 Valuation — SaaS / Tech specific.
Rule of 40: Revenue Growth % + Operating Margin % ≥ 40

Companies exceeding Rule of 40 deserve premium EV/Sales multiples.
Only applicable to Technology and Communication Services sectors.
"""

import json
import os
from typing import Dict, Any

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import SECTOR_MULTIPLES_FALLBACK, KR_SECTOR_MULTIPLES_FALLBACK

# Sectors where Rule of 40 is applicable
APPLICABLE_SECTORS = {
    "Technology",
    "Communication Services",
}

# Rule of 40 score → EV/Sales multiple mapping
# Based on empirical data from public SaaS companies (2020-2025)
R40_MULTIPLES = [
    # (min_score, max_score, ev_sales_multiple)
    (60, 999, 15.0),   # Elite (e.g., high-growth + profitable)
    (50, 60,  12.0),   # Excellent
    (40, 50,   9.0),   # Good (meets Rule of 40)
    (30, 40,   6.0),   # Below threshold
    (20, 30,   4.0),   # Weak
    (0,  20,   2.5),   # Poor
    (-999, 0,  1.5),   # Negative — burning cash, shrinking
]


def compute_rule_of_40(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute fair value using Rule of 40 methodology.
    Only active for Technology and Communication Services sectors.
    """
    result = {
        "model": "Rule of 40",
        "fair_value": None,
        "upside_pct": None,
        "confidence": "N/A",
        "details": {},
    }

    sector = data.get("sector", "")
    if sector not in APPLICABLE_SECTORS:
        result["confidence"] = "N/A (Non-tech sector)"
        result["details"]["note"] = "Rule of 40 only applies to Tech / CommServices"
        return result

    current_price = data.get("current_price")
    shares = data.get("shares_outstanding")
    revenue = data.get("revenue")

    if not current_price or not shares or not revenue or revenue <= 0:
        result["confidence"] = "Insufficient Data"
        return result

    # Get growth and margin components
    rev_growth_pct = None
    op_margin_pct = None

    rg = data.get("revenue_growth")
    if rg is not None:
        rev_growth_pct = rg * 100  # Convert decimal to %

    om = data.get("operating_margin")
    if om is not None:
        op_margin_pct = om * 100  # Convert decimal to %

    if rev_growth_pct is None or op_margin_pct is None:
        result["confidence"] = "Insufficient Data"
        result["details"]["note"] = "Need both revenue growth and operating margin"
        return result

    # Calculate Rule of 40 score
    r40_score = rev_growth_pct + op_margin_pct

    # Map score to EV/Sales multiple
    ev_sales_mult = 2.5  # default
    for min_s, max_s, mult in R40_MULTIPLES:
        if min_s <= r40_score < max_s:
            ev_sales_mult = mult
            break

    # Interpolate within the bracket for smoother values
    for i, (min_s, max_s, mult) in enumerate(R40_MULTIPLES):
        if min_s <= r40_score < max_s:
            # Linear interpolation within bracket
            if i > 0:
                prev_mult = R40_MULTIPLES[i - 1][2]
                range_size = max_s - min_s
                position = (r40_score - min_s) / range_size if range_size > 0 else 0
                ev_sales_mult = mult + (prev_mult - mult) * position
            break

    total_debt = data.get("total_debt") or 0
    cash = data.get("cash") or 0

    # Calculate fair value
    implied_ev = revenue * ev_sales_mult
    implied_equity = implied_ev - total_debt + cash
    fair_value = implied_equity / shares if implied_equity > 0 else None

    if fair_value and fair_value > 0:
        result["fair_value"] = round(fair_value, 2)
        result["upside_pct"] = round((fair_value / current_price - 1) * 100, 1)

    # Confidence
    if rev_growth_pct > 0 and abs(op_margin_pct) < 100:
        result["confidence"] = "High" if r40_score >= 30 else "Medium"
    else:
        result["confidence"] = "Low"

    result["details"] = {
        "rule_of_40_score": round(r40_score, 1),
        "revenue_growth_pct": round(rev_growth_pct, 1),
        "operating_margin_pct": round(op_margin_pct, 1),
        "ev_sales_multiple": round(ev_sales_mult, 1),
        "meets_rule_of_40": r40_score >= 40,
        "sector": sector,
    }

    return result
