"""
Screener Grades — lightweight grades computed from yfinance .info data only.
Used for the stock screener feature. Computes 3 category grades
(Financial, Valuation, Macro) and an overall grade.

Financial (50%) + Valuation (30%) + Macro (20%) = Overall
"""

import os
import sys
from typing import Dict, Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from config import SECTOR_MULTIPLES_FALLBACK


# ── Utilities ─────────────────────────────────────────────

def _clamp(score: float, lo: float = 0, hi: float = 100) -> float:
    return max(lo, min(hi, score))


def _safe(val):
    """Safely convert to float, returning None for NaN/invalid."""
    if val is None:
        return None
    try:
        f = float(val)
        return f if f == f else None  # NaN check
    except (TypeError, ValueError):
        return None


# ── Grade scale (same as category_grades.py) ─────────────

GRADE_MAP = [
    (93, "A+"), (86, "A"), (80, "A-"),
    (75, "B+"), (68, "B"), (62, "B-"),
    (55, "C+"), (48, "C"), (42, "C-"),
    (35, "D+"), (28, "D"), (22, "D-"),
]

GRADE_COLORS = {
    "A+": "#1B5E20", "A": "#2E7D32", "A-": "#388E3C",
    "B+": "#558B2F", "B": "#689F38", "B-": "#7CB342",
    "C+": "#F9A825", "C": "#FFA000", "C-": "#FF8F00",
    "D+": "#E65100", "D": "#BF360C", "D-": "#B71C1C",
}


def score_to_grade(score: float) -> str:
    for threshold, grade in GRADE_MAP:
        if score >= threshold:
            return grade
    return "D-"


# ═══════════════════════════════════════════════════════════
# ① Financial Grade
#    (mirrors category_grades.grade_financial — 5 sub-scores)
# ═══════════════════════════════════════════════════════════

def grade_screener_financial(data: Dict[str, Any]) -> float:
    score = 0.0

    # Revenue growth (20 pts)
    rg = _safe(data.get("revenue_growth"))
    if rg is not None:
        rg_pct = rg * 100 if abs(rg) < 5 else rg
        if rg_pct >= 20:
            score += 20
        elif rg_pct >= 10:
            score += 16
        elif rg_pct >= 5:
            score += 12
        elif rg_pct >= 0:
            score += 8
        else:
            score += 4
    else:
        score += 10

    # Operating margin (20 pts)
    om = _safe(data.get("operating_margin"))
    if om is not None:
        om_pct = om * 100 if abs(om) < 5 else om
        if om_pct >= 25:
            score += 20
        elif om_pct >= 15:
            score += 16
        elif om_pct >= 10:
            score += 12
        elif om_pct >= 5:
            score += 8
        else:
            score += 4
    else:
        score += 10

    # ROE (20 pts)
    roe = _safe(data.get("roe"))
    if roe is not None:
        roe_pct = roe * 100 if abs(roe) < 5 else roe
        if roe_pct >= 25:
            score += 20
        elif roe_pct >= 15:
            score += 16
        elif roe_pct >= 10:
            score += 12
        elif roe_pct >= 5:
            score += 8
        else:
            score += 4
    else:
        score += 10

    # FCF Margin (20 pts)
    fcf = _safe(data.get("fcf"))
    rev = _safe(data.get("revenue"))
    if fcf is not None and rev and rev > 0:
        fm = (fcf / rev) * 100
        if fm >= 20:
            score += 20
        elif fm >= 10:
            score += 16
        elif fm >= 5:
            score += 12
        elif fm >= 0:
            score += 8
        else:
            score += 4
    else:
        score += 10

    # Debt/Equity (20 pts) — lower is better
    de = _safe(data.get("debt_to_equity"))
    if de is not None:
        if de <= 0.3:
            score += 20
        elif de <= 0.7:
            score += 16
        elif de <= 1.5:
            score += 12
        elif de <= 3.0:
            score += 8
        else:
            score += 4
    else:
        score += 10

    return _clamp(score)


# ═══════════════════════════════════════════════════════════
# ② Valuation Grade
#    (sector-relative multiples comparison)
# ═══════════════════════════════════════════════════════════

def grade_screener_valuation(data: Dict[str, Any]) -> float:
    sector = data.get("sector", "N/A")
    benchmarks = SECTOR_MULTIPLES_FALLBACK.get(sector, {})
    if not benchmarks:
        # Market-wide fallback averages
        benchmarks = {"ev_ebitda": 14.0, "pe": 20.0, "ps": 3.0}

    score = 0.0
    max_available = 0.0

    # P/E vs sector benchmark (40 pts)
    pe = _safe(data.get("forward_pe")) or _safe(data.get("trailing_pe"))
    pe_bench = benchmarks.get("pe", 20)
    if pe is not None and pe > 0:
        ratio = pe / pe_bench
        if ratio <= 0.5:
            score += 40
        elif ratio <= 0.75:
            score += 32
        elif ratio <= 1.0:
            score += 24
        elif ratio <= 1.25:
            score += 16
        elif ratio <= 1.5:
            score += 10
        else:
            score += 4
        max_available += 40

    # EV/EBITDA vs sector benchmark (35 pts)
    eve = _safe(data.get("ev_to_ebitda"))
    eve_bench = benchmarks.get("ev_ebitda", 14)
    if eve is not None and eve > 0:
        ratio = eve / eve_bench
        if ratio <= 0.5:
            score += 35
        elif ratio <= 0.75:
            score += 28
        elif ratio <= 1.0:
            score += 21
        elif ratio <= 1.25:
            score += 14
        elif ratio <= 1.5:
            score += 8
        else:
            score += 4
        max_available += 35

    # P/B (25 pts)
    pb = _safe(data.get("price_to_book"))
    if pb is not None and pb > 0:
        if pb <= 1.0:
            score += 25
        elif pb <= 2.0:
            score += 20
        elif pb <= 3.0:
            score += 15
        elif pb <= 5.0:
            score += 10
        elif pb <= 10.0:
            score += 5
        else:
            score += 2
        max_available += 25

    if max_available == 0:
        return 50.0  # neutral default

    # Scale to 100
    return _clamp((score / max_available) * 100)


# ═══════════════════════════════════════════════════════════
# OVERALL SCREENER GRADE
# ═══════════════════════════════════════════════════════════

# Key fields used to assess data completeness
_COMPLETENESS_FIELDS_FIN = ["revenue_growth", "operating_margin", "roe", "fcf", "debt_to_equity"]
_COMPLETENESS_FIELDS_VAL = ["trailing_pe", "ev_to_ebitda", "price_to_book"]
_COMPLETENESS_FIELDS_ALL = _COMPLETENESS_FIELDS_FIN + _COMPLETENESS_FIELDS_VAL
_COMPLETENESS_THRESHOLD = 3  # min fields required for a meaningful grade


def _count_data_completeness(stock_info: Dict[str, Any]) -> int:
    """Count how many of the 8 key grading fields have non-null values."""
    count = 0
    for key in _COMPLETENESS_FIELDS_ALL:
        val = _safe(stock_info.get(key))
        if val is not None:
            count += 1
    return count


def compute_screener_grades(stock_info: Dict[str, Any],
                            macro_score: float = 50.0) -> Dict[str, Any]:
    """
    Compute lightweight screener grades.
    Financial (50%) + Valuation (30%) + Macro (20%).

    data_completeness: int (0-8) — number of key fields available.
    If < 3 fields are available, overall_grade is set to "N/A".
    """
    fin_score = grade_screener_financial(stock_info)
    val_score = grade_screener_valuation(stock_info)
    overall_score = _clamp(fin_score * 0.50 + val_score * 0.30 + macro_score * 0.20)
    completeness = _count_data_completeness(stock_info)
    overall_grade = score_to_grade(overall_score)

    return {
        "overall_score": round(overall_score, 1),
        "overall_grade": overall_grade,
        "overall_color": GRADE_COLORS.get(overall_grade, "#9E9E9E"),
        "valuation_score": round(val_score, 1),
        "valuation_grade": score_to_grade(val_score),
        "valuation_color": GRADE_COLORS.get(score_to_grade(val_score), "#9E9E9E"),
        "financial_score": round(fin_score, 1),
        "financial_grade": score_to_grade(fin_score),
        "financial_color": GRADE_COLORS.get(score_to_grade(fin_score), "#9E9E9E"),
        "macro_score": round(macro_score, 1),
        "macro_grade": score_to_grade(macro_score),
        "macro_color": GRADE_COLORS.get(score_to_grade(macro_score), "#9E9E9E"),
        "data_completeness": completeness,
    }
