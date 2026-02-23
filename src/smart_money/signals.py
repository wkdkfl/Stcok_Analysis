"""
Smart Money Signals — Insider transactions, institutional ownership, short interest, buybacks.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any


def compute_smart_money(data: Dict[str, Any], guru_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Compute smart money signals from insider/institutional data + guru holdings."""
    result = {
        "insider": _analyze_insiders(data),
        "institutional": _analyze_institutional(data),
        "short_interest": _analyze_short(data),
        "buyback": _analyze_buyback(data),
        "guru": guru_data or {"guru_holders": [], "guru_count": 0, "total_guru_value": 0},
        "overall_signal": "Neutral",
        "overall_color": "#FF9800",
    }

    # Aggregate signal
    scores = []
    ins = result["insider"]
    if ins.get("signal") == "Bullish":
        scores.append(1)
    elif ins.get("signal") == "Bearish":
        scores.append(-1)
    else:
        scores.append(0)

    si = result["short_interest"]
    if si.get("signal") == "Bullish":
        scores.append(1)
    elif si.get("signal") == "Bearish":
        scores.append(-1)
    else:
        scores.append(0)

    bb = result["buyback"]
    if bb.get("signal") == "Bullish":
        scores.append(1)
    else:
        scores.append(0)

    # Guru investor signal — having gurus hold this stock is bullish
    guru_count = result["guru"].get("guru_count", 0)
    if guru_count >= 3:
        scores.append(1)
    elif guru_count >= 1:
        scores.append(0.5)
    else:
        scores.append(0)

    avg = np.mean(scores) if scores else 0
    if avg > 0.3:
        result["overall_signal"] = "Bullish"
        result["overall_color"] = "#4CAF50"
    elif avg < -0.3:
        result["overall_signal"] = "Bearish"
        result["overall_color"] = "#F44336"
    else:
        result["overall_signal"] = "Neutral"
        result["overall_color"] = "#FF9800"

    return result


def _analyze_insiders(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze insider transactions."""
    result = {
        "signal": "Neutral",
        "recent_buys": 0,
        "recent_sells": 0,
        "net_signal": "N/A",
        "transactions": [],
    }

    it = data.get("insider_transactions")
    if it is None or it.empty:
        return result

    try:
        # Count buys vs sells
        buys = 0
        sells = 0
        for _, row in it.iterrows():
            text = str(row.get("Text", row.get("Transaction", ""))).lower()
            shares = row.get("Shares", row.get("Value", 0))
            if "purchase" in text or "buy" in text or "acquisition" in text:
                buys += 1
            elif "sale" in text or "sell" in text:
                sells += 1

        result["recent_buys"] = buys
        result["recent_sells"] = sells

        if buys > 0 and buys > sells:
            result["signal"] = "Bullish"
            result["net_signal"] = f"Net Buying ({buys} buys vs {sells} sells)"
        elif sells > buys * 2:
            result["signal"] = "Bearish"
            result["net_signal"] = f"Net Selling ({sells} sells vs {buys} buys)"
        else:
            result["net_signal"] = f"Mixed ({buys} buys, {sells} sells)"

        # Top 5 recent transactions
        result["transactions"] = it.head(5).to_dict("records") if len(it) > 0 else []

    except Exception:
        pass

    return result


def _analyze_institutional(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze institutional holdings."""
    result = {
        "pct_institutions": data.get("held_pct_institutions"),
        "pct_insiders": data.get("held_pct_insiders"),
        "top_holders": [],
    }

    ih = data.get("institutional_holders")
    if ih is not None and not ih.empty:
        try:
            result["top_holders"] = ih.head(10).to_dict("records")
        except Exception:
            pass

    return result


def _analyze_short(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze short interest."""
    result = {
        "short_ratio": data.get("short_ratio"),
        "short_pct_float": data.get("short_pct_float"),
        "signal": "Neutral",
        "risk_level": "Normal",
    }

    spf = data.get("short_pct_float")
    sr = data.get("short_ratio")

    if spf is not None:
        if isinstance(spf, (int, float)):
            pct = spf * 100 if spf < 1 else spf  # normalize
            if pct > 20:
                result["risk_level"] = "Very High (Squeeze Potential)"
                result["signal"] = "Bearish"
            elif pct > 10:
                result["risk_level"] = "Elevated"
                result["signal"] = "Bearish"
            elif pct < 3:
                result["risk_level"] = "Low"
                result["signal"] = "Bullish"

    if sr is not None and sr > 5:
        result["risk_level"] = result["risk_level"] + " (High Days to Cover)"

    return result


def _analyze_buyback(data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze share buyback activity."""
    result = {
        "buyback_amount": data.get("buyback"),
        "buyback_yield": None,
        "total_shareholder_yield": data.get("total_shareholder_yield"),
        "signal": "Neutral",
    }

    bb = data.get("buyback")
    mc = data.get("market_cap")
    if bb and mc and mc > 0:
        bb_yield = abs(bb) / mc
        result["buyback_yield"] = round(bb_yield * 100, 2)
        if bb_yield > 0.03:
            result["signal"] = "Bullish"

    tsy = data.get("total_shareholder_yield")
    if tsy:
        result["total_shareholder_yield"] = round(tsy * 100, 2)

    return result
