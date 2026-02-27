"""
Global configuration for Stock Intrinsic Value Analyzer.
"""
import os
from dotenv import load_dotenv

load_dotenv()  # .env 파일에서 환경변수 로드


def _get_secret(key: str, default: str = "") -> str:
    """Read a secret from Streamlit secrets (cloud) or environment variable."""
    # 1) Streamlit secrets (for Streamlit Community Cloud deployment)
    try:
        import streamlit as st
        val = st.secrets.get(key, None)
        if val:
            return str(val)
    except Exception:
        pass
    # 2) Environment variable (for local .env or system env)
    return os.environ.get(key, default)


# ── Supabase (DB & Auth) ─────────────────────────────────────
SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_SERVICE_KEY = _get_secret("SUPABASE_SERVICE_KEY")
ENCRYPTION_KEY = _get_secret("ENCRYPTION_KEY")  # Fernet key for API key encryption

# ── API Keys (from .env or Streamlit Secrets) ───────────────
OPENAI_API_KEY = _get_secret("OPENAI_API_KEY")
ANTHROPIC_API_KEY = _get_secret("ANTHROPIC_API_KEY")
OLLAMA_BASE_URL = _get_secret("OLLAMA_BASE_URL", "http://localhost:11434")

# ── FRED API ────────────────────────────────────────────────
# 무료 키 발급: https://fred.stlouisfed.org/docs/api/api_key.html
FRED_API_KEY = _get_secret("FRED_API_KEY")  # .env, Streamlit Secrets, 또는 직접 입력

# ── DCF 기본 가정 ───────────────────────────────────────────
DCF_DEFAULTS = {
    "high_growth_years": 5,
    "fade_years": 5,
    "terminal_growth_rate": 0.025,        # 2.5%
    "risk_free_rate": 0.043,               # 10Y Treasury (동적 업데이트)
    "equity_risk_premium": 0.055,          # Damodaran ERP
    "default_wacc": 0.10,                  # 10%
    "tax_rate": 0.21,                      # US corporate
    "monte_carlo_simulations": 10_000,
    "growth_rate_std": 0.03,               # MC 시뮬레이션 변동
    "wacc_std": 0.02,
    "margin_std": 0.05,
}

# ── 밸류에이션 모델 가중치 (기본값) ──────────────────────────
MODEL_WEIGHTS = {
    "dcf": 0.22,
    "reverse_dcf": 0.0,       # 시그널 전용, 가격 산출에 미포함
    "residual_income": 0.12,
    "epv": 0.12,
    "ddm": 0.05,              # 배당주만 활성
    "multiples": 0.15,
    "graham": 0.07,
    "peg": 0.07,
    "ev_sales": 0.05,
    "rule_of_40": 0.02,
    "sotp": 0.03,
    "analyst_target": 0.10,
}

# ── 섹터별 모델 가중치 매트릭스 ─────────────────────────────
# 섹터 특성에 따라 적합한 모델에 높은 가중치 부여
SECTOR_MODEL_WEIGHTS = {
    "Technology": {
        "dcf": 0.25, "residual_income": 0.05, "epv": 0.05, "ddm": 0.00,
        "multiples": 0.15, "graham": 0.05, "peg": 0.15, "ev_sales": 0.10,
        "rule_of_40": 0.10, "sotp": 0.00, "analyst_target": 0.10,
    },
    "Communication Services": {
        "dcf": 0.20, "residual_income": 0.08, "epv": 0.08, "ddm": 0.03,
        "multiples": 0.15, "graham": 0.05, "peg": 0.12, "ev_sales": 0.08,
        "rule_of_40": 0.08, "sotp": 0.03, "analyst_target": 0.10,
    },
    "Healthcare": {
        "dcf": 0.25, "residual_income": 0.10, "epv": 0.10, "ddm": 0.05,
        "multiples": 0.15, "graham": 0.05, "peg": 0.10, "ev_sales": 0.10,
        "rule_of_40": 0.00, "sotp": 0.05, "analyst_target": 0.05,
    },
    "Financial Services": {
        "dcf": 0.10, "residual_income": 0.25, "epv": 0.15, "ddm": 0.10,
        "multiples": 0.15, "graham": 0.10, "peg": 0.05, "ev_sales": 0.00,
        "rule_of_40": 0.00, "sotp": 0.05, "analyst_target": 0.05,
    },
    "Consumer Cyclical": {
        "dcf": 0.22, "residual_income": 0.12, "epv": 0.10, "ddm": 0.05,
        "multiples": 0.18, "graham": 0.08, "peg": 0.08, "ev_sales": 0.05,
        "rule_of_40": 0.00, "sotp": 0.02, "analyst_target": 0.10,
    },
    "Consumer Defensive": {
        "dcf": 0.20, "residual_income": 0.12, "epv": 0.12, "ddm": 0.10,
        "multiples": 0.15, "graham": 0.08, "peg": 0.05, "ev_sales": 0.03,
        "rule_of_40": 0.00, "sotp": 0.05, "analyst_target": 0.10,
    },
    "Industrials": {
        "dcf": 0.22, "residual_income": 0.12, "epv": 0.12, "ddm": 0.08,
        "multiples": 0.18, "graham": 0.08, "peg": 0.05, "ev_sales": 0.03,
        "rule_of_40": 0.00, "sotp": 0.02, "analyst_target": 0.10,
    },
    "Energy": {
        "dcf": 0.20, "residual_income": 0.10, "epv": 0.15, "ddm": 0.10,
        "multiples": 0.20, "graham": 0.10, "peg": 0.05, "ev_sales": 0.05,
        "rule_of_40": 0.00, "sotp": 0.00, "analyst_target": 0.05,
    },
    "Utilities": {
        "dcf": 0.15, "residual_income": 0.10, "epv": 0.20, "ddm": 0.15,
        "multiples": 0.15, "graham": 0.10, "peg": 0.05, "ev_sales": 0.00,
        "rule_of_40": 0.00, "sotp": 0.05, "analyst_target": 0.05,
    },
    "Real Estate": {
        "dcf": 0.15, "residual_income": 0.15, "epv": 0.15, "ddm": 0.15,
        "multiples": 0.15, "graham": 0.08, "peg": 0.02, "ev_sales": 0.00,
        "rule_of_40": 0.00, "sotp": 0.05, "analyst_target": 0.10,
    },
    "Basic Materials": {
        "dcf": 0.20, "residual_income": 0.10, "epv": 0.15, "ddm": 0.10,
        "multiples": 0.20, "graham": 0.10, "peg": 0.05, "ev_sales": 0.05,
        "rule_of_40": 0.00, "sotp": 0.00, "analyst_target": 0.05,
    },
}

# ── 섹터별 평균 배수 (Fallback) ─────────────────────────────
# data/sector_benchmarks.json 에서 동적 로드, 이것은 하드코딩 폴백
SECTOR_MULTIPLES_FALLBACK = {
    "Technology":        {"ev_ebitda": 20.0, "pe": 28.0, "ps": 6.0},
    "Healthcare":        {"ev_ebitda": 15.0, "pe": 22.0, "ps": 4.0},
    "Financial Services":{"ev_ebitda": 12.0, "pe": 13.0, "ps": 3.0},
    "Consumer Cyclical":  {"ev_ebitda": 14.0, "pe": 20.0, "ps": 2.0},
    "Consumer Defensive": {"ev_ebitda": 14.0, "pe": 22.0, "ps": 2.5},
    "Industrials":       {"ev_ebitda": 13.0, "pe": 20.0, "ps": 2.0},
    "Energy":            {"ev_ebitda": 6.0,  "pe": 10.0, "ps": 1.2},
    "Real Estate":       {"ev_ebitda": 18.0, "pe": 35.0, "ps": 7.0},
    "Communication Services": {"ev_ebitda": 12.0, "pe": 18.0, "ps": 3.0},
    "Utilities":         {"ev_ebitda": 12.0, "pe": 18.0, "ps": 2.5},
    "Basic Materials":   {"ev_ebitda": 8.0,  "pe": 14.0, "ps": 1.5},
}

# ── 섹터 ETF 매핑 (섹터 순환 분석용) ────────────────────────
SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial Services": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Industrials": "XLI",
    "Energy": "XLE",
    "Real Estate": "XLRE",
    "Communication Services": "XLC",
    "Utilities": "XLU",
    "Basic Materials": "XLB",
}

# ── 한국 섹터 ETF 매핑 (KODEX 기반) ─────────────────────────
KR_SECTOR_ETFS = {
    "Technology": "091160.KS",         # KODEX 반도체
    "Healthcare": "266420.KS",         # KODEX 헬스케어
    "Financial Services": "091170.KS", # KODEX 은행
    "Consumer Cyclical": "266360.KS",  # KODEX 경기소비재
    "Consumer Defensive": "266390.KS", # KODEX 필수소비재
    "Industrials": "102780.KS",        # KODEX 삼성그룹
    "Energy": "117460.KS",             # KODEX 에너지화학
    "Communication Services": "091180.KS",  # KODEX IT
    "Utilities": "117680.KS",          # KODEX 철강
    "Basic Materials": "117680.KS",    # KODEX 철강
}

# ── 한국 섹터별 평균 배수 (Fallback) ─────────────────────────
KR_SECTOR_MULTIPLES_FALLBACK = {
    "Technology":        {"ev_ebitda": 12.0, "pe": 18.0, "ps": 3.0},
    "Healthcare":        {"ev_ebitda": 20.0, "pe": 30.0, "ps": 5.0},
    "Financial Services":{"ev_ebitda": 8.0,  "pe": 7.0,  "ps": 1.5},
    "Consumer Cyclical":  {"ev_ebitda": 10.0, "pe": 15.0, "ps": 1.0},
    "Consumer Defensive": {"ev_ebitda": 10.0, "pe": 15.0, "ps": 1.0},
    "Industrials":       {"ev_ebitda": 8.0,  "pe": 12.0, "ps": 0.8},
    "Energy":            {"ev_ebitda": 5.0,  "pe": 8.0,  "ps": 0.5},
    "Real Estate":       {"ev_ebitda": 15.0, "pe": 20.0, "ps": 3.0},
    "Communication Services": {"ev_ebitda": 8.0, "pe": 12.0, "ps": 1.5},
    "Utilities":         {"ev_ebitda": 8.0,  "pe": 12.0, "ps": 1.0},
    "Basic Materials":   {"ev_ebitda": 6.0,  "pe": 10.0, "ps": 0.8},
}

# ── Fama-French 팩터 URL ─────────────────────────────────────
FF_FACTORS_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
FF_MOMENTUM_URL = "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/F-F_Momentum_Factor_daily_CSV.zip"

# ── FRED 시리즈 ID ────────────────────────────────────────────
FRED_SERIES = {
    "treasury_10y": "DGS10",
    "treasury_2y": "DGS2",
    "fed_funds": "FEDFUNDS",
    "ig_spread": "BAMLC0A0CM",
    "hy_spread": "BAMLH0A0HYM2",
    "vix": "VIXCLS",
    "consumer_sentiment": "UMCSENT",
}

# ── SEC EDGAR (Guru Investor Tracker) ─────────────────────────
SEC_EDGAR_BASE_URL = "https://efts.sec.gov/LATEST/search-index"
SEC_EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions"
SEC_EDGAR_ARCHIVES_URL = "https://www.sec.gov/cgi-bin/browse-edgar"
SEC_EDGAR_FULL_INDEX = "https://efts.sec.gov/LATEST"
SEC_EDGAR_HEADERS = {
    "User-Agent": os.environ.get(
        "SEC_USER_AGENT",
        "StockAnalyzer/1.0 (stock-analyzer@example.com)",
    ),
    "Accept-Encoding": "gzip, deflate",
}
SEC_CACHE_TTL = 86400  # 24h — 13F는 분기별이므로 하루 캐시

# 유명 투자자 CIK 매핑 (SEC EDGAR 기준)
GURU_INVESTORS = {
    "Berkshire Hathaway (Warren Buffett)":      "0001067983",
    "Bridgewater Associates (Ray Dalio)":        "0001350694",
    "Scion Asset Mgmt (Michael Burry)":          "0001649339",
    "Pershing Square (Bill Ackman)":             "0001336528",
    "Appaloosa Management (David Tepper)":       "0001656456",
    "Baupost Group (Seth Klarman)":              "0001061768",
    "Oaktree Capital (Howard Marks)":            "0000949509",
    "Icahn Enterprises (Carl Icahn)":            "0000921669",
    "Duquesne Family Office (Stanley Druckenmiller)": "0001536411",
    "Third Point (Dan Loeb)":                    "0001040273",
    "Soros Fund Management":                     "0001029160",
    "Tiger Global Management":                   "0001167483",
    "Greenlight Capital (David Einhorn)":        "0001079114",
    "Himalaya Capital (Li Lu)":                  "0001709323",
    "Renaissance Technologies":                  "0001037389",
}

# ── Screener ─────────────────────────────────────────────────
SCREENER_UNIVERSES = {
    "S&P 500": "sp500",
    "NASDAQ 100": "nasdaq100",
    "S&P 500 + NASDAQ 100": "sp500_nasdaq100",
    "KOSPI 200": "kospi200",
    "KOSDAQ 150": "kosdaq150",
    "선택안함 (전체)": "all",
}
SCREENER_CACHE_TTL = 86400  # 24h

# ── Country Options (Screener) ───────────────────────────────
COUNTRY_OPTIONS = {
    "🇺🇸 미국 (US)": "us",
    "🇰🇷 한국 (KR)": "kr",
    "🇯🇵 일본 (JP)": "jp",
    "🇨🇳 중국 (CN)": "cn",
}

# region code → Yahoo Finance country name (for post-filter matching)
COUNTRY_REGION_TO_NAME = {
    "us": ["United States"],
    "kr": ["South Korea"],
    "jp": ["Japan"],
    "cn": ["China"],
}

# 국가별 최소 시가총액 슬라이더 기본값 (USD 기준)
COUNTRY_MIN_CAP_OPTIONS = {
    "$0 (전체)": 0,
    "$100M": 100_000_000,
    "$500M": 500_000_000,
    "$1B": 1_000_000_000,
    "$5B": 5_000_000_000,
    "$10B": 10_000_000_000,
    "$50B": 50_000_000_000,
}

# ── UI ───────────────────────────────────────────────────────
CACHE_TTL = 3600  # 초단위
MAX_TICKERS = 10
MAX_PORTFOLIO_TICKERS = 30

# ── Portfolio & Backtest ─────────────────────────────────────
BENCHMARKS = {
    "S&P 500 (SPY)": "SPY",
    "NASDAQ 100 (QQQ)": "QQQ",
    "Dow Jones (DIA)": "DIA",
    "Russell 2000 (IWM)": "IWM",
    "KOSPI": "^KS11",
    "KOSDAQ": "^KQ11",
    "KODEX 200": "069500.KS",
}

BACKTEST_DEFAULTS = {
    "initial_capital": 100_000,
    "transaction_cost": 0.001,  # 0.1%
    "rebalance_freq": "M",     # Monthly
}

STRATEGY_NAMES = {
    "동일 비중 (Equal Weight)": "equal_weight",
    "모멘텀 (12-1M)": "momentum",
    "MA 크로스오버 (50/200)": "ma_crossover",
    "스크리너 등급 기반": "screener_grade",
}

WEIGHT_SCHEME_NAMES = {
    "동일 비중": "equal",
    "시가총액 비중": "market_cap",
    "역변동성 비중": "inverse_vol",
    "리스크 패리티": "risk_parity",
}

REBALANCE_FREQ_MAP = {
    "월간 (Monthly)": "M",
    "분기 (Quarterly)": "Q",
    "반기 (6-Month)": "6M",
    "연간 (Yearly)": "Y",
}

# ── AI Report ────────────────────────────────────────────────
AI_REPORT_DEFAULTS = {
    "default_provider": "OpenAI",
    "default_model": "gpt-4o-mini",
    "max_tokens": 2500,
    "temperature": 0.4,
}
