"""
Stock Intrinsic Value Analyzer — Streamlit Application
Institutional-grade valuation tool with 7 models, quality scoring,
smart money signals, quant factors, macro regime, and risk analysis.
"""

import streamlit as st
import pandas as pd
import numpy as np
import sys
import os

# ── Path setup ───────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    MAX_TICKERS, DCF_DEFAULTS, SCREENER_UNIVERSES, SECTOR_MULTIPLES_FALLBACK,
    MAX_PORTFOLIO_TICKERS, BENCHMARKS, BACKTEST_DEFAULTS, STRATEGY_NAMES,
    WEIGHT_SCHEME_NAMES, REBALANCE_FREQ_MAP,
)

# ── Page Config ──────────────────────────────────────────
st.set_page_config(
    page_title="Stock Intrinsic Value Analyzer",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ───────────────────────────────────────────
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 15px 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .metric-card h3 { font-size: 14px; margin: 0; opacity: 0.9; }
    .metric-card h1 { font-size: 24px; margin: 5px 0 0 0; }
    .signal-box {
        padding: 15px;
        border-radius: 10px;
        text-align: center;
        font-size: 20px;
        font-weight: bold;
    }
    .grade-card {
        padding: 10px 6px;
        border-radius: 8px;
        text-align: center;
        color: white;
        margin: 2px;
    }
    .grade-card .grade-label {
        font-size: 11px;
        opacity: 0.9;
        margin: 0;
    }
    .grade-card .grade-value {
        font-size: 22px;
        font-weight: bold;
        margin: 2px 0 0 0;
    }
    .grade-card .grade-score {
        font-size: 10px;
        opacity: 0.8;
        margin: 0;
    }
    div[data-testid="stMetricValue"] { font-size: 20px; }
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════
with st.sidebar:
    st.title("📊 Stock Analyzer")
    st.markdown("---")

    # ── 종목 분석 설정 ────────────────────────────────────
    with st.expander("📊 종목 분석", expanded=True):
        ticker_input = st.text_input(
            "Ticker(s) — 쉼표로 구분",
            value="AAPL",
            placeholder="AAPL, MSFT, NVDA",
            help="미국 주식 티커를 입력하세요. 복수 입력 시 Compare 탭에서 비교 가능"
        )

        st.markdown("#### DCF 가정 조정")
        col1, col2 = st.columns(2)
        with col1:
            wacc_override = st.slider("WACC (%)", 4.0, 20.0, 10.0, 0.5) / 100
        with col2:
            terminal_g = st.slider("Terminal Growth (%)", 0.0, 5.0, 2.5, 0.5) / 100

        high_growth_yrs = st.slider("High Growth Period (yrs)", 3, 10, 5)
        growth_override = st.slider("Growth Rate Override (%)", -10.0, 40.0, 0.0, 1.0)

        show_macro = st.checkbox("Show Macro Environment", value=True)

        analyze_btn = st.button("🔍 분석 시작", type="primary", use_container_width=True)

    # ── 스크리너 설정 ────────────────────────────────────
    with st.expander("🔎 스크리너 필터", expanded=False):
        scr_universe = st.selectbox(
            "유니버스",
            list(SCREENER_UNIVERSES.keys()),
            index=2,
            key="scr_universe",
        )

        scr_grade = st.multiselect(
            "Overall Grade",
            ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-"],
            default=["A+", "A", "A-", "B+", "B", "B-"],
            key="scr_grade",
        )

        scr_cap = st.multiselect(
            "시가총액",
            ["Mega (>200B)", "Large (10-200B)", "Mid (2-10B)", "Small (<2B)"],
            default=["Mega (>200B)", "Large (10-200B)", "Mid (2-10B)", "Small (<2B)"],
            key="scr_cap",
        )

        scr_sector = st.multiselect(
            "섹터",
            list(SECTOR_MULTIPLES_FALLBACK.keys()),
            default=[],
            key="scr_sector",
            help="비워두면 전체 섹터",
        )

        scr_country = st.text_input(
            "국가 (쉼표 구분, 비워두면 전체)",
            value="",
            key="scr_country",
            placeholder="United States, Ireland",
        )

        st.markdown("#### 추가 필터")
        scr_pe = st.slider("P/E 범위", 0.0, 100.0, (0.0, 100.0), key="scr_pe")
        scr_div = st.slider("최소 배당수익률 (%)", 0.0, 10.0, 0.0, 0.5, key="scr_div")
        scr_roe = st.slider("최소 ROE (%)", 0.0, 50.0, 0.0, 1.0, key="scr_roe")

        scr_sort = st.selectbox(
            "정렬 기준",
            ["Overall Grade ↓", "시가총액 ↓", "P/E ↑", "ROE ↓", "배당수익률 ↓"],
            key="scr_sort",
        )

        scan_btn = st.button("🔍 스크리닝 시작", type="primary",
                             use_container_width=True, key="scan_btn")

    # ── 13F 구루 ────────────────────────────────────────
    with st.expander("🏦 13F 구루", expanded=False):
        st.caption("SEC 13F 공시 기반 유명 투자자 포트폴리오 조회")
        st.markdown(
            "상단의 **🏦 13F 구루** 탭에서\n"
            "버핏, 달리오 등 15명의 구루 투자자\n"
            "포트폴리오와 보유 종목을 확인하세요."
        )

    # ── 포트폴리오 시뮬레이터 ────────────────────────────
    with st.expander("💼 포트폴리오", expanded=False):
        pf_ticker_input = st.text_input(
            "종목 (쉼표 구분, 최대 30)",
            value="AAPL, MSFT, GOOG, AMZN, NVDA",
            placeholder="AAPL, MSFT, GOOG",
            key="pf_ticker_input",
            help="포트폴리오에 포함할 미국 주식 티커",
        )
        pf_weight_scheme = st.selectbox(
            "가중치 방식",
            list(WEIGHT_SCHEME_NAMES.keys()),
            index=0,
            key="pf_weight_scheme",
        )
        pf_col1, pf_col2 = st.columns(2)
        with pf_col1:
            pf_start = st.date_input(
                "시작일", value=pd.Timestamp.now() - pd.DateOffset(years=3),
                key="pf_start",
            )
        with pf_col2:
            pf_end = st.date_input(
                "종료일", value=pd.Timestamp.now(),
                key="pf_end",
            )
        pf_benchmarks = st.multiselect(
            "벤치마크",
            list(BENCHMARKS.keys()),
            default=["S&P 500 (SPY)"],
            key="pf_benchmarks",
        )
        pf_capital = st.number_input(
            "초기 자본 ($)", value=100_000, min_value=1_000,
            step=10_000, key="pf_capital",
        )
        simulate_btn = st.button(
            "💼 시뮬레이션 실행", type="primary",
            use_container_width=True, key="simulate_btn",
        )

    # ── 백테스트 ────────────────────────────────────────
    with st.expander("📈 백테스트", expanded=False):
        bt_strategy = st.selectbox(
            "전략",
            list(STRATEGY_NAMES.keys()),
            index=0,
            key="bt_strategy",
        )
        bt_ticker_input = st.text_input(
            "유니버스 종목 (쉼표 구분)",
            value="AAPL, MSFT, GOOG, AMZN, NVDA, META, TSLA, JPM, V, JNJ",
            key="bt_ticker_input",
            help="백테스트에 사용할 종목 풀 (최대 30개)",
        )
        bt_col1, bt_col2 = st.columns(2)
        with bt_col1:
            bt_start = st.date_input(
                "시작일", value=pd.Timestamp.now() - pd.DateOffset(years=5),
                key="bt_start",
            )
        with bt_col2:
            bt_end = st.date_input(
                "종료일", value=pd.Timestamp.now(),
                key="bt_end",
            )
        bt_rebal = st.selectbox(
            "리밸런싱 주기",
            list(REBALANCE_FREQ_MAP.keys()),
            index=0,
            key="bt_rebal",
        )
        bt_benchmark = st.selectbox(
            "벤치마크",
            list(BENCHMARKS.keys()),
            index=0,
            key="bt_benchmark",
        )
        bt_col3, bt_col4 = st.columns(2)
        with bt_col3:
            bt_top_n = st.slider("Top N (모멘텀/등급)", 3, 20, 10, key="bt_top_n")
        with bt_col4:
            bt_cost = st.slider("거래비용 (%)", 0.0, 1.0, 0.1, 0.05, key="bt_cost")
        bt_capital = st.number_input(
            "초기 자본 ($)", value=100_000, min_value=1_000,
            step=10_000, key="bt_capital",
        )
        backtest_btn = st.button(
            "📈 백테스트 실행", type="primary",
            use_container_width=True, key="backtest_btn",
        )

    st.markdown("---")
    st.caption("Data: Yahoo Finance | FRED | SEC EDGAR")
    st.caption("Models: DCF, Reverse DCF, Residual Income, EPV, DDM, Multiples, Graham")


# ═══════════════════════════════════════════════════════════
# MAIN LOGIC
# ═══════════════════════════════════════════════════════════

def parse_tickers(text: str) -> list:
    """Parse comma-separated ticker input."""
    tickers = [t.strip().upper() for t in text.replace(";", ",").split(",")]
    return [t for t in tickers if t][:MAX_TICKERS]


def run_analysis(ticker: str, dcf_overrides: dict):
    """Run all analyses for a single ticker."""
    from src.fetcher.yahoo import fetch_stock_data
    from src.fetcher.fred import fetch_macro_data
    from src.valuation.aggregator import run_all_valuations
    from src.quality.piotroski import compute_piotroski
    from src.quality.altman import compute_altman_z
    from src.quality.beneish import compute_beneish
    from src.quality.dupont import compute_dupont
    from src.quality.earnings_quality import (
        compute_earnings_quality, compute_eva, compute_quality_grade
    )
    from src.smart_money.signals import compute_smart_money
    from src.quant.signals import compute_quant_signals
    from src.risk.metrics import compute_risk_metrics
    from src.sector.detector import detect_and_compute_sector_metrics
    from src.macro.regime import compute_macro_regime

    # Fetch data
    with st.spinner(f"📡 {ticker} 데이터 수집 중..."):
        stock_data = fetch_stock_data(ticker)

    if not stock_data.get("current_price"):
        st.error(f"❌ {ticker}: 데이터를 가져올 수 없습니다. 티커를 확인해주세요.")
        return None

    results = {"data": stock_data}

    # Valuation
    with st.spinner("📈 밸류에이션 모델 실행 중..."):
        results["valuation"] = run_all_valuations(stock_data, dcf_overrides)

    # Quality
    with st.spinner("🔍 품질 분석 중..."):
        results["piotroski"] = compute_piotroski(stock_data)
        results["altman"] = compute_altman_z(stock_data)
        results["beneish"] = compute_beneish(stock_data)
        results["dupont"] = compute_dupont(stock_data)
        eq = compute_earnings_quality(stock_data)
        results["earnings_quality"] = eq
        eva = compute_eva(stock_data)
        results["eva"] = eva
        results["quality_grade"] = compute_quality_grade(
            results["piotroski"], results["altman"],
            results["beneish"], eq, eva
        )

    # Smart Money / Quant / Risk
    with st.spinner("🧠 스마트머니 & 퀀트 분석 중..."):
        # Guru investor holdings (SEC 13F)
        guru_data = None
        try:
            from src.fetcher.sec_edgar import fetch_guru_holdings_for_ticker
            guru_data = fetch_guru_holdings_for_ticker(ticker)
        except Exception:
            guru_data = {"guru_holders": [], "guru_count": 0, "total_guru_value": 0}
        results["guru"] = guru_data
        results["smart_money"] = compute_smart_money(stock_data, guru_data)
        results["quant"] = compute_quant_signals(stock_data)
        results["risk"] = compute_risk_metrics(stock_data)

    # Sector
    results["sector_metrics"] = detect_and_compute_sector_metrics(stock_data)

    # Macro
    if show_macro:
        with st.spinner("🌍 매크로 환경 분석 중..."):
            macro = fetch_macro_data()
            results["macro"] = compute_macro_regime(macro, stock_data)
    else:
        results["macro"] = None

    # Category Grades & Overall Verdict
    with st.spinner("📊 종합 등급 산출 중..."):
        from src.grading.category_grades import compute_all_grades
        results["grades"] = compute_all_grades(results)

    return results


def display_single_ticker(results: dict):
    """Display full analysis for a single ticker."""
    data = results["data"]
    valuation = results["valuation"]

    # ── Header ───────────────────────────────────────────
    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(f"## {data['name']} ({data['ticker']})")
        st.caption(f"{data['sector']} · {data['industry']} · {data['country']}")
    with col2:
        price = data.get("current_price", 0)
        st.metric("Current Price", f"${price:,.2f}")
    with col3:
        mc = data.get("market_cap")
        if mc:
            st.metric("Market Cap", f"${mc/1e9:,.1f}B")

    # ── Signal Banner ────────────────────────────────────
    grades = results.get("grades", {})
    signal = grades.get("signal", valuation.get("signal", "N/A"))
    signal_color = grades.get("signal_color", valuation.get("signal_color", "gray"))
    overall_grade = grades.get("overall_grade", "N/A")
    overall_score = grades.get("overall_score", 0)
    fair_value = valuation.get("fair_value")
    upside = valuation.get("upside_pct")
    fv_range = valuation.get("fair_value_range")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            f'<div class="signal-box" style="background-color: {signal_color}; color: white;">'
            f'{signal}</div>',
            unsafe_allow_html=True,
        )
    with col2:
        st.metric("Overall Grade", f"{overall_grade} ({overall_score:.0f}점)")
    with col3:
        if fair_value:
            st.metric("Fair Value (종합)", f"${fair_value:,.2f}",
                      delta=f"{upside:+.1f}%" if upside else None)
    with col4:
        if fv_range:
            st.metric("Fair Value Range", f"${fv_range[0]:,.0f} - ${fv_range[1]:,.0f}")

    # ── Category Grade Cards (7 cards in a row) ──────────
    from src.grading.category_grades import CATEGORY_LABELS
    cats = grades.get("categories", {})
    if cats:
        grade_cols = st.columns(7)
        cat_order = ["valuation", "quality", "financial", "smart_money",
                     "risk_quant", "macro", "sector"]
        for col, key in zip(grade_cols, cat_order):
            c = cats.get(key, {})
            g = c.get("grade", "N/A")
            s = c.get("score", 0)
            clr = c.get("color", "#9E9E9E")
            label = CATEGORY_LABELS.get(key, key)
            with col:
                st.markdown(
                    f'<div class="grade-card" style="background-color: {clr};">'
                    f'<p class="grade-label">{label}</p>'
                    f'<p class="grade-value">{g}</p>'
                    f'<p class="grade-score">{s:.0f}/100</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    # ── KPI Cards ────────────────────────────────────────
    kpi_cols = st.columns(6)
    kpi_data = [
        ("P/E", data.get("trailing_pe"), ".1f"),
        ("Fwd P/E", data.get("forward_pe"), ".1f"),
        ("EV/EBITDA", data.get("ev_to_ebitda"), ".1f"),
        ("P/B", data.get("price_to_book"), ".2f"),
        ("Div Yield", f"{(data.get('dividend_yield') or 0)*100:.1f}%", "s"),
        ("Beta", data.get("beta"), ".2f"),
    ]
    for col, (label, val, fmt) in zip(kpi_cols, kpi_data):
        with col:
            if val is not None:
                display_val = val if fmt == "s" else f"{val:{fmt}}"
                st.metric(label, display_val)
            else:
                st.metric(label, "N/A")

    # ── Tabs ─────────────────────────────────────────────
    tabs = st.tabs([
        "📈 Valuation", "🏅 Quality", "💰 Financials",
        "🧠 Smart Money", "⚡ Risk & Quant",
        "🌍 Macro", "🏭 Sector"
    ])

    # ──────────── TAB: VALUATION ─────────────────────────
    with tabs[0]:
        _render_valuation_tab(results)

    # ──────────── TAB: QUALITY ───────────────────────────
    with tabs[1]:
        _render_quality_tab(results)

    # ──────────── TAB: FINANCIALS ────────────────────────
    with tabs[2]:
        _render_financials_tab(results)

    # ──────────── TAB: SMART MONEY ───────────────────────
    with tabs[3]:
        _render_smart_money_tab(results)

    # ──────────── TAB: RISK & QUANT ──────────────────────
    with tabs[4]:
        _render_risk_quant_tab(results)

    # ──────────── TAB: MACRO ─────────────────────────────
    with tabs[5]:
        _render_macro_tab(results)

    # ──────────── TAB: SECTOR ────────────────────────────
    with tabs[6]:
        _render_sector_tab(results)


# ═══════════════════════════════════════════════════════════
# TAB RENDERERS
# ═══════════════════════════════════════════════════════════

def _render_valuation_tab(results: dict):
    from src.charts.all_charts import chart_valuation_comparison, chart_monte_carlo

    valuation = results["valuation"]
    data = results["data"]
    current_price = data.get("current_price", 0)

    # Summary table
    st.subheader("밸류에이션 모델 비교")
    summary = valuation.get("models_summary", [])
    if summary:
        df = pd.DataFrame(summary)
        df.columns = ["Model", "Fair Value ($)", "Upside (%)", "Confidence"]
        st.dataframe(df, use_container_width=True, hide_index=True)

    # Charts side by side
    col1, col2 = st.columns(2)
    with col1:
        fig = chart_valuation_comparison(valuation, current_price)
        if fig:
            st.pyplot(fig)

    with col2:
        dcf_result = valuation.get("models", {}).get("dcf", {})
        mc_dist = dcf_result.get("mc_distribution")
        fv = dcf_result.get("fair_value") or valuation.get("fair_value") or 0
        if mc_dist is not None and len(mc_dist) > 0:
            fig_mc = chart_monte_carlo(mc_dist, current_price, fv)
            if fig_mc:
                st.pyplot(fig_mc)

    # Reverse DCF
    st.subheader("Reverse DCF — 시장 내재 기대치")
    rev_dcf = valuation.get("models", {}).get("reverse_dcf", {})
    if rev_dcf.get("implied_growth_rate") is not None:
        col1, col2 = st.columns(2)
        with col1:
            st.metric("시장 내재 성장률", f"{rev_dcf['implied_growth_rate']}%")
        with col2:
            st.info(rev_dcf.get("assessment", ""))
    else:
        st.caption(rev_dcf.get("assessment", "분석 불가"))

    # DCF Details
    with st.expander("DCF 상세 파라미터"):
        dcf_details = dcf_result.get("details", {})
        if dcf_details:
            cols = st.columns(4)
            items = list(dcf_details.items())
            for i, (k, v) in enumerate(items):
                with cols[i % 4]:
                    st.metric(k.replace("_", " ").title(), f"{v}")

        # MC stats
        if dcf_result.get("mc_p10"):
            st.markdown("**Monte Carlo Summary**")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("10th Percentile", f"${dcf_result['mc_p10']:,.0f}")
            c2.metric("Median", f"${dcf_result.get('mc_median', 0):,.0f}")
            c3.metric("Mean", f"${dcf_result.get('mc_mean', 0):,.0f}")
            c4.metric("90th Percentile", f"${dcf_result['mc_p90']:,.0f}")


def _render_quality_tab(results: dict):
    from src.charts.all_charts import chart_quality_radar

    data = results["data"]
    piotroski = results["piotroski"]
    altman = results["altman"]
    beneish = results["beneish"]
    dupont = results["dupont"]
    eq = results["earnings_quality"]
    eva = results["eva"]
    qg = results["quality_grade"]

    # Quality Grade header
    st.subheader(f"Quality Grade: {qg['grade']} ({qg['score']:.0f}/{qg['max_score']})")

    col_left, col_right = st.columns([1, 1])

    with col_left:
        # Piotroski F-Score
        st.markdown(f"### Piotroski F-Score: {piotroski['score']}/9 ({piotroski['grade']})")
        for signal_name, passed, value in piotroski.get("signals", []):
            icon = "✅" if passed else "❌"
            val_str = f" ({value})" if value is not None else ""
            st.markdown(f"{icon} {signal_name}{val_str}")

        # Altman Z-Score
        st.markdown(f"### Altman Z-Score: {altman.get('z_score', 'N/A')} ({altman.get('zone', 'N/A')})")
        if altman.get("components"):
            for k, v in altman["components"].items():
                st.caption(f"  {k}: {v}")

        # Beneish M-Score
        st.markdown(f"### Beneish M-Score: {beneish.get('m_score', 'N/A')}")
        st.caption(f"Manipulation Risk: {beneish.get('manipulation_risk', 'N/A')}")

    with col_right:
        # Radar chart
        fig = chart_quality_radar(data, piotroski, altman, eva)
        if fig:
            st.plotly_chart(fig, use_container_width=True)

        # EVA & ROIC
        st.markdown("### EVA & ROIC Spread")
        c1, c2, c3 = st.columns(3)
        c1.metric("ROIC", f"{eva.get('roic', 'N/A')}%")
        c2.metric("WACC", f"{eva.get('wacc', 'N/A')}%")
        c3.metric("Spread", f"{eva.get('spread', 'N/A')}%")
        st.caption(eva.get("verdict", ""))

        # Earnings Quality
        st.markdown(f"### Earnings Quality: {eq.get('earnings_quality', 'N/A')}")
        ar = data.get("accrual_ratio")
        ccr = data.get("cash_conversion")
        if ar is not None:
            st.caption(f"Accrual Ratio: {ar:.4f}")
        if ccr is not None:
            st.caption(f"Cash Conversion Ratio: {ccr:.2f}")

    # DuPont
    with st.expander("DuPont 5-Factor Decomposition"):
        ts = dupont.get("time_series", [])
        if ts:
            df = pd.DataFrame(ts)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.caption("데이터 부족")


def _render_financials_tab(results: dict):
    from src.charts.all_charts import chart_revenue_profit, chart_margins

    data = results["data"]

    # Charts
    col1, col2 = st.columns(2)
    with col1:
        fig = chart_revenue_profit(data)
        if fig:
            st.pyplot(fig)
    with col2:
        fig = chart_margins(data)
        if fig:
            st.pyplot(fig)

    # Financial statements
    sub_tabs = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])

    with sub_tabs[0]:
        inc = data.get("income_stmt")
        if inc is not None and not inc.empty:
            st.dataframe((inc / 1e6).round(1), use_container_width=True)
            st.caption("($ millions)")
        else:
            st.caption("데이터 없음")

    with sub_tabs[1]:
        bs = data.get("balance_sheet")
        if bs is not None and not bs.empty:
            st.dataframe((bs / 1e6).round(1), use_container_width=True)
            st.caption("($ millions)")
        else:
            st.caption("데이터 없음")

    with sub_tabs[2]:
        cf = data.get("cashflow")
        if cf is not None and not cf.empty:
            st.dataframe((cf / 1e6).round(1), use_container_width=True)
            st.caption("($ millions)")
        else:
            st.caption("데이터 없음")

    # Key ratios
    with st.expander("Key Financial Ratios"):
        ratios = {
            "Gross Margin": f"{(data.get('gross_margin') or 0)*100:.1f}%",
            "Operating Margin": f"{(data.get('operating_margin') or 0)*100:.1f}%",
            "Net Margin": f"{(data.get('profit_margin') or 0)*100:.1f}%",
            "ROE": f"{(data.get('roe') or 0)*100:.1f}%",
            "ROA": f"{(data.get('roa') or 0)*100:.1f}%",
            "ROIC": f"{(data.get('roic') or 0)*100:.1f}%",
            "D/E": f"{data.get('debt_to_equity') or 'N/A'}",
            "Current Ratio": f"{data.get('current_ratio') or 'N/A'}",
            "Interest Coverage": f"{data.get('interest_coverage') or 'N/A'}",
            "Net Debt/EBITDA": f"{data.get('net_debt_to_ebitda') or 'N/A'}",
        }
        cols = st.columns(5)
        for i, (k, v) in enumerate(ratios.items()):
            with cols[i % 5]:
                st.metric(k, v)


def _render_smart_money_tab(results: dict):
    sm = results["smart_money"]
    data = results["data"]
    guru = results.get("guru", {})
    guru_count = guru.get("guru_count", 0)

    # Overall signal
    st.markdown(
        f'<div class="signal-box" style="background-color: {sm["overall_color"]}; '
        f'color: white;">Smart Money: {sm["overall_signal"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    # Guru summary (brief) + link to dedicated tab
    if guru_count > 0:
        st.info(
            f"🏆 {guru_count}명의 유명 투자자가 이 종목을 보유 중입니다. "
            f"상세 내역은 **🏦 13F 구루** 탭에서 확인하세요."
        )
    else:
        st.caption("구루 투자자 정보는 **🏦 13F 구루** 탭에서 확인할 수 있습니다.")

    st.markdown("---")

    # ── Smart Money Signals ─────────────────────────
    col1, col2 = st.columns(2)

    with col1:
        # Insider
        ins = sm["insider"]
        st.subheader(f"👤 Insider Transactions — {ins['signal']}")
        st.caption(ins.get("net_signal", ""))
        c1, c2 = st.columns(2)
        c1.metric("Recent Buys", ins.get("recent_buys", 0))
        c2.metric("Recent Sells", ins.get("recent_sells", 0))

        # Short Interest
        si = sm["short_interest"]
        st.subheader(f"📉 Short Interest — {si['signal']}")
        c1, c2 = st.columns(2)
        spf = si.get("short_pct_float")
        c1.metric("Short % Float",
                   f"{spf*100:.1f}%" if spf and isinstance(spf, (int, float)) else "N/A")
        c2.metric("Short Ratio (DTC)", si.get("short_ratio", "N/A"))
        st.caption(f"Risk Level: {si.get('risk_level', 'N/A')}")

    with col2:
        # Institutional
        inst = sm["institutional"]
        st.subheader("🏛️ Institutional Ownership")
        c1, c2 = st.columns(2)
        pct_inst = inst.get("pct_institutions")
        pct_ins = inst.get("pct_insiders")
        c1.metric("Institutions", f"{pct_inst*100:.1f}%" if pct_inst else "N/A")
        c2.metric("Insiders", f"{pct_ins*100:.1f}%" if pct_ins else "N/A")

        if inst.get("top_holders"):
            with st.expander("Top 10 Institutional Holders"):
                df = pd.DataFrame(inst["top_holders"])
                st.dataframe(df, use_container_width=True, hide_index=True)

        # Buyback
        bb = sm["buyback"]
        st.subheader(f"🔄 Buyback — {bb['signal']}")
        c1, c2 = st.columns(2)
        c1.metric("Buyback Yield", f"{bb.get('buyback_yield', 'N/A')}%")
        c2.metric("Total Shareholder Yield", f"{bb.get('total_shareholder_yield', 'N/A')}%")


def _render_risk_quant_tab(results: dict):
    from src.charts.all_charts import chart_drawdown, chart_price_with_ma

    data = results["data"]
    risk = results["risk"]
    quant = results["quant"]

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"⚠️ Risk: {risk.get('overall_risk', 'N/A')}")

        # Return metrics
        rm = risk["return_metrics"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Sharpe", rm.get("sharpe_ratio", "N/A"))
        c2.metric("Sortino", rm.get("sortino_ratio", "N/A"))
        c3.metric("Max DD", f"{rm.get('max_drawdown', 'N/A')}%")
        c4.metric("Ann. Vol", f"{rm.get('annual_volatility', 'N/A')}%")

        # VaR
        var = risk["var"]
        c1, c2, c3 = st.columns(3)
        c1.metric("VaR 95%", f"{var.get('var_95', 'N/A')}%")
        c2.metric("VaR 99%", f"{var.get('var_99', 'N/A')}%")
        c3.metric("CVaR 95%", f"{var.get('cvar_95', 'N/A')}%")

        # Leverage
        lev = risk["leverage"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("D/E", lev.get("debt_to_equity", "N/A"))
        c2.metric("ND/EBITDA", lev.get("net_debt_to_ebitda", "N/A"))
        c3.metric("Int Coverage", lev.get("interest_coverage", "N/A"))
        c4.metric("Unlev Beta", lev.get("unlevered_beta", "N/A"))

    with col2:
        # Quant signals
        st.subheader(f"📊 Technical: {quant.get('overall_signal', 'Neutral')}")

        mom = quant["momentum"]
        c1, c2, c3 = st.columns(3)
        c1.metric("12M Mom", f"{mom.get('momentum_12m', 'N/A')}%")
        c2.metric("6M Mom", f"{mom.get('momentum_6m', 'N/A')}%")
        c3.metric("1M Mom", f"{mom.get('momentum_1m', 'N/A')}%")

        tech = quant["technicals"]
        c1, c2, c3 = st.columns(3)
        c1.metric("RSI (14)", tech.get("rsi_14", "N/A"))
        c2.metric("Bollinger %", tech.get("bollinger_position", "N/A"))
        c3.metric("52W Position", f"{tech.get('fifty_two_week_proximity', 'N/A')}%")

        # Special flags
        flags = []
        if tech.get("golden_cross"):
            flags.append("🟢 Golden Cross detected")
        if tech.get("death_cross"):
            flags.append("🔴 Death Cross detected")
        if tech.get("obv_trend"):
            flags.append(f"OBV: {tech['obv_trend']}")
        for f in flags:
            st.caption(f)

        # Earnings momentum
        sue = quant["earnings_momentum"]
        if sue.get("sue_score") is not None:
            st.metric("SUE Score", sue["sue_score"])

    # Charts
    fig_price = chart_price_with_ma(data)
    if fig_price:
        st.pyplot(fig_price)

    fig_dd = chart_drawdown(data)
    if fig_dd:
        st.pyplot(fig_dd)


def _render_macro_tab(results: dict):
    macro = results.get("macro")
    if not macro:
        st.info("매크로 분석이 비활성화되어 있습니다. 사이드바에서 활성화하세요.")
        return

    st.subheader("🌍 Macro Environment")
    st.markdown(f"**{macro.get('summary', '')}**")
    st.info(macro.get("implication", ""))

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("### Yield Curve")
        yc = macro["yield_curve"]
        c1, c2, c3 = st.columns(3)
        c1.metric("10Y", f"{yc.get('treasury_10y', 'N/A')}%")
        c2.metric("2Y", f"{yc.get('treasury_2y', 'N/A')}%")
        c3.metric("Spread", f"{yc.get('spread', 'N/A')}%")
        if yc.get("inverted"):
            st.error("⚠️ 수익률곡선 역전!")

    with col2:
        st.markdown("### Credit & ERP")
        cr = macro["credit"]
        st.metric("HY Spread", f"{cr.get('hy_spread', 'N/A')}")
        st.caption(f"Credit Regime: {cr.get('regime', 'N/A')}")
        erp = macro["erp"]
        st.metric("Equity Risk Premium", f"{erp.get('erp', 'N/A')}%")
        st.caption(erp.get("assessment", ""))

    with col3:
        st.markdown("### VIX & Cycle")
        vx = macro["vix"]
        st.metric("VIX", vx.get("level", "N/A"))
        st.caption(f"Regime: {vx.get('regime', 'N/A')}")

        sr = macro["sector_rotation"]
        if sr.get("cycle_phase"):
            st.metric("Business Cycle", sr["cycle_phase"])
        if sr.get("favorable") is True:
            st.success("이 종목의 섹터는 현재 순풍 ↗")
        elif sr.get("favorable") is False:
            st.warning("이 종목의 섹터는 현재 역풍 ↘")

    # Sector rotation table
    ranking = macro.get("sector_rotation", {}).get("sector_ranking", {})
    if ranking:
        with st.expander("Sector Rotation — 3M Relative Strength"):
            df = pd.DataFrame(list(ranking.items()), columns=["Sector", "3M Return (%)"])
            st.dataframe(df, use_container_width=True, hide_index=True)


def _render_sector_tab(results: dict):
    sm = results["sector_metrics"]
    st.subheader(f"🏭 Sector: {sm['sector_type']}")
    st.caption(f"{sm['sector']} · {sm['industry']}")

    metrics = sm.get("metrics", {})
    if not metrics:
        st.caption("이 섹터에 대한 추가 지표가 없습니다.")
        return

    cols = st.columns(min(len(metrics), 4))
    for i, (k, v) in enumerate(metrics.items()):
        if k == "note":
            st.caption(f"ℹ️ {v}")
            continue
        with cols[i % min(len(metrics), 4)]:
            label = k.replace("_", " ").title()
            if isinstance(v, bool):
                st.metric(label, "✅" if v else "❌")
            elif isinstance(v, (int, float)):
                st.metric(label, f"{v}")
            else:
                st.metric(label, str(v))


# ═══════════════════════════════════════════════════════════
# COMPARISON TAB (Multi-Ticker)
# ═══════════════════════════════════════════════════════════

def display_comparison(all_results: list):
    """Display comparison across multiple tickers."""
    from src.charts.all_charts import chart_comparison_heatmap

    st.markdown("---")
    st.header("📊 Multi-Ticker Comparison")

    # Summary table
    rows = []
    for r in all_results:
        d = r["data"]
        v = r["valuation"]
        g = r.get("grades", {})
        cats = g.get("categories", {})
        row = {
            "Ticker": d["ticker"],
            "Price": f"${d.get('current_price', 0):,.2f}",
            "Signal": g.get("signal", v.get("signal", "N/A")),
            "Overall": g.get("overall_grade", "N/A"),
            "Fair Value": f"${v.get('fair_value', 0):,.2f}" if v.get("fair_value") else "N/A",
            "Upside": f"{v.get('upside_pct', 0):+.1f}%" if v.get("upside_pct") is not None else "N/A",
            "Valuation": cats.get("valuation", {}).get("grade", "-"),
            "Quality": cats.get("quality", {}).get("grade", "-"),
            "Financial": cats.get("financial", {}).get("grade", "-"),
            "Smart$": cats.get("smart_money", {}).get("grade", "-"),
            "Risk&Q": cats.get("risk_quant", {}).get("grade", "-"),
            "Macro": cats.get("macro", {}).get("grade", "-"),
            "Sector": cats.get("sector", {}).get("grade", "-"),
        }
        rows.append(row)

    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)

    # Heatmap
    tickers_data = [r["data"] for r in all_results]
    valuations = [r["valuation"] for r in all_results]
    fig = chart_comparison_heatmap(tickers_data, valuations)
    if fig:
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# 13F GURU TAB
# ═══════════════════════════════════════════════════════════

def _render_guru_top5_section():
    """Render the 🔥 Guru Top 5 most commonly held stocks with grades."""
    st.subheader("🔥 구루 인기 종목 Top 5")
    st.caption("15명의 구루 투자자가 가장 많이 중복 보유 중인 종목 (SEC 13F 기준)")

    top5_btn = st.button(
        "🔄 구루 인기 종목 조회",
        key="guru_top5_btn",
        use_container_width=False,
        help="15명의 구루 포트폴리오를 순회합니다. 최초 조회 시 약 10~30초 소요됩니다.",
    )

    if top5_btn:
        try:
            from src.fetcher.sec_edgar import fetch_guru_overlap_top
            from src.fetcher.screener_cache import fetch_light_info
            from src.grading.screener_grades import compute_screener_grades, GRADE_COLORS

            with st.spinner("📡 15명 구루 포트폴리오 집계 중..."):
                overlap = fetch_guru_overlap_top(top_n=5)

            if not overlap:
                st.warning("구루 포트폴리오 데이터를 가져올 수 없습니다.")
                st.session_state["guru_top5"] = None
                return

            # Compute grades for each ticker
            results = []
            grade_bar = st.progress(0)
            for i, item in enumerate(overlap):
                ticker = item["ticker"]
                grade_bar.progress((i + 1) / len(overlap), text=f"등급 산출 중... {ticker}")
                info = fetch_light_info(ticker)
                grades = {}
                if info:
                    grades = compute_screener_grades(info)
                results.append({**item, "grades": grades, "info": info})
                import time as _time
                _time.sleep(0.15)  # gentle rate limit
            grade_bar.empty()
            st.session_state["guru_top5"] = results

        except Exception as e:
            st.error(f"조회 실패: {e}")
            st.session_state["guru_top5"] = None

    # Display cached results
    top5_data = st.session_state.get("guru_top5")
    if top5_data:
        from src.grading.screener_grades import GRADE_COLORS

        # ── Card layout: 5 columns ──
        cols = st.columns(len(top5_data))
        for col, item in zip(cols, top5_data):
            g = item.get("grades", {})
            grade = g.get("overall_grade", "N/A")
            score = g.get("overall_score", 0)
            color = GRADE_COLORS.get(grade, "#666")
            guru_count = item["guru_count"]
            ticker = item["ticker"]
            name = (item.get("info") or {}).get("name", item.get("name", ""))
            if len(name) > 18:
                name = name[:16] + "…"

            val = item.get("total_value", 0)
            val_str = (f"${val/1e9:,.1f}B" if val >= 1e9
                       else f"${val/1e6:,.0f}M" if val >= 1e6
                       else f"${val:,.0f}")

            with col:
                st.markdown(
                    f'<div class="grade-card" style="background-color:{color};">'
                    f'<p class="grade-label" style="font-size:13px;font-weight:bold;">{ticker}</p>'
                    f'<p style="font-size:11px;margin:0;opacity:0.85;">{name}</p>'
                    f'<p class="grade-value">{grade}</p>'
                    f'<p class="grade-score">Score: {score:.0f}</p>'
                    f'<p style="font-size:12px;margin:2px 0;">👥 {guru_count}명 보유</p>'
                    f'<p style="font-size:11px;margin:0;opacity:0.85;">{val_str}</p>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

        # ── Detail table ──
        with st.expander("📋 상세 테이블", expanded=False):
            detail_rows = []
            for i, item in enumerate(top5_data, 1):
                g = item.get("grades", {})
                gurus_str = ", ".join(
                    n.split("(")[0].strip() if "(" in n else n
                    for n in item.get("gurus", [])
                )
                detail_rows.append({
                    "#": i,
                    "티커": item["ticker"],
                    "종목명": (item.get("info") or {}).get("name", item.get("name", "")),
                    "구루 수": item["guru_count"],
                    "보유 구루": gurus_str,
                    "합산 금액": f"${item.get('total_value', 0):,.0f}",
                    "Overall Grade": g.get("overall_grade", "N/A"),
                    "Score": f"{g.get('overall_score', 0):.0f}",
                })
            df_top5 = pd.DataFrame(detail_rows)
            st.dataframe(df_top5, use_container_width=True, hide_index=True)


def display_guru_tab():
    """Display the 13F Guru Investor tab — independent of ticker analysis."""
    from config import GURU_INVESTORS

    st.header("🏦 13F 구루 투자자")
    st.caption("SEC 13F 공시 기반으로 유명 투자 기관의 포트폴리오와 보유 내역을 조회합니다.")

    # ── 🔥 구루 인기 종목 Top 5 ──────────────────────────
    _render_guru_top5_section()

    st.markdown("---")

    # ── Sub-tabs inside guru tab ─────────────────────
    guru_sub1, guru_sub2, guru_sub3 = st.tabs([
        "📋 포트폴리오 뷰어", "🔍 구루 보유 종목 검색", "📊 구루 총람"
    ])

    # ──────────── SUB-TAB A: Portfolio Viewer ─────────
    with guru_sub1:
        selected_guru = st.selectbox(
            "투자자 선택",
            options=list(GURU_INVESTORS.keys()),
            index=0,
            key="guru_tab_portfolio_selector",
        )
        if selected_guru:
            try:
                from src.fetcher.sec_edgar import fetch_guru_portfolio
                with st.spinner(f"📡 {selected_guru} 포트폴리오 조회 중..."):
                    portfolio = fetch_guru_portfolio(selected_guru, top_n=20)
                if portfolio and portfolio.get("top_holdings"):
                    # Summary metrics
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("보고 기준일", portfolio["report_date"])
                    c2.metric("제출일", portfolio["filing_date"])
                    c3.metric("총 포트폴리오",
                              f"${portfolio['total_value']/1e9:,.1f}B"
                              if portfolio['total_value'] >= 1e9
                              else f"${portfolio['total_value']/1e6:,.0f}M")
                    c4.metric("총 보유 종목", f"{portfolio['holdings_count']}개")

                    st.markdown("---")

                    # Holdings table
                    st.subheader(f"Top {len(portfolio['top_holdings'])} 보유 종목")
                    port_rows = []
                    for h in portfolio["top_holdings"]:
                        port_rows.append({
                            "#": h["rank"],
                            "종목": h["name"],
                            "티커": h.get("ticker", "—"),
                            "주식수": f"{h['shares']:,}",
                            "금액": f"${h['value_usd']:,.0f}",
                            "비중": f"{h['pct_of_portfolio']:.2f}%",
                        })
                    df_port = pd.DataFrame(port_rows)
                    st.dataframe(df_port, use_container_width=True, hide_index=True)

                    # Sector distribution pie chart
                    _render_guru_sector_chart(portfolio["top_holdings"])
                else:
                    st.warning("해당 투자자의 13F 데이터를 가져올 수 없습니다.")
            except Exception as e:
                st.error(f"포트폴리오 조회 실패: {e}")

    # ──────────── SUB-TAB B: Ticker Search ───────────
    with guru_sub2:
        # Pre-fill from analysis results if available
        default_ticker = ""
        ar = st.session_state.get("all_results")
        if ar and len(ar) > 0:
            default_ticker = ar[0].get("data", {}).get("ticker", "")

        search_ticker = st.text_input(
            "구루 보유 여부를 조회할 티커",
            value=default_ticker,
            placeholder="AAPL",
            key="guru_ticker_search_input",
        ).strip().upper()

        search_btn = st.button("🔍 검색", key="guru_search_btn")

        if search_btn and search_ticker:
            try:
                from src.fetcher.sec_edgar import fetch_guru_holdings_for_ticker
                with st.spinner(f"📡 {search_ticker} 구루 보유 현황 조회 중... (15명 순회, 1~2분 소요)"):
                    guru_data = fetch_guru_holdings_for_ticker(search_ticker)
                st.session_state["guru_ticker_search"] = guru_data
            except Exception as e:
                st.error(f"조회 실패: {e}")
                st.session_state["guru_ticker_search"] = None

        # Display cached search results
        guru_data = st.session_state.get("guru_ticker_search")
        if guru_data and guru_data.get("ticker"):
            holders = guru_data.get("guru_holders", [])
            count = guru_data.get("guru_count", 0)
            searched_ticker = guru_data["ticker"]

            st.subheader(f"🏆 {searched_ticker} — {count}명의 구루가 보유 중")

            if holders:
                guru_rows = []
                for g in holders:
                    guru_rows.append({
                        "투자자": g["investor"],
                        "보유 주식수": f"{g['shares']:,}",
                        "보유 금액": f"${g['value_usd']:,.0f}",
                        "포트폴리오 비중": f"{g['pct_of_portfolio']:.2f}%",
                        "보고일": g.get("report_date", "N/A"),
                        "제출일": g.get("filing_date", "N/A"),
                    })
                df_guru = pd.DataFrame(guru_rows)
                st.dataframe(df_guru, use_container_width=True, hide_index=True)

                total_val = guru_data.get("total_guru_value", 0)
                if total_val > 0:
                    st.info(
                        f"💰 {count}명의 유명 투자자가 총 "
                        f"**${total_val:,.0f}** 규모로 보유 중 (SEC 13F 기준)"
                    )
            else:
                st.caption("현재 추적 중인 15명의 유명 투자자 중 이 종목을 보유한 투자자가 없습니다.")

    # ──────────── SUB-TAB C: Guru List ───────────────
    with guru_sub3:
        st.subheader("📊 추적 중인 구루 투자자 목록")
        st.caption("SEC EDGAR 13F 공시 기반 — 15명의 유명 투자 기관")

        guru_list_rows = []
        for i, (name, cik) in enumerate(GURU_INVESTORS.items(), 1):
            guru_list_rows.append({
                "#": i,
                "투자자 / 기관": name,
                "CIK": cik,
            })
        df_gurus = pd.DataFrame(guru_list_rows)
        st.dataframe(df_gurus, use_container_width=True, hide_index=True)

        st.markdown("""---
**안내:**
- 13F 공시는 $1억 이상 운용 기관의 분기별 보고서입니다.
- 보고 기준일과 실제 제출일 사이에 최대 45일의 시차가 있을 수 있습니다.
- 포트폴리오 뷰어 탭에서 각 구루의 상세 보유 내역을 확인할 수 있습니다.
        """)


def _render_guru_sector_chart(holdings: list):
    """Render a sector distribution pie chart from guru holdings."""
    import plotly.express as px

    # Group by first word/keyword of company name as a rough sector proxy
    # Since we only have name and ticker, we do a simple grouping
    sector_values = {}
    for h in holdings:
        ticker = h.get("ticker", "—")
        val = h.get("value_usd", 0)
        name = h.get("name", "Unknown")
        sector_values[f"{ticker} ({name[:20]})"] = val

    if sector_values:
        df = pd.DataFrame({
            "종목": list(sector_values.keys()),
            "금액": list(sector_values.values()),
        })
        fig = px.pie(
            df, values="금액", names="종목",
            title="보유 종목 비중",
            hole=0.4,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label")
        fig.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════════════════
# SCREENER HELPERS
# ═══════════════════════════════════════════════════════════

def _apply_screener_filters(stocks: list) -> list:
    """Apply sidebar filter criteria to screener scan data."""
    filtered = list(stocks)

    # Grade filter
    grade_filter = st.session_state.get("scr_grade", [])
    if grade_filter:
        filtered = [s for s in filtered
                    if s.get("grades", {}).get("overall_grade") in grade_filter]

    # Market cap filter
    cap_filter = st.session_state.get("scr_cap", [])
    if cap_filter and len(cap_filter) < 4:
        def _cap_match(mc):
            if mc is None:
                return False
            if "Mega (>200B)" in cap_filter and mc > 200e9:
                return True
            if "Large (10-200B)" in cap_filter and 10e9 <= mc <= 200e9:
                return True
            if "Mid (2-10B)" in cap_filter and 2e9 <= mc <= 10e9:
                return True
            if "Small (<2B)" in cap_filter and mc < 2e9:
                return True
            return False
        filtered = [s for s in filtered if _cap_match(s.get("market_cap"))]

    # Sector filter
    sector_filter = st.session_state.get("scr_sector", [])
    if sector_filter:
        filtered = [s for s in filtered if s.get("sector") in sector_filter]

    # Country filter
    country_text = st.session_state.get("scr_country", "")
    if country_text.strip():
        countries = [c.strip() for c in country_text.split(",") if c.strip()]
        if countries:
            filtered = [s for s in filtered if s.get("country") in countries]

    # P/E range
    pe_range = st.session_state.get("scr_pe", (0.0, 100.0))
    if pe_range != (0.0, 100.0):
        def _pe_match(s):
            pe = s.get("forward_pe") or s.get("trailing_pe")
            if pe is None:
                return True  # Include stocks without P/E
            return pe_range[0] <= pe <= pe_range[1]
        filtered = [s for s in filtered if _pe_match(s)]

    # Min dividend yield
    min_div = st.session_state.get("scr_div", 0.0)
    if min_div > 0:
        filtered = [s for s in filtered
                    if (s.get("dividend_yield") or 0) * 100 >= min_div]

    # Min ROE
    min_roe = st.session_state.get("scr_roe", 0.0)
    if min_roe > 0:
        filtered = [s for s in filtered
                    if s.get("roe") is not None and s["roe"] * 100 >= min_roe]

    # Sort
    sort_by = st.session_state.get("scr_sort", "Overall Grade ↓")
    if sort_by == "Overall Grade ↓":
        filtered.sort(key=lambda x: x.get("grades", {}).get("overall_score", 0), reverse=True)
    elif sort_by == "시가총액 ↓":
        filtered.sort(key=lambda x: x.get("market_cap") or 0, reverse=True)
    elif sort_by == "P/E ↑":
        filtered.sort(key=lambda x: (x.get("forward_pe") or x.get("trailing_pe") or 999))
    elif sort_by == "ROE ↓":
        filtered.sort(key=lambda x: x.get("roe") or 0, reverse=True)
    elif sort_by == "배당수익률 ↓":
        filtered.sort(key=lambda x: x.get("dividend_yield") or 0, reverse=True)

    return filtered


def display_screener():
    """Display the stock screener tab."""
    from src.fetcher.screener_cache import (
        load_cached_scan, scan_universe as _scan_universe, load_universe
    )

    universe_key = SCREENER_UNIVERSES.get(scr_universe, "sp500_nasdaq100")

    # ── Load data (session → disk cache) ─────────────────
    scan_data = None
    if (st.session_state.get("screener_data")
            and st.session_state.get("screener_universe") == universe_key):
        scan_data = st.session_state["screener_data"]
    else:
        cached = load_cached_scan(universe_key)
        if cached:
            st.session_state["screener_data"] = cached
            st.session_state["screener_universe"] = universe_key
            scan_data = cached

    # ── Run scan if button pressed ───────────────────────
    if scan_btn:
        st.info(f"🔄 **{scr_universe}** 유니버스 스캔을 시작합니다... (약 5-10분 소요)")
        progress_bar = st.progress(0)
        status_text = st.empty()
        scan_data = _scan_universe(universe_key, progress_bar, status_text)
        st.session_state["screener_data"] = scan_data
        st.session_state["screener_universe"] = universe_key
        progress_bar.empty()
        status_text.empty()
        st.success(
            f"✅ 스캔 완료! {scan_data['successful']}/{scan_data['total_scanned']}개 종목 성공"
        )

    # ── No data yet ──────────────────────────────────────
    if not scan_data:
        universe_tickers = load_universe(universe_key)
        st.info(
            f"📋 **{scr_universe}** 유니버스: {len(universe_tickers)}개 종목\n\n"
            f"아직 스캔 데이터가 없습니다. 사이드바의 **🔎 스크리너 필터**에서 "
            f"**'스크리닝 시작'** 버튼을 클릭하세요.\n\n"
            f"⏱️ 최초 스캔: 약 5-10분 소요 (이후 24시간 캐시)"
        )
        return

    # ── Scan summary header ──────────────────────────────
    scan_time = scan_data.get("scan_time", "N/A")
    c1, c2, c3 = st.columns(3)
    c1.metric("스캔 종목 수", f"{scan_data.get('successful', 0)}")
    c2.metric("스캔 시간", str(scan_time)[:16])
    c3.metric("실패", f"{scan_data.get('failed', 0)}")

    st.markdown("---")

    # ── Apply filters ────────────────────────────────────
    stocks = scan_data.get("stocks", [])
    filtered = _apply_screener_filters(stocks)

    st.subheader(f"필터 결과: {len(filtered)}개 / {len(stocks)}개 종목")

    if not filtered:
        st.warning("조건에 맞는 종목이 없습니다. 필터를 조정해보세요.")
        return

    # ── Build display table ──────────────────────────────
    rows = []
    for i, s in enumerate(filtered):
        g = s.get("grades", {})
        mc = s.get("market_cap")
        mc_str = f"${mc/1e9:.1f}B" if mc and mc >= 1e9 else (
            f"${mc/1e6:.0f}M" if mc else "N/A")
        pe = s.get("forward_pe") or s.get("trailing_pe")
        roe = s.get("roe")
        dy = s.get("dividend_yield")

        rows.append({
            "#": i + 1,
            "티커": s["ticker"],
            "기업명": s.get("name", ""),
            "섹터": s.get("sector", "N/A"),
            "국가": s.get("country", "N/A"),
            "시가총액": mc_str,
            "현재가": f"${s.get('current_price', 0):,.2f}",
            "Overall": f"{g.get('overall_grade', '—')} ({g.get('overall_score', 0):.0f})",
            "Valuation": g.get("valuation_grade", "—"),
            "Financial": g.get("financial_grade", "—"),
            "Macro": g.get("macro_grade", "—"),
            "P/E": f"{pe:.1f}" if pe else "—",
            "ROE": f"{roe*100:.1f}%" if roe else "—",
            "배당률": f"{dy*100:.1f}%" if dy else "—",
        })

    df_screen = pd.DataFrame(rows)
    st.dataframe(df_screen, use_container_width=True, hide_index=True, height=500)

    # ── Grade legend ─────────────────────────────────────
    with st.expander("ℹ️ 등급 범례 및 안내"):
        st.markdown("""
| 등급 | 점수 범위 | 의미 |
|------|----------|------|
| A+ ~ A- | 80-100 | 우수 |
| B+ ~ B- | 62-79 | 양호 |
| C+ ~ C- | 42-61 | 보통 |
| D+ ~ D- | 0-41 | 미흡 |

**스크리너 등급 산출 방식:** Financial(50%) + Valuation(30%) + Macro(20%)

- **Financial:** 매출성장률, 영업이익률, ROE, FCF마진, D/E
- **Valuation:** P/E, EV/EBITDA, P/B를 섹터 평균과 비교
- **Macro:** 시장 전체 환경 (기본값 50점)

Quality, Smart Money, Risk&Quant, Sector 등급은 **전체 분석**에서만 확인 가능합니다.
        """)

    # ── Select tickers for full analysis ─────────────────
    st.markdown("---")
    st.subheader("📊 선택 종목 전체 분석")
    ticker_options = [s["ticker"] for s in filtered]
    selected_tickers = st.multiselect(
        "분석할 종목 선택 (최대 10개)",
        ticker_options,
        max_selections=10,
        key="scr_select_tickers",
    )

    if selected_tickers:
        if st.button("🔍 선택 종목 전체 분석 실행", type="primary", key="scr_full_analysis"):
            dcf_overrides = {
                "risk_free_rate": DCF_DEFAULTS["risk_free_rate"],
                "equity_risk_premium": DCF_DEFAULTS["equity_risk_premium"],
                "terminal_growth_rate": terminal_g,
                "high_growth_years": high_growth_yrs,
                "fade_years": DCF_DEFAULTS["fade_years"],
            }
            if wacc_override != 0.10:
                dcf_overrides["default_wacc"] = wacc_override
            if growth_override != 0.0:
                dcf_overrides["growth_override"] = growth_override / 100

            full_results = []
            for ticker in selected_tickers:
                result = run_analysis(ticker, dcf_overrides)
                if result:
                    full_results.append(result)

            if full_results:
                st.session_state["all_results"] = full_results
                st.success(
                    f"✅ {len(full_results)}개 종목 분석 완료! "
                    f"**📊 종목 분석** 탭에서 결과를 확인하세요."
                )
            else:
                st.error("분석에 실패했습니다. 티커를 확인해주세요.")


# ═══════════════════════════════════════════════════════════
# PORTFOLIO SIMULATOR TAB
# ═══════════════════════════════════════════════════════════

def display_portfolio_tab():
    """Display the Portfolio Simulator tab."""
    from src.portfolio.fetcher import fetch_multi_history, fetch_benchmarks
    from src.portfolio.weights import (
        equal_weight, market_cap_weight, inverse_vol_weight, risk_parity_weight,
    )
    from src.portfolio.analytics import (
        correlation_matrix, portfolio_metrics, rolling_metrics,
        factor_exposure, monthly_returns_table, contribution_by_ticker,
    )
    from src.charts.all_charts import (
        chart_portfolio_equity_curve, chart_portfolio_drawdown,
        chart_correlation_heatmap, chart_weight_allocation, chart_rolling_sharpe,
    )

    st.header("💼 포트폴리오 시뮬레이터")
    st.caption("종목 구성 → 가중치 배정 → 성과/리스크 분석")

    # ── Run simulation when button pressed ──────────────
    if simulate_btn:
        raw_tickers = [t.strip().upper() for t in pf_ticker_input.replace(";", ",").split(",")]
        tickers = [t for t in raw_tickers if t][:MAX_PORTFOLIO_TICKERS]

        if len(tickers) < 1:
            st.warning("종목을 최소 1개 입력하세요.")
            return

        start_str = str(pf_start)
        end_str = str(pf_end)

        with st.spinner("📡 가격 데이터 수집 중..."):
            prices = fetch_multi_history(tickers, start_str, end_str)

        if prices is None or prices.empty:
            st.error("가격 데이터를 가져올 수 없습니다. 티커/기간을 확인하세요.")
            return

        valid_tickers = [t for t in tickers if t in prices.columns]
        if not valid_tickers:
            st.error("유효한 종목 데이터가 없습니다.")
            return

        prices = prices[valid_tickers]

        # Weights
        scheme_key = WEIGHT_SCHEME_NAMES.get(pf_weight_scheme, "equal")
        returns_df = prices.pct_change().dropna()

        if scheme_key == "equal":
            weights = equal_weight(valid_tickers)
        elif scheme_key == "market_cap":
            import yfinance as yf
            caps = {}
            for t in valid_tickers:
                try:
                    info = yf.Ticker(t).info
                    caps[t] = info.get("marketCap", 0)
                except Exception:
                    caps[t] = 0
            weights = market_cap_weight(valid_tickers, caps)
        elif scheme_key == "inverse_vol":
            weights = inverse_vol_weight(returns_df)
        elif scheme_key == "risk_parity":
            weights = risk_parity_weight(returns_df)
        else:
            weights = equal_weight(valid_tickers)

        # Compute weighted NAV
        weighted_rets = pd.Series(0.0, index=returns_df.index)
        for t, w in weights.items():
            if t in returns_df.columns:
                weighted_rets += returns_df[t] * w
        nav = (1 + weighted_rets).cumprod() * pf_capital

        # Benchmarks
        bench_names = pf_benchmarks if pf_benchmarks else ["S&P 500 (SPY)"]
        bench_df = fetch_benchmarks(bench_names, start_str, end_str)
        bench_nav = None
        bench_name_first = bench_names[0] if bench_names else "S&P 500 (SPY)"
        if not bench_df.empty and bench_name_first in bench_df.columns:
            bseries = bench_df[bench_name_first].dropna()
            common = nav.index.intersection(bseries.index)
            if len(common) > 0:
                bseries = bseries.loc[common]
                bench_nav = (bseries / bseries.iloc[0]) * pf_capital

        st.session_state["portfolio_results"] = {
            "nav": nav,
            "bench_nav": bench_nav,
            "bench_df": bench_df,
            "prices": prices,
            "weights": weights,
            "tickers": valid_tickers,
            "scheme": pf_weight_scheme,
            "capital": pf_capital,
        }

    # ── Display results ──────────────────────────────────
    pf_data = st.session_state.get("portfolio_results")
    if not pf_data:
        st.info(
            "왼쪽 사이드바의 **💼 포트폴리오**에서 종목을 입력하고\n"
            "**시뮬레이션 실행** 버튼을 클릭하세요."
        )
        return

    nav = pf_data["nav"]
    bench_nav = pf_data.get("bench_nav")
    prices = pf_data["prices"]
    weights = pf_data["weights"]
    tickers = pf_data["tickers"]
    capital = pf_data["capital"]

    # ── Summary metrics row ──────────────────────────────
    if bench_nav is not None and not bench_nav.empty:
        pm = portfolio_metrics(nav, bench_nav)
    else:
        pm = {}

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("총 수익률", f"{pm.get('total_return', 0):.1f}%")
    c2.metric("연간 수익률", f"{pm.get('annual_return', 0):.1f}%")
    c3.metric("연간 변동성", f"{pm.get('annual_volatility', 0):.1f}%")
    c4.metric("Sharpe", f"{pm.get('sharpe_ratio', 0):.2f}")
    c5.metric("MDD", f"{pm.get('max_drawdown', 0):.1f}%")

    # ── Sub-tabs ─────────────────────────────────────────
    pf_sub1, pf_sub2, pf_sub3 = st.tabs(["📈 성과 분석", "📊 종목 분석", "⚠️ 리스크 분석"])

    with pf_sub1:
        # Equity curve
        st.plotly_chart(
            chart_portfolio_equity_curve(nav, bench_nav),
            use_container_width=True,
        )
        # Drawdown
        st.plotly_chart(
            chart_portfolio_drawdown(nav),
            use_container_width=True,
        )
        # Monthly returns
        st.subheader("📅 월별 수익률 (%)")
        monthly = monthly_returns_table(nav)
        if not monthly.empty:
            st.dataframe(monthly.style.format("{:.1f}", na_rep="—").background_gradient(
                cmap="RdYlGn", vmin=-10, vmax=10, axis=None,
            ), use_container_width=True)

    with pf_sub2:
        col_w, col_corr = st.columns(2)
        with col_w:
            st.plotly_chart(
                chart_weight_allocation(weights, f"포트폴리오 비중 ({pf_data['scheme']})"),
                use_container_width=True,
            )
        with col_corr:
            corr = correlation_matrix(prices)
            if not corr.empty:
                st.plotly_chart(
                    chart_correlation_heatmap(corr),
                    use_container_width=True,
                )
        # Contribution
        contrib = contribution_by_ticker(prices, weights)
        if contrib is not None and not contrib.empty:
            st.subheader("📊 종목별 수익 기여도")
            st.dataframe(contrib, use_container_width=True, hide_index=True)

    with pf_sub3:
        # Rolling Sharpe
        if bench_nav is not None and not bench_nav.empty:
            rm = rolling_metrics(nav, bench_nav)
            if "rolling_sharpe" in rm and not rm["rolling_sharpe"].empty:
                st.plotly_chart(
                    chart_rolling_sharpe(rm["rolling_sharpe"]),
                    use_container_width=True,
                )
            # Alpha / Beta / Info Ratio
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Alpha (연간)", f"{pm.get('alpha', 0):.2f}%")
            c2.metric("Beta", f"{pm.get('beta', 0):.2f}")
            c3.metric("Tracking Error", f"{pm.get('tracking_error', 0):.1f}%")
            c4.metric("Info Ratio", f"{pm.get('information_ratio', 0):.2f}")

        # Factor exposure
        st.subheader("📉 Fama-French 팩터 노출도")
        fe = factor_exposure(nav)
        if fe:
            factor_cols = [c for c in fe if c not in ("alpha_daily", "r_squared")]
            fc1, fc2, fc3 = st.columns([2, 2, 1])
            with fc1:
                for f in factor_cols[:3]:
                    st.metric(f, f"{fe[f]:.4f}")
            with fc2:
                for f in factor_cols[3:]:
                    st.metric(f, f"{fe[f]:.4f}")
            with fc3:
                st.metric("R²", f"{fe.get('r_squared', 0):.2%}")
                st.metric("일별 Alpha", f"{fe.get('alpha_daily', 0):.6f}")
        else:
            st.caption("Fama-French 팩터 데이터를 불러올 수 없습니다.")


# ═══════════════════════════════════════════════════════════
# BACKTEST TAB
# ═══════════════════════════════════════════════════════════

def display_backtest_tab():
    """Display the Backtest tab."""
    from src.portfolio.fetcher import fetch_multi_history, fetch_benchmark
    from src.portfolio.backtest import (
        run_backtest, BacktestConfig, Strategy,
    )
    from src.portfolio.analytics import monthly_returns_table
    from src.charts.all_charts import (
        chart_portfolio_equity_curve, chart_portfolio_drawdown,
        chart_backtest_trades,
    )

    st.header("📈 백테스트")
    st.caption("과거 데이터를 사용하여 투자 전략의 성과를 시뮬레이션합니다.")

    # ── Run backtest ─────────────────────────────────────
    if backtest_btn:
        raw_tickers = [t.strip().upper() for t in bt_ticker_input.replace(";", ",").split(",")]
        tickers = [t for t in raw_tickers if t][:MAX_PORTFOLIO_TICKERS]

        if len(tickers) < 2:
            st.warning("종목을 최소 2개 입력하세요.")
            return

        start_str = str(bt_start)
        end_str = str(bt_end)
        strategy_key = STRATEGY_NAMES.get(bt_strategy, "equal_weight")
        strategy = Strategy(strategy_key)
        freq = REBALANCE_FREQ_MAP.get(bt_rebal, "M")
        bench_ticker = BENCHMARKS.get(bt_benchmark, "SPY")

        config = BacktestConfig(
            tickers=tickers,
            start=start_str,
            end=end_str,
            strategy=strategy,
            initial_capital=bt_capital,
            rebalance_freq=freq,
            benchmark_ticker=bench_ticker,
            transaction_cost=bt_cost / 100,
            top_n=bt_top_n,
        )

        with st.spinner("📡 가격 데이터 수집 중..."):
            prices = fetch_multi_history(tickers, start_str, end_str)
            bench_prices = fetch_benchmark(bt_benchmark, start_str, end_str)

        if prices is None or prices.empty:
            st.error("가격 데이터를 가져올 수 없습니다.")
            return
        if bench_prices is None or bench_prices.empty:
            st.error("벤치마크 데이터를 가져올 수 없습니다.")
            return

        try:
            with st.spinner("📊 백테스트 실행 중..."):
                result = run_backtest(config, prices, bench_prices)
            st.session_state["backtest_results"] = result
        except Exception as e:
            st.error(f"백테스트 실패: {e}")
            return

    # ── Display results ──────────────────────────────────
    bt_result = st.session_state.get("backtest_results")
    if not bt_result:
        st.info(
            "왼쪽 사이드바의 **📈 백테스트**에서 전략/종목을 설정하고\n"
            "**백테스트 실행** 버튼을 클릭하세요."
        )
        return

    metrics = bt_result.metrics

    # ── Strategy name ────────────────────────────────────
    st.subheader(f"전략: {bt_result.strategy_name}")

    # ── Summary metrics row ──────────────────────────────
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("총 수익률", f"{metrics.get('total_return', 0):.1f}%")
    c2.metric("연간 수익률", f"{metrics.get('annual_return', 0):.1f}%")
    c3.metric("Sharpe", f"{metrics.get('sharpe_ratio', 0):.2f}")
    c4.metric("Sortino", f"{metrics.get('sortino_ratio', 0):.2f}")
    c5.metric("MDD", f"{metrics.get('max_drawdown', 0):.1f}%")
    c6.metric("벤치마크 수익", f"{metrics.get('benchmark_return', 0):.1f}%")

    # ── Sub-tabs ─────────────────────────────────────────
    bt_sub1, bt_sub2, bt_sub3 = st.tabs(["📈 결과", "📋 매매 내역", "📊 전략 상세"])

    with bt_sub1:
        # Equity curve
        st.plotly_chart(
            chart_portfolio_equity_curve(
                bt_result.nav_series,
                bt_result.benchmark_series,
                title=f"백테스트 수익률 곡선 — {bt_result.strategy_name}",
            ),
            use_container_width=True,
        )
        # Drawdown
        st.plotly_chart(
            chart_portfolio_drawdown(bt_result.nav_series),
            use_container_width=True,
        )
        # Monthly returns
        st.subheader("📅 월별 수익률 (%)")
        monthly = monthly_returns_table(bt_result.nav_series)
        if not monthly.empty:
            st.dataframe(monthly.style.format("{:.1f}", na_rep="—").background_gradient(
                cmap="RdYlGn", vmin=-10, vmax=10, axis=None,
            ), use_container_width=True)

    with bt_sub2:
        # Trade log
        st.plotly_chart(
            chart_backtest_trades(bt_result.trades_log),
            use_container_width=True,
        )

        if bt_result.trades_log:
            st.subheader("📋 전체 매매 기록")
            trade_rows = []
            for event in bt_result.trades_log:
                for trade in event.get("trades", []):
                    trade_rows.append({
                        "날짜": event["date"],
                        "종목": trade["ticker"],
                        "매매": trade["action"],
                        "수량": f"{trade['shares']:.2f}",
                        "가격": f"${trade['price']:.2f}",
                        "금액": f"${trade['value']:,.0f}",
                    })
            if trade_rows:
                df_trades = pd.DataFrame(trade_rows)
                st.dataframe(df_trades, use_container_width=True, hide_index=True, height=400)
        else:
            st.caption("매매 기록이 없습니다.")

    with bt_sub3:
        # Detailed metrics
        st.subheader("📊 상세 성과 지표")
        detail_c1, detail_c2, detail_c3 = st.columns(3)

        with detail_c1:
            st.markdown("**수익률**")
            st.metric("총 수익률", f"{metrics.get('total_return', 0):.2f}%")
            st.metric("연간 수익률", f"{metrics.get('annual_return', 0):.2f}%")
            st.metric("벤치마크 수익률", f"{metrics.get('benchmark_return', 0):.2f}%")
            st.metric("벤치마크 연간수익", f"{metrics.get('benchmark_ann_return', 0):.2f}%")

        with detail_c2:
            st.markdown("**리스크**")
            st.metric("연간 변동성", f"{metrics.get('annual_volatility', 0):.2f}%")
            st.metric("Max Drawdown", f"{metrics.get('max_drawdown', 0):.2f}%")
            st.metric("Calmar Ratio", f"{metrics.get('calmar_ratio', 0):.2f}")
            st.metric("승률", f"{metrics.get('win_rate', 0):.1f}%")

        with detail_c3:
            st.markdown("**시장 대비**")
            st.metric("Alpha", f"{metrics.get('alpha', 0):.2f}%")
            st.metric("Beta", f"{metrics.get('beta', 0):.2f}")
            st.metric("Sharpe", f"{metrics.get('sharpe_ratio', 0):.2f}")
            st.metric("Sortino", f"{metrics.get('sortino_ratio', 0):.2f}")

        # Weights history
        if bt_result.weights_history:
            st.subheader("📊 리밸런싱별 비중 변화")
            wh_rows = []
            for wh in bt_result.weights_history:
                row = {"날짜": wh["date"]}
                row.update({t: f"{w*100:.1f}%" for t, w in wh["weights"].items()})
                wh_rows.append(row)
            df_wh = pd.DataFrame(wh_rows)
            st.dataframe(df_wh, use_container_width=True, hide_index=True, height=300)

        st.caption(
            f"거래일수: {metrics.get('trading_days', 0)} | "
            f"기간: {metrics.get('years', 0):.1f}년"
        )


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

# Initialize session state
if "all_results" not in st.session_state:
    st.session_state["all_results"] = None
if "screener_data" not in st.session_state:
    st.session_state["screener_data"] = None
if "screener_universe" not in st.session_state:
    st.session_state["screener_universe"] = None
if "guru_ticker_search" not in st.session_state:
    st.session_state["guru_ticker_search"] = None
if "guru_top5" not in st.session_state:
    st.session_state["guru_top5"] = None
if "portfolio_results" not in st.session_state:
    st.session_state["portfolio_results"] = None
if "backtest_results" not in st.session_state:
    st.session_state["backtest_results"] = None

# ── Main Tabs ────────────────────────────────────────────
tab_analysis, tab_screener, tab_guru, tab_portfolio, tab_backtest = st.tabs([
    "📊 종목 분석", "🔎 스크리너", "🏦 13F 구루", "💼 포트폴리오", "📈 백테스트"
])


# ──────────── TAB: ANALYSIS ──────────────────────────────
with tab_analysis:
    if analyze_btn:
        tickers = parse_tickers(ticker_input)
        if tickers:
            dcf_overrides = {
                "risk_free_rate": DCF_DEFAULTS["risk_free_rate"],
                "equity_risk_premium": DCF_DEFAULTS["equity_risk_premium"],
                "terminal_growth_rate": terminal_g,
                "high_growth_years": high_growth_yrs,
                "fade_years": DCF_DEFAULTS["fade_years"],
            }
            if wacc_override != 0.10:
                dcf_overrides["default_wacc"] = wacc_override
            if growth_override != 0.0:
                dcf_overrides["growth_override"] = growth_override / 100

            new_results = []
            for ticker in tickers:
                result = run_analysis(ticker, dcf_overrides)
                if result:
                    new_results.append(result)

            if new_results:
                st.session_state["all_results"] = new_results
            else:
                st.error("분석할 수 있는 종목이 없습니다. 티커를 확인해주세요.")
        else:
            st.warning("티커를 입력해주세요.")

    all_results = st.session_state.get("all_results")

    if all_results:
        if len(all_results) == 1:
            display_single_ticker(all_results[0])
        else:
            for r in all_results:
                with st.expander(
                    f"📊 {r['data']['ticker']} — {r['data']['name']}",
                    expanded=False,
                ):
                    display_single_ticker(r)
            display_comparison(all_results)
    else:
        st.title("📊 Stock Intrinsic Value Analyzer")
        st.markdown("""
        **미국 주식의 적정 가치를 분석하는 도구입니다.**

        왼쪽 사이드바에서 **📊 종목 분석**을 펼치고 티커를 입력 후
        **"분석 시작"** 버튼을 클릭하세요.

        **분석 항목:**
        - 7개 밸류에이션 모델 (DCF, Reverse DCF, Residual Income, EPV, DDM, Multiples, Graham)
        - 품질 점수 (Piotroski F-Score, Altman Z-Score, Beneish M-Score, DuPont)
        - 스마트머니 시그널 (내부자 거래, 기관 보유, 공매도)
        - 퀀트/기술 분석 (모멘텀, RSI, 볼린저밴드, 이동평균)
        - 매크로 환경 (수익률곡선, VIX, 신용 스프레드)
        - 리스크 지표 (Sharpe, Sortino, VaR, Max Drawdown)
        - 섹터별 전문 지표

        **🔎 스크리너:** S&P 500 / NASDAQ 100 종목을 필터링하여
        등급 기반으로 유망 종목을 찾을 수 있습니다.

        **🏦 13F 구루:** 버핏, 달리오 등 유명 투자자의
        SEC 13F 공시 기반 포트폴리오와 보유 종목을 조회할 수 있습니다.

        **💼 포트폴리오:** 종목 구성과 가중치를 설정하여
        포트폴리오 수익률, 리스크, 팩터 노출도를 분석합니다.

        **📈 백테스트:** 4가지 전략(동일비중, 모멘텀, MA크로스, 등급기반)으로
        과거 성과를 시뮬레이션합니다.
        """)

# ──────────── TAB: SCREENER ──────────────────────────────
with tab_screener:
    display_screener()

# ──────────── TAB: 13F GURU ──────────────────────────────
with tab_guru:
    display_guru_tab()

# ──────────── TAB: PORTFOLIO ─────────────────────────────
with tab_portfolio:
    display_portfolio_tab()

# ──────────── TAB: BACKTEST ──────────────────────────────
with tab_backtest:
    display_backtest_tab()
