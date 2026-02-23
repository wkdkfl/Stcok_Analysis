"""
Backtest Engine — run historical simulations for 4 strategies.

Strategies:
  1. Equal-weight Buy & Hold
  2. Momentum (12-1 month top N)
  3. Moving Average Crossover (50/200 day)
  4. Screener Grade (current grade → past returns)
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class Strategy(Enum):
    EQUAL_WEIGHT = "equal_weight"
    MOMENTUM = "momentum"
    MA_CROSSOVER = "ma_crossover"
    SCREENER_GRADE = "screener_grade"


@dataclass
class BacktestConfig:
    tickers: List[str]
    start: str                       # "YYYY-MM-DD"
    end: str                         # "YYYY-MM-DD"
    strategy: Strategy = Strategy.EQUAL_WEIGHT
    initial_capital: float = 100_000
    rebalance_freq: str = "M"        # M=monthly, Q=quarterly, 6M, Y
    benchmark_ticker: str = "SPY"
    transaction_cost: float = 0.001  # 0.1%
    top_n: int = 10                  # for momentum / screener strategies
    ma_short: int = 50
    ma_long: int = 200


@dataclass
class BacktestResult:
    nav_series: pd.Series              # daily NAV (index=date)
    benchmark_series: pd.Series        # daily benchmark NAV
    trades_log: List[Dict[str, Any]]   # list of trade events
    metrics: Dict[str, Any]            # summary stats
    weights_history: List[Dict[str, Any]] = field(default_factory=list)
    strategy_name: str = ""


def run_backtest(config: BacktestConfig, prices: pd.DataFrame,
                 benchmark_prices: pd.Series) -> BacktestResult:
    """
    Run a backtest given pre-fetched price data.

    Parameters
    ----------
    config : BacktestConfig
    prices : DataFrame with columns=tickers, index=dates, values=close prices
    benchmark_prices : Series with benchmark close prices (same date range)

    Returns
    -------
    BacktestResult
    """
    prices = prices.ffill().dropna(how="all")
    common_idx = prices.index.intersection(benchmark_prices.index)
    if len(common_idx) < 20:
        raise ValueError("데이터가 부족합니다. 기간을 조정하세요.")

    prices = prices.loc[common_idx]
    benchmark_prices = benchmark_prices.loc[common_idx]

    # Dispatch to strategy
    if config.strategy == Strategy.EQUAL_WEIGHT:
        return _run_equal_weight(config, prices, benchmark_prices)
    elif config.strategy == Strategy.MOMENTUM:
        return _run_momentum(config, prices, benchmark_prices)
    elif config.strategy == Strategy.MA_CROSSOVER:
        return _run_ma_crossover(config, prices, benchmark_prices)
    elif config.strategy == Strategy.SCREENER_GRADE:
        return _run_screener_grade(config, prices, benchmark_prices)
    else:
        return _run_equal_weight(config, prices, benchmark_prices)


# ═══════════════════════════════════════════════════════════
# Helper: rebalance date generation
# ═══════════════════════════════════════════════════════════

def _get_rebalance_dates(index: pd.DatetimeIndex, freq: str) -> List[pd.Timestamp]:
    """Generate rebalance dates aligned to trading calendar."""
    if freq == "M":
        month_ends = index.to_series().groupby(index.to_period("M")).last()
    elif freq == "Q":
        month_ends = index.to_series().groupby(index.to_period("Q")).last()
    elif freq == "6M":
        month_ends = index.to_series().groupby(index.to_period("6M")).last()
    elif freq == "Y":
        month_ends = index.to_series().groupby(index.to_period("Y")).last()
    else:
        month_ends = index.to_series().groupby(index.to_period("M")).last()
    return list(month_ends.values)


def _compute_nav(
    prices: pd.DataFrame,
    weights_at_rebalance: Dict[pd.Timestamp, Dict[str, float]],
    initial_capital: float,
    transaction_cost: float,
) -> tuple:
    """
    Compute daily NAV from weight allocations at rebalance dates.

    Returns (nav_series, trades_log, weights_history)
    """
    dates = prices.index
    nav = pd.Series(index=dates, dtype=float)
    trades_log = []
    weights_history = []
    cash = initial_capital
    holdings: Dict[str, float] = {}  # ticker → number of shares (fractional)

    sorted_rebal_dates = sorted(weights_at_rebalance.keys())
    next_rebal_idx = 0

    for i, date in enumerate(dates):
        # Check if rebalance
        if next_rebal_idx < len(sorted_rebal_dates) and date >= sorted_rebal_dates[next_rebal_idx]:
            target_weights = weights_at_rebalance[sorted_rebal_dates[next_rebal_idx]]
            next_rebal_idx += 1

            # Current portfolio value
            pf_value = cash
            for t, shares in holdings.items():
                if t in prices.columns:
                    p = prices.loc[date, t]
                    if pd.notna(p):
                        pf_value += shares * p

            # Execute rebalance
            new_holdings = {}
            total_cost = 0.0
            trade_details = []
            for t, w in target_weights.items():
                if t not in prices.columns:
                    continue
                p = prices.loc[date, t]
                if pd.isna(p) or p <= 0:
                    continue
                target_value = pf_value * w
                new_shares = target_value / p
                old_shares = holdings.get(t, 0.0)
                delta = new_shares - old_shares
                cost = abs(delta * p) * transaction_cost
                total_cost += cost
                new_holdings[t] = new_shares
                if abs(delta) > 0.001:
                    trade_details.append({
                        "ticker": t,
                        "action": "BUY" if delta > 0 else "SELL",
                        "shares": round(abs(delta), 2),
                        "price": round(p, 2),
                        "value": round(abs(delta * p), 0),
                    })

            holdings = new_holdings
            cash = 0  # fully invested
            # Deduct transaction costs from NAV
            pf_value -= total_cost

            if trade_details:
                trades_log.append({
                    "date": str(date.date()) if hasattr(date, 'date') else str(date),
                    "trades": trade_details,
                    "cost": round(total_cost, 2),
                    "portfolio_value": round(pf_value, 0),
                })
                weights_history.append({
                    "date": str(date.date()) if hasattr(date, 'date') else str(date),
                    "weights": {t: round(w, 4) for t, w in target_weights.items()},
                })

        # Compute daily NAV
        pf_value = cash
        for t, shares in holdings.items():
            if t in prices.columns:
                p = prices.loc[date, t]
                if pd.notna(p):
                    pf_value += shares * p
        nav.iloc[i] = pf_value

    return nav, trades_log, weights_history


def _build_benchmark_nav(benchmark_prices: pd.Series, initial_capital: float) -> pd.Series:
    """Convert benchmark prices to NAV starting at initial_capital."""
    return (benchmark_prices / benchmark_prices.iloc[0]) * initial_capital


def _compute_metrics(nav: pd.Series, bench_nav: pd.Series, rf_annual: float = 0.043) -> Dict[str, Any]:
    """Compute summary metrics for backtest."""
    days = len(nav)
    years = days / 252

    total_ret = (nav.iloc[-1] / nav.iloc[0] - 1) * 100
    ann_ret = ((nav.iloc[-1] / nav.iloc[0]) ** (1 / max(years, 0.01)) - 1) * 100

    daily_ret = nav.pct_change().dropna()
    ann_vol = float(daily_ret.std() * np.sqrt(252) * 100)

    rf_daily = rf_annual / 252
    excess = daily_ret.mean() - rf_daily
    sharpe = float((excess / daily_ret.std()) * np.sqrt(252)) if daily_ret.std() > 0 else 0

    downside = daily_ret[daily_ret < 0]
    sortino = float((excess / downside.std()) * np.sqrt(252)) if len(downside) > 0 and downside.std() > 0 else 0

    cum = (1 + daily_ret).cumprod()
    rolling_max = cum.cummax()
    dd = cum / rolling_max - 1
    max_dd = float(dd.min() * 100)

    calmar = ann_ret / abs(max_dd) if abs(max_dd) > 0 else 0

    # Benchmark metrics
    bench_ret = (bench_nav.iloc[-1] / bench_nav.iloc[0] - 1) * 100
    bench_daily = bench_nav.pct_change().dropna()
    bench_ann_ret = ((bench_nav.iloc[-1] / bench_nav.iloc[0]) ** (1 / max(years, 0.01)) - 1) * 100

    # Alpha / Beta
    aligned = pd.DataFrame({"port": daily_ret, "bench": bench_daily}).dropna()
    if len(aligned) > 20:
        cov_matrix = np.cov(aligned["port"], aligned["bench"])
        beta = float(cov_matrix[0, 1] / cov_matrix[1, 1]) if cov_matrix[1, 1] > 0 else 1.0
        alpha = ann_ret - (rf_annual * 100 + beta * (bench_ann_ret - rf_annual * 100))
    else:
        beta = 1.0
        alpha = 0

    # Win rate
    win_rate = float((daily_ret > 0).sum() / len(daily_ret) * 100) if len(daily_ret) > 0 else 0

    return {
        "total_return": round(total_ret, 2),
        "annual_return": round(ann_ret, 2),
        "annual_volatility": round(ann_vol, 2),
        "sharpe_ratio": round(sharpe, 2),
        "sortino_ratio": round(sortino, 2),
        "max_drawdown": round(max_dd, 2),
        "calmar_ratio": round(calmar, 2),
        "alpha": round(alpha, 2),
        "beta": round(beta, 2),
        "win_rate": round(win_rate, 1),
        "benchmark_return": round(bench_ret, 2),
        "benchmark_ann_return": round(bench_ann_ret, 2),
        "trading_days": days,
        "years": round(years, 1),
    }


# ═══════════════════════════════════════════════════════════
# Strategy 1: Equal-Weight Buy & Hold
# ═══════════════════════════════════════════════════════════

def _run_equal_weight(config, prices, benchmark_prices):
    tickers = [t for t in config.tickers if t in prices.columns]
    if not tickers:
        raise ValueError("유효한 종목이 없습니다.")

    rebal_dates = _get_rebalance_dates(prices.index, config.rebalance_freq)
    if not rebal_dates:
        rebal_dates = [prices.index[0]]

    w = 1.0 / len(tickers)
    weights_map = {}
    for d in rebal_dates:
        weights_map[d] = {t: w for t in tickers}

    nav, trades, weights_hist = _compute_nav(prices, weights_map,
                                              config.initial_capital, config.transaction_cost)
    bench_nav = _build_benchmark_nav(benchmark_prices, config.initial_capital)
    metrics = _compute_metrics(nav, bench_nav)

    return BacktestResult(
        nav_series=nav,
        benchmark_series=bench_nav,
        trades_log=trades,
        metrics=metrics,
        weights_history=weights_hist,
        strategy_name="동일 비중 (Equal Weight)",
    )


# ═══════════════════════════════════════════════════════════
# Strategy 2: Momentum (12-1 month)
# ═══════════════════════════════════════════════════════════

def _run_momentum(config, prices, benchmark_prices):
    rebal_dates = _get_rebalance_dates(prices.index, config.rebalance_freq)
    top_n = min(config.top_n, len(prices.columns))

    weights_map = {}
    for d in rebal_dates:
        # Look back 252 trading days (12m), skip last 21 (1m)
        loc = prices.index.get_loc(d)
        if loc < 252:
            # Not enough history, equal-weight all
            valid = list(prices.columns)
            w = 1.0 / len(valid) if valid else 0
            weights_map[d] = {t: w for t in valid}
            continue

        past_12m = prices.iloc[max(0, loc - 252):max(0, loc - 21)]
        if past_12m.empty:
            continue

        # 12-1 momentum score: return over 12m minus last 1m
        mom_scores = {}
        for t in prices.columns:
            series = past_12m[t].dropna()
            if len(series) > 50:
                ret = series.iloc[-1] / series.iloc[0] - 1
                mom_scores[t] = ret

        if not mom_scores:
            continue

        ranked = sorted(mom_scores.items(), key=lambda x: x[1], reverse=True)[:top_n]
        w = 1.0 / len(ranked)
        weights_map[d] = {t: w for t, _ in ranked}

    if not weights_map:
        # Fallback to equal weight at start
        tickers = list(prices.columns)
        w = 1.0 / len(tickers) if tickers else 0
        weights_map[prices.index[0]] = {t: w for t in tickers}

    nav, trades, weights_hist = _compute_nav(prices, weights_map,
                                              config.initial_capital, config.transaction_cost)
    bench_nav = _build_benchmark_nav(benchmark_prices, config.initial_capital)
    metrics = _compute_metrics(nav, bench_nav)

    return BacktestResult(
        nav_series=nav,
        benchmark_series=bench_nav,
        trades_log=trades,
        metrics=metrics,
        weights_history=weights_hist,
        strategy_name="모멘텀 (12-1M)",
    )


# ═══════════════════════════════════════════════════════════
# Strategy 3: Moving Average Crossover (50/200)
# ═══════════════════════════════════════════════════════════

def _run_ma_crossover(config, prices, benchmark_prices):
    ma_short = config.ma_short
    ma_long = config.ma_long
    rebal_dates = _get_rebalance_dates(prices.index, config.rebalance_freq)

    weights_map = {}
    for d in rebal_dates:
        loc = prices.index.get_loc(d)
        if loc < ma_long:
            tickers = list(prices.columns)
            w = 1.0 / len(tickers) if tickers else 0
            weights_map[d] = {t: w for t in tickers}
            continue

        # Check MA crossover for each ticker
        bullish = []
        for t in prices.columns:
            series = prices[t].iloc[:loc + 1]
            short_ma = series.rolling(ma_short).mean().iloc[-1]
            long_ma = series.rolling(ma_long).mean().iloc[-1]
            if pd.notna(short_ma) and pd.notna(long_ma) and short_ma > long_ma:
                bullish.append(t)

        if bullish:
            w = 1.0 / len(bullish)
            weights_map[d] = {t: w for t in bullish}
        else:
            # All cash — hold benchmark proxy or just flat
            # Represent as zero weight (NAV stays flat)
            weights_map[d] = {}

    if not weights_map:
        tickers = list(prices.columns)
        w = 1.0 / len(tickers) if tickers else 0
        weights_map[prices.index[0]] = {t: w for t in tickers}

    nav, trades, weights_hist = _compute_nav(prices, weights_map,
                                              config.initial_capital, config.transaction_cost)
    bench_nav = _build_benchmark_nav(benchmark_prices, config.initial_capital)
    metrics = _compute_metrics(nav, bench_nav)

    return BacktestResult(
        nav_series=nav,
        benchmark_series=bench_nav,
        trades_log=trades,
        metrics=metrics,
        weights_history=weights_hist,
        strategy_name=f"MA 크로스오버 ({ma_short}/{ma_long})",
    )


# ═══════════════════════════════════════════════════════════
# Strategy 4: Screener Grade (current grades → past returns)
# ═══════════════════════════════════════════════════════════

def _run_screener_grade(config, prices, benchmark_prices):
    """
    Uses current screener grades to select top N stocks,
    then backtests as if those stocks were bought at start of period.
    Note: Grades are NOT historically recomputed — this is a
    'what if I had bought today's top stocks N months ago?' test.
    """
    # Just equal-weight the provided tickers (pre-filtered by grade in app.py)
    tickers = [t for t in config.tickers if t in prices.columns]
    if not tickers:
        raise ValueError("유효한 종목이 없습니다.")

    # Rebalance on start date only (buy & hold with current picks)
    rebal_dates = _get_rebalance_dates(prices.index, config.rebalance_freq)
    if not rebal_dates:
        rebal_dates = [prices.index[0]]

    w = 1.0 / len(tickers)
    weights_map = {}
    for d in rebal_dates:
        weights_map[d] = {t: w for t in tickers}

    nav, trades, weights_hist = _compute_nav(prices, weights_map,
                                              config.initial_capital, config.transaction_cost)
    bench_nav = _build_benchmark_nav(benchmark_prices, config.initial_capital)
    metrics = _compute_metrics(nav, bench_nav)

    return BacktestResult(
        nav_series=nav,
        benchmark_series=bench_nav,
        trades_log=trades,
        metrics=metrics,
        weights_history=weights_hist,
        strategy_name="스크리너 등급 기반",
    )
