"""
Lightweight i18n — bilingual Korean/English support.
Usage: from src.i18n import t
       t("sidebar.title")  → "📊 Stock Analyzer" or "📊 주식 분석기"
"""

import streamlit as st
from typing import Dict

# ═══════════════════════════════════════════════════════════
# STRING TABLE
# ═══════════════════════════════════════════════════════════

_STRINGS: Dict[str, Dict[str, str]] = {
    # ── Sidebar ──────────────────────────────────────────
    "sidebar.title": {"ko": "📊 Stock Analyzer", "en": "📊 Stock Analyzer"},
    "sidebar.analysis": {"ko": "📊 종목 분석", "en": "📊 Stock Analysis"},
    "sidebar.ticker_label": {"ko": "Ticker(s) — 쉼표로 구분", "en": "Ticker(s) — comma separated"},
    "sidebar.ticker_help": {"ko": "미국 주식 티커를 입력하세요. 복수 입력 시 Compare 탭에서 비교 가능", "en": "Enter US stock tickers. Multiple tickers enable comparison tab."},
    "sidebar.dcf_title": {"ko": "#### DCF 가정 조정", "en": "#### DCF Assumptions"},
    "sidebar.show_macro": {"ko": "Show Macro Environment", "en": "Show Macro Environment"},
    "sidebar.analyze_btn": {"ko": "🔍 분석 시작", "en": "🔍 Start Analysis"},
    "sidebar.screener": {"ko": "🔎 스크리너 필터", "en": "🔎 Screener Filters"},
    "sidebar.universe": {"ko": "유니버스", "en": "Universe"},
    "sidebar.cap": {"ko": "시가총액", "en": "Market Cap"},
    "sidebar.sector": {"ko": "섹터", "en": "Sector"},
    "sidebar.sector_help": {"ko": "비워두면 전체 섹터", "en": "Leave empty for all sectors"},
    "sidebar.country": {"ko": "국가", "en": "Country"},
    "sidebar.country_help": {"ko": "필터링할 국가를 선택하세요 (비워두면 전체)", "en": "Select countries to filter (empty = all)"},
    "sidebar.country_required": {"ko": "⚠️ '선택안함 (전체)' 유니버스는 국가를 1개 이상 선택해야 합니다.", "en": "⚠️ 'None (All)' universe requires at least 1 country."},
    "sidebar.min_market_cap": {"ko": "최소 시가총액", "en": "Min Market Cap"},
    "sidebar.min_market_cap_help": {"ko": "스캔 범위를 줄이려면 시가총액 기준을 높이세요", "en": "Increase to narrow scan scope"},
    "sidebar.extra_filters": {"ko": "#### 추가 필터", "en": "#### Additional Filters"},
    "sidebar.pe_range": {"ko": "P/E 범위", "en": "P/E Range"},
    "sidebar.min_div": {"ko": "최소 배당수익률 (%)", "en": "Min Dividend Yield (%)"},
    "sidebar.min_roe": {"ko": "최소 ROE (%)", "en": "Min ROE (%)"},
    "sidebar.sort_by": {"ko": "정렬 기준", "en": "Sort By"},
    "sidebar.scan_btn": {"ko": "🔍 스크리닝 시작", "en": "🔍 Start Screening"},
    "sidebar.guru": {"ko": "🏦 13F 구루", "en": "🏦 13F Gurus"},
    "sidebar.guru_desc": {"ko": "SEC 13F 공시 기반 유명 투자자 포트폴리오 조회", "en": "SEC 13F institutional investor portfolio viewer"},
    "sidebar.portfolio": {"ko": "💼 포트폴리오", "en": "💼 Portfolio"},
    "sidebar.pf_tickers": {"ko": "종목 (쉼표 구분, 최대 30)", "en": "Tickers (comma separated, max 30)"},
    "sidebar.pf_tickers_help": {"ko": "포트폴리오에 포함할 주식 티커", "en": "Stock tickers for portfolio"},
    "sidebar.weight_scheme": {"ko": "가중치 방식", "en": "Weight Scheme"},
    "sidebar.start_date": {"ko": "시작일", "en": "Start Date"},
    "sidebar.end_date": {"ko": "종료일", "en": "End Date"},
    "sidebar.benchmark": {"ko": "벤치마크", "en": "Benchmark"},
    "sidebar.capital": {"ko": "초기 자본", "en": "Initial Capital"},
    "sidebar.simulate_btn": {"ko": "💼 시뮬레이션 실행", "en": "💼 Run Simulation"},
    "sidebar.backtest": {"ko": "📈 백테스트", "en": "📈 Backtest"},
    "sidebar.strategy": {"ko": "전략", "en": "Strategy"},
    "sidebar.bt_tickers": {"ko": "유니버스 종목 (쉼표 구분)", "en": "Universe tickers (comma separated)"},
    "sidebar.bt_tickers_help": {"ko": "백테스트에 사용할 종목 풀 (최대 30개)", "en": "Stock pool for backtest (max 30)"},
    "sidebar.rebal_freq": {"ko": "리밸런싱 주기", "en": "Rebalancing Frequency"},
    "sidebar.top_n": {"ko": "Top N (모멘텀/등급)", "en": "Top N (momentum/grade)"},
    "sidebar.tx_cost": {"ko": "거래비용 (%)", "en": "Transaction Cost (%)"},
    "sidebar.backtest_btn": {"ko": "📈 백테스트 실행", "en": "📈 Run Backtest"},
    "sidebar.ai_report": {"ko": "🤖 AI 리포트", "en": "🤖 AI Report"},
    "sidebar.ai_key_help": {"ko": ".env 파일에 키가 있으면 자동 로드됩니다", "en": "Auto-loaded from .env if available"},
    "sidebar.ai_language": {"ko": "리포트 언어", "en": "Report Language"},
    "sidebar.data_source": {"ko": "Data: Yahoo Finance | FRED | SEC EDGAR", "en": "Data: Yahoo Finance | FRED | SEC EDGAR"},

    # ── Main Tabs ────────────────────────────────────────
    "tab.analysis": {"ko": "📊 종목 분석", "en": "📊 Analysis"},
    "tab.screener": {"ko": "🔎 스크리너", "en": "🔎 Screener"},
    "tab.guru": {"ko": "🏦 13F 구루", "en": "🏦 13F Gurus"},
    "tab.portfolio": {"ko": "💼 포트폴리오", "en": "💼 Portfolio"},
    "tab.backtest": {"ko": "📈 백테스트", "en": "📈 Backtest"},

    # ── Sub-tabs ─────────────────────────────────────────
    "subtab.valuation": {"ko": "📈 Valuation", "en": "📈 Valuation"},
    "subtab.quality": {"ko": "🏅 Quality", "en": "🏅 Quality"},
    "subtab.financials": {"ko": "💰 Financials", "en": "💰 Financials"},
    "subtab.smart_money": {"ko": "🧠 Smart Money", "en": "🧠 Smart Money"},
    "subtab.risk_quant": {"ko": "⚡ Risk & Quant", "en": "⚡ Risk & Quant"},
    "subtab.macro": {"ko": "🌍 Macro", "en": "🌍 Macro"},
    "subtab.sector": {"ko": "🏭 Sector", "en": "🏭 Sector"},
    "subtab.ai_report": {"ko": "🤖 AI 리포트", "en": "🤖 AI Report"},

    # ── Spinner / Status ─────────────────────────────────
    "spinner.fetching": {"ko": "📡 {ticker} 데이터 수집 중...", "en": "📡 Fetching {ticker} data..."},
    "spinner.analyzing": {"ko": "⚡ {ticker} 분석 중... (밸류에이션 / 품질 / 퀀트 / 매크로 동시 진행)", "en": "⚡ Analyzing {ticker}... (valuation / quality / quant / macro in parallel)"},
    "spinner.grades": {"ko": "📊 종합 등급 산출 중...", "en": "📊 Computing overall grades..."},
    "spinner.scanning": {"ko": "🔄 **{universe}** 스캔을 시작합니다... (병렬 처리: ~30초-2분)", "en": "🔄 Starting **{universe}** scan... (parallel: ~30s-2min)"},
    "spinner.scanning_country": {"ko": "🔄 **{countries}** 전체 주식 스캔 중... (yfinance Screener API)", "en": "🔄 Scanning all stocks for **{countries}**... (yfinance Screener API)"},
    "spinner.ai_report": {"ko": "🤖 AI 리포트 생성 중... (10~30초 소요)", "en": "🤖 Generating AI report... (10-30 sec)"},

    # ── Error Messages ───────────────────────────────────
    "err.no_data": {"ko": "❌ {ticker}: 데이터를 가져올 수 없습니다. 티커를 확인해주세요.", "en": "❌ {ticker}: Failed to fetch data. Check the ticker symbol."},
    "err.no_tickers": {"ko": "분석할 수 있는 종목이 없습니다. 티커를 확인해주세요.", "en": "No analyzable stocks found. Check your tickers."},
    "err.partial_fail": {"ko": "⚠️ 일부 분석이 실패했습니다: {sections}\n\n해당 섹션은 빈 데이터로 표시됩니다. 네트워크를 확인 후 다시 분석해보세요.", "en": "⚠️ Some analyses failed: {sections}\n\nAffected sections will show empty data. Check your network and retry."},
    "err.section_fail": {"ko": "⚠️ 이 섹션의 일부 데이터를 불러오지 못했습니다: {names}\n\n네트워크를 확인하고 **분석 시작** 버튼으로 다시 분석해보세요.", "en": "⚠️ Some data for this section could not be loaded: {names}\n\nCheck your network and retry with the **Start Analysis** button."},
    "err.no_section_data": {"ko": "{section} 데이터를 사용할 수 없습니다.", "en": "{section} data is not available."},
    "err.enter_ticker": {"ko": "티커를 입력해주세요.", "en": "Please enter a ticker."},
    "err.api_key_missing": {"ko": "⚠️ {provider} API 키가 설정되지 않았습니다.\n\n왼쪽 사이드바 **🤖 AI 리포트** 에서 API 키를 입력하거나 `.env` 파일에 설정하세요.", "en": "⚠️ {provider} API key not set.\n\nEnter it in the sidebar **🤖 AI Report** or set it in the `.env` file."},

    # ── Screener ─────────────────────────────────────────
    "screener.scan_complete": {"ko": "✅ 스캔 완료! {ok}/{total}개 종목 성공", "en": "✅ Scan complete! {ok}/{total} stocks successful"},
    "screener.scan_failed": {"ko": "⚠️ {count}개 종목 스캔 실패 (클릭하여 보기)", "en": "⚠️ {count} stocks failed (click to view)"},
    "screener.no_data": {"ko": "📋 **{universe}** 유니버스: {count}개 종목\n\n아직 스캔 데이터가 없습니다. 사이드바의 **🔎 스크리너 필터**에서 **'스크리닝 시작'** 버튼을 클릭하세요.\n\n⏱️ 최초 스캔: 약 30초~2분 소요 (병렬 처리, 이후 24시간 캐시)", "en": "📋 **{universe}** universe: {count} stocks\n\nNo scan data yet. Click **'Start Screening'** in the sidebar.\n\n⏱️ First scan: ~30s-2min (parallel, then 24h cache)"},
    "screener.filter_result": {"ko": "필터 결과: {filtered}개 / {total}개 종목", "en": "Filter result: {filtered} / {total} stocks"},
    "screener.no_match": {"ko": "조건에 맞는 종목이 없습니다. 필터를 조정해보세요.", "en": "No stocks match the filters. Try adjusting."},
    "screener.scanned": {"ko": "스캔 종목 수", "en": "Stocks Scanned"},
    "screener.scan_time": {"ko": "스캔 시간", "en": "Scan Time"},
    "screener.failed": {"ko": "실패", "en": "Failed"},

    # ── Sort options ─────────────────────────────────────
    "sort.grade": {"ko": "Overall Grade ↓", "en": "Overall Grade ↓"},
    "sort.cap": {"ko": "시가총액 ↓", "en": "Market Cap ↓"},
    "sort.pe": {"ko": "P/E ↑", "en": "P/E ↑"},
    "sort.roe": {"ko": "ROE ↓", "en": "ROE ↓"},
    "sort.div": {"ko": "배당수익률 ↓", "en": "Dividend Yield ↓"},

    # ── Cap labels ───────────────────────────────────────
    "cap.mega": {"ko": "Mega (>200B)", "en": "Mega (>200B)"},
    "cap.large": {"ko": "Large (10-200B)", "en": "Large (10-200B)"},
    "cap.mid": {"ko": "Mid (2-10B)", "en": "Mid (2-10B)"},
    "cap.small": {"ko": "Small (<2B)", "en": "Small (<2B)"},

    # ── Valuation tab ────────────────────────────────────
    "val.comparison": {"ko": "밸류에이션 모델 비교", "en": "Valuation Model Comparison"},

    # ── Macro tab ────────────────────────────────────────
    "macro.disabled": {"ko": "매크로 분석이 비활성화되어 있거나 데이터를 불러오지 못했습니다.", "en": "Macro analysis is disabled or data could not be loaded."},

    # ── Backtest / Portfolio ─────────────────────────────
    "bt.total_return": {"ko": "총 수익률", "en": "Total Return"},
    "bt.annual_return": {"ko": "연간 수익률", "en": "Annual Return"},
    "bt.benchmark_return": {"ko": "벤치마크 수익", "en": "Benchmark Return"},
    "bt.result_tab": {"ko": "📈 결과", "en": "📈 Results"},
    "bt.trades_tab": {"ko": "📋 매매 내역", "en": "📋 Trade Log"},
    "bt.detail_tab": {"ko": "📊 전략 상세", "en": "📊 Strategy Details"},
    "bt.strategy_label": {"ko": "전략", "en": "Strategy"},
    "bt.returns": {"ko": "**수익률**", "en": "**Returns**"},
    "bt.risk": {"ko": "**리스크**", "en": "**Risk**"},
    "bt.vs_market": {"ko": "**시장 대비**", "en": "**vs. Market**"},
    "bt.annual_vol": {"ko": "연간 변동성", "en": "Annual Volatility"},
    "bt.win_rate": {"ko": "승률", "en": "Win Rate"},
    "bt.no_trades": {"ko": "매매 기록이 없습니다.", "en": "No trade records."},
    "bt.weight_history": {"ko": "📊 리밸런싱별 비중 변화", "en": "📊 Weight Changes per Rebalance"},
    "bt.curve_title": {"ko": "백테스트 수익률 곡선", "en": "Backtest Equity Curve"},
    "bt.monthly_returns": {"ko": "📅 월별 수익률 (%)", "en": "📅 Monthly Returns (%)"},
    "bt.all_trades": {"ko": "📋 전체 매매 기록", "en": "📋 All Trades"},
    "bt.detail_metrics": {"ko": "📊 상세 성과 지표", "en": "📊 Detailed Metrics"},
    "bt.no_data": {"ko": "왼쪽 사이드바의 **📈 백테스트**에서 전략/종목을 설정하고\n**백테스트 실행** 버튼을 클릭하세요.", "en": "Set strategy/tickers in the sidebar **📈 Backtest** and click **Run Backtest**."},

    "pf.no_data": {"ko": "왼쪽 사이드바의 **💼 포트폴리오**에서 종목/가중치를 설정하고\n**시뮬레이션 실행** 버튼을 클릭하세요.", "en": "Set tickers/weights in the sidebar **💼 Portfolio** and click **Run Simulation**."},

    # ── Home ─────────────────────────────────────────────
    "home.title": {"ko": "📊 Stock Intrinsic Value Analyzer", "en": "📊 Stock Intrinsic Value Analyzer"},

    # ── AI Report ────────────────────────────────────────
    "ai.title": {"ko": "🤖 AI 투자 리포트 — {ticker}", "en": "🤖 AI Investment Report — {ticker}"},
    "ai.caption": {"ko": "LLM이 분석 결과를 종합하여 자연어 투자 리포트를 생성합니다.", "en": "LLM generates a natural-language investment report from analysis results."},
    "ai.generate": {"ko": "🤖 리포트 생성", "en": "🤖 Generate Report"},
    "ai.regenerate": {"ko": "🔄 리포트 재생성", "en": "🔄 Regenerate Report"},
    "ai.delete": {"ko": "🗑️ 삭제", "en": "🗑️ Delete"},
    "ai.download": {"ko": "📥 마크다운 다운로드", "en": "📥 Download Markdown"},
    "ai.copy": {"ko": "📋 원본 텍스트 보기 (복사용)", "en": "📋 View raw text (copy)"},
    "ai.empty": {"ko": "리포트가 비어있습니다. 다시 시도해주세요.", "en": "Report is empty. Please try again."},
    "ai.guide": {"ko": "**🤖 리포트 생성** 버튼을 클릭하면 AI가 분석 결과를 종합하여\n자연어 투자 리포트를 작성합니다.\n\n💡 사이드바의 **🤖 AI 리포트** 에서 LLM Provider, 모델, API 키를 설정하세요.", "en": "Click **🤖 Generate Report** to have AI create a comprehensive\ninvestment report from the analysis.\n\n💡 Set LLM Provider, model, and API key in the sidebar **🤖 AI Report**."},

    # ── Screener cache status ────────────────────────────
    "scan.scanning": {"ko": "스캔 중", "en": "Scanning"},
    "scan.success": {"ko": "성공", "en": "Success"},
    "scan.failure": {"ko": "실패", "en": "Failed"},
    "scan.remaining": {"ko": "남은 시간", "en": "Remaining"},

    # ── Auth / User ──────────────────────────────────────
    "auth.login_required": {"ko": "로그인이 필요합니다.", "en": "Login required."},
    "auth.welcome": {"ko": "환영합니다, {name}!", "en": "Welcome, {name}!"},
    "auth.logout": {"ko": "🚪 로그아웃", "en": "🚪 Logout"},
    "auth.upgrade": {"ko": "🔒 이 기능은 {role} 이상 등급에서 사용 가능합니다.", "en": "🔒 This feature requires {role} or higher."},
    "auth.quota_used": {"ko": "오늘 사용: {used}/{limit}건", "en": "Today: {used}/{limit} used"},
    "auth.save_analysis": {"ko": "💾 분석 저장", "en": "💾 Save Analysis"},
    "auth.saved": {"ko": "✅ 저장되었습니다!", "en": "✅ Saved!"},
    "auth.my_analyses": {"ko": "📂 내 분석 기록", "en": "📂 My Analyses"},
    "auth.my_reports": {"ko": "📂 내 리포트", "en": "📂 My Reports"},
    "auth.admin_panel": {"ko": "👑 관리자 패널", "en": "👑 Admin Panel"},

    # ── Tab (with admin) ─────────────────────────────────
    "tab.admin": {"ko": "👑 관리자", "en": "👑 Admin"},
}


def t(key: str, **kwargs) -> str:
    """
    Translate a string key using the current language setting.
    Supports .format()-style kwargs: t("err.no_data", ticker="AAPL")
    Falls back to Korean if key not found.
    """
    lang = st.session_state.get("language", "ko")
    entry = _STRINGS.get(key)
    if entry is None:
        return key  # fallback: return key itself
    text = entry.get(lang, entry.get("ko", key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except (KeyError, IndexError):
            pass
    return text


def get_language() -> str:
    """Get current language code."""
    return st.session_state.get("language", "ko")
