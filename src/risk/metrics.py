"""
Risk Metrics — Sharpe, Sortino, Max Drawdown, VaR/CVaR,
Leverage ratios, Hamada Beta.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import sys, os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import DCF_DEFAULTS
from src.market_context import get_market_defaults


def compute_risk_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute comprehensive risk metrics."""
    result = {
        "return_metrics": _compute_return_metrics(data),
        "leverage": _compute_leverage(data),
        "var": _compute_var(data),
        "overall_risk": "N/A",
    }

    # Overall risk assessment
    scores = []
    rm = result["return_metrics"]
    if rm.get("max_drawdown") is not None:
        mdd = abs(rm["max_drawdown"])
        if mdd > 50:
            scores.append(3)  # high risk
        elif mdd > 30:
            scores.append(2)
        else:
            scores.append(1)

    lev = result["leverage"]
    de = lev.get("debt_to_equity")
    if de is not None:
        if de > 2.0:
            scores.append(3)
        elif de > 1.0:
            scores.append(2)
        else:
            scores.append(1)

    ic = lev.get("interest_coverage")
    if ic is not None:
        if ic < 2:
            scores.append(3)
        elif ic < 5:
            scores.append(2)
        else:
            scores.append(1)

    if scores:
        avg = np.mean(scores)
        if avg >= 2.5:
            result["overall_risk"] = "High Risk"
        elif avg >= 1.5:
            result["overall_risk"] = "Moderate Risk"
        else:
            result["overall_risk"] = "Low Risk"

    return result


def _compute_return_metrics(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute Sharpe, Sortino, Max Drawdown."""
    result = {
        "sharpe_ratio": None,
        "sortino_ratio": None,
        "max_drawdown": None,
        "max_drawdown_date": None,
        "annual_volatility": None,
        "annual_return": None,
        "beta": data.get("beta"),
    }

    history = data.get("history")
    if history is None or len(history) < 100:
        return result

    close = history["Close"]
    daily_returns = close.pct_change().dropna()

    if len(daily_returns) < 50:
        return result

    _mkt = data.get("market", "US")
    rf_daily = get_market_defaults(_mkt)["risk_free_rate"] / 252

    # Annualized return
    total_days = len(daily_returns)
    years = total_days / 252
    total_return = float(close.iloc[-1]) / float(close.iloc[0]) - 1
    annual_return = (1 + total_return) ** (1 / years) - 1
    result["annual_return"] = round(annual_return * 100, 1)

    # Annual volatility
    annual_vol = float(daily_returns.std()) * np.sqrt(252)
    result["annual_volatility"] = round(annual_vol * 100, 1)

    # Sharpe Ratio
    excess = daily_returns.mean() - rf_daily
    if daily_returns.std() > 0:
        sharpe = (excess / daily_returns.std()) * np.sqrt(252)
        result["sharpe_ratio"] = round(float(sharpe), 2)

    # Sortino Ratio
    downside = daily_returns[daily_returns < 0]
    if len(downside) > 0 and downside.std() > 0:
        sortino = (excess / downside.std()) * np.sqrt(252)
        result["sortino_ratio"] = round(float(sortino), 2)

    # Max Drawdown
    cumulative = (1 + daily_returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdowns = cumulative / rolling_max - 1
    max_dd = float(drawdowns.min())
    result["max_drawdown"] = round(max_dd * 100, 1)

    try:
        dd_idx = drawdowns.idxmin()
        result["max_drawdown_date"] = str(dd_idx.date()) if dd_idx is not None else None
    except Exception:
        pass

    return result


def _compute_leverage(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute leverage and solvency metrics."""
    result = {
        "debt_to_equity": data.get("debt_to_equity"),
        "net_debt_to_ebitda": data.get("net_debt_to_ebitda"),
        "interest_coverage": data.get("interest_coverage"),
        "current_ratio": data.get("current_ratio"),
        "net_debt": data.get("net_debt"),
    }

    # Format
    for key in result:
        if result[key] is not None and isinstance(result[key], float):
            result[key] = round(result[key], 2)

    # Hamada Beta (unlevered)
    beta = data.get("beta")
    de = data.get("debt_to_equity")
    _mkt_lev = data.get("market", "US")
    tax = get_market_defaults(_mkt_lev)["tax_rate"]
    if beta and de:
        unlevered_beta = beta / (1 + (1 - tax) * de)
        result["unlevered_beta"] = round(unlevered_beta, 2)
    else:
        result["unlevered_beta"] = None

    return result


def _compute_var(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute Value at Risk and Conditional VaR."""
    result = {
        "var_95": None,
        "var_99": None,
        "cvar_95": None,
    }

    history = data.get("history")
    if history is None or len(history) < 100:
        return result

    daily_returns = history["Close"].pct_change().dropna()

    if len(daily_returns) < 50:
        return result

    # Historical VaR
    var_95 = float(np.percentile(daily_returns, 5))
    var_99 = float(np.percentile(daily_returns, 1))
    result["var_95"] = round(var_95 * 100, 2)
    result["var_99"] = round(var_99 * 100, 2)

    # Conditional VaR (Expected Shortfall)
    below_var = daily_returns[daily_returns <= var_95]
    if len(below_var) > 0:
        result["cvar_95"] = round(float(below_var.mean()) * 100, 2)

    return result
