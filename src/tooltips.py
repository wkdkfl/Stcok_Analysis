"""
Tooltip / help-text definitions for the Stock Analyzer UI.
Provides bilingual (ko/en) descriptions for:
  - Valuation models
  - Quality scores
  - Financial ratios
  - Risk & Quant metrics
  - Macro indicators
  - Grade methodology

Usage:
  from src.tooltips import tip
  st.metric("DCF", val, help=tip("val.dcf"))
"""

import streamlit as st
from typing import Dict

_TIPS: Dict[str, Dict[str, str]] = {
    # ═══════════════════════════════════════════════════════
    # Valuation Models
    # ═══════════════════════════════════════════════════════
    "val.dcf": {
        "ko": (
            "**DCF (현금흐름할인법)**\n\n"
            "미래 잉여현금흐름(FCF)을 WACC로 할인하여 기업의 내재가치를 산출합니다.\n"
            "• 고성장 기간 → 페이드 기간 → 영구성장(Terminal Value)\n"
            "• 핵심 가정: 성장률, WACC, 영구성장률"
        ),
        "en": (
            "**DCF (Discounted Cash Flow)**\n\n"
            "Discounts projected free cash flows at the WACC to estimate intrinsic value.\n"
            "• High-growth → Fade → Terminal Value\n"
            "• Key inputs: growth rate, WACC, terminal growth"
        ),
    },
    "val.reverse_dcf": {
        "ko": (
            "**Reverse DCF**\n\n"
            "현재 주가에 내포된 성장률(implied growth)을 역산합니다.\n"
            "시장이 기대하는 성장률과 본인의 추정치를 비교하세요."
        ),
        "en": (
            "**Reverse DCF**\n\n"
            "Back-solves for the growth rate implied by the current stock price.\n"
            "Compare the market's expectation with your own estimate."
        ),
    },
    "val.residual_income": {
        "ko": (
            "**Residual Income (잔여이익모형)**\n\n"
            "자기자본비용을 초과하는 이익(초과이익)의 현재가치 + 장부가치.\n"
            "ROE가 자기자본비용을 꾸준히 상회하면 양의 잔여이익 → 프리미엄."
        ),
        "en": (
            "**Residual Income Model**\n\n"
            "Book value + PV of earnings above the cost of equity.\n"
            "Positive residual income when ROE consistently exceeds cost of equity."
        ),
    },
    "val.epv": {
        "ko": (
            "**EPV (수익력가치)**\n\n"
            "현재 수익력이 영구적으로 지속된다고 가정하고 성장을 배제한 가치.\n"
            "EPV > 재생산비용 → 경제적 해자(moat) 존재 시사."
        ),
        "en": (
            "**EPV (Earnings Power Value)**\n\n"
            "Assumes current earnings power continues in perpetuity (no growth).\n"
            "EPV > reproduction cost → suggests economic moat."
        ),
    },
    "val.ddm": {
        "ko": (
            "**DDM (배당할인모형)**\n\n"
            "미래 배당금을 할인율로 현재가치화합니다.\n"
            "안정적인 배당을 지급하는 기업에 적합 (배당 없으면 산출 불가)."
        ),
        "en": (
            "**DDM (Dividend Discount Model)**\n\n"
            "Discounts expected future dividends.\n"
            "Best suited for stable dividend-paying companies."
        ),
    },
    "val.multiples": {
        "ko": (
            "**멀티플 분석 (상대가치)**\n\n"
            "P/E, EV/EBITDA, P/B, P/S 등 동종업계 평균 멀티플로 적정 가치를 추정.\n"
            "빠른 비교에 유용하지만 업종·성장률 차이에 주의."
        ),
        "en": (
            "**Multiples (Relative Valuation)**\n\n"
            "Estimates fair value using sector-average P/E, EV/EBITDA, P/B, P/S.\n"
            "Useful for quick comparison; be mindful of growth & sector differences."
        ),
    },
    "val.graham": {
        "ko": (
            "**Graham Formula**\n\n"
            "벤저민 그레이엄의 가치투자 공식: √(22.5 × EPS × BPS)\n"
            "보수적 가치 추정 — MOS(안전마진)를 내포합니다."
        ),
        "en": (
            "**Graham Formula**\n\n"
            "Benjamin Graham's value formula: √(22.5 × EPS × BPS)\n"
            "Conservative estimate with built-in margin of safety."
        ),
    },

    # ═══════════════════════════════════════════════════════
    # Quality Scores
    # ═══════════════════════════════════════════════════════
    "qual.piotroski": {
        "ko": (
            "**Piotroski F-Score (0-9)**\n\n"
            "수익성(4) + 레버리지/유동성(3) + 영업효율(2) 총 9개 바이너리 테스트.\n"
            "• 8-9: 강한 재무건전성\n"
            "• 0-2: 재무적 위험 신호"
        ),
        "en": (
            "**Piotroski F-Score (0-9)**\n\n"
            "9 binary tests across profitability (4), leverage/liquidity (3), efficiency (2).\n"
            "• 8-9: Strong financial health\n"
            "• 0-2: Financial distress signal"
        ),
    },
    "qual.altman": {
        "ko": (
            "**Altman Z-Score**\n\n"
            "부도 확률 예측 모형. 5개 재무비율의 가중합.\n"
            "• > 2.99: 안전 구간\n"
            "• 1.81-2.99: 회색 구간 (주의)\n"
            "• < 1.81: 위험 구간 (부도 가능성 높음)"
        ),
        "en": (
            "**Altman Z-Score**\n\n"
            "Bankruptcy prediction model using 5 weighted financial ratios.\n"
            "• > 2.99: Safe zone\n"
            "• 1.81-2.99: Grey zone (caution)\n"
            "• < 1.81: Distress zone (high bankruptcy risk)"
        ),
    },
    "qual.beneish": {
        "ko": (
            "**Beneish M-Score**\n\n"
            "이익조정(분식회계) 가능성을 감지하는 모형.\n"
            "• > -1.78: 이익조정 가능성 높음 ⚠️\n"
            "• < -1.78: 이익조정 가능성 낮음 ✅"
        ),
        "en": (
            "**Beneish M-Score**\n\n"
            "Detects potential earnings manipulation.\n"
            "• > -1.78: Likely manipulator ⚠️\n"
            "• < -1.78: Unlikely manipulator ✅"
        ),
    },
    "qual.dupont": {
        "ko": (
            "**DuPont 분석**\n\n"
            "ROE = 순이익률 × 자산회전율 × 재무레버리지\n"
            "ROE의 동인을 분해하여 수익성의 질을 평가합니다."
        ),
        "en": (
            "**DuPont Analysis**\n\n"
            "ROE = Net Margin × Asset Turnover × Equity Multiplier\n"
            "Decomposes ROE to assess quality of returns."
        ),
    },
    "qual.earnings_quality": {
        "ko": (
            "**Earnings Quality (이익의 질)**\n\n"
            "발생액(accruals) 대비 현금흐름 비율로 이익의 지속가능성 평가.\n"
            "현금흐름 기반 이익 > 발생액 기반 이익 → 높은 이익의 질."
        ),
        "en": (
            "**Earnings Quality**\n\n"
            "Measures sustainability of earnings via accruals vs. cash flows.\n"
            "Cash-based earnings > accrual-based → higher quality."
        ),
    },
    "qual.eva": {
        "ko": (
            "**EVA (경제적부가가치)**\n\n"
            "NOPAT - (투하자본 × WACC). 양의 EVA → 자본비용 초과 수익 창출.\n"
            "EVA 스프레드(%) = EVA / 투하자본으로 비교 가능."
        ),
        "en": (
            "**EVA (Economic Value Added)**\n\n"
            "NOPAT - (Invested Capital × WACC). Positive EVA → value creation.\n"
            "EVA Spread (%) = EVA / Invested Capital for comparisons."
        ),
    },

    # ═══════════════════════════════════════════════════════
    # Risk & Quant
    # ═══════════════════════════════════════════════════════
    "risk.sharpe": {
        "ko": "**Sharpe Ratio**: (수익률 - 무위험이자율) / 변동성. 1 이상이면 양호.",
        "en": "**Sharpe Ratio**: (Return - Risk-free rate) / Volatility. Above 1 is good.",
    },
    "risk.sortino": {
        "ko": "**Sortino Ratio**: 하방 변동성만 고려한 위험조정수익률. Sharpe보다 보수적.",
        "en": "**Sortino Ratio**: Risk-adjusted return using downside deviation only.",
    },
    "risk.var": {
        "ko": "**VaR (95%)**: 95% 신뢰수준에서 하루 최대 손실 위험.",
        "en": "**VaR (95%)**: Maximum daily loss at 95% confidence level.",
    },
    "risk.mdd": {
        "ko": "**Max Drawdown**: 고점 대비 최대 낙폭. 최악의 시나리오 리스크.",
        "en": "**Max Drawdown**: Largest peak-to-trough decline. Worst-case risk measure.",
    },
    "risk.beta": {
        "ko": "**Beta**: 시장 대비 민감도. 1 초과 → 시장보다 변동성 큼.",
        "en": "**Beta**: Sensitivity to market. >1 means more volatile than the market.",
    },
    "quant.rsi": {
        "ko": "**RSI (14일)**: 30 이하 과매도, 70 이상 과매수 시그널.",
        "en": "**RSI (14-day)**: Below 30 = oversold, above 70 = overbought.",
    },
    "quant.momentum": {
        "ko": "**모멘텀 (12개월)**: 최근 12개월 수익률. 양의 모멘텀 → 상승 추세.",
        "en": "**Momentum (12M)**: Last 12 months return. Positive → uptrend.",
    },

    # ═══════════════════════════════════════════════════════
    # Macro
    # ═══════════════════════════════════════════════════════
    "macro.yield_curve": {
        "ko": "**수익률곡선**: 10Y-2Y 스프레드. 음수(역전) → 경기침체 선행지표.",
        "en": "**Yield Curve**: 10Y-2Y spread. Negative (inverted) → recession leading indicator.",
    },
    "macro.vix": {
        "ko": "**VIX (공포지수)**: 옵션 시장의 내재변동성. 30 이상 → 높은 불확실성.",
        "en": "**VIX (Fear Index)**: Implied volatility from options. Above 30 → high uncertainty.",
    },
    "macro.credit_spread": {
        "ko": "**신용 스프레드**: 회사채-국채 금리차. 확대 → 신용위험 증가.",
        "en": "**Credit Spread**: Corporate-Treasury yield gap. Widening → rising credit risk.",
    },
    "macro.regime": {
        "ko": (
            "**매크로 레짐**\n\n"
            "수익률곡선, VIX, 신용 스프레드, 실업률 등을 종합하여\n"
            "현재 시장 환경을 분류합니다.\n"
            "• 🟢 확장기 · 🟡 후기확장 · 🟠 수축기 · 🔴 위기"
        ),
        "en": (
            "**Macro Regime**\n\n"
            "Classifies current market environment using yield curve, VIX,\n"
            "credit spread, unemployment rate.\n"
            "• 🟢 Expansion · 🟡 Late cycle · 🟠 Contraction · 🔴 Crisis"
        ),
    },

    # ═══════════════════════════════════════════════════════
    # Grade Methodology
    # ═══════════════════════════════════════════════════════
    "grade.overall": {
        "ko": (
            "**종합 등급 (A+~D-)**\n\n"
            "7개 카테고리(밸류에이션, 품질, 재무건전성, 스마트머니,\n"
            "모멘텀, 리스크, 성장성) 점수의 가중평균.\n"
            "A+: 매우 매력적 · D-: 매우 비매력적"
        ),
        "en": (
            "**Overall Grade (A+ to D-)**\n\n"
            "Weighted average of 7 categories (Valuation, Quality, Financial,\n"
            "Smart Money, Momentum, Risk, Growth).\n"
            "A+: Very attractive · D-: Very unattractive"
        ),
    },

    # ═══════════════════════════════════════════════════════
    # Financial Ratios
    # ═══════════════════════════════════════════════════════
    "fin.pe": {
        "ko": "**P/E (주가수익비율)**: 주가 / EPS. 낮을수록 저평가 가능성 (업종 비교 필요).",
        "en": "**P/E Ratio**: Price / EPS. Lower may indicate undervaluation (compare within sector).",
    },
    "fin.pb": {
        "ko": "**P/B (주가순자산비율)**: 주가 / BPS. 1 미만 → 순자산 대비 할인 거래.",
        "en": "**P/B Ratio**: Price / Book Value. Below 1 → trading below net assets.",
    },
    "fin.roe": {
        "ko": "**ROE (자기자본이익률)**: 순이익 / 자기자본. 15% 이상이면 우수.",
        "en": "**ROE (Return on Equity)**: Net Income / Equity. Above 15% is excellent.",
    },
    "fin.roic": {
        "ko": "**ROIC (투하자본이익률)**: NOPAT / 투하자본. WACC 초과 시 가치 창출.",
        "en": "**ROIC**: NOPAT / Invested Capital. Exceeding WACC = value creation.",
    },
    "fin.de": {
        "ko": "**D/E (부채비율)**: 총부채 / 자기자본. 낮을수록 재무적 안정성 높음.",
        "en": "**D/E Ratio**: Total Debt / Equity. Lower = greater financial stability.",
    },
    "fin.current": {
        "ko": "**유동비율**: 유동자산 / 유동부채. 1.5 이상이면 단기 유동성 양호.",
        "en": "**Current Ratio**: Current Assets / Current Liabilities. Above 1.5 is healthy.",
    },
    "fin.fcf_yield": {
        "ko": "**FCF Yield**: 잉여현금흐름 / 시가총액. 높을수록 현금 창출력 우수.",
        "en": "**FCF Yield**: Free Cash Flow / Market Cap. Higher = stronger cash generation.",
    },
    "fin.div_yield": {
        "ko": "**배당수익률**: 연간 배당금 / 주가. 안정적인 현금 수익.",
        "en": "**Dividend Yield**: Annual Dividend / Price. Stable cash income.",
    },
}


def tip(key: str) -> str:
    """
    Get a tooltip string for the given key in the current language.
    Returns empty string if key not found.
    """
    lang = st.session_state.get("language", "ko")
    entry = _TIPS.get(key)
    if entry is None:
        return ""
    return entry.get(lang, entry.get("ko", ""))
