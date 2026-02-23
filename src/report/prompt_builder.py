"""
Prompt Builder — convert analysis results dict into a structured
LLM prompt for investment report generation.
"""

from typing import Dict, Any, Tuple

# ── System Prompts ───────────────────────────────────────────

_SYSTEM_KO = """당신은 CFA 자격을 가진 시니어 주식 애널리스트입니다.
제공된 정량 데이터와 모델 결과만을 기반으로 객관적인 투자 분석 리포트를 작성하세요.

규칙:
1. 마크다운 형식으로 작성 (##, ###, 볼드, 리스트 활용)
2. 7개 섹션을 반드시 포함: 투자 요약, 밸류에이션, 품질/리스크, 기술적 분석, 스마트머니, 매크로, 액션플랜
3. 숫자를 인용할 때 반드시 제공된 데이터에서 가져오세요
4. "저평가/고평가/적정가"에 대한 명확한 판단을 내리세요
5. 결론에 매수/매도/보유 의견을 명시하세요
6. 투자 리스크 경고를 반드시 포함하세요
7. 2000자 이내로 간결하게 작성하세요"""

_SYSTEM_EN = """You are a senior equity analyst with a CFA designation.
Write an objective investment analysis report based solely on the quantitative data and model results provided.

Rules:
1. Write in Markdown format (##, ###, bold, bullet lists)
2. Include all 7 sections: Executive Summary, Valuation, Quality & Risk, Technical Analysis, Smart Money, Macro Environment, Action Plan
3. Only cite numbers from the provided data
4. Make a clear judgment on whether the stock is undervalued/overvalued/fairly valued
5. State a clear Buy/Sell/Hold recommendation in the conclusion
6. Include investment risk warnings
7. Keep it concise — under 2000 words"""


def _safe(d: Any, *keys, default="N/A"):
    """Safely traverse nested dicts/objects."""
    v = d
    for k in keys:
        if isinstance(v, dict):
            v = v.get(k)
        else:
            v = None
        if v is None:
            return default
    return v


def _fmt_pct(v, default="N/A") -> str:
    if v is None or v == "N/A":
        return default
    try:
        return f"{float(v):.1f}%"
    except (ValueError, TypeError):
        return str(v)


def _fmt_num(v, dp=2, default="N/A") -> str:
    if v is None or v == "N/A":
        return default
    try:
        return f"{float(v):,.{dp}f}"
    except (ValueError, TypeError):
        return str(v)


def _fmt_money(v, default="N/A") -> str:
    if v is None or v == "N/A":
        return default
    try:
        v = float(v)
        if v >= 1e12:
            return f"${v/1e12:.1f}T"
        if v >= 1e9:
            return f"${v/1e9:.1f}B"
        if v >= 1e6:
            return f"${v/1e6:.0f}M"
        return f"${v:,.0f}"
    except (ValueError, TypeError):
        return str(v)


# ═══════════════════════════════════════════════════════════
# DATA EXTRACTION
# ═══════════════════════════════════════════════════════════

def _build_stock_info(data: dict) -> str:
    return f"""## 종목 정보
- 종목: {data.get('name','?')} ({data.get('ticker','?')})
- 섹터/산업: {data.get('sector','?')} / {data.get('industry','?')}
- 국가: {data.get('country','?')}
- 현재가: ${_fmt_num(data.get('current_price'), 2)}
- 시가총액: {_fmt_money(data.get('market_cap'))}
- Beta: {_fmt_num(data.get('beta'), 2)}"""


def _build_valuation(val: dict) -> str:
    fv = _fmt_num(_safe(val, 'fair_value'), 2)
    upside = _fmt_pct(_safe(val, 'upside_pct'))
    signal = _safe(val, 'signal')
    fv_range = _safe(val, 'fair_value_range')

    models_lines = []
    for m in _safe(val, 'models_summary', default=[]):
        name = m.get('model', '?')
        mv = _fmt_num(m.get('fair_value'), 2)
        mu = _fmt_pct(m.get('upside_pct'))
        conf = m.get('confidence', '?')
        models_lines.append(f"  - {name}: ${mv} (Upside {mu}, Confidence: {conf})")

    # Reverse DCF
    rev = _safe(val, 'models', 'reverse_dcf', default={})
    igr = _safe(rev, 'implied_growth_rate')
    rev_assess = _safe(rev, 'assessment')

    range_str = ""
    if isinstance(fv_range, (list, tuple)) and len(fv_range) == 2:
        range_str = f"${_fmt_num(fv_range[0],2)} ~ ${_fmt_num(fv_range[1],2)}"

    return f"""## 밸류에이션
- 종합 적정가: ${fv}
- 상승여력(Upside): {upside}
- 밸류에이션 레인지: {range_str}
- 종합 시그널: {signal}
- 모델별 결과:
{chr(10).join(models_lines) if models_lines else '  - 데이터 없음'}
- Reverse DCF 내재성장률: {_fmt_pct(igr)}
- Reverse DCF 평가: {rev_assess}"""


def _build_quality(results: dict) -> str:
    pio = results.get('piotroski') or {}
    alt = results.get('altman') or {}
    ben = results.get('beneish') or {}
    eq = results.get('earnings_quality') or {}
    eva = results.get('eva') or {}
    qg = results.get('quality_grade') or {}

    return f"""## 품질 분석
- Piotroski F-Score: {_safe(pio,'score')}/9 ({_safe(pio,'grade')})
- Altman Z-Score: {_fmt_num(_safe(alt,'z_score'),2)} (Zone: {_safe(alt,'zone')})
- Beneish M-Score: {_fmt_num(_safe(ben,'m_score'),2)} (분식 위험: {_safe(ben,'manipulation_risk')})
- 이익 품질: {_safe(eq,'earnings_quality')}
- EVA: ROIC {_fmt_pct(_safe(eva,'roic'))}, WACC {_fmt_pct(_safe(eva,'wacc'))}, Spread {_fmt_pct(_safe(eva,'spread'))} → {_safe(eva,'verdict')}
- Quality Grade: {_safe(qg,'grade')} ({_safe(qg,'score')}/{_safe(qg,'max_score')})"""


def _build_financial_ratios(data: dict) -> str:
    return f"""## 재무 지표
- P/E (Trailing): {_fmt_num(data.get('trailing_pe'),1)}
- P/E (Forward): {_fmt_num(data.get('forward_pe'),1)}
- EV/EBITDA: {_fmt_num(data.get('ev_to_ebitda'),1)}
- P/B: {_fmt_num(data.get('price_to_book'),2)}
- 배당수익률: {_fmt_pct(data.get('dividend_yield') and data['dividend_yield']*100)}
- Gross Margin: {_fmt_pct(data.get('gross_margin') and data['gross_margin']*100)}
- Operating Margin: {_fmt_pct(data.get('operating_margin') and data['operating_margin']*100)}
- Net Margin: {_fmt_pct(data.get('profit_margin') and data['profit_margin']*100)}
- ROE: {_fmt_pct(data.get('roe') and data['roe']*100)}
- ROA: {_fmt_pct(data.get('roa') and data['roa']*100)}
- ROIC: {_fmt_pct(data.get('roic') and data['roic']*100)}
- D/E: {_fmt_num(data.get('debt_to_equity'),2)}
- Current Ratio: {_fmt_num(data.get('current_ratio'),2)}
- Revenue Growth: {_fmt_pct(data.get('revenue_growth') and data['revenue_growth']*100)}"""


def _build_smart_money(sm: dict, guru: dict) -> str:
    ins = sm.get('insider') or {}
    inst = sm.get('institutional') or {}
    short = sm.get('short_interest') or {}
    bb = sm.get('buyback') or {}

    guru_count = _safe(guru, 'guru_count', default=0)
    guru_val = _fmt_money(_safe(guru, 'total_guru_value', default=0))
    guru_names = []
    for g in _safe(guru, 'guru_holders', default=[]):
        guru_names.append(g.get('investor', '?'))

    return f"""## 스마트머니
- Insider 시그널: {_safe(ins,'signal')} (최근 매수 {_safe(ins,'recent_buys',default=0)}건, 매도 {_safe(ins,'recent_sells',default=0)}건)
- 기관 보유: {_fmt_pct(_safe(inst,'pct_institutions') and float(_safe(inst,'pct_institutions'))*100 if _safe(inst,'pct_institutions') not in (None,'N/A') else None)}
- 공매도: {_safe(short,'signal')} (Short % Float: {_fmt_pct(_safe(short,'short_pct_float'))}, ratio: {_fmt_num(_safe(short,'short_ratio'),1)})
- 자사주매입: {_safe(bb,'signal')} (Buyback Yield: {_fmt_pct(_safe(bb,'buyback_yield'))})
- 구루 투자자: {guru_count}명 보유 (합산 {guru_val})
  {', '.join(guru_names[:5]) if guru_names else '없음'}
- 종합 스마트머니 시그널: {_safe(sm,'overall_signal')}"""


def _build_quant(quant: dict) -> str:
    mom = quant.get('momentum') or {}
    tech = quant.get('technicals') or {}
    em = quant.get('earnings_momentum') or {}

    return f"""## 기술적 분석 / 퀀트
- 모멘텀 12M: {_fmt_pct(_safe(mom,'momentum_12m'))}, 6M: {_fmt_pct(_safe(mom,'momentum_6m'))}, 1M: {_fmt_pct(_safe(mom,'momentum_1m'))}
- 모멘텀 시그널: {_safe(mom,'signal')}
- RSI(14): {_fmt_num(_safe(tech,'rsi_14'),1)}
- Bollinger 위치: {_fmt_pct(_safe(tech,'bollinger_position'))}
- 52주 고가 근접도: {_fmt_pct(_safe(tech,'fifty_two_week_proximity'))}
- Golden Cross: {_safe(tech,'golden_cross')}, Death Cross: {_safe(tech,'death_cross')}
- 기술 시그널: {_safe(tech,'signal')}
- Earnings Momentum (SUE): {_fmt_num(_safe(em,'sue_score'),2)}, 시그널: {_safe(em,'signal')}
- 종합 퀀트 시그널: {_safe(quant,'overall_signal')}"""


def _build_risk(risk: dict) -> str:
    ret = risk.get('return_metrics') or {}
    var = risk.get('var') or {}
    lev = risk.get('leverage') or {}

    return f"""## 리스크
- Sharpe Ratio: {_fmt_num(_safe(ret,'sharpe_ratio'),2)}
- Sortino Ratio: {_fmt_num(_safe(ret,'sortino_ratio'),2)}
- Max Drawdown: {_fmt_pct(_safe(ret,'max_drawdown'))}
- Annual Volatility: {_fmt_pct(_safe(ret,'annual_volatility'))}
- VaR 95%: {_fmt_pct(_safe(var,'var_95'))}
- VaR 99%: {_fmt_pct(_safe(var,'var_99'))}
- CVaR 95%: {_fmt_pct(_safe(var,'cvar_95'))}
- D/E: {_fmt_num(_safe(lev,'debt_to_equity'),2)}, Net Debt/EBITDA: {_fmt_num(_safe(lev,'net_debt_to_ebitda'),2)}
- 종합 리스크: {_safe(risk,'overall_risk')}"""


def _build_macro(macro: dict) -> str:
    if not macro:
        return "## 매크로 환경\n- 매크로 데이터 없음 (비활성 상태)"

    yc = macro.get('yield_curve') or {}
    cr = macro.get('credit') or {}
    vix = macro.get('vix') or {}
    sr = macro.get('sector_rotation') or {}
    erp = macro.get('erp') or {}

    return f"""## 매크로 환경
- 10Y 국채: {_fmt_pct(_safe(yc,'treasury_10y'))}, 2Y: {_fmt_pct(_safe(yc,'treasury_2y'))}, Spread: {_fmt_pct(_safe(yc,'spread'))}
- 수익률곡선 역전: {_safe(yc,'inverted')}
- HY 스프레드: {_fmt_pct(_safe(cr,'hy_spread'))}, 신용 레짐: {_safe(cr,'regime')}
- VIX: {_fmt_num(_safe(vix,'level'),1)}, 레짐: {_safe(vix,'regime')}
- 경기 사이클 단계: {_safe(sr,'cycle_phase')} → 유리 섹터: {_safe(sr,'favorable')}
- ERP: {_fmt_pct(_safe(erp,'erp'))}, 평가: {_safe(erp,'assessment')}
- 요약: {_safe(macro,'summary')}
- 시사점: {_safe(macro,'implication')}"""


def _build_grades(grades: dict) -> str:
    cats = grades.get('categories') or {}
    lines = []
    for cat_name, cat_data in cats.items():
        if isinstance(cat_data, dict):
            lines.append(f"  - {cat_name}: {cat_data.get('grade','?')} ({cat_data.get('score',0):.0f}점)")

    return f"""## 종합 등급
- Overall Grade: {_safe(grades,'overall_grade')} ({_safe(grades,'overall_score')}점/100)
- 종합 시그널: {_safe(grades,'signal')}
- 카테고리별:
{chr(10).join(lines) if lines else '  - 데이터 없음'}"""


# ═══════════════════════════════════════════════════════════
# MAIN BUILDER
# ═══════════════════════════════════════════════════════════

def build_analysis_prompt(results: dict, language: str = "ko") -> Tuple[str, str]:
    """
    Build (system_prompt, user_prompt) from analysis results.

    Parameters
    ----------
    results : dict from run_analysis()
    language : "ko" for Korean, "en" for English

    Returns
    -------
    (system_prompt, user_prompt)
    """
    data = results.get("data") or {}
    val = results.get("valuation") or {}
    sm = results.get("smart_money") or {}
    guru = results.get("guru") or {}
    quant = results.get("quant") or {}
    risk = results.get("risk") or {}
    macro = results.get("macro")
    grades = results.get("grades") or {}

    system = _SYSTEM_KO if language == "ko" else _SYSTEM_EN

    sections = [
        _build_stock_info(data),
        _build_valuation(val),
        _build_financial_ratios(data),
        _build_quality(results),
        _build_quant(quant),
        _build_smart_money(sm, guru),
        _build_risk(risk),
        _build_macro(macro),
        _build_grades(grades),
    ]

    user_data = "\n\n".join(sections)

    if language == "ko":
        user_prompt = f"""아래 분석 데이터를 바탕으로 종합 투자 리포트를 작성해주세요.

{user_data}

위 데이터를 기반으로 7개 섹션(투자 요약, 밸류에이션 해설, 품질/리스크 분석, 기술적 분석, 스마트머니 해석, 매크로 시사점, 액션플랜)으로 구성된 투자 리포트를 작성하세요."""
    else:
        user_prompt = f"""Based on the analysis data below, write a comprehensive investment report.

{user_data}

Write the report in 7 sections: Executive Summary, Valuation Analysis, Quality & Risk, Technical Analysis, Smart Money Interpretation, Macro Implications, and Action Plan."""

    return system, user_prompt
