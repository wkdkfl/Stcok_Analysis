"""
PEG Ratio Valuation — Peter Lynch style.
Fair Value = EPS × Earnings Growth % × Sector PEG target

A PEG of 1.0 means the stock is fairly valued relative to growth.
Growth companies with PEG < 1 are considered undervalued.
"""

from typing import Dict, Any

# Sector-specific fair PEG targets (Wall Street consensus ranges)
SECTOR_PEG_TARGETS = {
    "Technology":             1.5,   # High growth tolerance
    "Communication Services": 1.3,
    "Healthcare":             1.4,   # Innovation premium
    "Consumer Cyclical":      1.2,
    "Consumer Defensive":     1.0,   # Slow & steady
    "Industrials":            1.1,
    "Financial Services":     0.9,   # Lower growth acceptable
    "Energy":                 0.8,   # Cyclical, low growth
    "Basic Materials":        0.9,
    "Real Estate":            1.0,
    "Utilities":              0.8,   # Regulated, low growth
}

DEFAULT_PEG_TARGET = 1.2


def compute_peg(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute fair value using PEG Ratio methodology.

    PEG = P/E ÷ Earnings Growth Rate (%)
    Fair P/E = Growth Rate × Target PEG
    Fair Value = EPS × Fair P/E
    """
    result = {
        "model": "PEG Ratio",
        "fair_value": None,
        "upside_pct": None,
        "confidence": "N/A",
        "details": {},
    }

    current_price = data.get("current_price")
    eps_fwd = data.get("eps_forward")
    eps_trail = data.get("eps_trailing")
    sector = data.get("sector", "")

    # Use forward EPS if available, else trailing
    eps = eps_fwd if eps_fwd and eps_fwd > 0 else eps_trail
    if not eps or eps <= 0 or not current_price:
        result["confidence"] = "Insufficient Data"
        return result

    # Estimate earnings growth rate (annualized, as a percentage)
    growth_rate = _estimate_growth_rate(data)
    if growth_rate is None or growth_rate <= 0:
        result["confidence"] = "N/A (No positive growth estimate)"
        result["details"]["note"] = "PEG requires positive earnings growth"
        return result

    # Get sector PEG target
    peg_target = SECTOR_PEG_TARGETS.get(sector, DEFAULT_PEG_TARGET)

    # Fair P/E = growth_rate_pct × PEG_target
    growth_pct = growth_rate * 100  # Convert to percentage (e.g., 0.15 → 15)
    fair_pe = growth_pct * peg_target

    # Cap fair P/E to reasonable bounds
    fair_pe = max(5, min(fair_pe, 60))

    fair_value = eps * fair_pe

    if fair_value > 0:
        result["fair_value"] = round(fair_value, 2)
        result["upside_pct"] = round((fair_value / current_price - 1) * 100, 1)

    # Confidence assessment
    actual_peg = data.get("peg_ratio")
    has_analyst_growth = data.get("earnings_growth") is not None
    has_fwd_eps = eps_fwd is not None and eps_fwd > 0

    if has_analyst_growth and has_fwd_eps:
        result["confidence"] = "High"
    elif has_analyst_growth or has_fwd_eps:
        result["confidence"] = "Medium"
    else:
        result["confidence"] = "Low"

    result["details"] = {
        "eps_used": round(eps, 2),
        "growth_rate": round(growth_rate * 100, 1),
        "peg_target": peg_target,
        "fair_pe": round(fair_pe, 1),
        "actual_peg": round(actual_peg, 2) if actual_peg else None,
        "sector": sector,
    }

    return result


def _estimate_growth_rate(data: Dict[str, Any]) -> float | None:
    """
    Estimate annualized earnings growth rate.
    Sources (blended): analyst estimate, forward vs trailing EPS, revenue growth.
    """
    estimates = []
    weights = []

    # 1) Analyst earnings growth estimate (highest priority)
    eg = data.get("earnings_growth")
    if eg is not None and eg > -1:
        estimates.append(eg)
        weights.append(0.50)

    # 2) Forward vs trailing EPS implied growth
    eps_fwd = data.get("eps_forward")
    eps_trail = data.get("eps_trailing")
    if eps_fwd and eps_trail and eps_trail > 0:
        implied = (eps_fwd / eps_trail) - 1
        if implied > -0.5:  # Sanity check
            estimates.append(implied)
            weights.append(0.30)

    # 3) Revenue growth as proxy
    rg = data.get("revenue_growth")
    if rg is not None and rg > -1:
        estimates.append(rg)
        weights.append(0.20)

    if not estimates:
        return None

    total_w = sum(weights)
    blended = sum(e * w for e, w in zip(estimates, weights)) / total_w

    # Cap at reasonable bounds
    return max(-0.10, min(blended, 0.50))
