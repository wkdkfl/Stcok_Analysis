"""
Quantitative / Technical analysis — Momentum, RSI, Bollinger, Moving Averages,
Factor Exposure (Fama-French), Earnings Momentum (SUE).
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional


def compute_quant_signals(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute all quantitative/technical signals."""
    history = data.get("history")
    result = {
        "momentum": _compute_momentum(history),
        "technicals": _compute_technicals(history, data),
        "earnings_momentum": _compute_sue(data),
        "overall_signal": "Neutral",
        "overall_color": "#FF9800",
    }

    # Aggregate
    scores = []
    for section in ["momentum", "technicals", "earnings_momentum"]:
        s = result[section].get("signal", "Neutral")
        if s == "Bullish":
            scores.append(1)
        elif s == "Bearish":
            scores.append(-1)
        else:
            scores.append(0)

    avg = np.mean(scores) if scores else 0
    if avg > 0.3:
        result["overall_signal"] = "Bullish"
        result["overall_color"] = "#4CAF50"
    elif avg < -0.3:
        result["overall_signal"] = "Bearish"
        result["overall_color"] = "#F44336"

    return result


def _compute_momentum(history: Optional[pd.DataFrame]) -> Dict[str, Any]:
    """12-1 month price momentum."""
    result = {"momentum_12m": None, "momentum_6m": None, "momentum_1m": None, "signal": "Neutral"}

    if history is None or len(history) < 252:
        return result

    close = history["Close"]
    if hasattr(close, 'iloc'):
        current = float(close.iloc[-1])
        m12 = float(close.iloc[-252]) if len(close) >= 252 else None
        m6 = float(close.iloc[-126]) if len(close) >= 126 else None
        m1 = float(close.iloc[-21]) if len(close) >= 21 else None

        # 12-1 month: exclude last month
        m12_ex = float(close.iloc[-22]) if len(close) >= 22 else current
        m12_start = float(close.iloc[-252]) if len(close) >= 252 else None

        if m12_start and m12_start > 0:
            result["momentum_12m"] = round((m12_ex / m12_start - 1) * 100, 1)
        if m6 and m6 > 0:
            result["momentum_6m"] = round((current / m6 - 1) * 100, 1)
        if m1 and m1 > 0:
            result["momentum_1m"] = round((current / m1 - 1) * 100, 1)

        # Signal based on 12-1 month momentum
        mom = result["momentum_12m"]
        if mom is not None:
            if mom > 15:
                result["signal"] = "Bullish"
            elif mom < -15:
                result["signal"] = "Bearish"

    return result


def _compute_technicals(history: Optional[pd.DataFrame], data: Dict) -> Dict[str, Any]:
    """RSI, Bollinger Bands, Moving Average signals."""
    result = {
        "rsi_14": None,
        "bollinger_position": None,
        "ma_50": None,
        "ma_200": None,
        "golden_cross": None,
        "death_cross": None,
        "fifty_two_week_proximity": None,
        "obv_trend": None,
        "signal": "Neutral",
    }

    if history is None or len(history) < 50:
        return result

    close = history["Close"]
    volume = history.get("Volume")

    # ── RSI (14-day) ─────────────────────────────────────
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = (-delta).where(delta < 0, 0.0)
    avg_gain = gain.rolling(14).mean()
    avg_loss = loss.rolling(14).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    if len(rsi.dropna()) > 0:
        result["rsi_14"] = round(float(rsi.iloc[-1]), 1)

    # ── Bollinger Bands ──────────────────────────────────
    sma20 = close.rolling(20).mean()
    std20 = close.rolling(20).std()
    if len(sma20.dropna()) > 0:
        upper = float(sma20.iloc[-1] + 2 * std20.iloc[-1])
        lower = float(sma20.iloc[-1] - 2 * std20.iloc[-1])
        current = float(close.iloc[-1])
        if upper != lower:
            position = (current - lower) / (upper - lower)
            result["bollinger_position"] = round(position, 2)
            # Band width (squeeze detection)
            bw = (upper - lower) / float(sma20.iloc[-1])
            result["bollinger_width"] = round(bw, 4)

    # ── Moving Averages ──────────────────────────────────
    if len(close) >= 50:
        ma50 = close.rolling(50).mean()
        result["ma_50"] = round(float(ma50.iloc[-1]), 2)

    if len(close) >= 200:
        ma200 = close.rolling(200).mean()
        result["ma_200"] = round(float(ma200.iloc[-1]), 2)

        # Golden/Death Cross detection (last 5 days)
        ma50_vals = close.rolling(50).mean()
        ma200_vals = close.rolling(200).mean()
        recent = pd.DataFrame({"ma50": ma50_vals, "ma200": ma200_vals}).dropna().tail(10)
        if len(recent) >= 2:
            crosses = recent["ma50"] - recent["ma200"]
            if crosses.iloc[-1] > 0 and crosses.iloc[0] < 0:
                result["golden_cross"] = True
            elif crosses.iloc[-1] < 0 and crosses.iloc[0] > 0:
                result["death_cross"] = True

    # ── 52-Week High Proximity ───────────────────────────
    high_52 = data.get("fifty_two_week_high")
    low_52 = data.get("fifty_two_week_low")
    current_price = data.get("current_price")
    if all([high_52, low_52, current_price]) and high_52 != low_52:
        prox = (current_price - low_52) / (high_52 - low_52)
        result["fifty_two_week_proximity"] = round(prox * 100, 1)

    # ── OBV Trend ────────────────────────────────────────
    if volume is not None and len(volume) > 20:
        direction = np.sign(close.diff())
        obv = (volume * direction).cumsum()
        obv_sma = obv.rolling(20).mean()
        if len(obv_sma.dropna()) > 0:
            if float(obv.iloc[-1]) > float(obv_sma.iloc[-1]):
                result["obv_trend"] = "Accumulation"
            else:
                result["obv_trend"] = "Distribution"

    # ── Aggregate Signal ─────────────────────────────────
    bull_count = 0
    bear_count = 0

    rsi = result["rsi_14"]
    if rsi is not None:
        if rsi < 30:
            bull_count += 1  # oversold
        elif rsi > 70:
            bear_count += 1  # overbought

    bp = result["bollinger_position"]
    if bp is not None:
        if bp < 0.2:
            bull_count += 1
        elif bp > 0.8:
            bear_count += 1

    if result.get("golden_cross"):
        bull_count += 2
    if result.get("death_cross"):
        bear_count += 2

    if current_price and result.get("ma_200"):
        if current_price > result["ma_200"]:
            bull_count += 1
        else:
            bear_count += 1

    if result["obv_trend"] == "Accumulation":
        bull_count += 1
    elif result["obv_trend"] == "Distribution":
        bear_count += 1

    if bull_count > bear_count + 1:
        result["signal"] = "Bullish"
    elif bear_count > bull_count + 1:
        result["signal"] = "Bearish"

    return result


def _compute_sue(data: Dict[str, Any]) -> Dict[str, Any]:
    """Standardized Unexpected Earnings (SUE) Score."""
    result = {"sue_score": None, "surprise_history": [], "signal": "Neutral"}

    eh = data.get("earnings_history")
    if eh is None or eh.empty:
        return result

    try:
        surprises = []
        for _, row in eh.iterrows():
            actual = row.get("epsActual", row.get("Reported EPS"))
            estimate = row.get("epsEstimate", row.get("EPS Estimate"))
            if actual is not None and estimate is not None and estimate != 0:
                surprise_pct = (actual - estimate) / abs(estimate)
                surprises.append(surprise_pct)

        if surprises:
            result["surprise_history"] = [round(s * 100, 1) for s in surprises]
            std = np.std(surprises) if len(surprises) > 1 else 0.01
            if std > 0:
                result["sue_score"] = round(surprises[0] / std, 2)

            # Recent surprises
            positive = sum(1 for s in surprises[:4] if s > 0)
            if positive >= 3:
                result["signal"] = "Bullish"
            elif positive <= 1:
                result["signal"] = "Bearish"
    except Exception:
        pass

    return result
