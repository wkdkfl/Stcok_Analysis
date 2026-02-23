"""
Altman Z-Score — Bankruptcy probability predictor.
Z = 1.2×X1 + 1.4×X2 + 3.3×X3 + 0.6×X4 + 1.0×X5
> 2.99 Safe | 1.81-2.99 Grey Zone | < 1.81 Distress
"""

from typing import Dict, Any


def compute_altman_z(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute Altman Z-Score."""
    result = {
        "z_score": None,
        "zone": "N/A",
        "components": {},
    }

    ta = data.get("total_assets")
    if not ta or ta <= 0:
        return result

    # X1 = Working Capital / Total Assets
    wc = data.get("working_capital")
    if wc is None:
        ca = data.get("current_assets") or 0
        cl = data.get("current_liabilities") or 0
        wc = ca - cl
    x1 = wc / ta

    # X2 = Retained Earnings / Total Assets
    re = data.get("retained_earnings") or 0
    x2 = re / ta

    # X3 = EBIT / Total Assets
    ebit = data.get("ebit")
    if ebit is None:
        return result
    x3 = ebit / ta

    # X4 = Market Cap / Total Liabilities
    mc = data.get("market_cap")
    tl = data.get("total_liabilities")
    if not mc or not tl or tl <= 0:
        return result
    x4 = mc / tl

    # X5 = Revenue / Total Assets
    rev = data.get("revenue")
    if not rev:
        return result
    x5 = rev / ta

    z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

    result["z_score"] = round(z, 2)
    result["components"] = {
        "X1 (WC/TA)": round(x1, 4),
        "X2 (RE/TA)": round(x2, 4),
        "X3 (EBIT/TA)": round(x3, 4),
        "X4 (MC/TL)": round(x4, 4),
        "X5 (Rev/TA)": round(x5, 4),
    }

    if z > 2.99:
        result["zone"] = "Safe Zone"
    elif z > 1.81:
        result["zone"] = "Grey Zone"
    else:
        result["zone"] = "Distress Zone"

    return result
