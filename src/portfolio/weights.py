"""
Portfolio Weights — 4 weighting schemes for portfolio construction.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional


def equal_weight(tickers: List[str]) -> Dict[str, float]:
    """Equal 1/N allocation."""
    n = len(tickers)
    if n == 0:
        return {}
    w = 1.0 / n
    return {t: w for t in tickers}


def market_cap_weight(tickers: List[str], caps: Dict[str, float]) -> Dict[str, float]:
    """Market-cap proportional weights."""
    valid = {t: caps.get(t, 0) for t in tickers if caps.get(t, 0) > 0}
    if not valid:
        return equal_weight(tickers)
    total = sum(valid.values())
    return {t: v / total for t, v in valid.items()}


def inverse_vol_weight(returns_df: pd.DataFrame) -> Dict[str, float]:
    """
    Inverse-volatility weighting.
    Lower volatility tickers get higher weight.
    """
    if returns_df.empty:
        return {}
    vols = returns_df.std()
    vols = vols.replace(0, np.nan).dropna()
    if vols.empty:
        return equal_weight(list(returns_df.columns))
    inv = 1.0 / vols
    total = inv.sum()
    return {t: float(inv[t] / total) for t in inv.index}


def risk_parity_weight(returns_df: pd.DataFrame, max_iter: int = 100) -> Dict[str, float]:
    """
    Simplified risk-parity: each asset contributes equally to portfolio risk.
    Uses iterative Newton-like approach.
    """
    if returns_df.empty or len(returns_df.columns) < 2:
        return equal_weight(list(returns_df.columns)) if not returns_df.empty else {}

    cov = returns_df.cov().values
    n = cov.shape[0]
    tickers = list(returns_df.columns)

    # Start with equal weight
    w = np.ones(n) / n

    for _ in range(max_iter):
        port_vol = np.sqrt(w @ cov @ w)
        if port_vol < 1e-12:
            break
        # Marginal risk contribution
        mrc = (cov @ w) / port_vol
        # Risk contribution
        rc = w * mrc
        # Target: equal risk contribution
        target_rc = port_vol / n
        # Adjust weights proportionally
        adj = target_rc / (rc + 1e-12)
        w = w * adj
        w = w / w.sum()  # normalize

    return {tickers[i]: float(w[i]) for i in range(n)}
