"""
Piotroski F-Score (0-9).
9 binary signals across profitability, leverage/liquidity, and efficiency.
Score ≥ 7 = Strong, 4-6 = Neutral, ≤ 3 = Weak.
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from src.fetcher.yahoo import _get_stmt_value


def compute_piotroski(data: Dict[str, Any]) -> Dict[str, Any]:
    """Compute Piotroski F-Score from financial statements."""
    result = {
        "score": 0,
        "max_score": 9,
        "grade": "N/A",
        "signals": [],
        "details": {},
    }

    inc = data.get("income_stmt")
    bs = data.get("balance_sheet")
    cf = data.get("cashflow")

    if inc is None or bs is None or cf is None:
        return result

    signals = []
    score = 0

    # Helper: get value for current (col 0) and prior year (col 1)
    def curr(stmt, names): return _get_stmt_value(stmt, names, 0)
    def prev(stmt, names): return _get_stmt_value(stmt, names, 1)

    # ── PROFITABILITY ────────────────────────────────────
    # 1. ROA > 0 (Net Income / Total Assets)
    ni = curr(inc, ["Net Income", "Net Income Common Stockholders"])
    ta = curr(bs, ["Total Assets"])
    if ni is not None and ta and ta > 0:
        roa = ni / ta
        passed = roa > 0
        signals.append(("ROA > 0", passed, round(roa * 100, 2)))
        score += int(passed)
    else:
        signals.append(("ROA > 0", False, None))

    # 2. Operating Cash Flow > 0
    cfo = curr(cf, ["Operating Cash Flow", "Total Cash From Operating Activities"])
    passed = cfo is not None and cfo > 0
    signals.append(("CFO > 0", passed, round(cfo) if cfo else None))
    score += int(passed)

    # 3. ΔROA > 0 (ROA improved)
    ni_prev = prev(inc, ["Net Income", "Net Income Common Stockholders"])
    ta_prev = prev(bs, ["Total Assets"])
    if all(v is not None for v in [ni, ta, ni_prev, ta_prev]) and ta > 0 and ta_prev > 0:
        roa_curr = ni / ta
        roa_prev = ni_prev / ta_prev
        delta = roa_curr - roa_prev
        passed = delta > 0
        signals.append(("ΔROA > 0", passed, round(delta * 100, 2)))
        score += int(passed)
    else:
        signals.append(("ΔROA > 0", False, None))

    # 4. Accruals: CFO > Net Income (quality of earnings)
    if cfo is not None and ni is not None:
        passed = cfo > ni
        signals.append(("CFO > NI (Low Accruals)", passed,
                       round((cfo - ni) if cfo and ni else 0)))
        score += int(passed)
    else:
        signals.append(("CFO > NI (Low Accruals)", False, None))

    # ── LEVERAGE & LIQUIDITY ─────────────────────────────
    # 5. ΔLeverage < 0 (long-term debt / assets decreased)
    ltd = curr(bs, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
    ltd_prev = prev(bs, ["Long Term Debt", "Long Term Debt And Capital Lease Obligation"])
    if all(v is not None for v in [ltd, ta, ltd_prev, ta_prev]) and ta > 0 and ta_prev > 0:
        lev = ltd / ta
        lev_prev = ltd_prev / ta_prev
        passed = lev < lev_prev
        signals.append(("ΔLeverage < 0", passed, round((lev - lev_prev) * 100, 2)))
        score += int(passed)
    else:
        signals.append(("ΔLeverage < 0", False, None))

    # 6. ΔCurrent Ratio > 0
    ca = curr(bs, ["Current Assets"])
    cl = curr(bs, ["Current Liabilities"])
    ca_prev = prev(bs, ["Current Assets"])
    cl_prev = prev(bs, ["Current Liabilities"])
    if all(v is not None for v in [ca, cl, ca_prev, cl_prev]) and cl > 0 and cl_prev > 0:
        cr = ca / cl
        cr_prev = ca_prev / cl_prev
        passed = cr > cr_prev
        signals.append(("ΔCurrent Ratio > 0", passed, round(cr - cr_prev, 2)))
        score += int(passed)
    else:
        signals.append(("ΔCurrent Ratio > 0", False, None))

    # 7. No new shares issued
    shares = curr(bs, ["Share Issued", "Ordinary Shares Number", "Common Stock Shares Outstanding"])
    shares_prev = prev(bs, ["Share Issued", "Ordinary Shares Number", "Common Stock Shares Outstanding"])
    if shares and shares_prev:
        passed = shares <= shares_prev
        signals.append(("No Dilution", passed, round(shares - shares_prev)))
        score += int(passed)
    else:
        signals.append(("No Dilution", False, None))

    # ── EFFICIENCY ───────────────────────────────────────
    # 8. ΔGross Margin > 0
    gp = curr(inc, ["Gross Profit"])
    rev = curr(inc, ["Total Revenue", "Revenue"])
    gp_prev = prev(inc, ["Gross Profit"])
    rev_prev = prev(inc, ["Total Revenue", "Revenue"])
    if all(v is not None for v in [gp, rev, gp_prev, rev_prev]) and rev > 0 and rev_prev > 0:
        gm = gp / rev
        gm_prev = gp_prev / rev_prev
        passed = gm > gm_prev
        signals.append(("ΔGross Margin > 0", passed, round((gm - gm_prev) * 100, 2)))
        score += int(passed)
    else:
        signals.append(("ΔGross Margin > 0", False, None))

    # 9. ΔAsset Turnover > 0
    if all(v is not None for v in [rev, ta, rev_prev, ta_prev]) and ta > 0 and ta_prev > 0:
        at = rev / ta
        at_prev = rev_prev / ta_prev
        passed = at > at_prev
        signals.append(("ΔAsset Turnover > 0", passed, round(at - at_prev, 3)))
        score += int(passed)
    else:
        signals.append(("ΔAsset Turnover > 0", False, None))

    result["score"] = score
    result["signals"] = signals

    if score >= 7:
        result["grade"] = "Strong"
    elif score >= 4:
        result["grade"] = "Neutral"
    else:
        result["grade"] = "Weak"

    return result
