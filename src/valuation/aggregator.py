"""
Valuation Aggregator — combines all valuation models with confidence-weighted averaging.
Produces final fair value estimate and Buy/Hold/Sell signal.
"""

import numpy as np
from typing import Dict, Any, List, Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import MODEL_WEIGHTS

from src.valuation.dcf import compute_dcf
from src.valuation.reverse_dcf import compute_reverse_dcf
from src.valuation.residual_income import compute_residual_income
from src.valuation.epv import compute_epv
from src.valuation.ddm import compute_ddm
from src.valuation.multiples import compute_multiples
from src.valuation.graham import compute_graham


CONFIDENCE_MULTIPLIERS = {
    "High": 1.0,
    "Medium": 0.7,
    "Low": 0.4,
}


def run_all_valuations(data: Dict[str, Any],
                       dcf_overrides: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Run all valuation models and aggregate results.

    Returns:
        Dictionary with:
        - models: list of individual model results
        - fair_value: aggregate fair value
        - upside_pct: aggregate upside %
        - signal: Strong Buy / Buy / Hold / Sell / Strong Sell
        - signal_color: green/yellow/red
        - reverse_dcf: reverse DCF analysis
    """
    results = {}

    # Run each model
    results["dcf"] = compute_dcf(data, dcf_overrides)
    results["reverse_dcf"] = compute_reverse_dcf(data, dcf_overrides)
    results["residual_income"] = compute_residual_income(data, dcf_overrides)
    results["epv"] = compute_epv(data, dcf_overrides)
    results["ddm"] = compute_ddm(data, dcf_overrides)
    results["multiples"] = compute_multiples(data)
    results["graham"] = compute_graham(data)

    # ── Aggregate Fair Value ─────────────────────────────
    models_with_values = []
    for key, res in results.items():
        if key == "reverse_dcf":
            continue  # signal only, no fair value
        fv = res.get("fair_value")
        if fv and fv > 0:
            conf = res.get("confidence", "Low")
            base_weight = MODEL_WEIGHTS.get(key, 0.1)
            conf_mult = CONFIDENCE_MULTIPLIERS.get(conf, 0.4)
            effective_weight = base_weight * conf_mult
            models_with_values.append((key, fv, effective_weight, res))

    aggregate = {
        "models": results,
        "models_summary": [],
        "fair_value": None,
        "upside_pct": None,
        "signal": "N/A",
        "signal_color": "gray",
        "fair_value_range": None,
    }

    if models_with_values:
        total_weight = sum(w for _, _, w, _ in models_with_values)
        if total_weight > 0:
            weighted_fv = sum(fv * w for _, fv, w, _ in models_with_values) / total_weight
            aggregate["fair_value"] = round(weighted_fv, 2)

            current_price = data.get("current_price", 0)
            if current_price and current_price > 0:
                upside = (weighted_fv / current_price - 1) * 100
                aggregate["upside_pct"] = round(upside, 1)
                aggregate["signal"], aggregate["signal_color"] = _get_signal(upside)

            # Range (min to max of model fair values)
            fvs = [fv for _, fv, _, _ in models_with_values]
            aggregate["fair_value_range"] = (round(min(fvs), 2), round(max(fvs), 2))

    # Build summary table
    for key, res in results.items():
        if key == "reverse_dcf":
            continue
        entry = {
            "model": res.get("model", key),
            "fair_value": res.get("fair_value"),
            "upside_pct": res.get("upside_pct"),
            "confidence": res.get("confidence", "N/A"),
        }
        aggregate["models_summary"].append(entry)

    return aggregate


def _get_signal(upside_pct: float) -> tuple:
    """Convert upside percentage to signal and color."""
    if upside_pct >= 30:
        return "Strong Buy", "#00C853"
    elif upside_pct >= 10:
        return "Buy", "#4CAF50"
    elif upside_pct >= -10:
        return "Hold", "#FF9800"
    elif upside_pct >= -25:
        return "Sell", "#F44336"
    else:
        return "Strong Sell", "#B71C1C"
