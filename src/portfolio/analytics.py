"""
Portfolio Analytics — correlation, rolling metrics, factor exposure,
and portfolio-level performance attribution.
"""

import numpy as np
import pandas as pd
from typing import Dict, Any, Optional


def correlation_matrix(prices: pd.DataFrame) -> pd.DataFrame:
    """Compute pairwise return correlation matrix."""
    returns = prices.pct_change().dropna()
    if returns.empty:
        return pd.DataFrame()
    return returns.corr()


def portfolio_metrics(
    nav: pd.Series,
    benchmark_nav: pd.Series,
    rf_annual: float = 0.043,
) -> Dict[str, Any]:
    """
    Comprehensive portfolio metrics including Alpha, Beta,
    Information Ratio, Tracking Error.
    """
    daily_ret = nav.pct_change().dropna()
    bench_ret = benchmark_nav.pct_change().dropna()

    aligned = pd.DataFrame({"port": daily_ret, "bench": bench_ret}).dropna()
    if len(aligned) < 20:
        return {}

    years = len(aligned) / 252
    rf_daily = rf_annual / 252

    # Returns
    total_ret = float(nav.iloc[-1] / nav.iloc[0] - 1)
    ann_ret = (1 + total_ret) ** (1 / max(years, 0.01)) - 1

    # Volatility
    ann_vol = float(aligned["port"].std() * np.sqrt(252))

    # Sharpe
    excess = aligned["port"].mean() - rf_daily
    sharpe = float(excess / aligned["port"].std() * np.sqrt(252)) if aligned["port"].std() > 0 else 0

    # Beta / Alpha
    cov_m = np.cov(aligned["port"], aligned["bench"])
    beta = float(cov_m[0, 1] / cov_m[1, 1]) if cov_m[1, 1] > 0 else 1.0

    bench_total = float(benchmark_nav.iloc[-1] / benchmark_nav.iloc[0] - 1)
    bench_ann = (1 + bench_total) ** (1 / max(years, 0.01)) - 1
    alpha = ann_ret - (rf_annual + beta * (bench_ann - rf_annual))

    # Tracking Error & Information Ratio
    active = aligned["port"] - aligned["bench"]
    tracking_error = float(active.std() * np.sqrt(252))
    info_ratio = float(active.mean() / active.std() * np.sqrt(252)) if active.std() > 0 else 0

    # Max Drawdown
    cum = (1 + aligned["port"]).cumprod()
    dd = cum / cum.cummax() - 1
    max_dd = float(dd.min())

    return {
        "total_return": round(total_ret * 100, 2),
        "annual_return": round(ann_ret * 100, 2),
        "annual_volatility": round(ann_vol * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "beta": round(beta, 2),
        "alpha": round(alpha * 100, 2),
        "tracking_error": round(tracking_error * 100, 2),
        "information_ratio": round(info_ratio, 2),
        "max_drawdown": round(max_dd * 100, 2),
    }


def rolling_metrics(
    nav: pd.Series,
    benchmark_nav: pd.Series,
    window: int = 252,
    rf_annual: float = 0.043,
) -> Dict[str, pd.Series]:
    """Compute rolling Sharpe, volatility, and beta."""
    daily_ret = nav.pct_change().dropna()
    bench_ret = benchmark_nav.pct_change().dropna()
    rf_daily = rf_annual / 252

    rolling_sharpe = (
        (daily_ret.rolling(window).mean() - rf_daily) /
        daily_ret.rolling(window).std()
    ) * np.sqrt(252)

    rolling_vol = daily_ret.rolling(window).std() * np.sqrt(252) * 100

    # Rolling beta
    aligned = pd.DataFrame({"port": daily_ret, "bench": bench_ret}).dropna()
    cov_roll = aligned["port"].rolling(window).cov(aligned["bench"])
    var_roll = aligned["bench"].rolling(window).var()
    rolling_beta = cov_roll / var_roll

    return {
        "rolling_sharpe": rolling_sharpe.dropna(),
        "rolling_volatility": rolling_vol.dropna(),
        "rolling_beta": rolling_beta.dropna(),
    }


def factor_exposure(nav: pd.Series) -> Optional[Dict[str, Any]]:
    """
    Regress portfolio returns against Fama-French 5 factors + Momentum.
    Returns factor loadings and R².
    """
    try:
        from src.fetcher.factors import fetch_ff_factors
        ff = fetch_ff_factors()
        if ff is None:
            return None

        daily_ret = nav.pct_change().dropna()
        daily_ret.index = pd.to_datetime(daily_ret.index)

        # Align dates
        ff.index = pd.to_datetime(ff.index)
        merged = pd.DataFrame({"port": daily_ret}).join(ff, how="inner").dropna()

        if len(merged) < 60:
            return None

        # OLS regression: port - RF = a + b1*MktRF + b2*SMB + ... + e
        y = merged["port"] - merged["RF"]
        factor_cols = [c for c in ["Mkt-RF", "SMB", "HML", "RMW", "CMA", "Mom"] if c in merged.columns]
        X = merged[factor_cols]
        X = X.assign(const=1.0)

        # Least squares
        result = np.linalg.lstsq(X.values, y.values, rcond=None)
        coeffs = result[0]

        # R²
        y_pred = X.values @ coeffs
        ss_res = np.sum((y.values - y_pred) ** 2)
        ss_tot = np.sum((y.values - y.values.mean()) ** 2)
        r_squared = 1 - ss_res / ss_tot if ss_tot > 0 else 0

        loadings = {}
        for i, col in enumerate(factor_cols):
            loadings[col] = round(float(coeffs[i]), 4)
        loadings["alpha_daily"] = round(float(coeffs[-1]), 6)
        loadings["r_squared"] = round(float(r_squared), 4)

        return loadings

    except Exception:
        return None


def monthly_returns_table(nav: pd.Series) -> pd.DataFrame:
    """
    Create a monthly returns pivot table (rows=year, cols=month).
    Values in percent.
    """
    daily_ret = nav.pct_change().dropna()
    daily_ret.index = pd.to_datetime(daily_ret.index)

    monthly = daily_ret.resample("M").apply(lambda x: (1 + x).prod() - 1)
    monthly = monthly * 100

    table = pd.DataFrame()
    table["Year"] = monthly.index.year
    table["Month"] = monthly.index.month
    table["Return"] = monthly.values

    pivot = table.pivot_table(values="Return", index="Year", columns="Month", aggfunc="first")
    pivot.columns = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
                     "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][:len(pivot.columns)]

    # Add annual total
    annual = daily_ret.resample("Y").apply(lambda x: (1 + x).prod() - 1) * 100
    year_map = dict(zip(annual.index.year, annual.values))
    pivot["연간"] = pivot.index.map(lambda y: round(year_map.get(y, 0), 2))

    return pivot.round(2)


def contribution_by_ticker(
    prices: pd.DataFrame,
    weights: Dict[str, float],
) -> pd.DataFrame:
    """
    Compute return contribution by each ticker
    given initial weights (buy & hold from start).
    """
    if prices.empty:
        return pd.DataFrame()

    total_returns = (prices.iloc[-1] / prices.iloc[0] - 1)
    contributions = []
    for t in prices.columns:
        w = weights.get(t, 0)
        ret = total_returns.get(t, 0)
        if pd.notna(ret):
            contributions.append({
                "티커": t,
                "비중": round(w * 100, 2),
                "수익률(%)": round(float(ret) * 100, 2),
                "기여(%)": round(w * float(ret) * 100, 2),
            })
    df = pd.DataFrame(contributions)
    if not df.empty:
        df = df.sort_values("기여(%)", ascending=False).reset_index(drop=True)
    return df
