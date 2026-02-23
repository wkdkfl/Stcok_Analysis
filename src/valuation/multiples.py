"""
Comparable Multiples Valuation.
- EV/EBITDA sector comparable
- P/E Relative (5-year avg & sector)
- P/FCF based
"""

import numpy as np
from typing import Dict, Any, Optional
import json, os, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import SECTOR_MULTIPLES_FALLBACK


def compute_multiples(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute fair values using comparable multiples.
    """
    result = {
        "model": "Comparable Multiples",
        "fair_value_ev_ebitda": None,
        "fair_value_pe": None,
        "fair_value_pfcf": None,
        "fair_value": None,  # weighted average
        "upside_pct": None,
        "confidence": "N/A",
        "details": {},
    }

    current_price = data.get("current_price")
    shares = data.get("shares_outstanding")
    sector = data.get("sector", "")

    if not current_price or not shares:
        result["confidence"] = "Insufficient Data"
        return result

    # Load sector benchmarks
    benchmarks = _load_sector_benchmarks(sector)

    values = []
    weights = []

    # ── EV/EBITDA Based ──────────────────────────────────
    ebitda = data.get("ebitda")
    total_debt = data.get("total_debt") or 0
    cash = data.get("cash") or 0
    target_ev_ebitda = benchmarks.get("ev_ebitda")

    if ebitda and ebitda > 0 and target_ev_ebitda:
        implied_ev = ebitda * target_ev_ebitda
        implied_equity = implied_ev - total_debt + cash
        fv_ev = implied_equity / shares if implied_equity > 0 else None
        if fv_ev and fv_ev > 0:
            result["fair_value_ev_ebitda"] = round(fv_ev, 2)
            values.append(fv_ev)
            weights.append(0.40)

    # ── P/E Based ────────────────────────────────────────
    eps_fwd = data.get("eps_forward")
    eps_trail = data.get("eps_trailing")
    target_pe = benchmarks.get("pe")
    own_pe = data.get("trailing_pe")

    # Use forward P/E if available, else trailing, with sector avg
    if eps_fwd and eps_fwd > 0:
        # Blend own historical P/E and sector P/E
        if own_pe and own_pe > 0 and target_pe:
            blended_pe = own_pe * 0.4 + target_pe * 0.6
        elif target_pe:
            blended_pe = target_pe
        else:
            blended_pe = own_pe or 15

        fv_pe = eps_fwd * blended_pe
        if fv_pe > 0:
            result["fair_value_pe"] = round(fv_pe, 2)
            values.append(fv_pe)
            weights.append(0.35)
    elif eps_trail and eps_trail > 0 and target_pe:
        fv_pe = eps_trail * target_pe
        if fv_pe > 0:
            result["fair_value_pe"] = round(fv_pe, 2)
            values.append(fv_pe)
            weights.append(0.30)

    # ── P/FCF Based ──────────────────────────────────────
    fcf = data.get("fcf")
    if fcf and fcf > 0 and shares > 0:
        fcf_per_share = fcf / shares
        # Target P/FCF: roughly EV/EBITDA × 0.8 (CapEx adjusted)
        target_pfcf = (target_ev_ebitda or 15) * 0.8
        fv_pfcf = fcf_per_share * target_pfcf
        if fv_pfcf > 0:
            result["fair_value_pfcf"] = round(fv_pfcf, 2)
            values.append(fv_pfcf)
            weights.append(0.25)

    # ── Weighted Average ─────────────────────────────────
    if values:
        total_w = sum(weights)
        weights = [w / total_w for w in weights]
        fair_value = sum(v * w for v, w in zip(values, weights))
        result["fair_value"] = round(fair_value, 2)
        result["upside_pct"] = round((fair_value / current_price - 1) * 100, 1)

    # Confidence
    if len(values) >= 3:
        result["confidence"] = "High"
    elif len(values) >= 2:
        result["confidence"] = "Medium"
    elif len(values) >= 1:
        result["confidence"] = "Low"

    result["details"] = {
        "sector": sector,
        "benchmark_ev_ebitda": target_ev_ebitda,
        "benchmark_pe": target_pe,
        "own_trailing_pe": own_pe,
        "methods_used": len(values),
    }

    return result


def _load_sector_benchmarks(sector: str) -> dict:
    """Load sector benchmarks from JSON file or fallback config."""
    # Try to load from data file
    json_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sector_benchmarks.json")
    try:
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                benchmarks = json.load(f)
                if sector in benchmarks:
                    return benchmarks[sector]
    except Exception:
        pass

    # Fallback to config
    return SECTOR_MULTIPLES_FALLBACK.get(sector, {"ev_ebitda": 15.0, "pe": 18.0, "ps": 3.0})
