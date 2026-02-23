"""
Graham Number — conservative value investing floor.
V = sqrt(22.5 × EPS × BPS)
"""

import math
from typing import Dict, Any


def compute_graham(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute Graham Number.
    """
    result = {
        "model": "Graham Number",
        "fair_value": None,
        "upside_pct": None,
        "confidence": "N/A",
        "details": {},
    }

    eps = data.get("eps_trailing")
    bps = data.get("bps")
    current_price = data.get("current_price")

    if not all([eps, bps, current_price]):
        result["confidence"] = "Insufficient Data"
        return result

    if eps <= 0 or bps <= 0:
        result["confidence"] = "N/A (Negative EPS or BPS)"
        result["details"]["note"] = "Graham Number requires positive EPS and BPS"
        return result

    graham = math.sqrt(22.5 * eps * bps)

    result["fair_value"] = round(graham, 2)
    result["upside_pct"] = round((graham / current_price - 1) * 100, 1)
    result["confidence"] = "Medium"  # Graham is a conservative floor estimate

    result["details"] = {
        "eps": round(eps, 2),
        "bps": round(bps, 2),
        "formula": "sqrt(22.5 × EPS × BPS)",
    }

    return result
