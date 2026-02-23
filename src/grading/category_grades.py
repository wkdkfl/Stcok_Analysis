"""
Category Grading System — A+ through D- (12 levels)
Computes grades for 7 categories and an overall weighted verdict.

Categories & weights:
  Valuation    40%    —  upside %, model convergence, coverage
  Quality      15%    —  Piotroski, Altman Z, Beneish M, EQ, EVA
  Financial    10%    —  Revenue growth, margins, ROE, FCF, leverage
  Smart Money  10%    —  Insider, short interest, buyback
  Risk & Quant 10%    —  Sharpe, MDD, VaR, momentum, RSI, technicals
  Macro        10%    —  VIX, yield curve, credit, sector rotation
  Sector        5%    —  Sector-specific KPIs normalised
"""

from typing import Dict, Any, Optional, Tuple
import numpy as np

# ── Grade scale (12 levels) ──────────────────────────────
_GRADE_TABLE: list[Tuple[float, str]] = [
    (93, "A+"), (85, "A"), (78, "A-"),
    (71, "B+"), (64, "B"), (57, "B-"),
    (50, "C+"), (43, "C"), (36, "C-"),
    (29, "D+"), (22, "D"),
]

_GRADE_COLORS: Dict[str, str] = {
    "A+": "#00C853", "A": "#00E676", "A-": "#69F0AE",
    "B+": "#2979FF", "B": "#448AFF", "B-": "#82B1FF",
    "C+": "#FF9100", "C": "#FFB300", "C-": "#FFD54F",
    "D+": "#FF5252", "D": "#FF1744", "D-": "#D50000",
}

CATEGORY_WEIGHTS = {
    "valuation":   0.40,
    "quality":     0.15,
    "financial":   0.10,
    "smart_money": 0.10,
    "risk_quant":  0.10,
    "macro":       0.10,
    "sector":      0.05,
}

CATEGORY_LABELS = {
    "valuation":   "밸류에이션",
    "quality":     "품질",
    "financial":   "재무",
    "smart_money": "스마트머니",
    "risk_quant":  "리스크&퀀트",
    "macro":       "매크로",
    "sector":      "섹터",
}


# ═══════════════════════════════════════════════════════════
# Utility
# ═══════════════════════════════════════════════════════════

def score_to_grade(score: float) -> str:
    """Convert 0-100 score to A+…D- grade."""
    score = max(0, min(100, score))
    for threshold, grade in _GRADE_TABLE:
        if score >= threshold:
            return grade
    return "D-"


def grade_color(grade: str) -> str:
    return _GRADE_COLORS.get(grade, "#9E9E9E")


def _clamp(val, lo=0, hi=100):
    return max(lo, min(hi, val))


def _safe(val, default=None):
    """Return val if numeric, else default."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


# ═══════════════════════════════════════════════════════════
# ① Valuation Grade
# ═══════════════════════════════════════════════════════════

def grade_valuation(valuation: Dict[str, Any]) -> float:
    upside = _safe(valuation.get("upside_pct"))
    if upside is None:
        return 50.0

    # Base score from upside %
    if upside >= 50:
        base = 100
    elif upside >= 40:
        base = 93
    elif upside >= 25:
        base = 85
    elif upside >= 15:
        base = 75
    elif upside >= 5:
        base = 65
    elif upside >= 0:
        base = 55
    elif upside >= -10:
        base = 42
    elif upside >= -20:
        base = 30
    elif upside >= -30:
        base = 20
    else:
        base = 10

    # Model convergence bonus: lower dispersion → +up to 8 pts
    models = valuation.get("models", {})
    fair_values = [
        m.get("fair_value") for k, m in models.items()
        if k != "reverse_dcf" and m.get("fair_value") is not None
    ]
    if len(fair_values) >= 2:
        avg_fv = np.mean(fair_values)
        if avg_fv > 0:
            dispersion = (max(fair_values) - min(fair_values)) / avg_fv
            if dispersion < 0.3:
                base += 8
            elif dispersion < 0.5:
                base += 4
            elif dispersion > 1.5:
                base -= 5

    # Model coverage: more models with data → +up to 5 pts
    total_models = 6  # DCF, RI, EPV, DDM, Multiples, Graham
    coverage = len(fair_values) / total_models
    base += (coverage - 0.5) * 10  # ±5

    return _clamp(base)


# ═══════════════════════════════════════════════════════════
# ② Quality Grade
# ═══════════════════════════════════════════════════════════

def grade_quality(piotroski: Dict, altman: Dict, beneish: Dict,
                  earnings_quality: Dict, eva: Dict) -> float:
    score = 0.0

    # Piotroski (25 pts)
    ps = _safe(piotroski.get("score"))
    if ps is not None:
        score += (ps / 9) * 25
    else:
        score += 12

    # Altman Z (25 pts)
    zone = altman.get("zone", "N/A")
    if zone == "Safe Zone":
        score += 25
    elif zone == "Grey Zone":
        score += 15
    elif zone == "Distress Zone":
        score += 5
    else:
        score += 12

    # Beneish M (20 pts)
    risk = beneish.get("manipulation_risk", "N/A")
    if "Low" in str(risk):
        score += 20
    elif "Moderate" in str(risk):
        score += 12
    elif "High" in str(risk):
        score += 4
    else:
        score += 10

    # Earnings Quality (15 pts)
    eq = earnings_quality.get("earnings_quality", "N/A")
    eq_map = {"Excellent": 15, "Good": 11, "Fair": 7, "Poor": 3}
    score += eq_map.get(eq, 7)

    # EVA / ROIC Spread (15 pts)
    spread = _safe(eva.get("spread"))
    if spread is not None:
        if spread >= 5:
            score += 15
        elif spread >= 2:
            score += 12
        elif spread >= 0:
            score += 9
        elif spread >= -3:
            score += 5
        else:
            score += 2
    else:
        score += 7

    return _clamp(score)


# ═══════════════════════════════════════════════════════════
# ③ Financial Grade
# ═══════════════════════════════════════════════════════════

def grade_financial(data: Dict[str, Any]) -> float:
    score = 0.0

    # Revenue growth (20 pts)
    rg = _safe(data.get("revenue_growth"))
    if rg is not None:
        rg_pct = rg * 100 if abs(rg) < 5 else rg  # normalise
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
    rev = _safe(data.get("revenue")) or _safe(data.get("total_revenue"))
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
# ④ Smart Money Grade
# ═══════════════════════════════════════════════════════════

def grade_smart_money(sm: Dict[str, Any]) -> float:
    score = 0.0

    # Insider signal (30 pts)
    ins_sig = sm.get("insider", {}).get("signal", "Neutral")
    if ins_sig == "Bullish":
        score += 30
    elif ins_sig == "Bearish":
        score += 5
    else:
        score += 17

    # Short interest (30 pts)
    si = sm.get("short_interest", {})
    rl = str(si.get("risk_level", "Normal"))
    if "Very High" in rl or "Extreme" in rl:
        score += 0
    elif "Elevated" in rl or "High" in rl:
        score += 10
    elif "Low" in rl:
        score += 30
    else:
        score += 18

    # Buyback (25 pts)
    bb_sig = sm.get("buyback", {}).get("signal", "Neutral")
    if bb_sig == "Bullish":
        score += 25
    elif bb_sig == "Bearish":
        score += 5
    else:
        score += 14

    # Guru Investors (15 pts)
    guru = sm.get("guru", {})
    guru_count = guru.get("guru_count", 0)
    if guru_count >= 5:
        score += 15
    elif guru_count >= 3:
        score += 12
    elif guru_count >= 2:
        score += 9
    elif guru_count >= 1:
        score += 6
    else:
        score += 0

    return _clamp(score)


# ═══════════════════════════════════════════════════════════
# ⑤ Risk & Quant Grade
# ═══════════════════════════════════════════════════════════

def grade_risk_quant(risk: Dict[str, Any], quant: Dict[str, Any]) -> float:
    score = 0.0

    # Sharpe Ratio (20 pts)
    sharpe = _safe(risk.get("return_metrics", {}).get("sharpe_ratio"))
    if sharpe is not None:
        if sharpe >= 1.5:
            score += 20
        elif sharpe >= 1.0:
            score += 16
        elif sharpe >= 0.5:
            score += 12
        elif sharpe >= 0:
            score += 8
        else:
            score += 4
    else:
        score += 10

    # Max Drawdown (15 pts) — smaller abs is better
    mdd = _safe(risk.get("return_metrics", {}).get("max_drawdown"))
    if mdd is not None:
        mdd_abs = abs(mdd)
        if mdd_abs <= 10:
            score += 15
        elif mdd_abs <= 20:
            score += 12
        elif mdd_abs <= 30:
            score += 9
        elif mdd_abs <= 50:
            score += 5
        else:
            score += 2
    else:
        score += 8

    # VaR 95 (10 pts) — smaller abs is better
    var95 = _safe(risk.get("var", {}).get("var_95"))
    if var95 is not None:
        v = abs(var95)
        if v <= 1.5:
            score += 10
        elif v <= 2.5:
            score += 8
        elif v <= 4.0:
            score += 5
        else:
            score += 2
    else:
        score += 5

    # Quant — Momentum signal (20 pts)
    mom_sig = quant.get("momentum", {}).get("signal", "Neutral")
    if mom_sig == "Bullish":
        score += 20
    elif mom_sig == "Bearish":
        score += 4
    else:
        score += 12

    # RSI appropriateness (15 pts) — 40-60 best, 30-70 good
    rsi = _safe(quant.get("technicals", {}).get("rsi_14"))
    if rsi is not None:
        if 40 <= rsi <= 60:
            score += 15
        elif 30 <= rsi <= 70:
            score += 12
        elif 25 <= rsi <= 75:
            score += 8
        else:
            score += 4
    else:
        score += 8

    # Technical signal (20 pts)
    tech_sig = quant.get("technicals", {}).get("signal",
               quant.get("overall_signal", "Neutral"))
    if tech_sig == "Bullish":
        score += 20
    elif tech_sig == "Bearish":
        score += 4
    else:
        score += 12

    return _clamp(score)


# ═══════════════════════════════════════════════════════════
# ⑥ Macro Grade
# ═══════════════════════════════════════════════════════════

def grade_macro(macro: Optional[Dict[str, Any]], data: Dict[str, Any]) -> float:
    if macro is None:
        return 50.0  # neutral when disabled

    score = 0.0

    # VIX regime (25 pts)
    vix_regime = macro.get("vix", {}).get("regime", "N/A")
    vix_map = {
        "Low Volatility (Complacent)": 25, "Normal": 20,
        "Elevated (Cautious)": 10, "High Volatility (Fear)": 5,
    }
    score += vix_map.get(vix_regime, 15)

    # Yield Curve (25 pts)
    yc = macro.get("yield_curve", {})
    inverted = yc.get("inverted")
    spread = _safe(yc.get("spread"))
    if inverted is True:
        score += 5
    elif spread is not None:
        if spread > 1.0:
            score += 25
        elif spread > 0.5:
            score += 20
        elif spread > 0:
            score += 15
        else:
            score += 8
    else:
        score += 12

    # Credit regime (25 pts)
    cr = macro.get("credit", {}).get("regime", "N/A")
    cr_map = {
        "Tight (Risk-On)": 25, "Normal": 18,
        "Widening (Caution)": 10, "Stressed (Risk-Off)": 5,
    }
    score += cr_map.get(cr, 12)

    # Sector favorable (25 pts)
    fav = macro.get("sector_rotation", {}).get("favorable")
    if fav is True:
        score += 25
    elif fav is False:
        score += 5
    else:
        score += 15

    return _clamp(score)


# ═══════════════════════════════════════════════════════════
# ⑦ Sector Grade
# ═══════════════════════════════════════════════════════════

def grade_sector(sector_metrics: Dict[str, Any], data: Dict[str, Any]) -> float:
    sm = sector_metrics.get("metrics", {})
    st = sector_metrics.get("sector_type", "General")

    if not sm:
        # Fallback: use financial indicators directly
        return _clamp(grade_financial(data) * 0.85)

    score = 50.0  # start neutral

    if st == "Tech / SaaS":
        r40 = _safe(sm.get("rule_of_40"))
        if r40 is not None:
            if r40 >= 60:
                score = 95
            elif r40 >= 40:
                score = 80
            elif r40 >= 25:
                score = 60
            else:
                score = 35
        fcf_m = _safe(sm.get("fcf_margin_%"))
        if fcf_m is not None:
            score += 5 if fcf_m > 20 else (-5 if fcf_m < 0 else 0)

    elif st == "Financial Services":
        rotce = _safe(sm.get("rotce_%"))
        if rotce is not None:
            if rotce >= 15:
                score = 90
            elif rotce >= 10:
                score = 70
            elif rotce >= 5:
                score = 50
            else:
                score = 30
        eff = _safe(sm.get("efficiency_ratio_%"))
        if eff is not None:
            score += 10 if eff < 55 else (-5 if eff > 70 else 0)

    elif st == "REIT":
        p_ffo = _safe(sm.get("p_ffo"))
        if p_ffo is not None:
            if p_ffo < 12:
                score = 85
            elif p_ffo < 18:
                score = 70
            elif p_ffo < 25:
                score = 50
            else:
                score = 35

    elif st == "Healthcare / Biotech":
        runway = _safe(sm.get("cash_runway_years"))
        if runway is not None:
            if runway >= 5:
                score = 90
            elif runway >= 3:
                score = 70
            elif runway >= 1:
                score = 45
            else:
                score = 20

    elif st == "Retail / Consumer":
        inv = _safe(sm.get("inventory_turnover"))
        if inv is not None:
            if inv >= 10:
                score = 90
            elif inv >= 6:
                score = 70
            elif inv >= 3:
                score = 50
            else:
                score = 35

    elif st == "Energy":
        fcf_y = _safe(sm.get("fcf_yield_%"))
        if fcf_y is not None:
            if fcf_y >= 10:
                score = 90
            elif fcf_y >= 5:
                score = 70
            elif fcf_y >= 0:
                score = 50
            else:
                score = 30

    return _clamp(score)


# ═══════════════════════════════════════════════════════════
# Master: compute all grades + overall verdict
# ═══════════════════════════════════════════════════════════

def compute_all_grades(results: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compute 7 category grades and aggregated overall verdict.

    Parameters
    ----------
    results : dict returned by run_analysis() in app.py

    Returns
    -------
    {
        "categories": {
            "valuation":   {"score": float, "grade": str, "color": str},
            "quality":     ...,
            "financial":   ...,
            "smart_money": ...,
            "risk_quant":  ...,
            "macro":       ...,
            "sector":      ...,
        },
        "overall_score": float,
        "overall_grade": str,
        "overall_color": str,
        "signal":        str,       # Strong Buy / Buy / Hold / Sell / Strong Sell
        "signal_color":  str,
    }
    """
    data = results.get("data", {})

    raw_scores = {
        "valuation":   grade_valuation(results.get("valuation", {})),
        "quality":     grade_quality(
                           results.get("piotroski", {}),
                           results.get("altman", {}),
                           results.get("beneish", {}),
                           results.get("earnings_quality", {}),
                           results.get("eva", {})),
        "financial":   grade_financial(data),
        "smart_money": grade_smart_money(results.get("smart_money", {})),
        "risk_quant":  grade_risk_quant(
                           results.get("risk", {}),
                           results.get("quant", {})),
        "macro":       grade_macro(results.get("macro"), data),
        "sector":      grade_sector(results.get("sector_metrics", {}), data),
    }

    # Build category dict
    categories = {}
    for key, sc in raw_scores.items():
        g = score_to_grade(sc)
        categories[key] = {"score": round(sc, 1), "grade": g, "color": grade_color(g)}

    # Weighted average — if macro is disabled, redistribute its weight
    weights = dict(CATEGORY_WEIGHTS)
    if results.get("macro") is None:
        macro_w = weights.pop("macro", 0)
        total_rest = sum(weights.values())
        if total_rest > 0:
            for k in weights:
                weights[k] += macro_w * (weights[k] / total_rest)

    weighted_sum = sum(raw_scores[k] * weights.get(k, 0) for k in raw_scores)
    total_w = sum(weights.get(k, 0) for k in raw_scores)
    overall_score = weighted_sum / total_w if total_w > 0 else 50.0

    overall_grade = score_to_grade(overall_score)
    overall_color = grade_color(overall_grade)

    # Signal from overall score
    if overall_score >= 75:
        signal, sig_color = "Strong Buy", "#00C853"
    elif overall_score >= 62:
        signal, sig_color = "Buy", "#4CAF50"
    elif overall_score >= 45:
        signal, sig_color = "Hold", "#FF9800"
    elif overall_score >= 30:
        signal, sig_color = "Sell", "#F44336"
    else:
        signal, sig_color = "Strong Sell", "#B71C1C"

    return {
        "categories": categories,
        "overall_score": round(overall_score, 1),
        "overall_grade": overall_grade,
        "overall_color": overall_color,
        "signal": signal,
        "signal_color": sig_color,
    }
