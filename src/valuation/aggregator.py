"""
Valuation Aggregator v2 — Enhanced with:
- 12 valuation models (7 original + 5 new)
- Sector-specific model weighting
- Data-driven growth premium / discount
- IQR-based fair value range (P25–P75) instead of raw min/max
- Confidence-weighted averaging
"""

import json
import os
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import MODEL_WEIGHTS, SECTOR_MODEL_WEIGHTS

from src.valuation.dcf import compute_dcf
from src.valuation.reverse_dcf import compute_reverse_dcf
from src.valuation.residual_income import compute_residual_income
from src.valuation.epv import compute_epv
from src.valuation.ddm import compute_ddm
from src.valuation.multiples import compute_multiples
from src.valuation.graham import compute_graham
from src.valuation.peg import compute_peg
from src.valuation.ev_sales import compute_ev_sales
from src.valuation.rule_of_40 import compute_rule_of_40
from src.valuation.sotp import compute_sotp
from src.valuation.analyst_target import compute_analyst_target


CONFIDENCE_MULTIPLIERS = {
    "High": 1.0,
    "Medium": 0.7,
    "Low": 0.4,
}

# Signal-only models (not included in fair value aggregation)
SIGNAL_ONLY_MODELS = {"reverse_dcf"}


def run_all_valuations(data: Dict[str, Any],
                       dcf_overrides: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Run all valuation models and aggregate results.

    Returns:
        Dictionary with:
        - models: dict of individual model results
        - models_summary: list of model summaries for display
        - fair_value: aggregate fair value (before growth adjustment)
        - fair_value_adjusted: growth-adjusted fair value
        - growth_adjustment_pct: growth premium/discount applied
        - upside_pct: aggregate upside % (based on adjusted value)
        - signal: Strong Buy / Buy / Hold / Sell / Strong Sell
        - signal_color: hex color
        - fair_value_range: (P25, P75) IQR range
        - reverse_dcf: reverse DCF analysis
    """
    results = {}

    # ── Run all 12 models ────────────────────────────────
    results["dcf"] = compute_dcf(data, dcf_overrides)
    results["reverse_dcf"] = compute_reverse_dcf(data, dcf_overrides)
    results["residual_income"] = compute_residual_income(data, dcf_overrides)
    results["epv"] = compute_epv(data, dcf_overrides)
    results["ddm"] = compute_ddm(data, dcf_overrides)
    results["multiples"] = compute_multiples(data)
    results["graham"] = compute_graham(data)
    results["peg"] = compute_peg(data)
    results["ev_sales"] = compute_ev_sales(data)
    results["rule_of_40"] = compute_rule_of_40(data)
    results["sotp"] = compute_sotp(data)
    results["analyst_target"] = compute_analyst_target(data)

    # ── Get sector-specific weights ──────────────────────
    sector = data.get("sector", "")
    sector_weights = SECTOR_MODEL_WEIGHTS.get(sector, MODEL_WEIGHTS)

    # ── Collect valid model values with effective weights ─
    models_with_values = []
    for key, res in results.items():
        if key in SIGNAL_ONLY_MODELS:
            continue
        fv = res.get("fair_value")
        if fv and fv > 0:
            conf = res.get("confidence", "Low")
            # Skip models with non-standard confidence strings
            if conf not in CONFIDENCE_MULTIPLIERS:
                continue
            base_weight = sector_weights.get(key, MODEL_WEIGHTS.get(key, 0.0))
            if base_weight <= 0:
                continue  # This model is not applicable for this sector
            conf_mult = CONFIDENCE_MULTIPLIERS.get(conf, 0.4)
            effective_weight = base_weight * conf_mult
            models_with_values.append((key, fv, effective_weight, res))

    # ── Build aggregate ──────────────────────────────────
    aggregate = {
        "models": results,
        "models_summary": [],
        "fair_value": None,
        "fair_value_adjusted": None,
        "growth_adjustment_pct": 0.0,
        "upside_pct": None,
        "signal": "N/A",
        "signal_color": "gray",
        "fair_value_range": None,
    }

    current_price = data.get("current_price", 0)

    if models_with_values:
        total_weight = sum(w for _, _, w, _ in models_with_values)
        if total_weight > 0:
            # ── Confidence-weighted fair value ───────────
            weighted_fv = sum(fv * w for _, fv, w, _ in models_with_values) / total_weight
            aggregate["fair_value"] = round(weighted_fv, 2)

            # ── Growth premium / discount ────────────────
            growth_adj = _compute_growth_adjustment(data, sector)
            aggregate["growth_adjustment_pct"] = round(growth_adj * 100, 1)
            adjusted_fv = weighted_fv * (1 + growth_adj)
            aggregate["fair_value_adjusted"] = round(adjusted_fv, 2)

            # ── Upside & signal (based on adjusted FV) ───
            if current_price and current_price > 0:
                upside = (adjusted_fv / current_price - 1) * 100
                aggregate["upside_pct"] = round(upside, 1)
                aggregate["signal"], aggregate["signal_color"] = _get_signal(upside)

            # ── IQR-based Fair Value Range (P25–P75) ─────
            aggregate["fair_value_range"] = _compute_iqr_range(
                models_with_values, growth_adj
            )

    # ── Build summary table ──────────────────────────────
    for key, res in results.items():
        if key in SIGNAL_ONLY_MODELS:
            continue
        fv = res.get("fair_value")
        entry = {
            "model": res.get("model", key),
            "fair_value": fv,
            "upside_pct": res.get("upside_pct"),
            "confidence": res.get("confidence", "N/A"),
            "weight": sector_weights.get(key, MODEL_WEIGHTS.get(key, 0.0)),
        }
        aggregate["models_summary"].append(entry)

    return aggregate


# ═══════════════════════════════════════════════════════════
# GROWTH PREMIUM / DISCOUNT
# ═══════════════════════════════════════════════════════════

def _compute_growth_adjustment(data: Dict[str, Any], sector: str) -> float:
    """
    Compute growth premium/discount based on company metrics vs sector average.

    Returns adjustment factor (e.g., +0.15 = +15% premium, -0.10 = -10% discount).
    Premium capped at +20%, discount capped at -15%.
    """
    adjustments = []

    # Load sector benchmarks
    benchmarks = _load_sector_benchmarks(sector)

    # ── 1) Revenue growth vs sector average ──────────────
    company_rev_growth = data.get("revenue_growth")
    sector_rev_growth = benchmarks.get("revenue_growth")

    if company_rev_growth is not None and sector_rev_growth and sector_rev_growth > 0:
        sector_rg_decimal = sector_rev_growth / 100.0  # Convert from % to decimal
        if sector_rg_decimal > 0:
            ratio = company_rev_growth / sector_rg_decimal
            # ratio > 1.5 → premium, ratio < 0.5 → discount
            growth_adj = (ratio - 1.0) * 0.10  # 10% of excess ratio
            growth_adj = max(-0.10, min(growth_adj, 0.15))
            adjustments.append(("revenue_growth", growth_adj, 0.40))

    # ── 2) Earnings growth vs expectation ────────────────
    earnings_growth = data.get("earnings_growth")
    if earnings_growth is not None:
        if earnings_growth > 0.20:
            eg_adj = min((earnings_growth - 0.10) * 0.3, 0.10)
        elif earnings_growth > 0:
            eg_adj = (earnings_growth - 0.05) * 0.2
        else:
            eg_adj = max(earnings_growth * 0.3, -0.10)
        adjustments.append(("earnings_growth", eg_adj, 0.30))

    # ── 3) ROE quality premium ───────────────────────────
    roe = data.get("roe")
    sector_roe = benchmarks.get("roe")
    if roe is not None and sector_roe and sector_roe > 0:
        roe_pct = roe * 100 if abs(roe) < 1 else roe  # Handle decimal vs pct
        roe_ratio = roe_pct / sector_roe
        roe_adj = (roe_ratio - 1.0) * 0.05
        roe_adj = max(-0.05, min(roe_adj, 0.05))
        adjustments.append(("roe_quality", roe_adj, 0.20))

    # ── 4) Margin quality premium ────────────────────────
    op_margin = data.get("operating_margin")
    sector_margin = benchmarks.get("operating_margin")
    if op_margin is not None and sector_margin and sector_margin > 0:
        om_pct = op_margin * 100 if abs(op_margin) < 1 else op_margin
        margin_ratio = om_pct / sector_margin
        margin_adj = (margin_ratio - 1.0) * 0.03
        margin_adj = max(-0.03, min(margin_adj, 0.03))
        adjustments.append(("margin_quality", margin_adj, 0.10))

    if not adjustments:
        return 0.0

    # Weighted blend of adjustments
    total_w = sum(w for _, _, w in adjustments)
    blended = sum(adj * w for _, adj, w in adjustments) / total_w if total_w > 0 else 0.0

    # Cap final adjustment
    return max(-0.15, min(blended, 0.20))


def _load_sector_benchmarks(sector: str) -> dict:
    """Load sector benchmarks from JSON or return empty dict."""
    json_path = os.path.join(os.path.dirname(__file__), "..", "..", "data", "sector_benchmarks.json")
    try:
        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                benchmarks = json.load(f)
                if sector in benchmarks:
                    return benchmarks[sector]
    except Exception:
        pass
    return {}


# ═══════════════════════════════════════════════════════════
# IQR-BASED FAIR VALUE RANGE
# ═══════════════════════════════════════════════════════════

def _compute_iqr_range(
    models_with_values: List[tuple],
    growth_adj: float,
) -> Tuple[float, float]:
    """
    Compute fair value range using weighted IQR (P25–P75).
    Falls back to min/max if fewer than 4 models.
    """
    fvs = [fv for _, fv, _, _ in models_with_values]
    weights = [w for _, _, w, _ in models_with_values]

    if len(fvs) < 4:
        # Not enough models for IQR — use min/max
        low = min(fvs) * (1 + growth_adj)
        high = max(fvs) * (1 + growth_adj)
        return (round(low, 2), round(high, 2))

    # Weighted percentile calculation
    p25 = _weighted_percentile(fvs, weights, 25)
    p75 = _weighted_percentile(fvs, weights, 75)

    # Apply growth adjustment
    p25 *= (1 + growth_adj)
    p75 *= (1 + growth_adj)

    return (round(p25, 2), round(p75, 2))


def _weighted_percentile(values: list, weights: list, percentile: float) -> float:
    """
    Compute weighted percentile using linear interpolation.
    """
    # Sort by value
    paired = sorted(zip(values, weights))
    sorted_vals = [v for v, _ in paired]
    sorted_weights = [w for _, w in paired]

    # Cumulative weight
    total_w = sum(sorted_weights)
    cum_weights = []
    cumsum = 0
    for w in sorted_weights:
        cumsum += w
        cum_weights.append(cumsum / total_w * 100)

    target = percentile

    # Find interpolation position
    if target <= cum_weights[0]:
        return sorted_vals[0]
    if target >= cum_weights[-1]:
        return sorted_vals[-1]

    for i in range(len(cum_weights) - 1):
        if cum_weights[i] <= target <= cum_weights[i + 1]:
            # Linear interpolation
            frac = (target - cum_weights[i]) / (cum_weights[i + 1] - cum_weights[i])
            return sorted_vals[i] + frac * (sorted_vals[i + 1] - sorted_vals[i])

    return sorted_vals[-1]


# ═══════════════════════════════════════════════════════════
# SIGNAL LOGIC
# ═══════════════════════════════════════════════════════════

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
