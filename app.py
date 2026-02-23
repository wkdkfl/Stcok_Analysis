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

from config import MAX_TICKERS, DCF_DEFAULTS, SCREENER_UNIVERSES, SECTOR_MULTIPLES_FALLBACK

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

    # Overall signal
    st.markdown(
        f'<div class="signal-box" style="background-color: {sm["overall_color"]}; '
        f'color: white;">Smart Money: {sm["overall_signal"]}</div>',
        unsafe_allow_html=True,
    )
    st.markdown("")

    # ── Section A: Guru Investor Holdings ─────────────────
    guru_holders = guru.get("guru_holders", [])
    guru_count = guru.get("guru_count", 0)

    st.subheader(f"🏆 유명 투자자 보유 현황 — {guru_count}명의 구루가 보유 중")
    if guru_holders:
        guru_rows = []
        for g in guru_holders:
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

        # Highlight info
        total_val = guru.get("total_guru_value", 0)
        if total_val > 0:
            st.info(f"💰 {guru_count}명의 유명 투자자가 총 **${total_val:,.0f}** 규모로 보유 중 (SEC 13F 기준)")
    else:
        st.caption("현재 추적 중인 유명 투자자 중 이 종목을 보유한 투자자가 없습니다.")

    st.markdown("---")

    # ── Section B: Guru Portfolio Viewer ──────────────────
    from config import GURU_INVESTORS
    st.subheader("📋 구루 투자자 포트폴리오 뷰어")
    selected_guru = st.selectbox(
        "투자자 선택",
        options=list(GURU_INVESTORS.keys()),
        index=0,
        key="guru_portfolio_selector",
    )
    if selected_guru:
        try:
            from src.fetcher.sec_edgar import fetch_guru_portfolio
            with st.spinner(f"📡 {selected_guru} 포트폴리오 조회 중..."):
                portfolio = fetch_guru_portfolio(selected_guru, top_n=20)
            if portfolio and portfolio.get("top_holdings"):
                st.caption(
                    f"📅 보고 기준일: {portfolio['report_date']} | "
                    f"제출일: {portfolio['filing_date']} | "
                    f"총 포트폴리오: ${portfolio['total_value']:,.0f} | "
                    f"총 보유 종목: {portfolio['holdings_count']}개"
                )
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
            else:
                st.caption("해당 투자자의 13F 데이터를 가져올 수 없습니다.")
        except Exception as e:
            st.caption(f"포트폴리오 조회 실패: {e}")

    st.markdown("---")

    # ── Section C: Original Smart Money Signals ──────────
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
# MAIN
# ═══════════════════════════════════════════════════════════

# Initialize session state
if "all_results" not in st.session_state:
    st.session_state["all_results"] = None
if "screener_data" not in st.session_state:
    st.session_state["screener_data"] = None
if "screener_universe" not in st.session_state:
    st.session_state["screener_universe"] = None

# ── Main Tabs ────────────────────────────────────────────
tab_analysis, tab_screener = st.tabs(["📊 종목 분석", "🔎 스크리너"])

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

        **🔎 스크리너:** 두 번째 탭에서 S&P 500 / NASDAQ 100 종목을 필터링하여
        등급 기반으로 유망 종목을 찾을 수 있습니다.
        """)

# ──────────── TAB: SCREENER ──────────────────────────────
with tab_screener:
    display_screener()
