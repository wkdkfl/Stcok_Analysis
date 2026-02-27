"""
Analyst Target Price Model.
Uses consensus analyst target prices from Yahoo Finance as a valuation input.

Wall Street analyst targets are based on proprietary models, industry knowledge,
and management guidance — incorporating them adds an external "wisdom of crowds"
signal to complement our quantitative models.
"""

from typing import Dict, Any


def compute_analyst_target(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Use analyst consensus target price as a valuation model.

    Uses Yahoo Finance fields:
    - target_mean: mean analyst target price
    - target_high: highest target
    - target_low: lowest target
    - num_analysts: number of analysts covering
    """
    result = {
        "model": "Analyst Target",
        "fair_value": None,
        "upside_pct": None,
        "confidence": "N/A",
        "details": {},
    }

    current_price = data.get("current_price")
    target_mean = data.get("target_mean")
    target_high = data.get("target_high")
    target_low = data.get("target_low")
    num_analysts = data.get("num_analysts")

    if not current_price or not target_mean:
        result["confidence"] = "Insufficient Data"
        return result

    # Use median-like estimate: blend mean with trimmed range
    if target_high and target_low:
        # Trimmed mean: average of mean and midpoint (reduces outlier impact)
        midpoint = (target_high + target_low) / 2
        fair_value = target_mean * 0.6 + midpoint * 0.4
    else:
        fair_value = target_mean

    if fair_value and fair_value > 0:
        result["fair_value"] = round(fair_value, 2)
        result["upside_pct"] = round((fair_value / current_price - 1) * 100, 1)

    # Confidence based on analyst coverage depth
    if num_analysts is not None:
        if num_analysts >= 15:
            result["confidence"] = "High"
        elif num_analysts >= 5:
            result["confidence"] = "Medium"
        elif num_analysts >= 1:
            result["confidence"] = "Low"
        else:
            result["confidence"] = "Insufficient Data"
    else:
        result["confidence"] = "Low"

    result["details"] = {
        "target_mean": target_mean,
        "target_high": target_high,
        "target_low": target_low,
        "num_analysts": num_analysts,
        "recommendation": data.get("recommendation"),
    }

    return result
