"""
Multi-Stage Discounted Cash Flow (DCF) Model with Monte Carlo Simulation.
- 3-stage: High Growth → Fade → Terminal
- Monte Carlo: 10,000 simulations varying growth, WACC, margins
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import DCF_DEFAULTS
from src.fetcher.yahoo import get_stmt_series, _get_stmt_value
from src.market_context import get_dcf_overrides


def compute_dcf(data: Dict[str, Any], overrides: Optional[Dict] = None) -> Dict[str, Any]:
    """
    Compute intrinsic value using Multi-Stage DCF with Monte Carlo.

    Parameters:
        data: Stock data dictionary from fetcher
        overrides: Optional overrides for DCF assumptions (from UI sliders)

    Returns:
        Dictionary with fair_value, upside_pct, mc_distribution, etc.
    """
    market = data.get("market", "US")
    cfg = {**DCF_DEFAULTS, **get_dcf_overrides(market), **(overrides or {})}
    result = {
        "model": "Multi-Stage DCF",
        "fair_value": None,
        "upside_pct": None,
        "confidence": "N/A",
        "details": {},
    }

    # ── Get inputs ───────────────────────────────────────
    fcf = data.get("fcf")
    current_price = data.get("current_price")
    shares = data.get("shares_outstanding")
    beta = data.get("beta") or 1.0
    total_debt = data.get("total_debt") or 0
    cash = data.get("cash") or 0
    market_cap = data.get("market_cap")

    if not all([fcf, current_price, shares]) or fcf <= 0:
        result["confidence"] = "Insufficient Data"
        result["details"]["error"] = "FCF not available or negative"
        return result

    # ── Estimate growth rate ─────────────────────────────
    growth_rate = _estimate_growth_rate(data)
    risk_free = cfg.get("risk_free_rate", 0.043)
    erp = cfg.get("equity_risk_premium", 0.055)

    # ── WACC calculation ─────────────────────────────────
    cost_of_equity = risk_free + beta * erp
    cost_of_debt = _estimate_cost_of_debt(data, risk_free)
    tax_rate = cfg["tax_rate"]

    if market_cap and total_debt:
        total_capital = market_cap + total_debt
        equity_weight = market_cap / total_capital
        debt_weight = total_debt / total_capital
    else:
        equity_weight = 0.8
        debt_weight = 0.2

    wacc = equity_weight * cost_of_equity + debt_weight * cost_of_debt * (1 - tax_rate)
    wacc = max(wacc, 0.06)  # floor at 6%

    # ── Deterministic DCF ────────────────────────────────
    fair_value_per_share = _dcf_valuation(
        fcf=fcf,
        growth_high=growth_rate,
        growth_terminal=cfg["terminal_growth_rate"],
        wacc=wacc,
        high_years=cfg["high_growth_years"],
        fade_years=cfg["fade_years"],
        total_debt=total_debt,
        cash=cash,
        shares=shares,
    )

    result["fair_value"] = round(fair_value_per_share, 2) if fair_value_per_share else None
    if fair_value_per_share and current_price:
        result["upside_pct"] = round((fair_value_per_share / current_price - 1) * 100, 1)

    # ── Monte Carlo Simulation ───────────────────────────
    n_sim = cfg["monte_carlo_simulations"]
    mc_values = []

    np.random.seed(42)
    growth_samples = np.random.normal(growth_rate, cfg["growth_rate_std"], n_sim)
    wacc_samples = np.random.normal(wacc, cfg["wacc_std"], n_sim)
    margin_factors = np.random.normal(1.0, cfg["margin_std"], n_sim)

    for i in range(n_sim):
        g = max(growth_samples[i], -0.05)  # floor growth at -5%
        w = max(wacc_samples[i], 0.04)     # floor WACC at 4%
        adj_fcf = fcf * margin_factors[i]
        if adj_fcf <= 0:
            continue

        val = _dcf_valuation(
            fcf=adj_fcf,
            growth_high=g,
            growth_terminal=cfg["terminal_growth_rate"],
            wacc=w,
            high_years=cfg["high_growth_years"],
            fade_years=cfg["fade_years"],
            total_debt=total_debt,
            cash=cash,
            shares=shares,
        )
        if val and val > 0:
            mc_values.append(val)

    if mc_values:
        mc_arr = np.array(mc_values)
        result["mc_median"] = round(float(np.median(mc_arr)), 2)
        result["mc_mean"] = round(float(np.mean(mc_arr)), 2)
        result["mc_p10"] = round(float(np.percentile(mc_arr, 10)), 2)
        result["mc_p25"] = round(float(np.percentile(mc_arr, 25)), 2)
        result["mc_p75"] = round(float(np.percentile(mc_arr, 75)), 2)
        result["mc_p90"] = round(float(np.percentile(mc_arr, 90)), 2)
        result["mc_distribution"] = mc_arr
    else:
        result["mc_distribution"] = np.array([])

    # ── Confidence ───────────────────────────────────────
    result["confidence"] = _assess_confidence(data, growth_rate, wacc)

    # ── Details ──────────────────────────────────────────
    result["details"] = {
        "fcf": fcf,
        "growth_rate": round(growth_rate * 100, 2),
        "wacc": round(wacc * 100, 2),
        "cost_of_equity": round(cost_of_equity * 100, 2),
        "cost_of_debt": round(cost_of_debt * 100, 2),
        "beta": beta,
        "terminal_growth": round(cfg["terminal_growth_rate"] * 100, 2),
        "equity_weight": round(equity_weight * 100, 1),
    }

    return result


def _dcf_valuation(fcf, growth_high, growth_terminal, wacc,
                   high_years, fade_years, total_debt, cash, shares) -> Optional[float]:
    """Core DCF calculation: 3-stage model."""
    if wacc <= growth_terminal:
        return None

    pv_fcf = 0.0
    current_fcf = fcf
    year = 0

    # Stage 1: High growth
    for y in range(1, high_years + 1):
        current_fcf *= (1 + growth_high)
        pv_fcf += current_fcf / ((1 + wacc) ** y)
        year = y

    # Stage 2: Fade (linear interpolation from high to terminal growth)
    for y in range(1, fade_years + 1):
        fade_pct = y / fade_years
        fade_growth = growth_high * (1 - fade_pct) + growth_terminal * fade_pct
        current_fcf *= (1 + fade_growth)
        total_year = high_years + y
        pv_fcf += current_fcf / ((1 + wacc) ** total_year)
        year = total_year

    # Stage 3: Terminal value (Gordon Growth)
    terminal_fcf = current_fcf * (1 + growth_terminal)
    terminal_value = terminal_fcf / (wacc - growth_terminal)
    pv_terminal = terminal_value / ((1 + wacc) ** year)

    # Enterprise Value → Equity Value → Per Share
    enterprise_value = pv_fcf + pv_terminal
    equity_value = enterprise_value - total_debt + cash

    if shares and shares > 0 and equity_value > 0:
        return equity_value / shares
    return None


def _estimate_growth_rate(data: Dict[str, Any]) -> float:
    """Estimate future FCF growth rate from multiple signals."""
    estimates = []

    # 1. Analyst consensus EPS growth
    eg = data.get("earnings_growth")
    if eg and isinstance(eg, (int, float)):
        estimates.append(eg)

    # 2. Revenue growth (trailing)
    rg = data.get("revenue_growth")
    if rg and isinstance(rg, (int, float)):
        estimates.append(rg)

    # 3. Historical revenue CAGR
    hist = data.get("revenue_growth_hist")
    if hist is not None and len(hist) > 0:
        avg = hist.mean()
        if not np.isnan(avg):
            estimates.append(avg)

    # 4. Sustainable growth rate: ROE × (1 - payout)
    roe = data.get("roe")
    payout = data.get("payout_ratio") or 0
    if roe and isinstance(roe, (int, float)):
        sgr = roe * (1 - min(payout, 1.0))
        estimates.append(sgr)

    if estimates:
        # Weighted: analyst > recent revenue > historical > SGR
        weights = [0.35, 0.25, 0.25, 0.15][:len(estimates)]
        weights = [w / sum(weights) for w in weights]
        growth = sum(e * w for e, w in zip(estimates, weights))
        # Cap at reasonable bounds
        return max(min(growth, 0.40), -0.10)

    return 0.05  # fallback 5%


def _estimate_cost_of_debt(data: Dict[str, Any], risk_free: float) -> float:
    """Estimate cost of debt from interest expense and total debt."""
    ie = data.get("interest_expense")
    td = data.get("total_debt")
    if ie and td and td > 0:
        cost = abs(ie) / td
        return max(cost, risk_free)  # at least risk-free
    return risk_free + 0.02  # fallback: Rf + 2% spread


def _assess_confidence(data: Dict[str, Any], growth: float, wacc: float) -> str:
    """Assess DCF confidence level based on data quality."""
    score = 0

    if data.get("fcf") and data["fcf"] > 0:
        score += 2
    if data.get("revenue_growth_hist") is not None:
        score += 1
    if data.get("earnings_growth") is not None:
        score += 1
    if data.get("beta") is not None:
        score += 1
    if abs(growth) < 0.25:
        score += 1  # moderate growth = more reliable
    if data.get("interest_expense") is not None:
        score += 1

    if score >= 6:
        return "High"
    elif score >= 4:
        return "Medium"
    else:
        return "Low"
